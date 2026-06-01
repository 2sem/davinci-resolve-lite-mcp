#!/usr/bin/env python
"""Offline tests for the resolve_mcp package — no DaVinci Resolve required.

Run:  python3 tests/test_server.py
Uses a fake Resolve object to exercise the MCP dispatcher end to end.
"""

import json
import os
import sys
import tempfile

# Make the package importable and keep logs out of ~/Movies during tests.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
os.environ.setdefault("DAVINCI_MCP_LOG_DIR", tempfile.mkdtemp())

EXPECTED_TOOL_COUNT = 64


# --------------------------------------------------------------------------
# Minimal fake Resolve object graph
# --------------------------------------------------------------------------
class FakeTimeline:
    def __init__(self, name="Timeline 1"):
        self._name = name
        self._tc = "01:00:05:12"

    def GetName(self):
        return self._name

    def GetStartFrame(self):
        return 0

    def GetEndFrame(self):
        return 100

    def GetStartTimecode(self):
        return "01:00:00:00"

    def GetCurrentTimecode(self):
        return self._tc

    def SetCurrentTimecode(self, tc):
        self._tc = tc
        return True

    def GetTrackCount(self, _ttype):
        return 1

    def GetSetting(self, name=None):
        return {"timelineName": self._name} if name is None else "value"


class FakeProject:
    def __init__(self):
        self._tl = FakeTimeline()

    def GetName(self):
        return "FakeProject"

    def GetCurrentTimeline(self):
        return self._tl

    def GetTimelineCount(self):
        return 1

    def GetTimelineByIndex(self, idx):
        return self._tl if idx == 1 else None

    def GetSetting(self, name=None):
        table = {
            "timelineFrameRate": 30.0,
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        return table if name is None else table.get(name, "")


class FakePM:
    def GetCurrentProject(self):
        return FakeProject()

    def GetProjectListInCurrentFolder(self):
        return ["FakeProject", "Other"]


class FakeResolve:
    def GetProjectManager(self):
        return FakePM()

    def GetProductName(self):
        return "DaVinci Resolve"

    def GetVersionString(self):
        return "20.3.2.9"

    def GetCurrentPage(self):
        return "edit"

    def OpenPage(self, _page):
        return True


class InlineBridge:
    """Runs jobs inline (single-threaded) — fine for tests."""

    def __init__(self, resolve):
        self.resolve = resolve

    def call(self, func):
        return func(self.resolve)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
def check(label, cond):
    if not cond:
        raise AssertionError(label)
    print(f"  ok: {label}")


def main():
    # 1. Package imports cleanly.
    import resolve_mcp
    from resolve_mcp import server, tools
    from resolve_mcp.server import MCPDispatcher
    print("import:")
    check("resolve_mcp imports", resolve_mcp.SERVER_NAME == "davinci-resolve-lite-mcp")
    check(f"{EXPECTED_TOOL_COUNT} tools registered", len(tools.TOOLS) == EXPECTED_TOOL_COUNT)

    # 2. Launcher module imports and stays inert (no resolve in __main__).
    import davinci_mcp_server  # noqa: F401
    check("launcher imports + inert", True)

    # 3. Dispatcher protocol.
    print("dispatcher:")
    d = MCPDispatcher(InlineBridge(FakeResolve()))

    r = d.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    check("initialize serverInfo", r["result"]["serverInfo"]["name"] == "davinci-resolve-lite-mcp")

    check("notifications return None",
          d.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None)

    r = d.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    check("tools/list count", len(names) == EXPECTED_TOOL_COUNT)
    for required in ("get_status", "set_setting", "delete_clip", "render_current_timeline"):
        check(f"tool present: {required}", required in names)

    # 4. tools/call success + payload.
    r = d.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "get_status", "arguments": {}}})
    payload = json.loads(r["result"]["content"][0]["text"])
    check("get_status payload", payload["project"] == "FakeProject" and r["result"]["isError"] is False)

    r = d.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "set_timecode", "arguments": {"timecode": "01:02:03:04"}}})
    check("set_timecode round-trips",
          json.loads(r["result"]["content"][0]["text"])["timecode"] == "01:02:03:04")

    # 5. Error paths.
    r = d.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "open_page", "arguments": {"page": "bogus"}}})
    check("bad arg -> isError", r["result"]["isError"] is True)

    r = d.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                  "params": {"name": "does_not_exist", "arguments": {}}})
    check("unknown tool -> isError", r["result"]["isError"] is True)

    r = d.handle({"jsonrpc": "2.0", "id": 7, "method": "frobnicate"})
    check("unknown method -> -32601", r["error"]["code"] == -32601)

    # 6. Bridge fails fast once stopped (no hang on done.wait).
    print("bridge:")
    from resolve_mcp.bridge import ResolveBridge
    b = ResolveBridge("R")
    b.stop()
    try:
        b.call(lambda r: r)
        raise AssertionError("call() after stop should raise")
    except RuntimeError:
        check("call() after stop raises (no hang)", True)

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
