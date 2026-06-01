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
        ok = resolve.OpenPage(page)
        return {"ok": bool(ok), "page": page}

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
        ok = tl.SetCurrentTimecode(args["timecode"])
        return {"ok": bool(ok), "timecode": tl.GetCurrentTimecode()}

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
        if args.get("jobId"):
            if not project.DeleteRenderJob(args["jobId"]):
                raise ToolError(f"DeleteRenderJob({args['jobId']!r}) failed.")
            return {"ok": True, "deleted": args["jobId"]}
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

    return tools


TOOLS = _build_tools()
