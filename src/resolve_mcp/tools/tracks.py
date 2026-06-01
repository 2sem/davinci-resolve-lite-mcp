"""Tracks Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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
