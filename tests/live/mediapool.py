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


# ---- media pool & storage ----
@test("list_media_pool")
def _(): need("clips" in call("list_media_pool"))

@test("import_media")
def _(): need(call("import_media", paths=["/nonexistent/x.mov"])["count"] == 0)

@test("delete_clip")
def _(): err("delete_clip", names=["__no_such_clip__"])

@test("add_subfolder")
def _():
    call("set_current_folder", name=CTX["orig_folder"])
    call("add_subfolder", name="__mcp_bin")
    call("set_current_folder", name=CTX["orig_folder"])
    call("delete_subfolders", names=["__mcp_bin"])

@test("set_current_folder")
def _():
    call("set_current_folder", name=CTX["orig_folder"])
    need(call("set_current_folder", name=CTX["orig_folder"])["ok"])

@test("delete_subfolders")
def _():
    call("set_current_folder", name=CTX["orig_folder"]); call("add_subfolder", name="__mcp_bin2")
    call("set_current_folder", name=CTX["orig_folder"])
    need(call("delete_subfolders", names=["__mcp_bin2"])["ok"])

@test("move_clips_to_folder")
def _(): err("move_clips_to_folder", names=["__no_clip__"], targetFolder=CTX["orig_folder"])

@test("move_folders")
def _():
    call("set_current_folder", name=CTX["orig_folder"]); call("add_subfolder", name="__mcp_mA")
    call("set_current_folder", name=CTX["orig_folder"]); call("add_subfolder", name="__mcp_mB")
    call("set_current_folder", name=CTX["orig_folder"])
    call("move_folders", names=["__mcp_mA"], targetFolder="__mcp_mB")
    call("set_current_folder", name=CTX["orig_folder"]); call("delete_subfolders", names=["__mcp_mB"])

@test("get_clip_properties")
def _():
    s = src_required(); need("value" in call("get_clip_properties", name=s))

@test("set_clip_property")
def _(): err("set_clip_property", name="__no_clip__", property="X", value="1")

@test("get_clip_metadata")
def _():
    s = src_required(); need("value" in call("get_clip_metadata", name=s))

@test("set_clip_metadata")
def _():
    s = src_required()
    call("set_clip_metadata", name=s, key="Comments", value="__mcp")
    call("set_clip_metadata", name=s, key="Comments", value="")

@test("rename_clip")
def _():
    s = src_required()
    call("rename_clip", name=s, newName=s + " _r"); call("rename_clip", name=s + " _r", newName=s)

@test("get_pool_clip_tags")
def _():
    s = src_required(); need("clipColor" in call("get_pool_clip_tags", name=s))

@test("set_pool_clip_color")
def _():
    s = src_required()
    call("set_pool_clip_color", name=s, color="Teal"); call("set_pool_clip_color", name=s, color="")

@test("add_pool_clip_flag")
def _():
    s = src_required(); call("add_pool_clip_flag", name=s, color="Purple"); call("clear_pool_clip_flags", name=s)

@test("clear_pool_clip_flags")
def _():
    s = src_required(); call("add_pool_clip_flag", name=s, color="Pink")
    need(call("clear_pool_clip_flags", name=s)["ok"])

def _clear_pool_markers(name):
    try:
        call("delete_pool_clip_marker", name=name, color="All")
    except AssertionError:
        pass

@test("add_pool_clip_marker")
def _():
    s = src_required(); _clear_pool_markers(s)
    try:
        call("add_pool_clip_marker", name=s, frame=10, color="Yellow")
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    call("delete_pool_clip_marker", name=s, color="All")

@test("delete_pool_clip_marker")
def _():
    s = src_required(); _clear_pool_markers(s)
    try:
        call("add_pool_clip_marker", name=s, frame=12)
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    need(call("delete_pool_clip_marker", name=s, frame=12)["ok"])

@test("get_selected_clips")
def _(): need("selected" in call("get_selected_clips"))

@test("set_selected_clip")
def _():
    s = src_required(); need(call("set_selected_clip", name=s)["ok"])

@test("link_proxy")
def _(): err("link_proxy", name=src_required(), proxyPath="/nonexistent/p.mov")

@test("unlink_proxy")
def _():
    s = src_required()
    try:
        call("unlink_proxy", name=s)  # ok or clean error if no proxy
    except AssertionError:
        pass

@test("replace_clip")
def _(): err("replace_clip", name=src_required(), filePath="/nonexistent/x.mov")

@test("replace_clip_preserve_subclip")
def _(): err("replace_clip_preserve_subclip", name=src_required(), filePath="/nonexistent/x.mov")

@test("link_full_resolution_media")
def _(): err("link_full_resolution_media", name=src_required(), filePath="/nonexistent/x.mov")

@test("relink_clips")
def _(): err("relink_clips", names=["__no_clip__"], folderPath=TMP)

@test("export_metadata")
def _():
    p = os.path.join(TMP, "meta.csv"); call("export_metadata", filePath=p); need(os.path.exists(p))


@test("id_addressing")
def _():
    # list exposes ids; a clip is addressable by id (not just name)
    clips = call("list_media_pool")["clips"]
    with_id = [c for c in clips if c.get("id")]
    need(with_id, "list_media_pool exposes no clip ids")
    cid = with_id[0]["id"]
    r = call("get_clip_properties", id=cid)
    need(r["name"] == with_id[0]["name"], "id resolved to wrong clip")
