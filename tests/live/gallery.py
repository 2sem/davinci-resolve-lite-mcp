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


# ---- gallery ----
@test("grab_still")
def _():
    try:
        color_grab(); call("clear_gallery_stills")
    finally:
        call("open_page", page="edit")

@test("grab_all_stills")
def _():
    goto_scratch(); call("open_page", page="color")
    try:
        call("grab_all_stills", source=1); call("clear_gallery_stills")
    finally:
        call("open_page", page="edit")

@test("get_gallery_stills_count")
def _(): need("count" in call("get_gallery_stills_count"))

@test("list_gallery_stills")
def _(): need("stills" in call("list_gallery_stills"))

@test("set_gallery_still_label")
def _():
    try:
        color_grab()
        call("set_gallery_still_label", index=1, label="__mcp")
    finally:
        call("clear_gallery_stills"); call("open_page", page="edit")

@test("export_gallery_stills")
def _():
    try:
        color_grab()
        call("export_gallery_stills", folderPath=os.path.join(TMP, "stills"), format="jpg")
    except AssertionError as e:
        skip_if(e, "Still", STILL_FLAKE)
    finally:
        call("clear_gallery_stills"); call("open_page", page="edit")

@test("import_gallery_stills")
def _(): err("import_gallery_stills", paths=["/nonexistent/x.dpx"])

@test("delete_gallery_stills")
def _():
    try:
        color_grab(); need(call("delete_gallery_stills", indices=[1])["ok"])
    finally:
        call("clear_gallery_stills"); call("open_page", page="edit")

@test("clear_gallery_stills")
def _(): need(call("clear_gallery_stills")["ok"])

@test("apply_grade_from_drx")
def _():
    try:
        color_grab()
        call("export_gallery_stills", folderPath=os.path.join(TMP, "drx"), format="drx")
        drx = [f for f in os.listdir(os.path.join(TMP, "drx")) if f.endswith(".drx")]
        if not drx:
            raise Skip("no .drx exported")
        call("apply_grade_from_drx", VID1 | {"drxPath": os.path.join(TMP, "drx", drx[0])})
    except AssertionError as e:
        skip_if(e, "Still", STILL_FLAKE)
    finally:
        call("clear_gallery_stills"); call("open_page", page="edit")

@test("list_gallery_albums")
def _(): need("albums" in call("list_gallery_albums"))

@test("create_gallery_album")
def _(): need(call("create_gallery_album", name="__mcp_alb")["ok"])  # albums can't be deleted via API

@test("set_current_gallery_album")
def _():
    a = call("list_gallery_albums")["albums"][0]
    need(call("set_current_gallery_album", name=a)["ok"])

@test("list_powergrade_albums")
def _(): need("albums" in call("list_powergrade_albums"))

@test("create_powergrade_album")
def _(): need(call("create_powergrade_album", name="__mcp_pg")["ok"])  # not deletable via API
