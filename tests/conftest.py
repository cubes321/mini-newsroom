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
os.environ["NEWSROOM_LLM"] = "off"
os.environ.pop("NEWSROOM_LLM_LOG", None)
