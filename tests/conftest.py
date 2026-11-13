"""Every test runs against a temp town: set before pytest imports any test module.

CONFIG is built when newsroom.config is first imported, so a test module that set these
itself would be too late whenever an earlier module imported newsroom first, and the
real data/world.json and data/cache would be in play.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="newsroom-test-")
os.environ["NEWSROOM_TEST_DIR"] = _TMP
os.environ["NEWSROOM_WORLD"] = os.path.join(_TMP, "world.json")
os.environ["NEWSROOM_CACHE"] = os.path.join(_TMP, "cache")
os.environ["NEWSROOM_TIPLINE"] = os.path.join(_TMP, "tipline.txt")
os.environ["NEWSROOM_ADS"] = os.path.join(_TMP, "ads")
os.environ["NEWSROOM_CONTINUITY"] = os.path.join(_TMP, "continuity")
os.environ["NEWSROOM_LLM_CALLS"] = os.path.join(_TMP, "llm_calls")
os.environ["NEWSROOM_ANNALS"] = os.path.join(_TMP, "annals")       # the town's long memory: never the real one
os.environ["NEWSROOM_CONTROL"] = os.path.join(_TMP, "control.txt")   # the kill switch: never the real one
os.environ["NEWSROOM_LLM"] = "off"
os.environ["NEWSROOM_RUNDOWN"] = "0"      # no running orders booked by the real clock (test_rundown turns it on)
os.environ["NEWSROOM_COUNCIL_NIGHT"] = "0"     # 20:00 is The Inquiry whatever the date; council tests set "1"
os.environ["NEWSROOM_SPECIAL_DAY"] = "0"       # an ordinary day even at Christmas (test_christmas sets it)
os.environ["NEWSROOM_SPECIAL_NIGHT"] = "0"     # 19:00 is the studio Coastwide even on 5 November (test_special_nights)
os.environ.pop("NEWSROOM_LLM_LOG", None)
os.environ.pop("NEWSROOM_REVIEW", None)        # the documentary slot is a documentary unless a test says
