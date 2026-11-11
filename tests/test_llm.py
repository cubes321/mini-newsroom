"""Prompt caching on the anthropic route: the briefing's stable head is one cached block, other
providers never see the marker, and cache reads and writes are counted, DeepSeek's own cache hits included.

The Anthropic client is stubbed: no network.
"""
from types import SimpleNamespace

from pydantic import BaseModel

from newsroom import llm, world as world_mod
from newsroom.config import ProviderCfg

HAIKU = ProviderCfg(name="h", kind="anthropic", model="claude-haiku-5-5", cache_ttl="1h")
USER = f"TOWN BRIEFING\nthe town\n{llm.CACHE_BREAK}Last weather: rain\n\nWrite it."


def test_a_caching_provider_gets_the_head_as_a_marked_block():
    head, tail = llm._user_content(HAIKU, USER)
    assert head == {"type": "text", "text": "TOWN BRIEFING\nthe town\n",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"}}
    assert tail == {"type": "text", "text": "Last weather: rain\n\nWrite it."}


def test_other_providers_get_plain_text_without_the_marker():
    plain = "TOWN BRIEFING\nthe town\nLast weather: rain\n\nWrite it."
    assert llm._user_content(ProviderCfg(name="k", kind="openai"), USER) == plain
    assert llm._user_content(ProviderCfg(name="c", kind="anthropic"), USER) == plain


def test_the_briefings_have_one_break_after_the_public_figures():
    w = world_mod.seed()
    for text in (w.summary_for_prompt(), w.summary_for_editor()):
        head, _, tail = text.partition(llm.CACHE_BREAK)
        assert llm.CACHE_BREAK not in tail
        assert "Public figures" in head and "Residents" not in head and tail.startswith("Residents")


def test_the_head_survives_a_change_in_who_appears_most():
    w = world_mod.seed()
    head = w.summary_for_prompt().partition(llm.CACHE_BREAK)[0]
    officials = [p for p in w.people if p.kind in ("official", "worthy")]
    officials[-1].appearances += 50
    assert w.summary_for_prompt().partition(llm.CACHE_BREAK)[0] == head


class _Out(BaseModel):
    text: str


class _FakeClient:
    def __init__(self):
        self.sent = None

    def with_options(self, **kw):
        return self

    @property
    def messages(self):
        return self

    def create(self, **kw):
        self.sent = kw
        usage = SimpleNamespace(input_tokens=900, output_tokens=40,
                                cache_read_input_tokens=2100, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text='{"text": "hello"}')])


def test_a_cached_call_counts_the_whole_prompt_and_the_cache_read(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_ANTHROPIC", fake)
    monkeypatch.setenv("NEWSROOM_LLM", "claude_haiku")
    monkeypatch.setattr(llm, "_USAGE", {})
    assert llm.complete_json("weather", _Out, "system", USER).text == "hello"
    assert fake.sent["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    u = llm._USAGE["claude_haiku"]
    assert (u["in"], u["out"], u["cache_read"], u["cache_write"]) == (3000, 40, 2100, 0)
    assert "2100 cache read" in llm.usage_summary()


def test_an_openai_style_server_reports_its_own_cache_hits():
    deepseek = SimpleNamespace(prompt_tokens=4903, completion_tokens=2538, prompt_cache_hit_tokens=1152,
                               prompt_cache_miss_tokens=3751)
    openai_style = SimpleNamespace(prompt_tokens=900, prompt_tokens_details=SimpleNamespace(cached_tokens=640))
    assert llm._cached_prompt_tokens(deepseek) == 1152
    assert llm._cached_prompt_tokens(openai_style) == 640
    assert llm._cached_prompt_tokens(SimpleNamespace(prompt_tokens=10, prompt_tokens_details=None)) == 0
    assert "(1152 cache read, 0 written)" in llm._usage_text({"in": 4903, "out": 2538, "cache_read": 1152})


class _TimingOut(_FakeClient):
    def create(self, **kw):
        import anthropic
        import httpx
        raise anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_a_timed_out_call_is_counted_as_billed_with_an_estimate(monkeypatch, tmp_path):
    """A reply that never comes is still billed, maybe more than once: on 2026-10-25 Kimi billed 77 k3 calls where
    the log showed 23. The row and LLM USAGE carry an estimate: the prompt from its length, max_tokens as the ceiling."""
    import json

    import pytest

    from newsroom.config import CONFIG
    monkeypatch.setattr(llm, "_ANTHROPIC", _TimingOut())
    monkeypatch.setenv("NEWSROOM_LLM", "claude_haiku")
    monkeypatch.setenv("NEWSROOM_LLM_LOG", "1")
    monkeypatch.setattr(llm, "_USAGE", {})
    import dataclasses
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old, llm_calls=tmp_path))
    try:
        with pytest.raises(llm.LLMTimeout) as err:
            llm.complete_json("weather", _Out, "system " * 100, USER)
    finally:
        object.__setattr__(CONFIG, "paths", old)
    est = err.value.estimate
    prov = CONFIG.llm.provider("claude_haiku")
    assert est["sent"] == (prov.max_retries or 0) + 1 and est["out_max"] == (prov.max_tokens or 4000) and 150 < est["in"] < 2000
    u = llm._USAGE["claude_haiku"]
    assert u["failed"] == 1 and u["unanswered"] == est["sent"] and u["est_in"] == est["in"] * est["sent"]
    assert f"plus {est['sent']} unanswered (~{u['est_in']} in" in llm.usage_summary()
    [row] = [json.loads(l) for f in tmp_path.glob("*.jsonl") for l in f.read_text(encoding="utf-8").splitlines()]
    assert row["estimate"] == est and "timed out" in row["error"] and row["usage"] is None


def test_the_sport_the_auction_and_the_council_calendar_are_in_the_cached_head():
    """They change once a day at most; after the break they were paid for in full on every call."""
    w = world_mod.seed()
    head, _, tail = w.summary_for_prompt().partition(llm.CACHE_BREAK)
    assert "Sport: Tidewater Town FC" in head and "Council: full council meets" in head
    assert "Sport:" not in tail and "Open story threads" in tail and "Last weather" in tail
    # What changes from script to script stays after the break: the head is the same bytes.
    w.update_thread(None, "Harbour wall report due Friday", "The report goes to council on Friday.")
    w.record_headline("Harbour wall report due Friday")
    w.last_weather = {"map_state": "rain", "temp_c": 9, "headline": "Wet"}
    w.ensure_person("Nora Ellison", "runs the pool petition")
    assert w.summary_for_prompt().partition(llm.CACHE_BREAK)[0] == head
    assert world_mod.QUAY_LABEL not in w.summary_for_prompt(auction=False).partition(llm.CACHE_BREAK)[0]


def test_pictures_go_after_the_prompt_and_stay_out_of_the_call_log(monkeypatch, tmp_path):
    """The cut-out cartoons' picture check: each frame under its caption, and only to an anthropic provider."""
    import dataclasses
    import json

    import pytest

    from newsroom.config import CONFIG
    pic = tmp_path / "frame.jpg"
    pic.write_bytes(b"not really a jpeg")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_ANTHROPIC", fake)
    monkeypatch.setenv("NEWSROOM_LLM", "claude_haiku")
    monkeypatch.setenv("NEWSROOM_LLM_LOG", "1")
    monkeypatch.setattr(llm, "_USAGE", {})
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old, llm_calls=tmp_path))
    try:
        assert llm.complete_json("weather", _Out, "system", "Look at this.", images=[("Shot 1:", pic)]).text == "hello"
    finally:
        object.__setattr__(CONFIG, "paths", old)
    content = fake.sent["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "text", "image"] and content[1]["text"] == "Shot 1:"
    assert content[2]["source"] == {"type": "base64", "media_type": "image/jpeg", "data": "bm90IHJlYWxseSBhIGpwZWc="}
    [row] = [json.loads(l) for f in tmp_path.glob("*.jsonl") for l in f.read_text(encoding="utf-8").splitlines()]
    assert row["messages"][0]["content"][2] == {"type": "image", "source": "(picture left out)"}
    with pytest.raises(llm.LLMError):
        llm._picture_blocks(ProviderCfg(name="d", kind="openai", model="m"), [("Shot 1:", pic)])
