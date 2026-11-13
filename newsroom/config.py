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
                  "continuity": "NEWSROOM_CONTINUITY", "pictures": "NEWSROOM_PICTURES_DIR",
                  "control": "NEWSROOM_CONTROL", "annals": "NEWSROOM_ANNALS"}


@dataclass(frozen=True)
class BroadcastCfg:
    width: int = 960
    height: int = 540
    fps: int = 60
    parallax: bool = False               # layered location backdrops that drift (parallax.py; or --parallax)
    audio_device: str = ""               # sound output by (part of) its name; "" = the system's (or --audio-device)
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
    week_review: bool = True             # Sundays: the slot is The Week in Port Wexley (review.py)
    year_review: bool = True             # 31 December: The Year in Port Wexley


@dataclass(frozen=True)
class InquiryCfg:
    commission_from: str = "18:30"       # tonight's subject is chosen in idle time from here (inquiry.py)
    airs_at: str = "20:00"               # when The Inquiry starts; no commission after it
    min_mentions: int = 3                # a story needs this much coverage to be investigated
    rest_days: int = 7                   # and not to have been investigated in this many days


@dataclass(frozen=True)
class PanelCfg:
    commission_from: str = "18:30"       # tonight's lineup is chosen in idle time from here (panel.py)
    airs_at: str = "20:30"               # when The Panel starts; no commission after it


@dataclass(frozen=True)
class PhoneInCfg:
    commission_from: str = "08:30"       # today's question and studio guest are chosen in idle time from here (phonein.py)
    airs_at: str = "10:00"               # when Have Your Say starts; no booking after it


@dataclass(frozen=True)
class ChamberCfg:
    first_meeting: str = "2026-11-05"    # full council's first meeting on air (council.py), a Thursday,
    every_days: int = 14                 # then every other Thursday
    commission_from: str = "18:30"       # tonight's agenda and votes are booked in idle time from here (chamber.py)
    airs_at: str = "20:00"               # when The Chamber starts (until 21:00); no booking after it


@dataclass(frozen=True)
class StoryCfg:
    plan_every_s: float = 1200.0
    thin_board: int = 8                  # below this many open the desk may seed two new stories a round, else one
    seeds_per_day: int = 10              # planned new stories a day, the desk's and the senior editor's together,
    seeds_from: str = "06:00"            # none before this (the overnight repeats), then released evenly
    seeds_over_h: float = 18.0           # over this many hours: one every 1.8 h, the last by midnight
    batch: int = 8                       # threads the desk plans per call, least recently planned first
    review_every_s: float = 7200.0       # the senior editor reviews the desk's board this often (0: never)
    max_live_threads: int = 40           # past this many open, the stalest fade (world.fade_threads)
    fade_oneoff_h: float = 8.0           # hours of air time without a new beat before a thread fades,
    fade_quiet_h: float = 24.0           # for one covered once or twice, most threads,
    fade_resolving_h: float = 12.0       # one winding down,
    fade_peak_h: float = 72.0            # and one at its peak
    # The running-stories pool (world.pool_threads): a long story whose NEXT names a later day waits for it,
    # off the writers' board, instead of being reported with nothing new until it is closed as stalled.
    pool: bool = True
    pool_after_days: int = 2             # long: open this many days,
    pool_after_mentions: int = 10        # or covered this often


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
class PicturesCfg:
    """ComfyUI pictures in shadow mode (pictures.py): made in the back office, shown nowhere yet."""
    enabled: bool = False                # or --pictures for one run
    url: str = "http://127.0.0.1:8188"   # ComfyUI's HTTP API
    model: str = "z_image"               # "z_image" (Z-Image Turbo), "qwen_image" (+ Lightning 8 steps), "qwen_image_cfg" (12 steps, cfg 2.5)
    per_day: int = 150                   # pictures a broadcast day at most (every show, in shadow mode)
    min_free_gb: float = 12.0            # free GPU memory needed to load the model from cold
    idle_free_s: float = 600.0           # unload ComfyUI's models after this long with nothing to make
    poll_s: float = 30.0                 # how long the painter waits on its queue between looks
    wait_s: float = 120.0                # how long it waits when ComfyUI is down or busy, or the GPU is full
    queue_max: int = 40                  # requests waiting at most; past that new ones are dropped
    brief: bool = True                   # one short call per picture says what to draw (task picture_brief)


@dataclass(frozen=True)
class BackupsCfg:
    """Copies of the world file in data/backups (world.backup)."""
    keep: int = 14                       # days of daily copies kept; 0 = no backups at all


@dataclass(frozen=True)
class CacheCfg:
    """Clearing old scripts and audio out of the segment cache (prune.py)."""
    keep_days: float = 0.0               # 0: never. Else entries this old that the archive doesn't hold go, in idle time
    every_days: float = 1.0              # how often: 1 = once a day (at the first idle moment after a start), 7 = weekly


@dataclass(frozen=True)
class SafetyCfg:
    """The word check on everything that goes on air (safety.py)."""
    enabled: bool = True
    extra_terms: list[str] = field(default_factory=list)   # more terms, as in assets/safety/blocklist.txt


@dataclass(frozen=True)
class StreamCfg:
    """Restarting the OBS stream so YouTube keeps each part (obs.StreamDirector; only with --obs)."""
    restart_at: list[str] = field(default_factory=list)    # "HH:MM": restart on the first bumper at or after each
    gap_s: float = 5.0                   # between stopping and starting again
    keep_alive: bool = False             # start a stream found stopped at a break, whoever stopped it


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
    pictures: Path = ROOT / "data" / "pictures"
    control: Path = ROOT / "data" / "control.txt"     # "testcard" or "air" (control.py)
    annals: Path = ROOT / "data" / "annals"            # a page a day, and its keepsake clips (annals.py)


@dataclass(frozen=True)
class RundownCfg:
    """The model-planned running orders (rundown.py): a theme and a subject per item, booked in idle time."""
    shows: tuple[str, ...] = ("magazine", "late")   # show ids planned each night; () turns it off
    lead_min: int = 90                   # booked from this many minutes before the show starts


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
    panel: PanelCfg
    chamber: ChamberCfg
    phonein: PhoneInCfg
    breaking: BreakingCfg
    adverts: AdvertsCfg
    continuity: ContinuityCfg
    pictures: PicturesCfg
    safety: SafetyCfg = field(default_factory=SafetyCfg)
    cache: CacheCfg = field(default_factory=CacheCfg)
    backups: BackupsCfg = field(default_factory=BackupsCfg)
    stream: StreamCfg = field(default_factory=StreamCfg)
    rundown: RundownCfg = field(default_factory=RundownCfg)


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
        panel=PanelCfg(**raw.get("panel", {})),
        chamber=ChamberCfg(**raw.get("chamber", {})),
        phonein=PhoneInCfg(**raw.get("phonein", {})),
        breaking=BreakingCfg(**raw.get("breaking", {})),
        adverts=AdvertsCfg(**raw.get("adverts", {})),
        continuity=ContinuityCfg(**raw.get("continuity", {})),
        pictures=PicturesCfg(**raw.get("pictures", {})),
        safety=SafetyCfg(**raw.get("safety", {})),
        cache=CacheCfg(**raw.get("cache", {})),
        backups=BackupsCfg(**raw.get("backups", {})),
        stream=StreamCfg(**raw.get("stream", {})),
        rundown=RundownCfg(**{k: tuple(v) if isinstance(v, list) else v for k, v in raw.get("rundown", {}).items()}),
    )
    cfg.paths.cache.mkdir(parents=True, exist_ok=True)
    return cfg


CONFIG = load()
