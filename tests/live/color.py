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
