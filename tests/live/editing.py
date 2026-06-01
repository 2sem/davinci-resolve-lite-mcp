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


# ---- editing (operate on scratch V1 item #1) ----
@test("add_clip_to_timeline")
def _():
    goto_scratch(); s = src_required()
    n0 = len(call("get_track_items", trackType="video", index=1)["items"])
    call("add_clip_to_timeline", name=s, startFrame=0, endFrame=30, recordFrame=300)
    n1 = len(call("get_track_items", trackType="video", index=1)["items"])
    need(n1 == n0 + 1)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n1)

@test("append_clips_to_timeline")
def _():
    goto_scratch(); s = src_required()
    r = call("append_clips_to_timeline", names=[s]); need(r["appended"] >= 1)
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("delete_timeline_item")
def _():
    goto_scratch(); s = src_required()
    call("append_clips_to_timeline", names=[s])
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    need(call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)["ok"])

def _delete_last_video_item():
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    if n >= 1:
        call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("insert_title")
def _():
    goto_scratch(); call("set_timecode", timecode=call("get_timecode")["timecode"])
    try:
        call("insert_title", title="Text"); _delete_last_video_item()
    except AssertionError:
        raise Skip("'Text' title not available")

@test("insert_fusion_title")
def _():
    goto_scratch()
    call("insert_fusion_title", title="Text+"); _delete_last_video_item()

@test("insert_generator")
def _():
    goto_scratch()
    try:
        call("insert_generator", name="Solid Color"); _delete_last_video_item()
    except AssertionError:
        raise Skip("'Solid Color' generator not available")

@test("create_compound_clip")
def _():
    goto_scratch(); src_required()
    items = call("get_track_items", trackType="video", index=1)["items"]
    need(len(items) >= 1)
    name = call("create_compound_clip", trackType="video", trackIndex=1,
                itemIndices=[1], name="__mcp_comp")["created"]
    _delete_last_video_item()
    try:
        call("delete_clip", names=[name])
    except AssertionError:
        pass

@test("create_fusion_clip")
def _():
    goto_scratch(); src_required()
    call("append_clips_to_timeline", names=[CTX["src"]])
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    call("create_fusion_clip", trackType="video", trackIndex=1, itemIndices=[n])
    _delete_last_video_item()

@test("get_timeline_item_property")
def _():
    goto_scratch(); need("value" in call("get_timeline_item_property", VID1 | {"property": "ZoomX"}))

@test("set_timeline_item_property")
def _():
    goto_scratch()
    call("set_timeline_item_property", VID1 | {"property": "ZoomX", "value": 1.2})
    call("set_timeline_item_property", VID1 | {"property": "ZoomX", "value": 1.0})

@test("get_timeline_item_timing")
def _():
    goto_scratch(); need("sourceStartFrame" in call("get_timeline_item_timing", VID1))

@test("get_current_video_item")
def _():
    goto_scratch(); call("set_timecode", timecode=call("get_timecode")["timecode"])
    need("item" in call("get_current_video_item"))

@test("set_clip_enabled")
def _():
    goto_scratch()
    call("set_clip_enabled", VID1 | {"enabled": False})
    call("set_clip_enabled", VID1 | {"enabled": True})

@test("get_clip_tags")
def _():
    goto_scratch(); need("clipColor" in call("get_clip_tags", VID1))

@test("set_clip_color")
def _():
    goto_scratch()
    call("set_clip_color", VID1 | {"color": "Orange"}); call("set_clip_color", VID1 | {"color": ""})

@test("add_clip_flag")
def _():
    goto_scratch(); call("add_clip_flag", VID1 | {"color": "Blue"}); call("clear_clip_flags", VID1)

@test("clear_clip_flags")
def _():
    goto_scratch(); call("add_clip_flag", VID1 | {"color": "Red"})
    need(call("clear_clip_flags", VID1)["ok"])

def _clear_clip_markers():
    try:
        call("delete_clip_marker", VID1 | {"color": "All"})
    except AssertionError:
        pass

@test("add_clip_marker")
def _():
    goto_scratch(); _clear_clip_markers()
    try:
        call("add_clip_marker", VID1 | {"frame": 10, "color": "Green"})
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    call("delete_clip_marker", VID1 | {"color": "All"})

@test("delete_clip_marker")
def _():
    goto_scratch(); _clear_clip_markers()
    try:
        call("add_clip_marker", VID1 | {"frame": 12})
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    need(call("delete_clip_marker", VID1 | {"frame": 12})["ok"])
