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
                  "ads": "NEWSROOM_ADS", "llm_calls": "NEWSROOM_LLM_CALLS",
                  "continuity": "NEWSROOM_CONTINUITY"}


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
    cache_ttl: str = ""                  # anthropic: "5m" or "1h" caches the prompt up to llm.CACHE_BREAK
    extra_body: dict = field(default_factory=dict)
    fallback: str = ""                   # another provider that takes a call this one fails (one hop)


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
    british_guests: bool = False         # guests cast with a British accent get British pronunciation
    voices: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SpecialCfg:
    check_every_s: float = 900.0
    cooldown_s: float = 3600.0
    target_s: float = 300.0
    min_mentions: int = 2
    min_buffer_frac: float = 0.8


@dataclass(frozen=True)
class DocumentaryCfg:
    title: str = "PORT WEXLEY STORIES"   # the strand: title cards, the ticker, the studio wall
    target_s: float = 900.0              # fifteen minutes of speech
    commission_from: str = "18:00"       # the day's documentary is commissioned in idle time from here
    airs_at: str = "21:00"               # and airs at the first news bumper from here
    window_s: float = 3600.0             # not ready within this: it waits for tomorrow's slot
    repeat_at: str = "02:00"             # it airs again after the first overnight test card from here


@dataclass(frozen=True)
class InquiryCfg:
    commission_from: str = "18:30"       # tonight's subject is chosen in idle time from here (inquiry.py)
    airs_at: str = "20:00"               # when The Inquiry starts; no commission after it
    min_mentions: int = 3                # a story needs this much coverage to be investigated
    rest_days: int = 7                   # and not to have been investigated in this many days


@dataclass(frozen=True)
class StoryCfg:
    plan_every_s: float = 1200.0
    thin_board: int = 8                  # below this many open the desk may seed two new stories a round, else one
    seeds_per_day: int = 8               # planned new stories a day, the desk's and the senior editor's together
    batch: int = 8                       # threads the desk plans per call, least recently planned first
    review_every_s: float = 7200.0       # the senior editor reviews the desk's board this often (0: never)
    max_live_threads: int = 40           # past this many open, the stalest fade (world.fade_threads)
    fade_oneoff_h: float = 8.0           # hours of air time without a new beat before a thread fades,
    fade_quiet_h: float = 24.0           # for one covered once or twice, most threads,
    fade_resolving_h: float = 12.0       # one winding down,
    fade_peak_h: float = 72.0            # and one at its peak


@dataclass(frozen=True)
class BreakingCfg:
    cooldown_s: float = 900.0
    target_s: float = 60.0
    max_age_s: float = 600.0
    tip_ttl_s: float = 21600.0
    max_tips: int = 3
    desk_per_day: int = 1
    scene_window_s: float = 2700.0


@dataclass(frozen=True)
class AdvertsCfg:
    pool_size: int = 40                  # voiced ads kept; the oldest model-written ones go first
    make_every_s: float = 1800.0         # the model writes a new one this often, in idle time
    max_in_a_row: int = 3                # then the filler card and the weather replay take over


@dataclass(frozen=True)
class ContinuityCfg:
    notice_every_s: float = 2700.0       # the model writes a community notice this often, in idle time
    notices_per_day: int = 4             # from the day's open stories; they expire at midnight


@dataclass(frozen=True)
class PathsCfg:
    data: Path = ROOT / "data"
    cache: Path = ROOT / "data" / "cache"
    world: Path = ROOT / "data" / "world.json"
    assets: Path = ROOT / "assets"
    tipline: Path = ROOT / "data" / "tipline.txt"
    llm_calls: Path = ROOT / "data" / "llm_calls"
    ads: Path = ROOT / "data" / "ads"
    continuity: Path = ROOT / "data" / "continuity"


@dataclass(frozen=True)
class Config:
    broadcast: BroadcastCfg
    llm: LLMCfg
    tts: TTSCfg
    paths: PathsCfg
    special: SpecialCfg
    documentary: DocumentaryCfg
    story: StoryCfg
    inquiry: InquiryCfg
    breaking: BreakingCfg
    adverts: AdvertsCfg
    continuity: ContinuityCfg


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
        documentary=DocumentaryCfg(**raw.get("documentary", {})),
        story=StoryCfg(**raw.get("story", {})),
        inquiry=InquiryCfg(**raw.get("inquiry", {})),
        breaking=BreakingCfg(**raw.get("breaking", {})),
        adverts=AdvertsCfg(**raw.get("adverts", {})),
        continuity=ContinuityCfg(**raw.get("continuity", {})),
    )
    cfg.paths.cache.mkdir(parents=True, exist_ok=True)
    return cfg


CONFIG = load()
