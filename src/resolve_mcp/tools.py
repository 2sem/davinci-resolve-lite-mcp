"""Tool definitions: each wraps a slice of the Resolve API.

A tool handler has signature ``handler(resolve, args) -> dict``. ToolError is
raised for user-facing failures (returned to the client as an isError result).
"""

import os


class ToolError(Exception):
    """Raised by tools for user-facing failures."""


def _require_project(resolve):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    if not project:
        raise ToolError("No project is open in DaVinci Resolve.")
    return project


def _require_timeline(resolve):
    project = _require_project(resolve)
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise ToolError("No timeline is open in the current project.")
    return timeline


def _track_item(resolve, args):
    """Resolve a TimelineItem by trackType + 1-based trackIndex + 1-based itemIndex."""
    tl = _require_timeline(resolve)
    ttype = args["trackType"]
    tidx = args["trackIndex"]
    iidx = args["itemIndex"]
    items = tl.GetItemListInTrack(ttype, tidx) or []
    if iidx < 1 or iidx > len(items):
        raise ToolError(
            f"No item #{iidx} on {ttype}{tidx} (track has {len(items)} item(s))."
        )
    return items[iidx - 1]


def _pool_clip(resolve, name):
    """Find a MediaPoolItem by name in the current media pool folder."""
    project = _require_project(resolve)
    folder = project.GetMediaPool().GetCurrentFolder()
    if not folder:
        raise ToolError("No current media pool folder.")
    for clip in folder.GetClipList() or []:
        if clip.GetName() == name:
            return clip
    raise ToolError(f"Clip {name!r} not found in current folder.")


def _find_folder(mp, name):
    """Find a media-pool Folder by name, searching the whole tree from root."""
    root = mp.GetRootFolder()
    stack = [root] if root else []
    while stack:
        folder = stack.pop()
        if folder.GetName() == name:
            return folder
        stack.extend(folder.GetSubFolderList() or [])
    raise ToolError(f"Media pool folder {name!r} not found.")


def _require_gallery(resolve):
    gallery = _require_project(resolve).GetGallery()
    if not gallery:
        raise ToolError("Gallery is unavailable.")
    return gallery


def _track_items_by_index(resolve, track_type, track_index, item_indices):
    """Return TimelineItems for 1-based item_indices on a track."""
    tl = _require_timeline(resolve)
    items = tl.GetItemListInTrack(track_type, track_index) or []
    chosen = []
    for idx in item_indices:
        if idx < 1 or idx > len(items):
            raise ToolError(
                f"No item #{idx} on {track_type}{track_index} ({len(items)} item(s))."
            )
        chosen.append(items[idx - 1])
    return tl, chosen


VALID_PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")


# Each entry: name -> {description, inputSchema, handler(resolve, args) -> dict}
def _build_tools():
    tools = {}

    def tool(name, description, schema):
        def register(fn):
            tools[name] = {
                "description": description,
                "inputSchema": schema or {"type": "object", "properties": {}},
                "handler": fn,
            }
            return fn

        return register

    @tool(
        "get_status",
        "Return Resolve product/version and the current project, timeline and page.",
        None,
    )
    def get_status(resolve, args):
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None
        timeline = project.GetCurrentTimeline() if project else None
        return {
            "product": resolve.GetProductName(),
            "version": resolve.GetVersionString(),
            "currentPage": resolve.GetCurrentPage(),
            "project": project.GetName() if project else None,
            "timeline": timeline.GetName() if timeline else None,
        }

    @tool(
        "open_page",
        "Switch the Resolve UI to a page.",
        {
            "type": "object",
            "properties": {
                "page": {"type": "string", "enum": list(VALID_PAGES)},
            },
            "required": ["page"],
        },
    )
    def open_page(resolve, args):
        page = args.get("page")
        if page not in VALID_PAGES:
            raise ToolError(f"page must be one of {VALID_PAGES}")
        if not resolve.OpenPage(page):
            raise ToolError(f"OpenPage({page!r}) failed.")
        return {"ok": True, "page": page}

    @tool(
        "list_projects",
        "List project names in the current database folder.",
        None,
    )
    def list_projects(resolve, args):
        pm = resolve.GetProjectManager()
        if not pm:
            raise ToolError("Project manager unavailable.")
        return {"projects": pm.GetProjectListInCurrentFolder()}

    @tool(
        "load_project",
        "Load a project by name from the current database folder.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def load_project(resolve, args):
        pm = resolve.GetProjectManager()
        project = pm.LoadProject(args["name"]) if pm else None
        if not project:
            raise ToolError(f"Could not load project {args['name']!r}.")
        return {"loaded": project.GetName()}

    @tool(
        "get_project_info",
        "Return name, framerate, resolution and timeline count for the current project.",
        None,
    )
    def get_project_info(resolve, args):
        project = _require_project(resolve)
        return {
            "name": project.GetName(),
            "framerate": project.GetSetting("timelineFrameRate"),
            "resolutionWidth": project.GetSetting("timelineResolutionWidth"),
            "resolutionHeight": project.GetSetting("timelineResolutionHeight"),
            "timelineCount": project.GetTimelineCount(),
        }

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
        "get_track_items",
        "List clips on a track. trackType one of video/audio/subtitle, 1-based index.",
        {
            "type": "object",
            "properties": {
                "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
                "index": {"type": "integer", "minimum": 1},
            },
            "required": ["trackType", "index"],
        },
    )
    def get_track_items(resolve, args):
        tl = _require_timeline(resolve)
        ttype = args["trackType"]
        idx = args["index"]
        items = tl.GetItemListInTrack(ttype, idx) or []
        out = []
        for it in items:
            out.append(
                {
                    "name": it.GetName(),
                    "start": it.GetStart(),
                    "end": it.GetEnd(),
                    "duration": it.GetDuration(),
                }
            )
        return {"track": f"{ttype}{idx}", "items": out}

    _ITEM_ADDR = {
        "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
        "trackIndex": {"type": "integer", "minimum": 1},
        "itemIndex": {"type": "integer", "minimum": 1, "description": "1-based position on the track"},
    }

    @tool(
        "get_timeline_item_property",
        "Read transform/crop/composite properties of a timeline clip. Address it "
        "by trackType + trackIndex + itemIndex (1-based position on the track). "
        "Omit 'property' to return all properties as a dict. Common properties: "
        "Pan, Tilt, ZoomX, ZoomY, RotationAngle, AnchorPointX/Y, "
        "CropLeft/Right/Top/Bottom, CropSoftness, Opacity, FlipX, FlipY, "
        "CompositeMode, Distortion.",
        {
            "type": "object",
            "properties": {**_ITEM_ADDR, "property": {"type": "string"}},
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def get_timeline_item_property(resolve, args):
        item = _track_item(resolve, args)
        prop = args.get("property")
        value = item.GetProperty(prop) if prop else item.GetProperty()
        return {
            "item": item.GetName(),
            "property": prop,
            "value": value,
        }

    @tool(
        "get_timeline_item_timing",
        "Return timing/placement of a timeline clip: timeline start/end/duration, "
        "left/right offsets (trim headroom), source in/out frames, the clip's "
        "track type+index, and any linked items. Address by trackType + "
        "trackIndex + itemIndex (1-based).",
        {
            "type": "object",
            "properties": dict(_ITEM_ADDR),
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def get_timeline_item_timing(resolve, args):
        item = _track_item(resolve, args)
        track = item.GetTrackTypeAndIndex() or []
        return {
            "item": item.GetName(),
            "start": item.GetStart(),
            "end": item.GetEnd(),
            "duration": item.GetDuration(),
            "leftOffset": item.GetLeftOffset(),
            "rightOffset": item.GetRightOffset(),
            "sourceStartFrame": item.GetSourceStartFrame(),
            "sourceEndFrame": item.GetSourceEndFrame(),
            "trackType": track[0] if len(track) > 0 else None,
            "trackIndex": track[1] if len(track) > 1 else None,
            "linkedItems": [i.GetName() for i in (item.GetLinkedItems() or [])],
        }

    @tool(
        "set_timeline_item_property",
        "Set a transform/crop/composite property on a timeline clip. Address it "
        "by trackType + trackIndex + itemIndex (1-based position on the track). "
        "'value' is usually a number (e.g. ZoomX=1.5, Pan=120, RotationAngle=90, "
        "CropLeft=200, Opacity=80). Common properties: Pan, Tilt, ZoomX, ZoomY, "
        "RotationAngle, AnchorPointX/Y, CropLeft/Right/Top/Bottom, CropSoftness, "
        "Opacity, FlipX, FlipY, CompositeMode, Distortion.",
        {
            "type": "object",
            "properties": {
                **_ITEM_ADDR,
                "property": {"type": "string"},
                "value": {"type": ["number", "string", "boolean"]},
            },
            "required": ["trackType", "trackIndex", "itemIndex", "property", "value"],
        },
    )
    def set_timeline_item_property(resolve, args):
        item = _track_item(resolve, args)
        prop = args["property"]
        value = args["value"]
        if not item.SetProperty(prop, value):
            raise ToolError(
                f"SetProperty({prop!r}, {value!r}) failed on {item.GetName()!r} "
                "(unknown property or invalid value)."
            )
        return {"ok": True, "item": item.GetName(), "property": prop, "value": value}

    @tool(
        "get_clip_tags",
        "Return a timeline clip's color label, flags and markers. Address by "
        "trackType + trackIndex + itemIndex (1-based).",
        {
            "type": "object",
            "properties": dict(_ITEM_ADDR),
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def get_clip_tags(resolve, args):
        item = _track_item(resolve, args)
        return {
            "item": item.GetName(),
            "clipColor": item.GetClipColor(),
            "flags": item.GetFlagList() or [],
            "markers": item.GetMarkers() or {},
        }

    @tool(
        "set_clip_color",
        "Set a timeline clip's color label (e.g. Orange, Yellow, Green, Blue, "
        "Purple, Pink, Brown). Pass an empty 'color' to clear it.",
        {
            "type": "object",
            "properties": {**_ITEM_ADDR, "color": {"type": "string"}},
            "required": ["trackType", "trackIndex", "itemIndex", "color"],
        },
    )
    def set_clip_color(resolve, args):
        item = _track_item(resolve, args)
        color = args["color"]
        ok = item.ClearClipColor() if color == "" else item.SetClipColor(color)
        if not ok:
            raise ToolError(f"Setting clip color to {color!r} failed.")
        return {"ok": True, "item": item.GetName(), "clipColor": item.GetClipColor()}

    @tool(
        "add_clip_flag",
        "Add a colored flag to a timeline clip (e.g. Blue, Cyan, Green, Yellow, "
        "Red, Pink, Purple).",
        {
            "type": "object",
            "properties": {**_ITEM_ADDR, "color": {"type": "string"}},
            "required": ["trackType", "trackIndex", "itemIndex", "color"],
        },
    )
    def add_clip_flag(resolve, args):
        item = _track_item(resolve, args)
        if not item.AddFlag(args["color"]):
            raise ToolError(f"AddFlag({args['color']!r}) failed.")
        return {"ok": True, "item": item.GetName(), "flags": item.GetFlagList() or []}

    @tool(
        "clear_clip_flags",
        "Clear flags from a timeline clip. 'color' defaults to 'All'.",
        {
            "type": "object",
            "properties": {**_ITEM_ADDR, "color": {"type": "string", "default": "All"}},
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def clear_clip_flags(resolve, args):
        item = _track_item(resolve, args)
        if not item.ClearFlags(args.get("color", "All")):
            raise ToolError("ClearFlags failed (no matching flag?).")
        return {"ok": True, "item": item.GetName(), "flags": item.GetFlagList() or []}

    @tool(
        "add_clip_marker",
        "Add a marker on a timeline clip at 'frame' (offset within the clip). "
        "Address by trackType + trackIndex + itemIndex (1-based).",
        {
            "type": "object",
            "properties": {
                **_ITEM_ADDR,
                "frame": {"type": "integer"},
                "color": {"type": "string", "default": "Blue"},
                "name": {"type": "string", "default": ""},
                "note": {"type": "string", "default": ""},
                "duration": {"type": "integer", "default": 1},
            },
            "required": ["trackType", "trackIndex", "itemIndex", "frame"],
        },
    )
    def add_clip_marker(resolve, args):
        item = _track_item(resolve, args)
        ok = item.AddMarker(
            args["frame"],
            args.get("color", "Blue"),
            args.get("name", ""),
            args.get("note", ""),
            args.get("duration", 1),
            "",
        )
        if not ok:
            raise ToolError("AddMarker failed (a marker may already exist at that frame).")
        return {"ok": True, "item": item.GetName(), "frame": args["frame"]}

    @tool(
        "delete_clip_marker",
        "Delete marker(s) on a timeline clip: give 'frame' (offset within the "
        "clip) or 'color' (all of that color; 'All' = every marker). Provide "
        "exactly one of frame/color.",
        {
            "type": "object",
            "properties": {
                **_ITEM_ADDR,
                "frame": {"type": "integer"},
                "color": {"type": "string"},
            },
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def delete_clip_marker(resolve, args):
        item = _track_item(resolve, args)
        has_frame = args.get("frame") is not None
        has_color = bool(args.get("color"))
        if has_frame == has_color:
            raise ToolError("Provide exactly one of 'frame' or 'color'.")
        if has_frame:
            ok = item.DeleteMarkerAtFrame(args["frame"])
            target = {"frame": args["frame"]}
        else:
            ok = item.DeleteMarkersByColor(args["color"])
            target = {"color": args["color"]}
        if not ok:
            raise ToolError(f"No clip marker matched {target}.")
        return {"ok": True, "item": item.GetName(), **target}

    def _node_graph(resolve, args):
        item = _track_item(resolve, args)
        graph = item.GetNodeGraph()
        if graph is None:
            raise ToolError("This clip has no node graph.")
        return item, graph

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    _TRACK_ADDR = {
        "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
        "trackIndex": {"type": "integer", "minimum": 1},
    }

    @tool(
        "add_track",
        "Add a track. For audio, 'audioType' can be mono/stereo/5.1/7.1/etc "
        "(default mono). Optional 1-based 'index' inserts at that position "
        "(appends if omitted).",
        {
            "type": "object",
            "properties": {
                "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
                "audioType": {"type": "string"},
                "index": {"type": "integer", "minimum": 1},
            },
            "required": ["trackType"],
        },
    )
    def add_track(resolve, args):
        tl = _require_timeline(resolve)
        ttype = args["trackType"]
        opts = {}
        if args.get("audioType"):
            opts["audioType"] = args["audioType"]
        if args.get("index"):
            opts["index"] = args["index"]
        ok = tl.AddTrack(ttype, opts) if opts else tl.AddTrack(ttype)
        if not ok:
            raise ToolError(f"AddTrack({ttype}) failed.")
        return {"ok": True, "trackType": ttype, "count": tl.GetTrackCount(ttype)}

    @tool(
        "delete_track",
        "Delete the track of the given type at the 1-based trackIndex.",
        {
            "type": "object",
            "properties": dict(_TRACK_ADDR),
            "required": ["trackType", "trackIndex"],
        },
    )
    def delete_track(resolve, args):
        tl = _require_timeline(resolve)
        ttype, idx = args["trackType"], args["trackIndex"]
        if not tl.DeleteTrack(ttype, idx):
            raise ToolError(f"DeleteTrack({ttype}, {idx}) failed.")
        return {"ok": True, "trackType": ttype, "count": tl.GetTrackCount(ttype)}

    @tool(
        "set_track_enabled",
        "Enable or disable a track (trackType + 1-based trackIndex).",
        {
            "type": "object",
            "properties": {**_TRACK_ADDR, "enabled": {"type": "boolean"}},
            "required": ["trackType", "trackIndex", "enabled"],
        },
    )
    def set_track_enabled(resolve, args):
        tl = _require_timeline(resolve)
        ttype, idx, enabled = args["trackType"], args["trackIndex"], bool(args["enabled"])
        if not tl.SetTrackEnable(ttype, idx, enabled):
            raise ToolError(f"SetTrackEnable({ttype}, {idx}, {enabled}) failed.")
        return {"ok": True, "trackType": ttype, "trackIndex": idx, "enabled": enabled}

    @tool(
        "set_track_locked",
        "Lock or unlock a track (trackType + 1-based trackIndex).",
        {
            "type": "object",
            "properties": {**_TRACK_ADDR, "locked": {"type": "boolean"}},
            "required": ["trackType", "trackIndex", "locked"],
        },
    )
    def set_track_locked(resolve, args):
        tl = _require_timeline(resolve)
        ttype, idx, locked = args["trackType"], args["trackIndex"], bool(args["locked"])
        if not tl.SetTrackLock(ttype, idx, locked):
            raise ToolError(f"SetTrackLock({ttype}, {idx}, {locked}) failed.")
        return {"ok": True, "trackType": ttype, "trackIndex": idx, "locked": locked}

    @tool(
        "set_track_name",
        "Rename a track (trackType + 1-based trackIndex).",
        {
            "type": "object",
            "properties": {**_TRACK_ADDR, "name": {"type": "string"}},
            "required": ["trackType", "trackIndex", "name"],
        },
    )
    def set_track_name(resolve, args):
        tl = _require_timeline(resolve)
        ttype, idx, name = args["trackType"], args["trackIndex"], args["name"]
        if not tl.SetTrackName(ttype, idx, name):
            raise ToolError(f"SetTrackName({ttype}, {idx}) failed.")
        return {"ok": True, "trackType": ttype, "trackIndex": idx, "name": name}

    @tool(
        "delete_timeline_item",
        "Delete a clip from the timeline (by trackType + trackIndex + itemIndex, "
        "1-based). Set 'ripple' true to close the gap left behind.",
        {
            "type": "object",
            "properties": {**_ITEM_ADDR, "ripple": {"type": "boolean", "default": False}},
            "required": ["trackType", "trackIndex", "itemIndex"],
        },
    )
    def delete_timeline_item(resolve, args):
        tl = _require_timeline(resolve)
        item = _track_item(resolve, args)
        name = item.GetName()
        if not tl.DeleteClips([item], bool(args.get("ripple", False))):
            raise ToolError("DeleteClips failed.")
        return {"ok": True, "deleted": name}

    @tool(
        "insert_title",
        "Insert a title generator (e.g. 'Text') into the timeline at the "
        "playhead.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    )
    def insert_title(resolve, args):
        tl = _require_timeline(resolve)
        item = tl.InsertTitleIntoTimeline(args["title"])
        if not item:
            raise ToolError(f"InsertTitleIntoTimeline({args['title']!r}) failed (unknown title).")
        return {"ok": True, "inserted": item.GetName()}

    @tool(
        "insert_fusion_title",
        "Insert a Fusion title (e.g. 'Text+') into the timeline at the playhead.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    )
    def insert_fusion_title(resolve, args):
        tl = _require_timeline(resolve)
        item = tl.InsertFusionTitleIntoTimeline(args["title"])
        if not item:
            raise ToolError(
                f"InsertFusionTitleIntoTimeline({args['title']!r}) failed (unknown title)."
            )
        return {"ok": True, "inserted": item.GetName()}

    @tool(
        "insert_generator",
        "Insert a generator (e.g. 'Solid Color') into the timeline at the "
        "playhead.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def insert_generator(resolve, args):
        tl = _require_timeline(resolve)
        item = tl.InsertGeneratorIntoTimeline(args["name"])
        if not item:
            raise ToolError(f"InsertGeneratorIntoTimeline({args['name']!r}) failed (unknown generator).")
        return {"ok": True, "inserted": item.GetName()}

    @tool(
        "get_timecode",
        "Get the current playhead timecode of the current timeline.",
        None,
    )
    def get_timecode(resolve, args):
        tl = _require_timeline(resolve)
        return {"timecode": tl.GetCurrentTimecode()}

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
        "list_media_pool",
        "List clips in the current media pool folder (and optionally subfolders).",
        {
            "type": "object",
            "properties": {
                "includeSubfolders": {"type": "boolean", "default": False},
            },
        },
    )
    def list_media_pool(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")

        def clip_info(clip):
            return {
                "name": clip.GetName(),
                "type": clip.GetClipProperty("Type"),
                "duration": clip.GetClipProperty("Duration"),
            }

        clips = [clip_info(c) for c in (folder.GetClipList() or [])]
        result = {"folder": folder.GetName(), "clips": clips}
        if args.get("includeSubfolders"):
            result["subfolders"] = [f.GetName() for f in (folder.GetSubFolderList() or [])]
        return result

    @tool(
        "import_media",
        "Import file/folder paths into the current media pool folder.",
        {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["paths"],
        },
    )
    def import_media(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        items = mp.ImportMedia(args["paths"]) or []
        return {"imported": [i.GetName() for i in items], "count": len(items)}

    @tool(
        "list_storage_volumes",
        "List mounted volumes/paths shown in Resolve's Media Storage.",
        None,
    )
    def list_storage_volumes(resolve, args):
        ms = resolve.GetMediaStorage()
        return {"volumes": ms.GetMountedVolumeList() or []}

    @tool(
        "browse_storage",
        "List subfolders and media files at an absolute folder path in Media "
        "Storage (browse disk before importing).",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    def browse_storage(resolve, args):
        ms = resolve.GetMediaStorage()
        path = os.path.expanduser(args["path"])
        return {
            "path": path,
            "subfolders": ms.GetSubFolderList(path) or [],
            "files": ms.GetFileList(path) or [],
        }

    @tool(
        "add_storage_items_to_pool",
        "Add file/folder paths from disk (Media Storage) into the current media "
        "pool folder. Returns the created clips.",
        {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["paths"],
        },
    )
    def add_storage_items_to_pool(resolve, args):
        ms = resolve.GetMediaStorage()
        paths = [os.path.expanduser(p) for p in args["paths"]]
        items = ms.AddItemListToMediaPool(paths) or []
        return {"added": [i.GetName() for i in items], "count": len(items)}

    @tool(
        "delete_clip",
        "Delete clips (by name, from the current media pool folder) from the "
        "media pool.",
        {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["names"],
        },
    )
    def delete_clip(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
        wanted, missing = [], []
        for n in args["names"]:
            (wanted if n in by_name else missing).append(by_name.get(n, n))
        if not wanted:
            raise ToolError(f"Clips not found in current folder: {missing}")
        if not mp.DeleteClips(wanted):
            raise ToolError("DeleteClips failed.")
        return {"deleted": len(wanted), "missing": [m for m in missing if isinstance(m, str)]}

    @tool(
        "get_clip_properties",
        "Read a media-pool clip's properties (by name, from the current folder). "
        "Omit 'property' to return all (resolution, FPS, codec, dates, etc.).",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "property": {"type": "string"},
            },
            "required": ["name"],
        },
    )
    def get_clip_properties(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        prop = args.get("property")
        value = clip.GetClipProperty(prop) if prop else clip.GetClipProperty()
        return {"name": clip.GetName(), "property": prop, "value": value}

    @tool(
        "set_clip_property",
        "Set a media-pool clip property (by name, from the current folder).",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "property": {"type": "string"},
                "value": {"type": ["string", "number", "boolean"]},
            },
            "required": ["name", "property", "value"],
        },
    )
    def set_clip_property(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.SetClipProperty(args["property"], str(args["value"])):
            raise ToolError(
                f"SetClipProperty({args['property']!r}) failed (unknown/read-only)."
            )
        return {"ok": True, "name": clip.GetName(), "property": args["property"], "value": args["value"]}

    @tool(
        "get_clip_metadata",
        "Read a media-pool clip's metadata (by name). Omit 'key' to return all "
        "set metadata as a dict.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "key": {"type": "string"},
            },
            "required": ["name"],
        },
    )
    def get_clip_metadata(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        key = args.get("key")
        value = clip.GetMetadata(key) if key else clip.GetMetadata()
        return {"name": clip.GetName(), "key": key, "value": value}

    @tool(
        "set_clip_metadata",
        "Set a media-pool clip's metadata key (by name).",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["name", "key", "value"],
        },
    )
    def set_clip_metadata(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.SetMetadata(args["key"], str(args["value"])):
            raise ToolError(f"SetMetadata({args['key']!r}) failed.")
        return {"ok": True, "name": clip.GetName(), "key": args["key"], "value": args["value"]}

    @tool(
        "rename_clip",
        "Rename a media-pool clip (by current name, from the current folder).",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "newName": {"type": "string"},
            },
            "required": ["name", "newName"],
        },
    )
    def rename_clip(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.SetName(args["newName"]):
            raise ToolError("SetName failed.")
        return {"ok": True, "name": clip.GetName()}

    @tool(
        "get_pool_clip_tags",
        "Return a media-pool clip's color label, flags and markers (by name).",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def get_pool_clip_tags(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        return {
            "name": clip.GetName(),
            "clipColor": clip.GetClipColor(),
            "flags": clip.GetFlagList() or [],
            "markers": clip.GetMarkers() or {},
        }

    @tool(
        "set_pool_clip_color",
        "Set a media-pool clip's color label (by name). Empty 'color' clears it.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "color": {"type": "string"}},
            "required": ["name", "color"],
        },
    )
    def set_pool_clip_color(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        ok = clip.ClearClipColor() if args["color"] == "" else clip.SetClipColor(args["color"])
        if not ok:
            raise ToolError(f"Setting clip color to {args['color']!r} failed.")
        return {"ok": True, "name": clip.GetName(), "clipColor": clip.GetClipColor()}

    @tool(
        "add_pool_clip_flag",
        "Add a colored flag to a media-pool clip (by name).",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "color": {"type": "string"}},
            "required": ["name", "color"],
        },
    )
    def add_pool_clip_flag(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.AddFlag(args["color"]):
            raise ToolError(f"AddFlag({args['color']!r}) failed.")
        return {"ok": True, "name": clip.GetName(), "flags": clip.GetFlagList() or []}

    @tool(
        "clear_pool_clip_flags",
        "Clear flags from a media-pool clip (by name). 'color' defaults to 'All'.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "color": {"type": "string", "default": "All"}},
            "required": ["name"],
        },
    )
    def clear_pool_clip_flags(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.ClearFlags(args.get("color", "All")):
            raise ToolError("ClearFlags failed (no matching flag?).")
        return {"ok": True, "name": clip.GetName(), "flags": clip.GetFlagList() or []}

    @tool(
        "add_pool_clip_marker",
        "Add a marker on a media-pool clip at 'frame' (source frame offset).",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "frame": {"type": "integer"},
                "color": {"type": "string", "default": "Blue"},
                "markerName": {"type": "string", "default": ""},
                "note": {"type": "string", "default": ""},
                "duration": {"type": "integer", "default": 1},
            },
            "required": ["name", "frame"],
        },
    )
    def add_pool_clip_marker(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        ok = clip.AddMarker(
            args["frame"],
            args.get("color", "Blue"),
            args.get("markerName", ""),
            args.get("note", ""),
            args.get("duration", 1),
            "",
        )
        if not ok:
            raise ToolError("AddMarker failed (a marker may already exist at that frame).")
        return {"ok": True, "name": clip.GetName(), "frame": args["frame"]}

    @tool(
        "delete_pool_clip_marker",
        "Delete marker(s) on a media-pool clip: give 'frame' (source offset) or "
        "'color' ('All' = every marker). Provide exactly one.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "frame": {"type": "integer"},
                "color": {"type": "string"},
            },
            "required": ["name"],
        },
    )
    def delete_pool_clip_marker(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        has_frame = args.get("frame") is not None
        has_color = bool(args.get("color"))
        if has_frame == has_color:
            raise ToolError("Provide exactly one of 'frame' or 'color'.")
        if has_frame:
            ok = clip.DeleteMarkerAtFrame(args["frame"])
            target = {"frame": args["frame"]}
        else:
            ok = clip.DeleteMarkersByColor(args["color"])
            target = {"color": args["color"]}
        if not ok:
            raise ToolError(f"No clip marker matched {target}.")
        return {"ok": True, "name": clip.GetName(), **target}

    @tool(
        "append_clips_to_timeline",
        "Append media pool clips (by name, from the current folder) to the current timeline.",
        {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["names"],
        },
    )
    def append_clips_to_timeline(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
        wanted = []
        missing = []
        for n in args["names"]:
            if n in by_name:
                wanted.append(by_name[n])
            else:
                missing.append(n)
        if missing:
            raise ToolError(f"Clips not found in current folder: {missing}")
        added = mp.AppendToTimeline(wanted) or []
        return {"appended": len(added), "missing": missing}

    @tool(
        "add_clip_to_timeline",
        "Place a media-pool clip (by name, from the current folder) onto the "
        "current timeline with precise control. Optional: startFrame/endFrame "
        "(source in/out trim), trackIndex (target track, 1-based), recordFrame "
        "(timeline frame to place at), mediaType (1=video only, 2=audio only). "
        "Omitted fields use Resolve defaults. This is the assembly primitive that "
        "append_clips_to_timeline (whole-clip append) does not cover.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "startFrame": {"type": "integer"},
                "endFrame": {"type": "integer"},
                "trackIndex": {"type": "integer", "minimum": 1},
                "recordFrame": {"type": "integer"},
                "mediaType": {"type": "integer", "enum": [1, 2]},
            },
            "required": ["name"],
        },
    )
    def add_clip_to_timeline(resolve, args):
        project = _require_project(resolve)
        _require_timeline(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
        item = by_name.get(args["name"])
        if not item:
            raise ToolError(f"Clip {args['name']!r} not found in current folder.")

        clip_info = {"mediaPoolItem": item}
        for key in ("startFrame", "endFrame", "trackIndex", "recordFrame", "mediaType"):
            if args.get(key) is not None:
                clip_info[key] = args[key]

        added = mp.AppendToTimeline([clip_info]) or []
        if not added:
            raise ToolError(
                "AppendToTimeline returned nothing (check trackIndex exists and "
                "the source in/out range is valid)."
            )
        return {"appended": len(added), "name": item.GetName()}

    @tool(
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

    @tool(
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
        clips, missing = [], []
        for n in args["names"]:
            (clips if n in by_name else missing).append(by_name.get(n, n))
        if missing:
            raise ToolError(f"Clips not found in current folder: {[m for m in missing if isinstance(m, str)]}")
        tl = mp.CreateTimelineFromClips(args["name"], clips)
        if not tl:
            raise ToolError("CreateTimelineFromClips failed (name not unique?).")
        return {"ok": True, "created": tl.GetName(), "clips": len(clips)}

    @tool(
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

    @tool(
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

    @tool(
        "get_render_presets",
        "List available render presets and current render format/codec.",
        None,
    )
    def get_render_presets(resolve, args):
        project = _require_project(resolve)
        return {
            "renderPresets": project.GetRenderPresetList(),
            "currentFormatAndCodec": project.GetCurrentRenderFormatAndCodec(),
        }

    @tool(
        "render_current_timeline",
        "Queue a render job for the current timeline and start rendering. "
        "Optionally set a render preset and an output directory/filename first.",
        {
            "type": "object",
            "properties": {
                "preset": {"type": "string"},
                "targetDir": {"type": "string"},
                "customName": {"type": "string"},
            },
        },
    )
    def render_current_timeline(resolve, args):
        project = _require_project(resolve)
        _require_timeline(resolve)
        if args.get("preset"):
            if not project.LoadRenderPreset(args["preset"]):
                raise ToolError(f"Render preset {args['preset']!r} not found.")
        settings = {}
        if args.get("targetDir"):
            settings["TargetDir"] = args["targetDir"]
        if args.get("customName"):
            settings["CustomName"] = args["customName"]
        if settings and not project.SetRenderSettings(settings):
            raise ToolError("SetRenderSettings failed.")
        job_id = project.AddRenderJob()
        if not job_id:
            raise ToolError("AddRenderJob failed.")
        started = project.StartRendering([job_id], False)
        return {"jobId": job_id, "started": bool(started)}

    @tool(
        "add_render_job",
        "Queue a render job for the current timeline WITHOUT starting it (for "
        "building a batch queue). Optionally set a preset and output "
        "directory/filename first. Returns the new job id.",
        {
            "type": "object",
            "properties": {
                "preset": {"type": "string"},
                "targetDir": {"type": "string"},
                "customName": {"type": "string"},
            },
        },
    )
    def add_render_job(resolve, args):
        project = _require_project(resolve)
        _require_timeline(resolve)
        if args.get("preset") and not project.LoadRenderPreset(args["preset"]):
            raise ToolError(f"Render preset {args['preset']!r} not found.")
        settings = {}
        if args.get("targetDir"):
            settings["TargetDir"] = os.path.expanduser(args["targetDir"])
        if args.get("customName"):
            settings["CustomName"] = args["customName"]
        if settings and not project.SetRenderSettings(settings):
            raise ToolError("SetRenderSettings failed.")
        job_id = project.AddRenderJob()
        if not job_id:
            raise ToolError("AddRenderJob failed.")
        return {"ok": True, "jobId": job_id}

    @tool(
        "get_render_status",
        "Return render-in-progress flag and the render job queue with statuses.",
        None,
    )
    def get_render_status(resolve, args):
        project = _require_project(resolve)
        jobs = project.GetRenderJobList() or []
        statuses = []
        for job in jobs:
            jid = job.get("JobId")
            statuses.append({"jobId": jid, "status": project.GetRenderJobStatus(jid)})
        return {
            "rendering": bool(project.IsRenderingInProgress()),
            "jobs": statuses,
        }

    @tool(
        "stop_rendering",
        "Stop any render currently in progress.",
        None,
    )
    def stop_rendering(resolve, args):
        project = _require_project(resolve)
        project.StopRendering()
        return {"ok": True, "rendering": bool(project.IsRenderingInProgress())}

    @tool(
        "delete_render_job",
        "Delete a render job from the queue by job id. Omit 'jobId' to clear the "
        "entire queue.",
        {
            "type": "object",
            "properties": {"jobId": {"type": "string"}},
        },
    )
    def delete_render_job(resolve, args):
        project = _require_project(resolve)
        job_id = args.get("jobId")
        if job_id == "":
            raise ToolError("jobId is empty; omit it entirely to clear the whole queue.")
        if job_id is not None:
            if not project.DeleteRenderJob(job_id):
                raise ToolError(f"DeleteRenderJob({job_id!r}) failed.")
            return {"ok": True, "deleted": job_id}
        if not project.DeleteAllRenderJobs():
            raise ToolError("DeleteAllRenderJobs failed.")
        return {"ok": True, "deleted": "all"}

    @tool(
        "get_render_formats",
        "List available render formats (format -> file extension). Pass 'format' "
        "to instead list codecs (description -> codec name) for that format.",
        {
            "type": "object",
            "properties": {"format": {"type": "string"}},
        },
    )
    def get_render_formats(resolve, args):
        project = _require_project(resolve)
        fmt = args.get("format")
        if fmt:
            return {"format": fmt, "codecs": project.GetRenderCodecs(fmt) or {}}
        return {"formats": project.GetRenderFormats() or {}}

    @tool(
        "set_render_format_codec",
        "Set the current render format (e.g. 'mp4', 'mov') and codec (e.g. "
        "'H264', 'H265'). Use get_render_formats to discover valid values.",
        {
            "type": "object",
            "properties": {
                "format": {"type": "string"},
                "codec": {"type": "string"},
            },
            "required": ["format", "codec"],
        },
    )
    def set_render_format_codec(resolve, args):
        project = _require_project(resolve)
        if not project.SetCurrentRenderFormatAndCodec(args["format"], args["codec"]):
            raise ToolError(
                f"SetCurrentRenderFormatAndCodec({args['format']!r}, "
                f"{args['codec']!r}) failed (invalid format/codec)."
            )
        return {"ok": True, **project.GetCurrentRenderFormatAndCodec()}

    @tool(
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

    @tool(
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

    @tool(
        "export_project",
        "Export (back up) the current project to a .drp file at the given path.",
        {
            "type": "object",
            "properties": {"filePath": {"type": "string"}},
            "required": ["filePath"],
        },
    )
    def export_project(resolve, args):
        pm = resolve.GetProjectManager()
        project = _require_project(resolve)
        path = os.path.expanduser(args["filePath"])
        directory = os.path.dirname(path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                raise ToolError(f"Could not create directory {directory!r}: {exc}")
        if not pm.ExportProject(project.GetName(), path):
            raise ToolError("ExportProject failed.")
        return {"ok": True, "filePath": path, "project": project.GetName()}

    @tool(
        "import_project",
        "Import a project from a .drp file. Optional 'name' for the imported "
        "project.",
        {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["filePath"],
        },
    )
    def import_project(resolve, args):
        pm = resolve.GetProjectManager()
        path = os.path.expanduser(args["filePath"])
        if not os.path.exists(path):
            raise ToolError(f"File not found: {path}")
        ok = pm.ImportProject(path, args["name"]) if args.get("name") else pm.ImportProject(path)
        if not ok:
            raise ToolError("ImportProject failed.")
        return {"ok": True, "filePath": path}

    @tool(
        "get_setting",
        "Read a project or timeline setting. scope = 'project' (default) or "
        "'timeline'. Omit 'name' to return all settings as a dict.",
        {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["project", "timeline"], "default": "project"},
                "name": {"type": "string"},
            },
        },
    )
    def get_setting(resolve, args):
        scope = args.get("scope", "project")
        target = _require_project(resolve) if scope == "project" else _require_timeline(resolve)
        name = args.get("name")
        value = target.GetSetting(name) if name else target.GetSetting()
        return {"scope": scope, "name": name, "value": value}

    @tool(
        "set_setting",
        "Set a project or timeline setting. scope = 'project' (default) or "
        "'timeline'. Both name and value are strings.",
        {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["project", "timeline"], "default": "project"},
                "name": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["name", "value"],
        },
    )
    def set_setting(resolve, args):
        scope = args.get("scope", "project")
        target = _require_project(resolve) if scope == "project" else _require_timeline(resolve)
        ok = target.SetSetting(args["name"], str(args["value"]))
        if not ok:
            raise ToolError(
                f"SetSetting failed for {scope} {args['name']!r}="
                f"{args['value']!r} (unknown key or invalid value)."
            )
        return {"ok": True, "scope": scope, "name": args["name"], "value": args["value"]}

    @tool(
        "save_project",
        "Save the current project (persists changes to disk).",
        None,
    )
    def save_project(resolve, args):
        pm = resolve.GetProjectManager()
        if not pm or not pm.SaveProject():
            raise ToolError("SaveProject failed.")
        return {"ok": True}

    @tool(
        "create_project",
        "Create and open a new project with a unique name.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def create_project(resolve, args):
        pm = resolve.GetProjectManager()
        project = pm.CreateProject(args["name"]) if pm else None
        if not project:
            raise ToolError(f"CreateProject({args['name']!r}) failed (name not unique?).")
        return {"ok": True, "created": project.GetName()}

    @tool(
        "close_project",
        "Close the current project WITHOUT saving. Call save_project first to "
        "keep changes.",
        None,
    )
    def close_project(resolve, args):
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None
        if not project:
            raise ToolError("No project is open.")
        name = project.GetName()
        if not pm.CloseProject(project):
            raise ToolError("CloseProject failed.")
        return {"ok": True, "closed": name}

    @tool(
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

    @tool(
        "detect_scene_cuts",
        "Detect and apply scene cuts along the current timeline.",
        None,
    )
    def detect_scene_cuts(resolve, args):
        tl = _require_timeline(resolve)
        if not tl.DetectSceneCuts():
            raise ToolError("DetectSceneCuts failed.")
        return {"ok": True}

    def _current_still_album(resolve):
        gallery = _require_gallery(resolve)
        album = gallery.GetCurrentStillAlbum()
        if not album:
            raise ToolError("No current gallery still album.")
        return album

    @tool(
        "get_gallery_stills_count",
        "Return how many stills are in the current gallery album.",
        None,
    )
    def get_gallery_stills_count(resolve, args):
        album = _current_still_album(resolve)
        return {"count": len(album.GetStills() or [])}

    @tool(
        "clear_gallery_stills",
        "Delete all stills in the current gallery album.",
        None,
    )
    def clear_gallery_stills(resolve, args):
        album = _current_still_album(resolve)
        stills = album.GetStills() or []
        if stills and not album.DeleteStills(stills):
            raise ToolError("DeleteStills failed.")
        return {"ok": True, "deleted": len(stills)}

    def _stills_by_index(album, indices):
        stills = album.GetStills() or []
        chosen = []
        for i in indices:
            if i < 1 or i > len(stills):
                raise ToolError(f"No still #{i} (album has {len(stills)}).")
            chosen.append(stills[i - 1])
        return chosen

    @tool(
        "list_gallery_stills",
        "List stills in the current gallery album, with their 1-based index and "
        "label.",
        None,
    )
    def list_gallery_stills(resolve, args):
        album = _current_still_album(resolve)
        stills = album.GetStills() or []
        return {
            "count": len(stills),
            "stills": [{"index": i + 1, "label": album.GetLabel(s)} for i, s in enumerate(stills)],
        }

    @tool(
        "set_gallery_still_label",
        "Set the label of a still (1-based index) in the current gallery album.",
        {
            "type": "object",
            "properties": {"index": {"type": "integer", "minimum": 1}, "label": {"type": "string"}},
            "required": ["index", "label"],
        },
    )
    def set_gallery_still_label(resolve, args):
        album = _current_still_album(resolve)
        still = _stills_by_index(album, [args["index"]])[0]
        if not album.SetLabel(still, args["label"]):
            raise ToolError("SetLabel failed.")
        return {"ok": True, "index": args["index"], "label": args["label"]}

    @tool(
        "export_gallery_stills",
        "Export stills from the current gallery album to a folder. format = one "
        "of dpx/cin/tif/jpg/png/ppm/bmp/xpm/drx. Omit 'indices' to export all.",
        {
            "type": "object",
            "properties": {
                "folderPath": {"type": "string"},
                "filePrefix": {"type": "string", "default": "still"},
                "format": {"type": "string", "default": "jpg"},
                "indices": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            },
            "required": ["folderPath"],
        },
    )
    def export_gallery_stills(resolve, args):
        album = _current_still_album(resolve)
        all_stills = album.GetStills() or []
        stills = _stills_by_index(album, args["indices"]) if args.get("indices") else all_stills
        if not stills:
            raise ToolError("No stills to export.")
        folder = os.path.expanduser(args["folderPath"])
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {folder!r}: {exc}")
        if not album.ExportStills(stills, folder, args.get("filePrefix", "still"), args.get("format", "jpg")):
            raise ToolError("ExportStills failed.")
        return {"ok": True, "exported": len(stills), "folder": folder}

    @tool(
        "import_gallery_stills",
        "Import still image files into the current gallery album.",
        {
            "type": "object",
            "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
            "required": ["paths"],
        },
    )
    def import_gallery_stills(resolve, args):
        album = _current_still_album(resolve)
        paths = [os.path.expanduser(p) for p in args["paths"]]
        if not album.ImportStills(paths):
            raise ToolError("ImportStills failed (no still imported).")
        return {"ok": True, "imported": len(paths)}

    @tool(
        "delete_gallery_stills",
        "Delete specific stills (1-based indices) from the current gallery album. "
        "Use clear_gallery_stills to delete all.",
        {
            "type": "object",
            "properties": {"indices": {"type": "array", "items": {"type": "integer", "minimum": 1}}},
            "required": ["indices"],
        },
    )
    def delete_gallery_stills(resolve, args):
        album = _current_still_album(resolve)
        stills = _stills_by_index(album, args["indices"])
        if not album.DeleteStills(stills):
            raise ToolError("DeleteStills failed.")
        return {"ok": True, "deleted": len(stills)}

    # ----- Bins / folders -----------------------------------------------
    @tool(
        "add_subfolder",
        "Create a subfolder under the current media pool folder.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def add_subfolder(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        parent = mp.GetCurrentFolder()
        if not parent:
            raise ToolError("No current media pool folder.")
        folder = mp.AddSubFolder(parent, args["name"])
        if not folder:
            raise ToolError(f"AddSubFolder({args['name']!r}) failed.")
        return {"ok": True, "created": folder.GetName()}

    @tool(
        "set_current_folder",
        "Set the current media pool folder by name (searched from the root).",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def set_current_folder(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = _find_folder(mp, args["name"])
        if not mp.SetCurrentFolder(folder):
            raise ToolError("SetCurrentFolder failed.")
        return {"ok": True, "currentFolder": folder.GetName()}

    @tool(
        "delete_subfolders",
        "Delete subfolders (by name) of the current media pool folder.",
        {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}}},
         "required": ["names"]},
    )
    def delete_subfolders(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        parent = mp.GetCurrentFolder()
        if not parent:
            raise ToolError("No current media pool folder.")
        by_name = {f.GetName(): f for f in (parent.GetSubFolderList() or [])}
        targets = [by_name[n] for n in args["names"] if n in by_name]
        missing = [n for n in args["names"] if n not in by_name]
        if not targets:
            raise ToolError(f"No matching subfolders: {missing}")
        if not mp.DeleteFolders(targets):
            raise ToolError("DeleteFolders failed.")
        return {"ok": True, "deleted": len(targets), "missing": missing}

    @tool(
        "move_clips_to_folder",
        "Move clips (by name, from the current folder) into a target folder "
        "(by name, searched from the root).",
        {"type": "object", "properties": {
            "names": {"type": "array", "items": {"type": "string"}},
            "targetFolder": {"type": "string"}},
         "required": ["names", "targetFolder"]},
    )
    def move_clips_to_folder(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
        clips = [by_name[n] for n in args["names"] if n in by_name]
        missing = [n for n in args["names"] if n not in by_name]
        if not clips:
            raise ToolError(f"No matching clips: {missing}")
        target = _find_folder(mp, args["targetFolder"])
        if not mp.MoveClips(clips, target):
            raise ToolError("MoveClips failed.")
        return {"ok": True, "moved": len(clips), "missing": missing, "to": target.GetName()}

    # ----- Mark in/out --------------------------------------------------
    @tool(
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

    @tool(
        "get_mark_in_out",
        "Get mark in/out of the current timeline, or of a media-pool clip if "
        "'clip' (name) is given.",
        {"type": "object", "properties": {"clip": {"type": "string"}}},
    )
    def get_mark_in_out(resolve, args):
        target = _pool_clip(resolve, args["clip"]) if args.get("clip") else _require_timeline(resolve)
        return {"markInOut": target.GetMarkInOut()}

    @tool(
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

    # ----- Compound / Fusion clips --------------------------------------
    @tool(
        "create_compound_clip",
        "Create a compound clip from items on a track (1-based itemIndices) of "
        "the current timeline. Optional 'name'.",
        {"type": "object", "properties": {
            "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
            "trackIndex": {"type": "integer", "minimum": 1},
            "itemIndices": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "name": {"type": "string"}},
         "required": ["trackType", "trackIndex", "itemIndices"]},
    )
    def create_compound_clip(resolve, args):
        tl, items = _track_items_by_index(resolve, args["trackType"], args["trackIndex"], args["itemIndices"])
        clip_info = {"name": args["name"]} if args.get("name") else {}
        item = tl.CreateCompoundClip(items, clip_info) if clip_info else tl.CreateCompoundClip(items)
        if not item:
            raise ToolError("CreateCompoundClip failed.")
        return {"ok": True, "created": item.GetName()}

    @tool(
        "create_fusion_clip",
        "Create a Fusion clip from items on a track (1-based itemIndices) of the "
        "current timeline.",
        {"type": "object", "properties": {
            "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
            "trackIndex": {"type": "integer", "minimum": 1},
            "itemIndices": {"type": "array", "items": {"type": "integer", "minimum": 1}}},
         "required": ["trackType", "trackIndex", "itemIndices"]},
    )
    def create_fusion_clip(resolve, args):
        tl, items = _track_items_by_index(resolve, args["trackType"], args["trackIndex"], args["itemIndices"])
        item = tl.CreateFusionClip(items)
        if not item:
            raise ToolError("CreateFusionClip failed.")
        return {"ok": True, "created": item.GetName()}

    @tool(
        "set_timeline_name",
        "Rename the current timeline.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def set_timeline_name(resolve, args):
        tl = _require_timeline(resolve)
        if not tl.SetName(args["name"]):
            raise ToolError("SetName failed (name not unique?).")
        return {"ok": True, "name": tl.GetName()}

    @tool(
        "set_timeline_start_timecode",
        "Set the start timecode of the current timeline (HH:MM:SS:FF).",
        {"type": "object", "properties": {"timecode": {"type": "string"}}, "required": ["timecode"]},
    )
    def set_timeline_start_timecode(resolve, args):
        tl = _require_timeline(resolve)
        if not tl.SetStartTimecode(args["timecode"]):
            raise ToolError(f"SetStartTimecode({args['timecode']!r}) failed.")
        return {"ok": True, "startTimecode": tl.GetStartTimecode()}

    # ----- Color: CDL, grade versions, color groups ---------------------
    @tool(
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

    @tool(
        "set_clip_enabled",
        "Enable or disable a timeline clip (mute its output).",
        {"type": "object", "properties": {**_ITEM_ADDR, "enabled": {"type": "boolean"}},
         "required": ["trackType", "trackIndex", "itemIndex", "enabled"]},
    )
    def set_clip_enabled(resolve, args):
        item = _track_item(resolve, args)
        if not item.SetClipEnabled(bool(args["enabled"])):
            raise ToolError("SetClipEnabled failed.")
        return {"ok": True, "item": item.GetName(), "enabled": bool(args["enabled"])}

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
        "list_color_groups",
        "List color groups in the current project.",
        None,
    )
    def list_color_groups(resolve, args):
        project = _require_project(resolve)
        return {"groups": [g.GetName() for g in (project.GetColorGroupsList() or [])]}

    @tool(
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

    def _color_group(project, name):
        for g in project.GetColorGroupsList() or []:
            if g.GetName() == name:
                return g
        raise ToolError(f"Color group {name!r} not found.")

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
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

    # ----- Media-pool item ops ------------------------------------------
    @tool(
        "link_proxy",
        "Link a proxy media file to a media-pool clip (by name).",
        {"type": "object", "properties": {"name": {"type": "string"}, "proxyPath": {"type": "string"}},
         "required": ["name", "proxyPath"]},
    )
    def link_proxy(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.LinkProxyMedia(os.path.expanduser(args["proxyPath"])):
            raise ToolError("LinkProxyMedia failed.")
        return {"ok": True, "name": clip.GetName()}

    @tool(
        "unlink_proxy",
        "Unlink proxy media from a media-pool clip (by name).",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def unlink_proxy(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.UnlinkProxyMedia():
            raise ToolError("UnlinkProxyMedia failed.")
        return {"ok": True, "name": clip.GetName()}

    @tool(
        "replace_clip",
        "Replace a media-pool clip's underlying media with another file (by name).",
        {"type": "object", "properties": {"name": {"type": "string"}, "filePath": {"type": "string"}},
         "required": ["name", "filePath"]},
    )
    def replace_clip(resolve, args):
        clip = _pool_clip(resolve, args["name"])
        if not clip.ReplaceClip(os.path.expanduser(args["filePath"])):
            raise ToolError("ReplaceClip failed.")
        return {"ok": True, "name": clip.GetName()}

    @tool(
        "get_selected_clips",
        "List currently selected media-pool clips.",
        None,
    )
    def get_selected_clips(resolve, args):
        project = _require_project(resolve)
        clips = project.GetMediaPool().GetSelectedClips() or []
        return {"selected": [c.GetName() for c in clips]}

    @tool(
        "set_selected_clip",
        "Select a media-pool clip (by name) in the current folder.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def set_selected_clip(resolve, args):
        project = _require_project(resolve)
        clip = _pool_clip(resolve, args["name"])
        if not project.GetMediaPool().SetSelectedClip(clip):
            raise ToolError("SetSelectedClip failed.")
        return {"ok": True, "name": clip.GetName()}

    # ----- Render extras ------------------------------------------------
    @tool(
        "save_render_preset",
        "Save the current render settings as a new preset.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def save_render_preset(resolve, args):
        project = _require_project(resolve)
        if not project.SaveAsNewRenderPreset(args["name"]):
            raise ToolError("SaveAsNewRenderPreset failed (name not unique?).")
        return {"ok": True, "preset": args["name"]}

    @tool(
        "delete_render_preset",
        "Delete a render preset by name.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def delete_render_preset(resolve, args):
        project = _require_project(resolve)
        if not project.DeleteRenderPreset(args["name"]):
            raise ToolError("DeleteRenderPreset failed.")
        return {"ok": True, "deleted": args["name"]}

    @tool(
        "load_render_preset",
        "Set a render preset (by name) as the current render preset.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def load_render_preset(resolve, args):
        project = _require_project(resolve)
        if not project.LoadRenderPreset(args["name"]):
            raise ToolError(f"Render preset {args['name']!r} not found.")
        return {"ok": True, "preset": args["name"]}

    @tool(
        "get_render_mode",
        "Get the render mode: 0 = individual clips, 1 = single clip.",
        None,
    )
    def get_render_mode(resolve, args):
        project = _require_project(resolve)
        return {"renderMode": project.GetCurrentRenderMode()}

    @tool(
        "set_render_mode",
        "Set the render mode: 0 = individual clips, 1 = single clip.",
        {"type": "object", "properties": {"mode": {"type": "integer", "enum": [0, 1]}}, "required": ["mode"]},
    )
    def set_render_mode(resolve, args):
        project = _require_project(resolve)
        if not project.SetCurrentRenderMode(args["mode"]):
            raise ToolError("SetCurrentRenderMode failed.")
        return {"ok": True, "renderMode": args["mode"]}

    @tool(
        "get_render_resolutions",
        "List render resolutions valid for a format + codec (or all if omitted).",
        {"type": "object", "properties": {"format": {"type": "string"}, "codec": {"type": "string"}}},
    )
    def get_render_resolutions(resolve, args):
        project = _require_project(resolve)
        if args.get("format") and args.get("codec"):
            res = project.GetRenderResolutions(args["format"], args["codec"])
        else:
            res = project.GetRenderResolutions()
        return {"resolutions": res or []}

    @tool(
        "get_quick_export_presets",
        "List available Quick Export presets.",
        None,
    )
    def get_quick_export_presets(resolve, args):
        project = _require_project(resolve)
        return {"presets": project.GetQuickExportRenderPresets() or []}

    @tool(
        "quick_export",
        "Quick Export the current timeline with a preset (from "
        "get_quick_export_presets). Optional targetDir / customName.",
        {"type": "object", "properties": {
            "preset": {"type": "string"},
            "targetDir": {"type": "string"},
            "customName": {"type": "string"}},
         "required": ["preset"]},
    )
    def quick_export(resolve, args):
        project = _require_project(resolve)
        _require_timeline(resolve)
        params = {}
        if args.get("targetDir"):
            params["TargetDir"] = os.path.expanduser(args["targetDir"])
        if args.get("customName"):
            params["CustomName"] = args["customName"]
        status = project.RenderWithQuickExport(args["preset"], params)
        if isinstance(status, str):
            raise ToolError(f"RenderWithQuickExport failed: {status}")
        return {"ok": True, "status": status}

    # ----- Misc ---------------------------------------------------------
    @tool(
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

    @tool(
        "insert_audio_at_playhead",
        "Insert audio media at the playhead on the selected Fairlight track. "
        "Offsets/durations are in samples.",
        {"type": "object", "properties": {
            "mediaPath": {"type": "string"},
            "startOffsetInSamples": {"type": "integer", "default": 0},
            "durationInSamples": {"type": "integer", "default": 0}},
         "required": ["mediaPath"]},
    )
    def insert_audio_at_playhead(resolve, args):
        project = _require_project(resolve)
        path = os.path.expanduser(args["mediaPath"])
        ok = project.InsertAudioToCurrentTrackAtPlayhead(
            path, args.get("startOffsetInSamples", 0), args.get("durationInSamples", 0))
        if not ok:
            raise ToolError("InsertAudioToCurrentTrackAtPlayhead failed.")
        return {"ok": True, "mediaPath": path}

    @tool(
        "grab_all_stills",
        "Grab a still from every clip in the current timeline. source 1 = first "
        "frame, 2 = middle frame.",
        {"type": "object", "properties": {"source": {"type": "integer", "enum": [1, 2], "default": 1}}},
    )
    def grab_all_stills(resolve, args):
        tl = _require_timeline(resolve)
        stills = tl.GrabAllStills(args.get("source", 1)) or []
        return {"ok": True, "grabbed": len(stills)}

    @tool(
        "reveal_in_storage",
        "Reveal a file/folder path in Resolve's Media Storage.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    def reveal_in_storage(resolve, args):
        ms = resolve.GetMediaStorage()
        if not ms.RevealInStorage(os.path.expanduser(args["path"])):
            raise ToolError("RevealInStorage failed.")
        return {"ok": True, "path": os.path.expanduser(args["path"])}

    @tool(
        "export_metadata",
        "Export metadata of clips in the current folder to a CSV file. If "
        "'names' is omitted, all media-pool clips are exported.",
        {"type": "object", "properties": {
            "filePath": {"type": "string"},
            "names": {"type": "array", "items": {"type": "string"}}},
         "required": ["filePath"]},
    )
    def export_metadata(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        path = os.path.expanduser(args["filePath"])
        directory = os.path.dirname(path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                raise ToolError(f"Could not create directory {directory!r}: {exc}")
        if args.get("names"):
            folder = mp.GetCurrentFolder()
            by_name = {c.GetName(): c for c in (folder.GetClipList() or [])} if folder else {}
            clips = [by_name[n] for n in args["names"] if n in by_name]
            ok = mp.ExportMetadata(path, clips)
        else:
            ok = mp.ExportMetadata(path)
        if not ok:
            raise ToolError("ExportMetadata failed.")
        return {"ok": True, "filePath": path}

    @tool(
        "refresh_lut_list",
        "Refresh Resolve's LUT list (run after adding LUT files on disk).",
        None,
    )
    def refresh_lut_list(resolve, args):
        project = _require_project(resolve)
        if not project.RefreshLUTList():
            raise ToolError("RefreshLUTList failed.")
        return {"ok": True}

    # ----- Gallery albums -----------------------------------------------
    @tool(
        "list_gallery_albums",
        "List the still albums in the gallery and the current album.",
        None,
    )
    def list_gallery_albums(resolve, args):
        gallery = _require_gallery(resolve)
        albums = gallery.GetGalleryStillAlbums() or []
        current = gallery.GetCurrentStillAlbum()
        cur_name = gallery.GetAlbumName(current) if current else None
        return {
            "albums": [gallery.GetAlbumName(a) for a in albums],
            "current": cur_name,
        }

    @tool(
        "create_gallery_album",
        "Create a new still album. Optional 'name' to label it.",
        {"type": "object", "properties": {"name": {"type": "string"}}},
    )
    def create_gallery_album(resolve, args):
        gallery = _require_gallery(resolve)
        album = gallery.CreateGalleryStillAlbum()
        if not album:
            raise ToolError("CreateGalleryStillAlbum failed.")
        if args.get("name"):
            gallery.SetAlbumName(album, args["name"])
        return {"ok": True, "album": gallery.GetAlbumName(album)}

    @tool(
        "set_current_gallery_album",
        "Set the current still album by name.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    )
    def set_current_gallery_album(resolve, args):
        gallery = _require_gallery(resolve)
        for album in gallery.GetGalleryStillAlbums() or []:
            if gallery.GetAlbumName(album) == args["name"]:
                if not gallery.SetCurrentStillAlbum(album):
                    raise ToolError("SetCurrentStillAlbum failed.")
                return {"ok": True, "current": args["name"]}
        raise ToolError(f"Gallery album {args['name']!r} not found.")

    return tools


TOOLS = _build_tools()
