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


# ---- tracks ----
@test("get_track_items")
def _(): need("items" in call("get_track_items", trackType="video", index=1))

@test("add_track")
def _():
    goto_scratch()
    n = call("add_track", trackType="video")["count"]; CTX["added_track"] = n

@test("set_track_name")
def _():
    goto_scratch(); call("set_track_name", trackType="video", trackIndex=2, name="mcp")

@test("set_track_enabled")
def _():
    goto_scratch()
    call("set_track_enabled", trackType="video", trackIndex=2, enabled=False)
    call("set_track_enabled", trackType="video", trackIndex=2, enabled=True)

@test("set_track_locked")
def _():
    goto_scratch()
    call("set_track_locked", trackType="video", trackIndex=2, locked=True)
    call("set_track_locked", trackType="video", trackIndex=2, locked=False)

@test("delete_track")
def _():
    goto_scratch(); call("delete_track", trackType="video", trackIndex=2)
