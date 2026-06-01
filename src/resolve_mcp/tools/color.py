"""Color Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
    "get_node_graph",
    "Inspect the color node graph of a timeline clip (by trackType + "
    "trackIndex + itemIndex). Returns node count and per-node label + LUT.",
    {
        "type": "object",
        "properties": dict(_ITEM_ADDR),
        "required": ["trackType", "trackIndex", "itemIndex"],
    },
)
def get_node_graph(resolve, args):
    item, graph = _node_graph(resolve, args)
    n = graph.GetNumNodes()
    nodes = []
    for i in range(1, (n or 0) + 1):
        nodes.append({"index": i, "label": graph.GetNodeLabel(i), "lut": graph.GetLUT(i)})
    return {"item": item.GetName(), "numNodes": n, "nodes": nodes}


@register(
    "set_node_lut",
    "Apply a LUT to a color node (1-based nodeIndex) of a timeline clip. "
    "'lutPath' is relative to the LUT folder or an absolute path.",
    {
        "type": "object",
        "properties": {
            **_ITEM_ADDR,
            "nodeIndex": {"type": "integer", "minimum": 1},
            "lutPath": {"type": "string"},
        },
        "required": ["trackType", "trackIndex", "itemIndex", "nodeIndex", "lutPath"],
    },
)
def set_node_lut(resolve, args):
    item, graph = _node_graph(resolve, args)
    if not graph.SetLUT(args["nodeIndex"], args["lutPath"]):
        raise ToolError(f"SetLUT(node {args['nodeIndex']}, {args['lutPath']!r}) failed.")
    return {"ok": True, "item": item.GetName(), "nodeIndex": args["nodeIndex"]}


@register(
    "set_node_enabled",
    "Enable or disable a color node (1-based nodeIndex) of a timeline clip.",
    {
        "type": "object",
        "properties": {
            **_ITEM_ADDR,
            "nodeIndex": {"type": "integer", "minimum": 1},
            "enabled": {"type": "boolean"},
        },
        "required": ["trackType", "trackIndex", "itemIndex", "nodeIndex", "enabled"],
    },
)
def set_node_enabled(resolve, args):
    item, graph = _node_graph(resolve, args)
    enabled = bool(args["enabled"])
    if not graph.SetNodeEnabled(args["nodeIndex"], enabled):
        raise ToolError(f"SetNodeEnabled(node {args['nodeIndex']}, {enabled}) failed.")
    return {"ok": True, "item": item.GetName(), "nodeIndex": args["nodeIndex"], "enabled": enabled}


@register(
    "reset_grades",
    "Reset all grades on every node of a timeline clip's node graph.",
    {
        "type": "object",
        "properties": dict(_ITEM_ADDR),
        "required": ["trackType", "trackIndex", "itemIndex"],
    },
)
def reset_grades(resolve, args):
    item, graph = _node_graph(resolve, args)
    if not graph.ResetAllGrades():
        raise ToolError("ResetAllGrades failed.")
    return {"ok": True, "item": item.GetName()}


@register(
    "apply_grade_from_drx",
    "Apply a saved .drx PowerGrade (still) to a timeline clip's node graph. "
    "gradeMode: 0 = no keyframes (default), 1 = source-timecode aligned, "
    "2 = start-frames aligned.",
    {
        "type": "object",
        "properties": {
            **_ITEM_ADDR,
            "drxPath": {"type": "string"},
            "gradeMode": {"type": "integer", "enum": [0, 1, 2], "default": 0},
        },
        "required": ["trackType", "trackIndex", "itemIndex", "drxPath"],
    },
)
def apply_grade_from_drx(resolve, args):
    item, graph = _node_graph(resolve, args)
    path = os.path.expanduser(args["drxPath"])
    if not os.path.exists(path):
        raise ToolError(f"File not found: {path}")
    if not graph.ApplyGradeFromDRX(path, args.get("gradeMode", 0)):
        raise ToolError("ApplyGradeFromDRX failed.")
    return {"ok": True, "item": item.GetName(), "drxPath": path}


@register(
    "get_node_tools",
    "List the tools/operators used in a node (1-based nodeIndex) of a "
    "timeline clip's node graph.",
    {
        "type": "object",
        "properties": {**_ITEM_ADDR, "nodeIndex": {"type": "integer", "minimum": 1}},
        "required": ["trackType", "trackIndex", "itemIndex", "nodeIndex"],
    },
)
def get_node_tools(resolve, args):
    item, graph = _node_graph(resolve, args)
    return {
        "item": item.GetName(),
        "nodeIndex": args["nodeIndex"],
        "tools": graph.GetToolsInNode(args["nodeIndex"]) or [],
    }


@register(
    "grab_still",
    "Grab a still from the current clip into the gallery (Color page). "
    "Switch to the Color page first for reliable results.",
    None,
)
def grab_still(resolve, args):
    tl = _require_timeline(resolve)
    still = tl.GrabStill()
    if not still:
        raise ToolError("GrabStill failed (open the Color page and select a clip).")
    return {"ok": True}


@register(
    "export_current_frame_as_still",
    "Export the current frame of the current timeline to an image file path. "
    "The path must end with a valid image extension (e.g. .jpg, .png, .tif).",
    {
        "type": "object",
        "properties": {"filePath": {"type": "string"}},
        "required": ["filePath"],
    },
)
def export_current_frame_as_still(resolve, args):
    project = _require_project(resolve)
    timeline = _require_timeline(resolve)
    path = os.path.expanduser(args["filePath"])
    # Mirror the reference flow (08_export_current_frame): ensure the output
    # directory exists, capture the timecode, then export.
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {directory!r}: {exc}")
    timecode = None
    try:
        timecode = timeline.GetCurrentTimecode()
    except Exception:  # noqa: BLE001
        pass
    ok = project.ExportCurrentFrameAsStill(path)
    if not ok:
        raise ToolError(
            f"ExportCurrentFrameAsStill failed for {path!r}. "
            "Check the path ends with a valid image extension (.jpg/.png/.tif)."
        )
    return {"ok": True, "filePath": path, "timecode": timecode}


@register(
    "set_cdl",
    "Apply an ASC CDL to a node of a timeline clip. slope/offset/power are "
    "'R G B' strings; saturation is a single value. nodeIndex is 1-based.",
    {"type": "object", "properties": {
        **_ITEM_ADDR,
        "nodeIndex": {"type": "integer", "minimum": 1, "default": 1},
        "slope": {"type": "string"}, "offset": {"type": "string"},
        "power": {"type": "string"}, "saturation": {"type": "string"}},
     "required": ["trackType", "trackIndex", "itemIndex"]},
)
def set_cdl(resolve, args):
    item = _track_item(resolve, args)
    cdl = {"NodeIndex": str(args.get("nodeIndex", 1))}
    for key, arg in (("Slope", "slope"), ("Offset", "offset"),
                     ("Power", "power"), ("Saturation", "saturation")):
        if args.get(arg) is not None:
            cdl[key] = str(args[arg])
    if not item.SetCDL(cdl):
        raise ToolError("SetCDL failed.")
    return {"ok": True, "item": item.GetName(), "cdl": cdl}


@register(
    "list_grade_versions",
    "List color versions of a timeline clip. versionType 0=local (default), "
    "1=remote.",
    {"type": "object", "properties": {**_ITEM_ADDR, "versionType": {"type": "integer", "enum": [0, 1], "default": 0}},
     "required": ["trackType", "trackIndex", "itemIndex"]},
)
def list_grade_versions(resolve, args):
    item = _track_item(resolve, args)
    vt = args.get("versionType", 0)
    return {
        "item": item.GetName(),
        "versions": item.GetVersionNameList(vt) or [],
        "current": item.GetCurrentVersion(),
    }


@register(
    "add_grade_version",
    "Add a color version to a timeline clip. versionType 0=local, 1=remote.",
    {"type": "object", "properties": {
        **_ITEM_ADDR, "name": {"type": "string"},
        "versionType": {"type": "integer", "enum": [0, 1], "default": 0}},
     "required": ["trackType", "trackIndex", "itemIndex", "name"]},
)
def add_grade_version(resolve, args):
    item = _track_item(resolve, args)
    if not item.AddVersion(args["name"], args.get("versionType", 0)):
        raise ToolError("AddVersion failed (name may exist).")
    return {"ok": True, "item": item.GetName(), "version": args["name"]}


@register(
    "load_grade_version",
    "Load a named color version on a timeline clip. versionType 0=local, "
    "1=remote.",
    {"type": "object", "properties": {
        **_ITEM_ADDR, "name": {"type": "string"},
        "versionType": {"type": "integer", "enum": [0, 1], "default": 0}},
     "required": ["trackType", "trackIndex", "itemIndex", "name"]},
)
def load_grade_version(resolve, args):
    item = _track_item(resolve, args)
    if not item.LoadVersionByName(args["name"], args.get("versionType", 0)):
        raise ToolError("LoadVersionByName failed.")
    return {"ok": True, "item": item.GetName(), "version": args["name"]}


@register(
    "delete_grade_version",
    "Delete a named color version of a timeline clip. versionType 0=local, "
    "1=remote.",
    {"type": "object", "properties": {
        **_ITEM_ADDR, "name": {"type": "string"},
        "versionType": {"type": "integer", "enum": [0, 1], "default": 0}},
     "required": ["trackType", "trackIndex", "itemIndex", "name"]},
)
def delete_grade_version(resolve, args):
    item = _track_item(resolve, args)
    if not item.DeleteVersionByName(args["name"], args.get("versionType", 0)):
        raise ToolError("DeleteVersionByName failed.")
    return {"ok": True, "item": item.GetName(), "deleted": args["name"]}


@register(
    "copy_grade",
    "Copy the grade from a source timeline clip to one or more target clips. "
    "Targets is a list of {trackType, trackIndex, itemIndex}.",
    {"type": "object", "properties": {
        **_ITEM_ADDR,
        "targets": {"type": "array", "items": {
            "type": "object",
            "properties": dict(_ITEM_ADDR),
            "required": ["trackType", "trackIndex", "itemIndex"]}}},
     "required": ["trackType", "trackIndex", "itemIndex", "targets"]},
)
def copy_grade(resolve, args):
    src = _track_item(resolve, args)
    tgts = [_track_item(resolve, t) for t in args["targets"]]
    if not src.CopyGrades(tgts):
        raise ToolError("CopyGrades failed.")
    return {"ok": True, "source": src.GetName(), "targets": len(tgts)}


@register(
    "list_color_groups",
    "List color groups in the current project.",
    None,
)
def list_color_groups(resolve, args):
    project = _require_project(resolve)
    return {"groups": [g.GetName() for g in (project.GetColorGroupsList() or [])]}


@register(
    "add_color_group",
    "Create a color group with a unique name.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def add_color_group(resolve, args):
    project = _require_project(resolve)
    group = project.AddColorGroup(args["name"])
    if not group:
        raise ToolError("AddColorGroup failed (name not unique?).")
    return {"ok": True, "created": group.GetName()}


@register(
    "delete_color_group",
    "Delete a color group by name.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def delete_color_group(resolve, args):
    project = _require_project(resolve)
    group = _color_group(project, args["name"])
    if not project.DeleteColorGroup(group):
        raise ToolError("DeleteColorGroup failed.")
    return {"ok": True, "deleted": args["name"]}


@register(
    "assign_to_color_group",
    "Assign a timeline clip to a color group (by group name).",
    {"type": "object", "properties": {**_ITEM_ADDR, "group": {"type": "string"}},
     "required": ["trackType", "trackIndex", "itemIndex", "group"]},
)
def assign_to_color_group(resolve, args):
    project = _require_project(resolve)
    item = _track_item(resolve, args)
    group = _color_group(project, args["group"])
    if not item.AssignToColorGroup(group):
        raise ToolError("AssignToColorGroup failed.")
    return {"ok": True, "item": item.GetName(), "group": args["group"]}


@register(
    "remove_from_color_group",
    "Remove a timeline clip from its color group.",
    {"type": "object", "properties": dict(_ITEM_ADDR),
     "required": ["trackType", "trackIndex", "itemIndex"]},
)
def remove_from_color_group(resolve, args):
    item = _track_item(resolve, args)
    if not item.RemoveFromColorGroup():
        raise ToolError("RemoveFromColorGroup failed (clip not in a group?).")
    return {"ok": True, "item": item.GetName()}


@register(
    "get_color_group_clips",
    "List the timeline clips that belong to a color group (by group name).",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def get_color_group_clips(resolve, args):
    project = _require_project(resolve)
    group = _color_group(project, args["name"])
    items = group.GetClipsInTimeline() or []
    return {"group": args["name"], "clips": [i.GetName() for i in items]}


@register(
    "rename_color_group",
    "Rename a color group.",
    {"type": "object", "properties": {"name": {"type": "string"}, "newName": {"type": "string"}},
     "required": ["name", "newName"]},
)
def rename_color_group(resolve, args):
    project = _require_project(resolve)
    group = _color_group(project, args["name"])
    if not group.SetName(args["newName"]):
        raise ToolError("SetName failed.")
    return {"ok": True, "name": args["newName"]}


@register(
    "get_color_group_node_graph",
    "Inspect a color group's shared grade graph. which = 'pre' (pre-clip) or "
    "'post' (post-clip). Returns node count + per-node label/LUT.",
    {"type": "object", "properties": {
        "name": {"type": "string"},
        "which": {"type": "string", "enum": ["pre", "post"], "default": "pre"}},
     "required": ["name"]},
)
def get_color_group_node_graph(resolve, args):
    project = _require_project(resolve)
    group = _color_group(project, args["name"])
    graph = group.GetPreClipNodeGraph() if args.get("which", "pre") == "pre" else group.GetPostClipNodeGraph()
    if graph is None:
        raise ToolError("Group node graph unavailable.")
    n = graph.GetNumNodes()
    nodes = [{"index": i, "label": graph.GetNodeLabel(i), "lut": graph.GetLUT(i)}
             for i in range(1, (n or 0) + 1)]
    return {"group": args["name"], "which": args.get("which", "pre"), "numNodes": n, "nodes": nodes}


@register(
    "export_lut",
    "Export a LUT from a timeline clip's grade. Requires the Color page to "
    "be open (open_page 'color' first). size = "
    "17ptcube/33ptcube/65ptcube/panasonic (default 33ptcube). 'path' should "
    "include the file name.",
    {"type": "object", "properties": {
        **_ITEM_ADDR,
        "size": {"type": "string", "enum": ["17ptcube", "33ptcube", "65ptcube", "panasonic"], "default": "33ptcube"},
        "path": {"type": "string"}},
     "required": ["trackType", "trackIndex", "itemIndex", "path"]},
)
def export_lut(resolve, args):
    item = _track_item(resolve, args)
    size_map = {
        "17ptcube": resolve.EXPORT_LUT_17PTCUBE,
        "33ptcube": resolve.EXPORT_LUT_33PTCUBE,
        "65ptcube": resolve.EXPORT_LUT_65PTCUBE,
        "panasonic": resolve.EXPORT_LUT_PANASONICVLUT,
    }
    path = os.path.expanduser(args["path"])
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {directory!r}: {exc}")
    if not item.ExportLUT(size_map[args.get("size", "33ptcube")], path):
        raise ToolError("ExportLUT failed.")
    return {"ok": True, "item": item.GetName(), "path": path}


@register(
    "refresh_lut_list",
    "Refresh Resolve's LUT list (run after adding LUT files on disk).",
    None,
)
def refresh_lut_list(resolve, args):
    project = _require_project(resolve)
    if not project.RefreshLUTList():
        raise ToolError("RefreshLUTList failed.")
    return {"ok": True}
