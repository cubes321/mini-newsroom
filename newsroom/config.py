"""Load config.toml into frozen dataclasses.

Everything tunable lives in config.toml at the project root so the model,
voices and buffer horizon can be changed without touching code.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# PathsCfg field -> environment variable that overrides it.
PATH_OVERRIDES = {"world": "NEWSROOM_WORLD", "cache": "NEWSROOM_CACHE", "tipline": "NEWSROOM_TIPLINE",
                  "ads": "NEWSROOM_ADS"}


@dataclass(frozen=True)
class BroadcastCfg:
    width: int = 960
    height: int = 540
    fps: int = 60
    horizon_s: float = 600.0
    words_per_minute: int = 150


@dataclass(frozen=True)
class ProviderCfg:
    name: str
    kind: str = "openai"                 # "openai" (any compatible endpoint) | "anthropic"
    base_url: str = ""
    api_key_env: str = ""
    model: str = ""
    temperature: float | None = None     # overrides LLMCfg.temperature when set
    max_tokens: int | None = None        # overrides LLMCfg.max_tokens (thinking models need more)
    timeout_s: float | None = None       # overrides LLMCfg.timeout_s (slow thinking models need more)
    max_retries: int = 1                 # SDK retries; each timed-out retry waits the full timeout again
    extra_body: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LLMCfg:
    default_provider: str = "lmstudio"
    timeout_s: float = 90.0
    first_call_timeout_s: float = 120.0
    max_tokens: int = 700
    temperature: float = 0.8
    log_calls: bool = False              # full prompt + reply of every call to data/llm_calls/<date>.jsonl
    routes: dict[str, str] = field(default_factory=dict)
    providers: dict[str, ProviderCfg] = field(default_factory=dict)

    def provider_name_for(self, task: str) -> str:
        return self.routes.get(task, self.default_provider)

    def provider(self, name: str) -> ProviderCfg:
        try:
            return self.providers[name]
        except KeyError:
            raise KeyError(f"no [llm.providers.{name}] in config.toml") from None


@dataclass(frozen=True)
class TTSCfg:
    backend: str = "kokoro"
    lang_code: str = "a"
    sample_rate: int = 24000
    device: str = "cpu"
    voices: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SpecialCfg:
    check_every_s: float = 900.0
    cooldown_s: float = 3600.0
    target_s: float = 300.0
    min_mentions: int = 2
    min_buffer_frac: float = 0.8


@dataclass(frozen=True)
class StoryCfg:
    plan_every_s: float = 1200.0
    max_open_threads: int = 8
    batch: int = 8                       # threads the desk plans per call, least recently planned first


@dataclass(frozen=True)
class BreakingCfg:
    cooldown_s: float = 900.0
    target_s: float = 60.0
    max_age_s: float = 600.0
    tip_ttl_s: float = 21600.0
    max_tips: int = 3


@dataclass(frozen=True)
class AdvertsCfg:
    pool_size: int = 40                  # voiced ads kept; the oldest model-written ones go first
    make_every_s: float = 1800.0         # the model writes a new one this often, in idle time
    max_in_a_row: int = 3                # then the filler card and the weather replay take over


@dataclass(frozen=True)
class PathsCfg:
    data: Path = ROOT / "data"
    cache: Path = ROOT / "data" / "cache"
    world: Path = ROOT / "data" / "world.json"
    assets: Path = ROOT / "assets"
    tipline: Path = ROOT / "data" / "tipline.txt"
    llm_calls: Path = ROOT / "data" / "llm_calls"
    ads: Path = ROOT / "data" / "ads"


@dataclass(frozen=True)
class Config:
    broadcast: BroadcastCfg
    llm: LLMCfg
    tts: TTSCfg
    paths: PathsCfg
    special: SpecialCfg
    story: StoryCfg
    breaking: BreakingCfg
    adverts: AdvertsCfg


def load(path: Path | None = None) -> Config:
    path = path or ROOT / "config.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    llm_raw = dict(raw.get("llm", {}))
    routes = llm_raw.pop("routes", {})
    providers = {
        name: ProviderCfg(name=name, **spec) for name, spec in llm_raw.pop("providers", {}).items()
    }
    tts_raw = dict(raw.get("tts", {}))
    voices = tts_raw.pop("voices", {})
    paths_raw = {k: ROOT / v for k, v in raw.get("paths", {}).items()}
    # Test runs point at another world and cache so they can't touch the town's canon
    # (python -m newsroom --world / --cache / --scratch set these). Relative to the cwd.
    for key, env in PATH_OVERRIDES.items():
        if os.environ.get(env):
            paths_raw[key] = Path(os.environ[env]).expanduser().absolute()

    cfg = Config(
        broadcast=BroadcastCfg(**raw.get("broadcast", {})),
        llm=LLMCfg(routes=routes, providers=providers, **llm_raw),
        tts=TTSCfg(voices=voices, **tts_raw),
        paths=PathsCfg(**paths_raw),
        special=SpecialCfg(**raw.get("special", {})),
        story=StoryCfg(**raw.get("story", {})),
        breaking=BreakingCfg(**raw.get("breaking", {})),
        adverts=AdvertsCfg(**raw.get("adverts", {})),
    )
    cfg.paths.cache.mkdir(parents=True, exist_ok=True)
    return cfg


CONFIG = load()
