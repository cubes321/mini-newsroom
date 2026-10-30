"""--route / NEWSROOM_ROUTES move a provider's tasks (or one task) to another for a run, so
Sonnet can stand in for DeepSeek's back office without editing config.toml."""
from newsroom import llm
from newsroom.config import CONFIG


def test_a_provider_swap_moves_every_task_routed_to_it(monkeypatch):
    monkeypatch.delenv("NEWSROOM_LLM", raising=False)
    monkeypatch.setenv("NEWSROOM_ROUTES", "deepseek_flash_think=claude_sonnet")
    assert llm.provider_for("story_desk") == llm.provider_for("editor") == "claude_sonnet"
    assert llm.provider_for("bulletin") == CONFIG.llm.provider_name_for("bulletin")


def test_a_task_swap_moves_only_that_task_and_wins_over_its_provider(monkeypatch):
    monkeypatch.delenv("NEWSROOM_LLM", raising=False)
    monkeypatch.setenv("NEWSROOM_ROUTES", " editor = deepseek_pro , deepseek_flash_think=moonshot_k3")
    assert llm.provider_for("editor") == "deepseek_pro"
    assert llm.provider_for("story_desk") == "moonshot_k3"


def test_the_deepseek_providers_are_declared():
    assert CONFIG.llm.provider("deepseek_pro").api_key_env == "DEEPSEEK_API_KEY"
    assert CONFIG.llm.provider("deepseek_flash").model == CONFIG.llm.provider("deepseek_flash_think").model == "deepseek-flash"
