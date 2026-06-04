#!/usr/bin/env python
"""Live integration tests for davinci-resolve-lite-mcp — one test per tool.

Runs against a RUNNING server (Workspace > Scripts > Utility > davinci_mcp_server)
with a project + at least one timeline + one media clip open.

  python3 tests/live_test.py                # run all
  python3 tests/live_test.py set_timecode   # run one feature (+ shared setup)
  python3 tests/live_test.py add_track set_cdl ...

Each test is reversible: mutations happen on a throwaway scratch timeline / temp
files that are cleaned up. File-dependent and session-destructive tools are
tested via their error path (clean ToolError) and marked accordingly.

Exit code 0 = all selected passed (skips allowed), 1 = a failure.
"""

import json
import os
import shutil
import sys
import urllib.request

HOST = os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("DAVINCI_MCP_PORT", "8765"))
URL = f"http://{HOST}:{PORT}/mcp"
TMP = os.path.join(os.path.expanduser("~"), "Movies", ".mcp_test")
SCRATCH = "__mcp_test_scratch"
VID1 = {"trackType": "video", "trackIndex": 1, "itemIndex": 1}

CTX = {}
_id = 0


class Skip(Exception):
    pass


def _rpc(method, params=None):
    global _id
    _id += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def call(tool, args=None, **kw):
    res = _rpc("tools/call", {"name": tool, "arguments": args if args is not None else kw})["result"]
    txt = res["content"][0]["text"]
    if res.get("isError"):
        raise AssertionError(f"{tool} -> {txt}")
    try:
        return json.loads(txt)
    except (ValueError, TypeError):
        return txt


def err(tool, args=None, **kw):
    """Assert the tool returns an isError result; return the message."""
    res = _rpc("tools/call", {"name": tool, "arguments": args if args is not None else kw})["result"]
    if not res.get("isError"):
        raise AssertionError(f"{tool} expected error, got: {res['content'][0]['text'][:80]}")
    return res["content"][0]["text"]


def need(cond, msg="assertion failed"):
    if not cond:
        raise AssertionError(msg)


def goto_scratch():
    for t in call("list_timelines")["timelines"]:
        if t["name"] == SCRATCH:
            call("set_current_timeline", index=t["index"])
            break
    else:
        raise AssertionError("scratch timeline missing")
    # Deterministic reset so every test starts identical: clear video/audio
    # tracks, then re-add ONE linked clip on V1 (no mediaType -> video+audio,
    # linked). Without this, linked split/ripple ops leak audio-track state
    # between tests. Deleting a linked item can drop its pair, so re-query each
    # pass and ignore stale indices.
    for tt in ("video", "audio"):
        for idx in (1, 2):
            while True:
                items = call("get_track_items", trackType=tt, index=idx)["items"]
                if not items:
                    break
                try:
                    call("delete_timeline_item", trackType=tt, trackIndex=idx,
                         itemIndex=len(items))
                except AssertionError:
                    break
    if CTX.get("src"):
        call("add_clip_to_timeline", name=CTX["src"], startFrame=0, endFrame=60,
             recordFrame=0, trackIndex=1)


def color_grab():
    """Put the playhead on the scratch clip, switch to Color, grab a still."""
    goto_scratch()
    call("set_timecode", timecode=call("get_timeline_info")["startTimecode"])
    call("open_page", page="color")
    call("grab_still")


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def setup():
    st = call("get_status")
    need(st.get("project"), "no project open")
    CTX["orig_timeline"] = st["timeline"]
    CTX["orig_folder"] = call("list_media_pool")["folder"]
    # pick a source clip from the current folder
    clips = call("list_media_pool")["clips"]
    src = None
    for c in clips:  # prefer a real A/V media clip (supports flags/color/metadata)
        ty = c.get("type") or ""
        if "비디오" in ty or "video" in ty.lower():
            src = c["name"]
            break
    CTX["src"] = src
    call("create_timeline", name=SCRATCH)  # becomes current
    if src:
        call("add_clip_to_timeline", name=src, startFrame=0, endFrame=60, recordFrame=0)
    os.makedirs(TMP, exist_ok=True)


def teardown():
    try:
        for t in call("list_timelines")["timelines"]:
            if t["name"] == CTX.get("orig_timeline"):
                call("set_current_timeline", index=t["index"])
                break
        call("set_current_folder", name=CTX.get("orig_folder", "Master"))
    except Exception as exc:  # noqa: BLE001
        print("  teardown(restore) warn:", exc)
    for name in (SCRATCH,):
        try:
            call("delete_timeline", name=name)
        except Exception:  # noqa: BLE001
            pass
    shutil.rmtree(TMP, ignore_errors=True)


# --------------------------------------------------------------------------
# tests — registered in order; name == tool == selectable feature
# --------------------------------------------------------------------------
TESTS = []


def test(name):
    def reg(fn):
        TESTS.append((name, fn))
        return fn
    return reg


def src_required():
    if not CTX.get("src"):
        raise Skip("no source clip in current folder")
    return CTX["src"]


def skip_if(exc, signature, reason):
    """Re-raise as Skip if the error matches a known env-flaky signature."""
    if signature in str(exc):
        raise Skip(reason)
    raise exc


MARKER_FLAKE = "Resolve marker state (AddMarker) — flaky in rapid succession; tool verified individually"
STILL_FLAKE = "Resolve gallery/still state (GrabStill/ExportStills) — flaky in rapid succession; verified individually"


def fresh_group(name):
    """Create a color group, removing any leftover of the same name first."""
    try:
        call("delete_color_group", name=name)
    except AssertionError:
        pass
    call("add_color_group", name=name)

# --------------------------------------------------------------------------
def main(argv):
    selected = set(argv[1:])
    names = {n for n, _ in TESTS}
    bad = selected - names
    if bad:
        print("Unknown features:", ", ".join(sorted(bad)))
        return 2
    try:
        call("get_status")
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach MCP server at {URL}: {exc}")
        print("Launch Workspace > Scripts > Utility > davinci_mcp_server first.")
        return 2

    run = [(n, f) for n, f in TESTS if not selected or n in selected]
    print(f"Running {len(run)} feature test(s)...\n")
    setup()
    passed = failed = skipped = 0
    fails = []
    try:
        for name, fn in run:
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except Skip as s:
                print(f"  SKIP  {name} ({s})")
                skipped += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL  {name}: {exc}")
                failed += 1
                fails.append(name)
            # Detect a wedged UI (Studio-upsell modal etc.): currentPage == null
            # means OpenPage/SetCurrentTimeline will fail for everything after.
            try:
                if call("get_status").get("currentPage") is None:
                    print("\n  ABORT: Resolve UI is on a non-page/modal screen "
                          "(currentPage=null) — likely a Studio-upgrade dialog "
                          f"triggered by '{name}'. Dismiss it in Resolve and re-run.")
                    break
            except Exception:  # noqa: BLE001
                break
    finally:
        teardown()
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    if fails:
        print("Failed:", ", ".join(fails))
    return 1 if failed else 0


# Import area modules in the original registration order.
from tests.live import status  # noqa: E402,F401
from tests.live import projects  # noqa: E402,F401
from tests.live import timelines  # noqa: E402,F401
from tests.live import tracks  # noqa: E402,F401
from tests.live import editing  # noqa: E402,F401
from tests.live import color  # noqa: E402,F401
from tests.live import gallery  # noqa: E402,F401
from tests.live import mediapool  # noqa: E402,F401
from tests.live import storage  # noqa: E402,F401
from tests.live import render  # noqa: E402,F401
