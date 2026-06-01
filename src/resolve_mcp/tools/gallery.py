"""Gallery Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
    "get_gallery_stills_count",
    "Return how many stills are in the current gallery album.",
    None,
)
def get_gallery_stills_count(resolve, args):
    album = _current_still_album(resolve)
    return {"count": len(album.GetStills() or [])}


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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


@register(
    "list_powergrade_albums",
    "List PowerGrade albums in the gallery.",
    None,
)
def list_powergrade_albums(resolve, args):
    gallery = _require_gallery(resolve)
    albums = gallery.GetGalleryPowerGradeAlbums() or []
    return {"albums": [gallery.GetAlbumName(a) for a in albums]}


@register(
    "create_powergrade_album",
    "Create a new PowerGrade album. Optional 'name' to label it.",
    {"type": "object", "properties": {"name": {"type": "string"}}},
)
def create_powergrade_album(resolve, args):
    gallery = _require_gallery(resolve)
    album = gallery.CreateGalleryPowerGradeAlbum()
    if not album:
        raise ToolError("CreateGalleryPowerGradeAlbum failed.")
    if args.get("name"):
        gallery.SetAlbumName(album, args["name"])
    return {"ok": True, "album": gallery.GetAlbumName(album)}


@register(
    "grab_all_stills",
    "Grab a still from every clip in the current timeline. source 1 = first "
    "frame, 2 = middle frame.",
    {"type": "object", "properties": {"source": {"type": "integer", "enum": [1, 2], "default": 1}}},
)
def grab_all_stills(resolve, args):
    tl = _require_timeline(resolve)
    stills = tl.GrabAllStills(args.get("source", 1)) or []
    return {"ok": True, "grabbed": len(stills)}


@register(
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


@register(
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


@register(
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
