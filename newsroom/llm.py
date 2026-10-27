"""One narrow door to the language models.

`complete_json(task, schema, system, user)` returns a validated pydantic
model or raises `LLMError`. Callers never see provider details; routing is
by task name via config.toml `[llm.routes]`, and each provider is described
under `[llm.providers.<name>]`.

Provider kinds:
- "openai": any OpenAI-compatible chat endpoint. LM Studio and llama.cpp
  locally, Moonshot (Kimi) in the cloud. The `openai` package is used only
  because that is the wire format these servers speak.
- "anthropic": the official Anthropic SDK with structured outputs.

NEWSROOM_LLM=off makes every task raise LLMUnavailable so writers fall back
to templates; NEWSROOM_LLM=<provider name> forces one provider for all tasks.

Robustness: Qwen-style <think> blocks are stripped before parsing; strict
json_schema mode falls back to json_object mode if a server rejects it; a
validation failure gets exactly one retry carrying the error text; the
second failure raises so the caller can use its canned fallback.

Prompt caching: a prompt builder puts CACHE_BREAK where the part that stays
the same from call to call ends (the town, presenters and public figures at
the top of the briefing). On an anthropic provider with `cache_ttl` set, that
part, together with the system prompt and schema ahead of it, is cached and
re-read at a tenth of the price; everywhere else the marker is just removed.

Accounting: every call's token counts go on its log line and into running
totals per provider (`usage_summary()`). "in" is the whole prompt, cached or
not, so providers compare; cache reads and writes are counted on the side. With `[llm] log_calls = true`,
--log-llm or NEWSROOM_LLM_LOG=1, the full prompt and reply of each call is
appended to data/llm_calls/<date>.jsonl.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import CONFIG, ProviderCfg

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Where the stable head of a user prompt ends. A control character, so it can't turn up in a prompt
# by accident; removed before anything is sent or logged except as the split it stands for.
CACHE_BREAK = "\x1e"

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    """The model produced nothing usable after retries."""


class LLMUnavailable(LLMError):
    """No provider reachable (server down, model unloaded, bad key, or NEWSROOM_LLM=off)."""


def provider_for(task: str) -> str:
    override = os.environ.get("NEWSROOM_LLM")
    if override:
        return override
    return CONFIG.llm.provider_name_for(task)


# ------------------------------------------------------------------ helpers


def clean_json_text(text: str) -> str:
    text = _THINK_RE.sub("", text)
    text = _FENCE_RE.sub("", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    return text.strip()


def _parse(schema: type[T], text: str) -> T:
    return schema.model_validate_json(clean_json_text(text))


# ------------------------------------------------------------- accounting

_USAGE: dict[str, dict[str, int]] = {}    # provider -> calls, failed, tokens in / out
_USAGE_LOCK = threading.Lock()


def _count(provider: str, usage: dict | None, *, failed: bool = False) -> None:
    with _USAGE_LOCK:
        u = _USAGE.setdefault(provider, {"calls": 0, "failed": 0, "in": 0, "out": 0, "cache_read": 0, "cache_write": 0})
        u["calls"] += 1
        u["failed"] += failed
        if usage:
            for k in ("in", "out", "cache_read", "cache_write"):
                u[k] += usage.get(k, 0)


def _cache_text(u: dict) -> str:
    return f" ({u['cache_read']} cache read, {u['cache_write']} written)" if u.get("cache_read") or u.get("cache_write") else ""


def usage_summary() -> str:
    """One line of per-provider totals since start, for STATS and the exit line."""
    with _USAGE_LOCK:
        return " | ".join(f"{p}: {u['calls']} calls ({u['failed']} failed), {u['in']} in{_cache_text(u)} / {u['out']} out"
                          for p, u in sorted(_USAGE.items())) or "no llm calls"


def _usage_text(usage: dict | None) -> str:
    if not usage:
        return "no usage reported"
    extra = f", {usage['reasoning']} reasoning" if usage.get("reasoning") else ""
    return f"{usage['in']} in{_cache_text(usage)} / {usage['out']} out{extra}"


_CALL_LOG_LOCK = threading.Lock()


def _log_calls_on() -> bool:
    return CONFIG.llm.log_calls or os.environ.get("NEWSROOM_LLM_LOG", "") not in ("", "0")


def _log_call(record: dict) -> None:
    """Append one call to today's JSONL file. Never lets a disk problem break a broadcast."""
    if not _log_calls_on():
        return
    try:
        path = CONFIG.paths.llm_calls / f"{datetime.now():%Y-%m-%d}.jsonl"
        line = json.dumps(record, ensure_ascii=False)
        with _CALL_LOG_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:  # noqa: BLE001
        log.warning("could not write llm call log: %s", e)


# ------------------------------------------------------- openai-compatible

_CLIENTS: dict[str, object] = {}
_CLIENT_LOCK = threading.Lock()
_FIRST_CALL_DONE: set[str] = set()
_USE_JSON_OBJECT: set[str] = set()      # providers that rejected strict json_schema


def _api_key(prov: ProviderCfg) -> str:
    if not prov.api_key_env:
        return "not-needed"
    key = os.environ.get(prov.api_key_env, "")
    if not key:
        raise LLMUnavailable(f"{prov.name}: environment variable {prov.api_key_env} is not set")
    return key


def _openai_client(prov: ProviderCfg):
    with _CLIENT_LOCK:
        if prov.name not in _CLIENTS:
            from openai import OpenAI

            _CLIENTS[prov.name] = OpenAI(base_url=prov.base_url, api_key=_api_key(prov),
                                         max_retries=prov.max_retries)
        return _CLIENTS[prov.name]


def list_models(provider: str | None = None) -> list[str]:
    """Model IDs the provider reports. Empty list if unreachable."""
    prov = CONFIG.llm.provider(provider or CONFIG.llm.default_provider)
    if prov.kind != "openai":
        return [prov.model]
    try:
        return sorted(m.id for m in _openai_client(prov).models.list().data)
    except Exception as e:  # noqa: BLE001
        log.warning("%s not reachable at %s: %s", prov.name, prov.base_url, str(e)[:160])
        return []


def _openai_raw(prov: ProviderCfg, system: str, messages: list[dict],
                schema: type[BaseModel]) -> tuple[str, dict | None]:
    """The reply text and its token usage ({in, out, reasoning}) if the server reported it."""
    import openai

    client = _openai_client(prov)
    timeout = prov.timeout_s or CONFIG.llm.timeout_s
    if prov.name not in _FIRST_CALL_DONE:     # a local server may still be loading the model
        timeout = max(timeout, CONFIG.llm.first_call_timeout_s)
    temperature = CONFIG.llm.temperature if prov.temperature is None else prov.temperature
    max_tokens = prov.max_tokens or CONFIG.llm.max_tokens
    common = dict(model=prov.model, max_tokens=max_tokens, temperature=temperature,
                  timeout=timeout, extra_body=prov.extra_body or None)

    def strict_call():
        return client.chat.completions.create(
            messages=[{"role": "system", "content": system}, *messages],
            response_format={"type": "json_schema", "json_schema": {
                "name": schema.__name__, "strict": True, "schema": schema.model_json_schema()}},
            **common,
        )

    def object_call():
        sys_with_schema = system + "\n\nReturn a JSON object matching this JSON schema exactly:\n" \
            + json.dumps(schema.model_json_schema())
        return client.chat.completions.create(
            messages=[{"role": "system", "content": sys_with_schema}, *messages],
            response_format={"type": "json_object"},
            **common,
        )

    try:
        if prov.name in _USE_JSON_OBJECT:
            resp = object_call()
        else:
            try:
                resp = strict_call()
            except openai.BadRequestError as e:
                # Could be the schema mode, or something unrelated (temperature,
                # max_tokens). Try plain JSON mode once; remember it only if it works.
                log.info("%s rejected the strict request (%s); trying json_object mode",
                         prov.name, str(e)[:160])
                resp = object_call()
                _USE_JSON_OBJECT.add(prov.name)
                log.warning("%s: strict json_schema unsupported; using json_object mode from now on", prov.name)
    except openai.APIConnectionError as e:
        raise LLMUnavailable(f"{prov.name} unreachable: {e}") from e
    except openai.AuthenticationError as e:
        raise LLMUnavailable(f"{prov.name}: authentication failed ({prov.api_key_env})") from e
    except openai.NotFoundError as e:
        raise LLMUnavailable(f"{prov.name}: model {prov.model!r} not found/loaded: {str(e)[:120]}") from e
    except openai.APIStatusError as e:
        raise LLMError(f"{prov.name} error {e.status_code}: {str(e)[:200]}") from e

    _FIRST_CALL_DONE.add(prov.name)
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        log.warning("%s hit max_tokens; output may be truncated", prov.name)
    usage = None
    if resp.usage:
        details = getattr(resp.usage, "completion_tokens_details", None)
        usage = {"in": resp.usage.prompt_tokens or 0, "out": resp.usage.completion_tokens or 0,
                 "reasoning": getattr(details, "reasoning_tokens", None) or 0}
    return choice.message.content or "", usage


# --------------------------------------------------------------- anthropic

_ANTHROPIC = None


def _anthropic_raw(prov: ProviderCfg, system: str, messages: list[dict],
                   schema: type[BaseModel]) -> tuple[str, dict | None]:
    """The reply text and its token usage, like _openai_raw; complete_json validates and retries.

    The API enforces the schema's shape but not limits such as a list's maximum length (those
    become hints in the descriptions), so a reply can still fail validation here.
    """
    global _ANTHROPIC
    import anthropic

    if _ANTHROPIC is None:
        _ANTHROPIC = anthropic.Anthropic()
    # extra_body's "effort" (low/medium/high/xhigh/max) goes into output_config next to the schema;
    # the rest (e.g. thinking = { type = "disabled" } on Haiku, { type = "between_tools" } on
    # Sonnet 5.5) is sent as is.
    extra = dict(prov.extra_body)
    output_config: dict = {"format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}}
    if effort := extra.pop("effort", None):
        output_config["effort"] = effort
    try:
        resp = _ANTHROPIC.with_options(
            timeout=prov.timeout_s or CONFIG.llm.timeout_s, max_retries=prov.max_retries,
        ).messages.create(
            model=prov.model,
            max_tokens=prov.max_tokens or max(CONFIG.llm.max_tokens * 4, 4000),
            system=system,
            messages=messages,
            output_config=output_config,
            extra_body=extra or None,
        )
    except anthropic.APIConnectionError as e:          # includes timeouts
        raise LLMUnavailable(f"Anthropic unreachable: {e}") from e
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("Anthropic: authentication failed (ANTHROPIC_API_KEY)") from e
    except TypeError as e:                              # no key at all: the SDK can't build its headers
        raise LLMUnavailable(f"Anthropic: no ANTHROPIC_API_KEY ({e})") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic error {e.status_code}: {e.message}") from e
    if resp.stop_reason == "refusal":
        raise LLMError("Anthropic declined the request")
    if resp.stop_reason == "max_tokens":
        log.warning("%s hit max_tokens; output may be truncated", prov.name)
    text = "".join(b.text for b in resp.content if b.type == "text")
    usage = None
    if u := resp.usage:
        read, write = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
        usage = {"in": u.input_tokens + read + write, "out": u.output_tokens, "cache_read": read, "cache_write": write}
    return text, usage


def _user_content(prov: ProviderCfg, user: str) -> str | list[dict]:
    """The first user turn. On a caching anthropic provider the text before CACHE_BREAK is a block
    of its own with the cache marker, so the system prompt, schema and that block are one cached
    prefix; otherwise the marker is dropped and the prompt goes as plain text."""
    stable, sep, rest = user.partition(CACHE_BREAK)
    if not sep or prov.kind != "anthropic" or not prov.cache_ttl:
        return user.replace(CACHE_BREAK, "")
    mark = {"type": "ephemeral", "ttl": prov.cache_ttl}
    rest = rest.replace(CACHE_BREAK, "")
    return [{"type": "text", "text": stable, "cache_control": mark}] + (
        [{"type": "text", "text": rest}] if rest.strip() else [])


# -------------------------------------------------------------------- public


def complete_json(task: str, schema: type[T], system: str, user: str, *, retries: int = 1) -> T:
    """Ask the model for an instance of `schema`. Raises LLMError on failure."""
    name = provider_for(task)
    if name == "off":
        raise LLMUnavailable("NEWSROOM_LLM=off")
    prov = CONFIG.llm.provider(name)
    if prov.kind not in ("openai", "anthropic"):
        raise LLMError(f"unknown provider kind {prov.kind!r} for {name!r}")
    messages: list[dict] = [{"role": "user", "content": _user_content(prov, user)}]

    def record(attempt: int, t0: float, *, text: str = "", usage: dict | None = None, error: str = "") -> None:
        _count(name, usage, failed=bool(error))
        _log_call({"ts": datetime.now().isoformat(timespec="seconds"), "task": task, "provider": name,
                   "model": prov.model, "attempt": attempt + 1, "elapsed_s": round(time.perf_counter() - t0, 1),
                   "usage": usage, "error": error or None, "system": system, "messages": messages,
                   "reply": text})

    raw = _anthropic_raw if prov.kind == "anthropic" else _openai_raw
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            text, usage = raw(prov, system, messages, schema)
        except LLMError as e:
            record(attempt, t0, error=str(e))
            raise
        try:
            out = _parse(schema, text)
            record(attempt, t0, text=text, usage=usage)
            log.info("llm %s via %s/%s ok in %.1fs (attempt %d, %s)", task, name, prov.model,
                     time.perf_counter() - t0, attempt + 1, _usage_text(usage))
            return out
        except (ValidationError, ValueError) as e:
            last_err = e
            record(attempt, t0, text=text, usage=usage, error=f"validation: {str(e)[:300]}")
            log.warning("llm %s attempt %d failed validation (%s): %s", task, attempt + 1,
                        _usage_text(usage), str(e)[:300])
            messages += [
                # Some servers reject an empty assistant turn; never send one.
                {"role": "assistant", "content": text or "(empty response)"},
                {"role": "user", "content": "Your previous output failed validation:\n"
                 f"{str(e)[:800]}\nReturn ONLY corrected JSON, nothing else."},
            ]
    raise LLMError(f"{task}: no valid output after {retries + 1} attempts: {last_err}")


# ----------------------------------------------------------------------- CLI


def _cli(argv: list[str]) -> int:
    import argparse
    import sys

    from . import world as world_mod
    from .models import SCRIPT_SCHEMAS, SegmentType, script_schema
    from .writers import build_prompt

    p = argparse.ArgumentParser(prog="python -m newsroom.llm")
    p.add_argument("type", choices=[t.value for t in SCRIPT_SCHEMAS])
    p.add_argument("--dry-run", action="store_true", help="print prompt and schema, call nothing")
    p.add_argument("--target", type=float, default=60.0, help="target seconds")
    p.add_argument("--show", default="news", help="schedule show id (news, breakfast, magazine, late)")
    p.add_argument("--part", default="", help="running-order part: open, cont or close")
    p.add_argument("--brief", default="", help="the running order's angle for the item")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-5s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from . import schedule

    seg_type = SegmentType(a.type)
    show = schedule.get(a.show)
    schema = script_schema(seg_type, show.cast_for(seg_type))
    w = world_mod.load()
    from . import tipline

    tips = tipline.offer() if seg_type is SegmentType.bulletin else []
    work = {"tip": "Smoke over the old cannery", "interrupting": "Coastwide"} if seg_type is SegmentType.breaking else None
    system, user = build_prompt(seg_type, w, target_s=a.target, show=show, part=a.part, brief=a.brief,
                                work=work, tips=tips)
    name = provider_for(a.type)
    if a.dry_run:
        print("=== SYSTEM ===\n" + system + "\n\n=== USER ===\n" + user.replace(CACHE_BREAK, "[cache break]\n"))
        print("\n=== SCHEMA ===\n" + json.dumps(schema.model_json_schema(), indent=1))
        print(f"\nprovider for {a.type!r}: {name}")
        return 0
    print(f"provider: {name}  models: {list_models(name) or '(none / unreachable)'}")
    out = complete_json(a.type, schema, system, user)
    print(out.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
