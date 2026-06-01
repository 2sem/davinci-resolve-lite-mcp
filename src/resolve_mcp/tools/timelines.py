"""Timelines Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
    "list_timelines",
    "List all timelines in the current project.",
    None,
)
def list_timelines(resolve, args):
    project = _require_project(resolve)
    current = project.GetCurrentTimeline()
    current_name = current.GetName() if current else None
    out = []
    for idx in range(1, project.GetTimelineCount() + 1):
        tl = project.GetTimelineByIndex(idx)
        if tl:
            name = tl.GetName()
            out.append({"index": idx, "name": name, "current": name == current_name})
    return {"timelines": out}


@register(
    "set_current_timeline",
    "Make the timeline at the given 1-based index current.",
    {
        "type": "object",
        "properties": {"index": {"type": "integer", "minimum": 1}},
        "required": ["index"],
    },
)
def set_current_timeline(resolve, args):
    project = _require_project(resolve)
    idx = args["index"]
    tl = project.GetTimelineByIndex(idx)
    if not tl:
        raise ToolError(f"No timeline at index {idx}.")
    if not project.SetCurrentTimeline(tl):
        raise ToolError("SetCurrentTimeline failed.")
    return {"current": tl.GetName()}


@register(
    "get_timeline_info",
    "Return name, frame range, start timecode and per-type track counts for the current timeline.",
    None,
)
def get_timeline_info(resolve, args):
    tl = _require_timeline(resolve)
    return {
        "name": tl.GetName(),
        "startFrame": tl.GetStartFrame(),
        "endFrame": tl.GetEndFrame(),
        "startTimecode": tl.GetStartTimecode(),
        "currentTimecode": tl.GetCurrentTimecode(),
        "tracks": {
            "video": tl.GetTrackCount("video"),
            "audio": tl.GetTrackCount("audio"),
            "subtitle": tl.GetTrackCount("subtitle"),
        },
    }


@register(
    "get_timecode",
    "Get the current playhead timecode of the current timeline.",
    None,
)
def get_timecode(resolve, args):
    tl = _require_timeline(resolve)
    return {"timecode": tl.GetCurrentTimecode()}


@register(
    "set_timecode",
    "Move the playhead to a timecode (format HH:MM:SS:FF).",
    {
        "type": "object",
        "properties": {"timecode": {"type": "string"}},
        "required": ["timecode"],
    },
)
def set_timecode(resolve, args):
    tl = _require_timeline(resolve)
    if not tl.SetCurrentTimecode(args["timecode"]):
        raise ToolError(
            f"SetCurrentTimecode({args['timecode']!r}) failed "
            "(bad format or out of timeline range; use HH:MM:SS:FF)."
        )
    return {"ok": True, "timecode": tl.GetCurrentTimecode()}


@register(
    "add_timeline_marker",
    "Add a marker on the current timeline at a frame offset from the timeline start.",
    {
        "type": "object",
        "properties": {
            "frame": {"type": "integer"},
            "color": {"type": "string", "default": "Blue"},
            "name": {"type": "string", "default": ""},
            "note": {"type": "string", "default": ""},
            "duration": {"type": "integer", "default": 1},
        },
        "required": ["frame"],
    },
)
def add_timeline_marker(resolve, args):
    tl = _require_timeline(resolve)
    ok = tl.AddMarker(
        args["frame"],
        args.get("color", "Blue"),
        args.get("name", ""),
        args.get("note", ""),
        args.get("duration", 1),
        "",
    )
    if not ok:
        raise ToolError("AddMarker failed (a marker may already exist at that frame).")
    return {"ok": True, "frame": args["frame"]}


@register(
    "delete_timeline_marker",
    "Delete timeline marker(s). Give 'frame' to delete the marker at that "
    "frame, or 'color' to delete all markers of that color ('All' = every "
    "marker). Provide exactly one of frame/color.",
    {
        "type": "object",
        "properties": {
            "frame": {"type": "integer"},
            "color": {"type": "string"},
        },
    },
)
def delete_timeline_marker(resolve, args):
    tl = _require_timeline(resolve)
    has_frame = args.get("frame") is not None
    has_color = bool(args.get("color"))
    if has_frame == has_color:
        raise ToolError("Provide exactly one of 'frame' or 'color'.")
    if has_frame:
        ok = tl.DeleteMarkerAtFrame(args["frame"])
        target = {"frame": args["frame"]}
    else:
        ok = tl.DeleteMarkersByColor(args["color"])
        target = {"color": args["color"]}
    if not ok:
        raise ToolError(f"No marker matched {target}.")
    return {"ok": True, **target}


@register(
    "create_timeline",
    "Create a new empty timeline with the given name.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def create_timeline(resolve, args):
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    tl = mp.CreateEmptyTimeline(args["name"])
    if not tl:
        raise ToolError("CreateEmptyTimeline failed (name may not be unique).")
    return {"created": tl.GetName()}


@register(
    "create_timeline_from_clips",
    "Create a new timeline (with a unique name) from media-pool clips (by "
    "name, in the order given, from the current folder).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "names": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "names"],
    },
)
def create_timeline_from_clips(resolve, args):
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    folder = mp.GetCurrentFolder()
    if not folder:
        raise ToolError("No current media pool folder.")
    by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
    if not args["names"]:
        raise ToolError("No clip names supplied.")
    clips, missing = [], []
    for n in args["names"]:
        (clips if n in by_name else missing).append(by_name.get(n, n))
    if missing:
        raise ToolError(f"Clips not found in current folder: {[m for m in missing if isinstance(m, str)]}")
    tl = mp.CreateTimelineFromClips(args["name"], clips)
    if not tl:
        raise ToolError("CreateTimelineFromClips failed (name not unique?).")
    return {"ok": True, "created": tl.GetName(), "clips": len(clips)}


@register(
    "delete_timeline",
    "Delete a timeline by name from the current project.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def delete_timeline(resolve, args):
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    name = args["name"]
    target = None
    for idx in range(1, project.GetTimelineCount() + 1):
        tl = project.GetTimelineByIndex(idx)
        if tl and tl.GetName() == name:
            target = tl
            break
    if not target:
        raise ToolError(f"No timeline named {name!r}.")
    if not mp.DeleteTimelines([target]):
        raise ToolError("DeleteTimelines failed.")
    return {"ok": True, "deleted": name}


@register(
    "export_timeline",
    "Export the current timeline to a file. exportType one of: "
    "AAF, EDL, XML(fcpxml), DRT, OTIO. Provide a full filePath.",
    {
        "type": "object",
        "properties": {
            "filePath": {"type": "string"},
            "exportType": {
                "type": "string",
                "enum": ["AAF", "EDL", "FCPXML", "DRT", "OTIO"],
            },
        },
        "required": ["filePath", "exportType"],
    },
)
def export_timeline(resolve, args):
    tl = _require_timeline(resolve)
    path = os.path.expanduser(args["filePath"])
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {directory!r}: {exc}")
    type_map = {
        "AAF": resolve.EXPORT_AAF,
        "EDL": resolve.EXPORT_EDL,
        "FCPXML": resolve.EXPORT_FCPXML_1_8,
        "DRT": resolve.EXPORT_DRT,
        "OTIO": resolve.EXPORT_OTIO,
    }
    etype = type_map.get(args["exportType"])
    ok = tl.Export(path, etype, resolve.EXPORT_NONE)
    if not ok:
        raise ToolError("Timeline Export failed.")
    return {"ok": True, "filePath": path}


@register(
    "import_timeline",
    "Create a timeline by importing a file (AAF/EDL/XML/FCPXML/DRT/OTIO). "
    "Optional 'timelineName' sets the new timeline's name.",
    {
        "type": "object",
        "properties": {
            "filePath": {"type": "string"},
            "timelineName": {"type": "string"},
        },
        "required": ["filePath"],
    },
)
def import_timeline(resolve, args):
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    path = os.path.expanduser(args["filePath"])
    if not os.path.exists(path):
        raise ToolError(f"File not found: {path}")
    options = {"timelineName": args["timelineName"]} if args.get("timelineName") else {}
    tl = mp.ImportTimelineFromFile(path, options) if options else mp.ImportTimelineFromFile(path)
    if not tl:
        raise ToolError("ImportTimelineFromFile failed.")
    return {"ok": True, "created": tl.GetName()}


@register(
    "duplicate_timeline",
    "Duplicate the current timeline. Optional 'name' for the copy.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
    },
)
def duplicate_timeline(resolve, args):
    tl = _require_timeline(resolve)
    dup = tl.DuplicateTimeline(args["name"]) if args.get("name") else tl.DuplicateTimeline()
    if not dup:
        raise ToolError("DuplicateTimeline failed.")
    return {"ok": True, "created": dup.GetName()}


@register(
    "set_mark_in_out",
    "Set mark in/out on the current timeline, or on a media-pool clip if "
    "'clip' (name) is given. Frames are 0-based (relative to the timeline "
    "start / clip start), not absolute timeline frame numbers. "
    "type = video/audio/all (default all).",
    {"type": "object", "properties": {
        "in": {"type": "integer"}, "out": {"type": "integer"},
        "type": {"type": "string", "enum": ["video", "audio", "all"], "default": "all"},
        "clip": {"type": "string"}},
     "required": ["in", "out"]},
)
def set_mark_in_out(resolve, args):
    target = _pool_clip(resolve, args["clip"]) if args.get("clip") else _require_timeline(resolve)
    if not target.SetMarkInOut(args["in"], args["out"], args.get("type", "all")):
        raise ToolError("SetMarkInOut failed.")
    return {"ok": True, "markInOut": target.GetMarkInOut()}


@register(
    "get_mark_in_out",
    "Get mark in/out of the current timeline, or of a media-pool clip if "
    "'clip' (name) is given.",
    {"type": "object", "properties": {"clip": {"type": "string"}}},
)
def get_mark_in_out(resolve, args):
    target = _pool_clip(resolve, args["clip"]) if args.get("clip") else _require_timeline(resolve)
    return {"markInOut": target.GetMarkInOut()}


@register(
    "clear_mark_in_out",
    "Clear mark in/out on the current timeline, or on a media-pool clip if "
    "'clip' (name) is given. type = video/audio/all (default all).",
    {"type": "object", "properties": {
        "type": {"type": "string", "enum": ["video", "audio", "all"], "default": "all"},
        "clip": {"type": "string"}}},
)
def clear_mark_in_out(resolve, args):
    target = _pool_clip(resolve, args["clip"]) if args.get("clip") else _require_timeline(resolve)
    target.ClearMarkInOut(args.get("type", "all"))
    return {"ok": True}


@register(
    "set_timeline_name",
    "Rename the current timeline.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def set_timeline_name(resolve, args):
    tl = _require_timeline(resolve)
    if not tl.SetName(args["name"]):
        raise ToolError("SetName failed (name not unique?).")
    return {"ok": True, "name": tl.GetName()}


@register(
    "set_timeline_start_timecode",
    "Set the start timecode of the current timeline (HH:MM:SS:FF).",
    {"type": "object", "properties": {"timecode": {"type": "string"}}, "required": ["timecode"]},
)
def set_timeline_start_timecode(resolve, args):
    tl = _require_timeline(resolve)
    if not tl.SetStartTimecode(args["timecode"]):
        raise ToolError(f"SetStartTimecode({args['timecode']!r}) failed.")
    return {"ok": True, "startTimecode": tl.GetStartTimecode()}


@register(
    "import_into_timeline",
    "Import timeline items from an AAF file into the current timeline.",
    {"type": "object", "properties": {"filePath": {"type": "string"}}, "required": ["filePath"]},
)
def import_into_timeline(resolve, args):
    tl = _require_timeline(resolve)
    path = os.path.expanduser(args["filePath"])
    if not os.path.exists(path):
        raise ToolError(f"File not found: {path}")
    if not tl.ImportIntoTimeline(path, {}):
        raise ToolError("ImportIntoTimeline failed.")
    return {"ok": True, "filePath": path}
