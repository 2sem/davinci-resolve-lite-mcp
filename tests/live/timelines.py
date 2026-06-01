import os

from tests.live import (
    CTX,
    MARKER_FLAKE,
    SCRATCH,
    STILL_FLAKE,
    TMP,
    VID1,
    Skip,
    call,
    color_grab,
    err,
    fresh_group,
    goto_scratch,
    need,
    skip_if,
    src_required,
    test,
)


# ---- timelines ----
@test("list_timelines")
def _(): need(any(t["name"] == SCRATCH for t in call("list_timelines")["timelines"]))

@test("set_current_timeline")
def _():
    call("set_current_timeline", index=1); goto_scratch()

@test("create_timeline")
def _():
    call("create_timeline", name="__mcp_ct"); call("delete_timeline", name="__mcp_ct"); goto_scratch()

@test("create_timeline_from_clips")
def _():
    s = src_required()
    call("create_timeline_from_clips", name="__mcp_cfc", names=[s])
    call("delete_timeline", name="__mcp_cfc"); goto_scratch()
    err("create_timeline_from_clips", name="__mcp_x", names=[])

@test("delete_timeline")
def _():
    call("create_timeline", name="__mcp_del"); goto_scratch()
    call("delete_timeline", name="__mcp_del")

@test("duplicate_timeline")
def _():
    goto_scratch()
    d = call("duplicate_timeline", name="__mcp_dup")["created"]
    goto_scratch(); call("delete_timeline", name=d)

@test("get_timeline_info")
def _(): need("tracks" in call("get_timeline_info"))

@test("set_timeline_name")
def _():
    goto_scratch()
    call("set_timeline_name", name=SCRATCH + "_r"); call("set_timeline_name", name=SCRATCH)

@test("set_timeline_start_timecode")
def _():
    goto_scratch()
    tc = call("get_timeline_info")["startTimecode"]
    call("set_timeline_start_timecode", timecode=tc)

@test("get_timecode")
def _(): need("timecode" in call("get_timecode"))

@test("set_timecode")
def _():
    goto_scratch()
    tc = call("get_timecode")["timecode"]; call("set_timecode", timecode=tc)

def _clear_timeline_markers():
    try:
        call("delete_timeline_marker", color="All")
    except AssertionError:
        pass

@test("add_timeline_marker")
def _():
    goto_scratch(); _clear_timeline_markers()
    f = call("get_timeline_info")["startFrame"] + 10  # markers use absolute timeline frames
    call("add_timeline_marker", frame=f, color="Blue", name="m")
    call("delete_timeline_marker", color="All")

@test("delete_timeline_marker")
def _():
    goto_scratch(); _clear_timeline_markers()
    f = call("get_timeline_info")["startFrame"] + 12
    try:
        call("add_timeline_marker", frame=f, color="Red")
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    need(call("delete_timeline_marker", frame=f)["ok"])

@test("set_mark_in_out")
def _():
    goto_scratch()
    call("set_mark_in_out", {"in": 0, "out": 10}); call("clear_mark_in_out")

@test("get_mark_in_out")
def _(): need("markInOut" in call("get_mark_in_out"))

@test("clear_mark_in_out")
def _(): need(call("clear_mark_in_out")["ok"])

@test("detect_scene_cuts")
def _():
    goto_scratch()
    try:
        call("detect_scene_cuts")  # Studio: runs
    except AssertionError as e:    # Lite: clean Studio-required gate (no modal)
        need("Studio" in str(e), f"unexpected error: {e}")

@test("export_timeline")
def _():
    goto_scratch()
    p = os.path.join(TMP, "tl.drt")
    call("export_timeline", filePath=p, exportType="DRT"); need(os.path.exists(p))

@test("import_timeline")
def _(): err("import_timeline", filePath="/nonexistent/x.drt")

@test("import_into_timeline")
def _(): err("import_into_timeline", filePath="/nonexistent/x.aaf")
