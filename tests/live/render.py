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


# ---- render & export ----
@test("export_current_frame_as_still")
def _():
    goto_scratch()
    p = os.path.join(TMP, "frame.jpg"); call("export_current_frame_as_still", filePath=p); need(os.path.exists(p))

@test("get_render_presets")
def _(): need("renderPresets" in call("get_render_presets"))

@test("save_render_preset")
def _():
    n = f"__mcp_rp_{os.getpid()}"
    call("save_render_preset", name=n); call("delete_render_preset", name=n)

@test("delete_render_preset")
def _():
    n = f"__mcp_rp2_{os.getpid()}"
    call("save_render_preset", name=n); need(call("delete_render_preset", name=n)["ok"])

@test("load_render_preset")
def _(): err("load_render_preset", name="__no_such_preset__")

@test("import_render_preset")
def _(): err("import_render_preset", filePath="/nonexistent/x.xml")

@test("export_render_preset")
def _():
    n = f"__mcp_rp3_{os.getpid()}"
    call("save_render_preset", name=n)
    try:
        call("export_render_preset", name=n, filePath=os.path.join(TMP, "rp.xml"))
    finally:
        call("delete_render_preset", name=n)

@test("get_render_formats")
def _(): need("formats" in call("get_render_formats"))

@test("set_render_format_codec")
def _():
    cur = call("get_render_presets")["currentFormatAndCodec"]
    call("set_render_format_codec", format="mov", codec="H264")  # free-safe combo
    call("set_render_format_codec", format=cur["format"], codec=cur["codec"])

@test("get_render_mode")
def _(): need("renderMode" in call("get_render_mode"))

@test("set_render_mode")
def _():
    m = call("get_render_mode")["renderMode"]
    call("set_render_mode", mode=1 if m == 0 else 0); call("set_render_mode", mode=m)

@test("get_render_resolutions")
def _(): need("resolutions" in call("get_render_resolutions"))

@test("get_quick_export_presets")
def _(): need("presets" in call("get_quick_export_presets"))

@test("quick_export")
def _(): raise Skip("renders to disk; heavy — exercised manually")

@test("add_render_job")
def _():
    goto_scratch()
    jid = call("add_render_job", targetDir=TMP, customName="__mcp_job")["jobId"]
    call("delete_render_job", jobId=jid)

@test("render_current_timeline")
def _(): raise Skip("starts a real render; heavy — exercised manually")

@test("get_render_status")
def _(): need("rendering" in call("get_render_status"))

@test("stop_rendering")
def _(): need(call("stop_rendering")["ok"])

@test("delete_render_job")
def _():
    goto_scratch()
    jid = call("add_render_job", targetDir=TMP, customName="__mcp_job2")["jobId"]
    need(call("delete_render_job", jobId=jid)["ok"])
