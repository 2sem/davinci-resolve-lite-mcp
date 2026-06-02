"""Mediapool Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
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
            "id": clip.GetUniqueId(),
            "type": clip.GetClipProperty("Type"),
            "duration": clip.GetClipProperty("Duration"),
        }

    clips = [clip_info(c) for c in (folder.GetClipList() or [])]
    result = {"folder": folder.GetName(), "clips": clips}
    if args.get("includeSubfolders"):
        result["subfolders"] = [f.GetName() for f in (folder.GetSubFolderList() or [])]
    return result


@register(
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


@register(
    "delete_clip",
    "Delete media-pool clips by name (current folder) and/or by id (any bin).",
    {
        "type": "object",
        "properties": {
            "names": {"type": "array", "items": {"type": "string"}},
            "ids": {"type": "array", "items": {"type": "string"}},
        },
    },
)
def delete_clip(resolve, args):
    clips = _resolve_clips(resolve, args.get("names"), args.get("ids"))
    mp = _require_project(resolve).GetMediaPool()
    if not mp.DeleteClips(clips):
        raise ToolError("DeleteClips failed.")
    return {"ok": True, "deleted": len(clips)}


@register(
    "get_clip_properties",
    "Read a media-pool clip's properties (by name, from the current folder). "
    "Omit 'property' to return all (resolution, FPS, codec, dates, etc.).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "property": {"type": "string"},
        },
        "required": [],
    },
)
def get_clip_properties(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    prop = args.get("property")
    value = clip.GetClipProperty(prop) if prop else clip.GetClipProperty()
    return {"name": clip.GetName(), "id": clip.GetUniqueId(), "property": prop, "value": value}


@register(
    "set_clip_property",
    "Set a media-pool clip property (by name, from the current folder).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "property": {"type": "string"},
            "value": {"type": ["string", "number", "boolean"]},
        },
        "required": ["property", "value"],
    },
)
def set_clip_property(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.SetClipProperty(args["property"], str(args["value"])):
        raise ToolError(
            f"SetClipProperty({args['property']!r}) failed (unknown/read-only)."
        )
    return {"ok": True, "name": clip.GetName(), "property": args["property"], "value": args["value"]}


@register(
    "get_clip_metadata",
    "Read a media-pool clip's metadata (by name). Omit 'key' to return all "
    "set metadata as a dict.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": [],
    },
)
def get_clip_metadata(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    key = args.get("key")
    value = clip.GetMetadata(key) if key else clip.GetMetadata()
    return {"name": clip.GetName(), "key": key, "value": value}


@register(
    "set_clip_metadata",
    "Set a media-pool clip's metadata key (by name).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "key": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["key", "value"],
    },
)
def set_clip_metadata(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.SetMetadata(args["key"], str(args["value"])):
        raise ToolError(f"SetMetadata({args['key']!r}) failed.")
    return {"ok": True, "name": clip.GetName(), "key": args["key"], "value": args["value"]}


@register(
    "rename_clip",
    "Rename a media-pool clip (by current name, from the current folder).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "newName": {"type": "string"},
        },
        "required": ["newName"],
    },
)
def rename_clip(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.SetName(args["newName"]):
        raise ToolError("SetName failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "get_pool_clip_tags",
    "Return a media-pool clip's color label, flags and markers (by name).",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}, "id": {"type": "string"}},
        "required": [],
    },
)
def get_pool_clip_tags(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    return {
        "name": clip.GetName(),
        "id": clip.GetUniqueId(),
        "clipColor": clip.GetClipColor(),
        "flags": clip.GetFlagList() or [],
        "markers": clip.GetMarkers() or {},
    }


@register(
    "set_pool_clip_color",
    "Set a media-pool clip's color label (by name). Empty 'color' clears it.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "color": {"type": "string"}},
        "required": ["color"],
    },
)
def set_pool_clip_color(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    ok = clip.ClearClipColor() if args["color"] == "" else clip.SetClipColor(args["color"])
    if not ok:
        raise ToolError(f"Setting clip color to {args['color']!r} failed.")
    return {"ok": True, "name": clip.GetName(), "clipColor": clip.GetClipColor()}


@register(
    "add_pool_clip_flag",
    "Add a colored flag to a media-pool clip (by name).",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "color": {"type": "string"}},
        "required": ["color"],
    },
)
def add_pool_clip_flag(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.AddFlag(args["color"]):
        raise ToolError(f"AddFlag({args['color']!r}) failed.")
    return {"ok": True, "name": clip.GetName(), "flags": clip.GetFlagList() or []}


@register(
    "clear_pool_clip_flags",
    "Clear flags from a media-pool clip (by name). 'color' defaults to 'All'.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "color": {"type": "string", "default": "All"}},
        "required": [],
    },
)
def clear_pool_clip_flags(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.ClearFlags(args.get("color", "All")):
        raise ToolError("ClearFlags failed (no matching flag?).")
    return {"ok": True, "name": clip.GetName(), "flags": clip.GetFlagList() or []}


@register(
    "add_pool_clip_marker",
    "Add a marker on a media-pool clip at 'frame' (source frame offset).",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "frame": {"type": "integer"},
            "color": {"type": "string", "default": "Blue"},
            "markerName": {"type": "string", "default": ""},
            "note": {"type": "string", "default": ""},
            "duration": {"type": "integer", "default": 1},
        },
        "required": ["frame"],
    },
)
def add_pool_clip_marker(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
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


@register(
    "delete_pool_clip_marker",
    "Delete marker(s) on a media-pool clip: give 'frame' (source offset) or "
    "'color' ('All' = every marker). Provide exactly one.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "id": {"type": "string"},
            "frame": {"type": "integer"},
            "color": {"type": "string"},
        },
        "required": [],
    },
)
def delete_pool_clip_marker(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
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


@register(
    "add_subfolder",
    "Create a subfolder under the current media pool folder. NOTE: Resolve "
    "makes the new folder the current folder, so call set_current_folder if "
    "you need to add siblings.",
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


@register(
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


@register(
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


@register(
    "move_clips_to_folder",
    "Move clips (by name from the current folder, and/or by id) into a target "
    "folder (by name, searched from the root).",
    {"type": "object", "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
        "ids": {"type": "array", "items": {"type": "string"}},
        "targetFolder": {"type": "string"}},
     "required": ["targetFolder"]},
)
def move_clips_to_folder(resolve, args):
    mp = _require_project(resolve).GetMediaPool()
    clips = _resolve_clips(resolve, args.get("names"), args.get("ids"))
    target = _find_folder(mp, args["targetFolder"])
    if not mp.MoveClips(clips, target):
        raise ToolError("MoveClips failed.")
    return {"ok": True, "moved": len(clips), "to": target.GetName()}


@register(
    "link_proxy",
    "Link a proxy media file to a media-pool clip (by name).",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "proxyPath": {"type": "string"}},
     "required": ["proxyPath"]},
)
def link_proxy(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.LinkProxyMedia(os.path.expanduser(args["proxyPath"])):
        raise ToolError("LinkProxyMedia failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "unlink_proxy",
    "Unlink proxy media from a media-pool clip (by name).",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}}, "required": []},
)
def unlink_proxy(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.UnlinkProxyMedia():
        raise ToolError("UnlinkProxyMedia failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "replace_clip",
    "Replace a media-pool clip's underlying media with another file (by name).",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "filePath": {"type": "string"}},
     "required": ["filePath"]},
)
def replace_clip(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.ReplaceClip(os.path.expanduser(args["filePath"])):
        raise ToolError("ReplaceClip failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "replace_clip_preserve_subclip",
    "Replace a media-pool clip's media (by name) while preserving its subclip "
    "extents.",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "filePath": {"type": "string"}},
     "required": ["filePath"]},
)
def replace_clip_preserve_subclip(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.ReplaceClipPreserveSubClip(os.path.expanduser(args["filePath"])):
        raise ToolError("ReplaceClipPreserveSubClip failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "link_full_resolution_media",
    "Relink a media-pool clip (by name) to full-resolution media at a path.",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}, "filePath": {"type": "string"}},
     "required": ["filePath"]},
)
def link_full_resolution_media(resolve, args):
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not clip.LinkFullResolutionMedia(os.path.expanduser(args["filePath"])):
        raise ToolError("LinkFullResolutionMedia failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "relink_clips",
    "Relink media-pool clips (by name from the current folder, and/or by id) to "
    "media found under a folder path.",
    {"type": "object", "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
        "ids": {"type": "array", "items": {"type": "string"}},
        "folderPath": {"type": "string"}},
     "required": ["folderPath"]},
)
def relink_clips(resolve, args):
    mp = _require_project(resolve).GetMediaPool()
    clips = _resolve_clips(resolve, args.get("names"), args.get("ids"))
    if not mp.RelinkClips(clips, os.path.expanduser(args["folderPath"])):
        raise ToolError("RelinkClips failed.")
    return {"ok": True, "relinked": len(clips)}


@register(
    "move_folders",
    "Move subfolders (by name) of the current folder into a target folder "
    "(by name, searched from the root).",
    {"type": "object", "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
        "targetFolder": {"type": "string"}},
     "required": ["names", "targetFolder"]},
)
def move_folders(resolve, args):
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    parent = mp.GetCurrentFolder()
    if not parent:
        raise ToolError("No current media pool folder.")
    by_name = {f.GetName(): f for f in (parent.GetSubFolderList() or [])}
    missing = [n for n in args["names"] if n not in by_name]
    if missing:
        raise ToolError(f"Subfolders not found: {missing}")
    folders = [by_name[n] for n in args["names"]]
    target = _find_folder(mp, args["targetFolder"])
    if not mp.MoveFolders(folders, target):
        raise ToolError("MoveFolders failed.")
    return {"ok": True, "moved": len(folders), "to": target.GetName()}


@register(
    "get_selected_clips",
    "List currently selected media-pool clips.",
    None,
)
def get_selected_clips(resolve, args):
    project = _require_project(resolve)
    clips = project.GetMediaPool().GetSelectedClips() or []
    return {"selected": [{"name": c.GetName(), "id": c.GetUniqueId()} for c in clips]}


@register(
    "set_selected_clip",
    "Select a media-pool clip (by name) in the current folder.",
    {"type": "object", "properties": {"name": {"type": "string"}, "id": {"type": "string"}}, "required": []},
)
def set_selected_clip(resolve, args):
    project = _require_project(resolve)
    clip = _pool_clip(resolve, args.get("name"), args.get("id"))
    if not project.GetMediaPool().SetSelectedClip(clip):
        raise ToolError("SetSelectedClip failed.")
    return {"ok": True, "name": clip.GetName()}


@register(
    "reveal_in_storage",
    "Reveal a file/folder path in Resolve's Media Storage.",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)
def reveal_in_storage(resolve, args):
    ms = resolve.GetMediaStorage()
    if not ms.RevealInStorage(os.path.expanduser(args["path"])):
        raise ToolError("RevealInStorage failed.")
    return {"ok": True, "path": os.path.expanduser(args["path"])}


@register(
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
