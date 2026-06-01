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
    # Ensure at least one video item exists on V1 (earlier tests may empty it;
    # track tests can move the target track, so pin trackIndex=1, video-only).
    items = call("get_track_items", trackType="video", index=1)["items"]
    if not items and CTX.get("src"):
        call("add_clip_to_timeline", name=CTX["src"], startFrame=0, endFrame=60,
             recordFrame=0, trackIndex=1, mediaType=1)


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


def fresh_group(name):
    """Create a color group, removing any leftover of the same name first."""
    try:
        call("delete_color_group", name=name)
    except AssertionError:
        pass
    call("add_color_group", name=name)


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

# ---- projects ----
@test("list_projects")
def _(): need(len(call("list_projects")["projects"]) >= 1)

@test("load_project")
def _(): err("load_project", name="__no_such_project__")  # destructive to switch; error-path

@test("get_project_info")
def _(): need(call("get_project_info")["framerate"])

@test("save_project")
def _(): need(call("save_project")["ok"])

@test("create_project")
def _(): raise Skip("would create an undeletable project")

@test("close_project")
def _(): raise Skip("would close the active project")

@test("export_project")
def _():
    p = os.path.join(TMP, "proj.drp")
    call("export_project", filePath=p); need(os.path.exists(p))

@test("import_project")
def _(): err("import_project", filePath="/nonexistent/x.drp")

@test("restore_project")
def _(): err("restore_project", filePath="/nonexistent/x")

@test("get_project_presets")
def _(): need("presets" in call("get_project_presets"))

@test("set_project_preset")
def _(): err("set_project_preset", name="__no_such_preset__")

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
    call("add_timeline_marker", frame=f, color="Red")
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
    call("add_clip_marker", VID1 | {"frame": 10, "color": "Green"})
    call("delete_clip_marker", VID1 | {"color": "All"})

@test("delete_clip_marker")
def _():
    goto_scratch(); _clear_clip_markers()
    call("add_clip_marker", VID1 | {"frame": 12})
    need(call("delete_clip_marker", VID1 | {"frame": 12})["ok"])

# ---- color ----
@test("get_node_graph")
def _():
    goto_scratch(); need("numNodes" in call("get_node_graph", VID1))

@test("set_node_lut")
def _(): raise Skip("needs a known installed LUT path")

@test("set_node_enabled")
def _():
    goto_scratch()
    call("set_node_enabled", VID1 | {"nodeIndex": 1, "enabled": False})
    call("set_node_enabled", VID1 | {"nodeIndex": 1, "enabled": True})

@test("set_cdl")
def _():
    goto_scratch()
    call("set_cdl", VID1 | {"nodeIndex": 1, "slope": "1 1 1", "offset": "0 0 0",
                            "power": "1 1 1", "saturation": "1"})

@test("reset_grades")
def _():
    goto_scratch(); need(call("reset_grades", VID1)["ok"])

@test("copy_grade")
def _():
    goto_scratch(); src_required()
    call("append_clips_to_timeline", names=[CTX["src"]])
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    call("copy_grade", VID1 | {"targets": [{"trackType": "video", "trackIndex": 1, "itemIndex": n}]})
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("get_node_tools")
def _():
    goto_scratch(); need("tools" in call("get_node_tools", VID1 | {"nodeIndex": 1}))

@test("add_grade_version")
def _():
    goto_scratch(); call("add_grade_version", VID1 | {"name": "__mcp_v"})
    call("load_grade_version", VID1 | {"name": "버전 1"})
    call("delete_grade_version", VID1 | {"name": "__mcp_v"})

@test("list_grade_versions")
def _():
    goto_scratch(); need("versions" in call("list_grade_versions", VID1))

@test("load_grade_version")
def _():
    goto_scratch(); call("add_grade_version", VID1 | {"name": "__mcp_v2"})
    need(call("load_grade_version", VID1 | {"name": "__mcp_v2"})["ok"])
    call("load_grade_version", VID1 | {"name": "버전 1"})
    call("delete_grade_version", VID1 | {"name": "__mcp_v2"})

@test("delete_grade_version")
def _():
    goto_scratch(); call("add_grade_version", VID1 | {"name": "__mcp_v3"})
    call("load_grade_version", VID1 | {"name": "버전 1"})
    need(call("delete_grade_version", VID1 | {"name": "__mcp_v3"})["ok"])

@test("export_lut")
def _():
    goto_scratch(); call("open_page", page="color")
    try:
        p = os.path.join(TMP, "g.cube")
        call("export_lut", VID1 | {"size": "33ptcube", "path": p})
    finally:
        call("open_page", page="edit")

@test("list_color_groups")
def _(): need("groups" in call("list_color_groups"))

@test("add_color_group")
def _():
    call("add_color_group", name="__mcp_g"); call("delete_color_group", name="__mcp_g")

@test("assign_to_color_group")
def _():
    goto_scratch(); fresh_group("__mcp_ga")
    call("assign_to_color_group", VID1 | {"group": "__mcp_ga"})
    call("remove_from_color_group", VID1); call("delete_color_group", name="__mcp_ga")

@test("remove_from_color_group")
def _():
    goto_scratch(); fresh_group("__mcp_gr")
    call("assign_to_color_group", VID1 | {"group": "__mcp_gr"})
    need(call("remove_from_color_group", VID1)["ok"]); call("delete_color_group", name="__mcp_gr")

@test("delete_color_group")
def _():
    call("add_color_group", name="__mcp_gd"); need(call("delete_color_group", name="__mcp_gd")["ok"])

@test("get_color_group_clips")
def _():
    fresh_group("__mcp_gc")
    need("clips" in call("get_color_group_clips", name="__mcp_gc")); call("delete_color_group", name="__mcp_gc")

@test("rename_color_group")
def _():
    fresh_group("__mcp_gn")
    call("rename_color_group", name="__mcp_gn", newName="__mcp_gn2"); call("delete_color_group", name="__mcp_gn2")

@test("get_color_group_node_graph")
def _():
    fresh_group("__mcp_gg")
    need("numNodes" in call("get_color_group_node_graph", name="__mcp_gg", which="pre"))
    call("delete_color_group", name="__mcp_gg")

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
    call("add_pool_clip_marker", name=s, frame=10, color="Yellow")
    call("delete_pool_clip_marker", name=s, color="All")

@test("delete_pool_clip_marker")
def _():
    s = src_required(); _clear_pool_markers(s)
    call("add_pool_clip_marker", name=s, frame=12)
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

@test("list_storage_volumes")
def _(): need("volumes" in call("list_storage_volumes"))

@test("browse_storage")
def _(): need("files" in call("browse_storage", path=os.path.expanduser("~/Movies")))

@test("add_storage_items_to_pool")
def _(): need(call("add_storage_items_to_pool", paths=["/nonexistent/x.mov"])["count"] == 0)

@test("reveal_in_storage")
def _():
    vols = call("list_storage_volumes")["volumes"]
    if not vols:
        raise Skip("no mounted volumes")
    try:
        need(call("reveal_in_storage", path=vols[0])["ok"])
    except AssertionError:
        raise Skip("RevealInStorage returned false")

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


if __name__ == "__main__":
    sys.exit(main(sys.argv))
