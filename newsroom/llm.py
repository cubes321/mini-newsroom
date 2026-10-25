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
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import CONFIG, ProviderCfg

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

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

            _CLIENTS[prov.name] = OpenAI(base_url=prov.base_url, api_key=_api_key(prov), max_retries=1)
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


def _openai_raw(prov: ProviderCfg, system: str, messages: list[dict], schema: type[BaseModel]) -> str:
    import openai

    client = _openai_client(prov)
    timeout = CONFIG.llm.timeout_s if prov.name in _FIRST_CALL_DONE else CONFIG.llm.first_call_timeout_s
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
    if resp.usage:
        log.debug("%s usage: %d in / %d out", prov.name, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return choice.message.content or ""


# --------------------------------------------------------------- anthropic

_ANTHROPIC = None


def _anthropic_parse(prov: ProviderCfg, system: str, messages: list[dict], schema: type[T]) -> T:
    global _ANTHROPIC
    import anthropic

    if _ANTHROPIC is None:
        _ANTHROPIC = anthropic.Anthropic()
    try:
        resp = _ANTHROPIC.messages.parse(
            model=prov.model,
            max_tokens=max(CONFIG.llm.max_tokens * 4, 4000),
            system=system,
            messages=messages,
            output_format=schema,
        )
    except anthropic.APIConnectionError as e:
        raise LLMUnavailable(f"Anthropic unreachable: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic error {e.status_code}: {e.message}") from e
    if resp.stop_reason == "refusal":
        raise LLMError("Anthropic declined the request")
    if resp.parsed_output is None:
        raise LLMError("Anthropic returned no parsed output")
    return resp.parsed_output


# -------------------------------------------------------------------- public


def complete_json(task: str, schema: type[T], system: str, user: str, *, retries: int = 1) -> T:
    """Ask the model for an instance of `schema`. Raises LLMError on failure."""
    name = provider_for(task)
    if name == "off":
        raise LLMUnavailable("NEWSROOM_LLM=off")
    prov = CONFIG.llm.provider(name)
    messages: list[dict] = [{"role": "user", "content": user}]

    if prov.kind == "anthropic":
        return _anthropic_parse(prov, system, messages, schema)
    if prov.kind != "openai":
        raise LLMError(f"unknown provider kind {prov.kind!r} for {name!r}")

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        text = _openai_raw(prov, system, messages, schema)
        try:
            out = _parse(schema, text)
            log.info("llm %s via %s/%s ok in %.1fs (attempt %d)", task, name, prov.model,
                     time.perf_counter() - t0, attempt + 1)
            return out
        except (ValidationError, ValueError) as e:
            last_err = e
            log.warning("llm %s attempt %d failed validation: %s", task, attempt + 1, str(e)[:300])
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
    p.add_argument("--show", default="news", help="schedule show id (news, breakfast)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-5s %(name)s: %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from . import schedule

    seg_type = SegmentType(a.type)
    show = schedule.get(a.show)
    schema = script_schema(seg_type, show.cast_for(seg_type))
    w = world_mod.load()
    system, user = build_prompt(seg_type, w, target_s=a.target, show=show)
    name = provider_for(a.type)
    if a.dry_run:
        print("=== SYSTEM ===\n" + system + "\n\n=== USER ===\n" + user)
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
