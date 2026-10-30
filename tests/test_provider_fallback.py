"""A provider with a `fallback` (DeepSeek's back office: Sonnet) passes on a call it fails, once and
from a fresh prompt; a run that pins one provider, or switches the models off, gets no fallback.

Both providers are stubbed: no network.
"""
import pytest

from newsroom import llm
from newsroom.config import CONFIG
from test_llm import USER, _FakeClient, _Out


@pytest.fixture
def flash_desk(monkeypatch):
    """The story desk on Flash thinking, as on the 2026-10-29 night; Sonnet is the stubbed fallback."""
    monkeypatch.delenv("NEWSROOM_LLM", raising=False)
    monkeypatch.setenv("NEWSROOM_ROUTES", "story_desk=deepseek_flash_think")
    monkeypatch.setattr(llm, "_USAGE", {})
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_ANTHROPIC", fake)
    return fake


def test_flash_falls_back_to_sonnet():
    assert CONFIG.llm.provider("deepseek_flash_think").fallback == "claude_sonnet"
    assert CONFIG.llm.provider("deepseek_pro").fallback == "claude_sonnet"
    assert not CONFIG.llm.provider("claude_haiku").fallback     # live scripts keep their canned fallback


def test_an_unreachable_provider_falls_back(monkeypatch, flash_desk):
    def down(*a, **kw):
        raise llm.LLMUnavailable("deepseek_flash_think unreachable: timed out")
    monkeypatch.setattr(llm, "_openai_raw", down)
    assert llm.complete_json("story_desk", _Out, "system", USER).text == "hello"
    # Sonnet got its own prompt, with the cached head the openai route had stripped
    assert flash_desk.sent["messages"][0]["content"][0]["cache_control"]["ttl"] == "1h"
    assert llm._USAGE["deepseek_flash_think"]["failed"] == 1 and llm._USAGE["claude_sonnet"]["calls"] == 1


def test_twice_invalid_falls_back_without_the_retry_turns(monkeypatch, flash_desk):
    calls = []

    def invalid(prov, system, messages, schema):
        calls.append(len(messages))
        return '{"nope": 1}', {"in": 10, "out": 5}
    monkeypatch.setattr(llm, "_openai_raw", invalid)
    assert llm.complete_json("story_desk", _Out, "system", USER).text == "hello"
    assert calls == [1, 3]                                     # the call and its one corrected retry
    assert len(flash_desk.sent["messages"]) == 1               # Sonnet starts afresh


def test_a_pinned_provider_or_models_off_gets_no_fallback(monkeypatch, flash_desk):
    def down(*a, **kw):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "_openai_raw", down)
    monkeypatch.setenv("NEWSROOM_LLM", "deepseek_flash_think")
    with pytest.raises(llm.LLMUnavailable):
        llm.complete_json("story_desk", _Out, "system", USER)
    assert flash_desk.sent is None
    monkeypatch.setenv("NEWSROOM_LLM", "off")
    with pytest.raises(llm.LLMUnavailable):
        llm.complete_json("story_desk", _Out, "system", USER)


def test_a_failed_fallback_still_raises(monkeypatch, flash_desk):
    def down(*a, **kw):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "_openai_raw", down)
    monkeypatch.setattr(llm, "_anthropic_raw", down)
    with pytest.raises(llm.LLMError):
        llm.complete_json("story_desk", _Out, "system", USER)
