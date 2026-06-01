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


# ---- status & navigation ----
@test("get_status")
def _(): need("product" in call("get_status"))

@test("open_page")
def _():
    call("open_page", page="color"); call("open_page", page="edit")

@test("get_setting")
def _(): need(call("get_setting", scope="project", name="timelineFrameRate")["value"])

@test("set_setting")
def _():
    v = call("get_setting", scope="timeline", name="useCustomSettings")["value"]
    call("set_setting", scope="timeline", name="useCustomSettings", value=str(v or "0"))

@test("refresh_lut_list")
def _(): need(call("refresh_lut_list")["ok"])
