"""Editing Resolve MCP tools."""

import json as _json
import os
import subprocess
import sys

from . import register
from ._helpers import *

_FONT_CACHE = None


def _load_system_fonts():
    """Map {family: [English styles]} from the OS font database (macOS).

    Cached for the server's lifetime — the first call shells out to
    system_profiler (~8s). The App Sandbox on Resolve Lite may deny the
    exec; that surfaces as a clear ToolError rather than a hang.
    """
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE
    if sys.platform != "darwin":
        raise ToolError("list_fonts is macOS-only (uses system_profiler).")
    try:
        # NOT text=True: Resolve's embedded Python uses an ASCII locale, so
        # text mode would decode the (often non-ASCII) font names with ascii
        # and crash. Capture bytes and decode UTF-8 ourselves.
        proc = subprocess.run(
            ["/usr/sbin/system_profiler", "-json", "SPFontsDataType"],
            capture_output=True,
            timeout=30,
        )
    except (PermissionError, OSError) as exc:
        raise ToolError(
            "font enumeration is blocked here (the Resolve Lite App Sandbox "
            f"denies running system_profiler: {type(exc).__name__}). It works "
            "on the non-sandboxed Studio build. Use a font you know is "
            "installed (style 'Regular' is safest)."
        )
    except subprocess.TimeoutExpired:
        raise ToolError(
            "font enumeration timed out (system_profiler took >30s). Use a "
            "font you know is installed (style 'Regular' is safest)."
        )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace")[:160].strip()
        raise ToolError(f"system_profiler failed (rc={proc.returncode}): {err}")
    try:
        data = _json.loads(proc.stdout.decode("utf-8", "replace")).get(
            "SPFontsDataType", []
        )
    except (ValueError, AttributeError) as exc:
        raise ToolError(f"could not parse system_profiler font output: {exc}")
    fams = {}
    for f in data:
        for t in f.get("typefaces", []):
            family = t.get("family")
            if not family:
                continue
            # system_profiler localizes 'style' (e.g. Korean '볼드체'); the
            # English style lives in 'fullname' as "Family Style".
            full = (t.get("fullname") or "").strip()
            if full.lower().startswith(family.lower()):
                style = full[len(family):].strip()
            else:
                style = (t.get("style") or "").strip()
            fams.setdefault(family, set()).add(style or "Regular")
    _FONT_CACHE = {k: sorted(v) for k, v in sorted(fams.items())}
    return _FONT_CACHE


def _playhead_frame(tl, project):
    """Current playhead position as a 0-based timeline frame.

    Timecode and GetStartFrame() are ABSOLUTE (include the start-timecode
    offset, e.g. 01:00:00:00 = 108000), but item.GetStart()/GetEnd() are
    0-based (relative to the timeline start). Subtract the start frame so the
    result is in the same space as the item bounds.

    Drop-frame timecode ('hh:mm:ss;ff', 29.97/59.94) labels skip frame numbers
    each minute except every 10th, so a plain parse over-counts; apply the
    drop-frame correction when ';' is present.
    """
    tc = tl.GetCurrentTimecode() or "00:00:00:00"
    fps = int(round(float(project.GetSetting("timelineFrameRate") or 24)))
    drop = ";" in tc
    parts = tc.replace(";", ":").split(":")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        raise ToolError(f"could not parse current timecode {tc!r}.")
    hh, mm, ss, ff = (int(p) for p in parts)
    abs_frame = ((hh * 60 + mm) * 60 + ss) * fps + ff
    if drop:
        # 2 dropped frames/min at 29.97, 4 at 59.94; none on every 10th minute.
        drop_per_min = round(fps * 0.066666)
        total_minutes = hh * 60 + mm
        abs_frame -= drop_per_min * (total_minutes - total_minutes // 10)
    return abs_frame - (tl.GetStartFrame() or 0)


def _ripple_remove(tl, project, ttype, tidx, removing, rstart, rend):
    """Delete a CONTIGUOUS block [rstart, rend) of items and close the gap.

    Works around a Resolve Lite bug: DeleteClips(items, True) (the native
    ripple delete) wipes the WHOLE track, not just the gap. So we ripple by
    hand: delete the block plus every downstream clip (non-ripple), then
    re-add the downstream clips shifted left by the block length.

    Caveats (documented on the callers): re-added downstream clips are fresh
    timeline items, so they lose clip-level grade/Fusion/transform/retime; and
    only this track is shifted, so linked audio on other tracks can desync.
    """
    if ttype not in ("video", "audio"):
        # AppendToTimeline re-adds only video (mediaType 1) or audio (2); a
        # subtitle clip cannot be re-added to close the gap. Reject up front,
        # before any delete, rather than corrupt the track.
        raise ToolError(
            f"ripple/cut is not supported on {ttype!r} tracks — only video and "
            "audio clips can be shifted to close the gap."
        )
    shift = rend - rstart
    media_type = 1 if ttype == "video" else 2
    items = tl.GetItemListInTrack(ttype, tidx) or []
    downstream = [it for it in items if it.GetStart() >= rend]
    specs = []
    names = [it.GetName() for it in downstream]  # capture before deleting
    for it in downstream:
        mp = it.GetMediaPoolItem()
        if not mp:
            raise ToolError(
                f"cannot ripple-close the gap: downstream clip {it.GetName()!r} "
                "has no media-pool source (title/generator/compound/nested) and "
                "cannot be shifted. Remove without ripple, or move it first."
            )
        src_in = it.GetSourceStartFrame()
        specs.append({
            "mediaPoolItem": mp,
            "startFrame": src_in,
            # exclusive out from duration (GetSourceEndFrame's convention varies
            # and drops a frame on real clips — see split_clip).
            "endFrame": src_in + (it.GetEnd() - it.GetStart()),
            "recordFrame": it.GetStart() - shift,
            "trackIndex": tidx,
            "mediaType": media_type,
        })
    if not tl.DeleteClips(list(removing) + downstream, False):
        raise ToolError("delete failed while rippling.")
    if specs:
        added = project.GetMediaPool().AppendToTimeline(specs) or []
        if len(added) != len(specs):
            raise ToolError(
                f"ripple re-add placed {len(added)}/{len(specs)} downstream "
                "clips — timeline may be inconsistent; undo in Resolve."
            )
    return names


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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


@register(
    "set_timeline_item_name",
    "Rename a timeline clip (the name shown on the timeline, independent of "
    "its underlying media-pool clip name).",
    {
        "type": "object",
        "properties": {**_ITEM_ADDR, "name": {"type": "string"}},
        "required": ["trackType", "trackIndex", "itemIndex", "name"],
    },
)
def set_timeline_item_name(resolve, args):
    item = _track_item(resolve, args)
    if not item.SetName(args["name"]):
        raise ToolError(f"SetName({args['name']!r}) failed.")
    return {"ok": True, "item": item.GetName()}


@register(
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


@register(
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


@register(
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


@register(
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


@register(
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
    if args.get("ripple", False):
        # Native DeleteClips(..., True) wipes the whole track on Resolve Lite,
        # so close the gap by hand (see _ripple_remove).
        project = _require_project(resolve)
        _ripple_remove(tl, project, args["trackType"], args["trackIndex"],
                       [item], item.GetStart(), item.GetEnd())
    elif not tl.DeleteClips([item], False):
        raise ToolError("DeleteClips failed.")
    return {"ok": True, "deleted": name}


@register(
    "insert_title",
    "Insert a title generator into the timeline at the playhead. `title` is "
    "the generator TEMPLATE name (e.g. 'Text', 'Lower Third'), NOT the "
    "displayed text. The on-screen text defaults to 'Basic Title' and cannot "
    "be changed via the Resolve API for basic titles — use "
    "insert_fusion_title ('Text+') if you need custom text.",
    {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Generator template name (e.g. 'Text'), not the displayed text.",
            }
        },
        "required": ["title"],
    },
)
def insert_title(resolve, args):
    tl = _require_timeline(resolve)
    item = tl.InsertTitleIntoTimeline(args["title"])
    if not item:
        raise ToolError(f"InsertTitleIntoTimeline({args['title']!r}) failed (unknown title).")
    return {"ok": True, "inserted": item.GetName()}


@register(
    "insert_fusion_title",
    "Insert a Fusion title into the timeline at the playhead. `title` is the "
    "Fusion title TEMPLATE name (e.g. 'Text+'), NOT the displayed text. "
    "Optionally pass `text` to set the on-screen text: it is written to the "
    "'StyledText' input of every Text+ (TextPlus) node in the title's Fusion "
    "composition. Templates whose text lives in a macro/published input may "
    "not update (response reports how many nodes were set).",
    {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Fusion title template name (e.g. 'Text+'), not the displayed text.",
            },
            "text": {
                "type": "string",
                "description": "Optional on-screen text to write into the title's Text+ node(s).",
            },
        },
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
    out = {"ok": True, "inserted": item.GetName()}
    text = args.get("text")
    if text is not None:
        comp = item.GetFusionCompByIndex(1)
        if not comp:
            raise ToolError(
                f"inserted {args['title']!r} but it has no Fusion composition to set text."
            )
        tools = comp.GetToolList(False, "TextPlus") or {}
        set_count = 0
        for tool in tools.values():
            tool.SetInput("StyledText", text)
            set_count += 1
        out["text"] = text
        out["text_nodes_set"] = set_count
        if set_count == 0:
            out["warning"] = "no Text+ (TextPlus) node found; text not applied."
    return out


@register(
    "set_fusion_title_text",
    "Set the on-screen text of an EXISTING Fusion title already on the "
    "timeline (e.g. one added by insert_fusion_title). Address the clip by "
    "trackType + trackIndex + itemIndex (1-based). Writes 'text' to the "
    "'StyledText' input of every Text+ (TextPlus) node in the clip's Fusion "
    "composition. MCP-original tool: no single Resolve API equivalent (it "
    "composes GetFusionCompByIndex + GetToolList + SetInput). Only works on "
    "Fusion titles; basic titles and non-Fusion clips have no composition.",
    {
        "type": "object",
        "properties": {
            **_ITEM_ADDR,
            "text": {
                "type": "string",
                "description": "On-screen text to write into the title's Text+ node(s).",
            },
        },
        "required": ["trackType", "trackIndex", "itemIndex", "text"],
    },
)
def set_fusion_title_text(resolve, args):
    item = _track_item(resolve, args)
    if item.GetFusionCompCount() < 1:
        raise ToolError(
            f"{item.GetName()!r} has no Fusion composition "
            "(not a Fusion title; basic titles cannot have their text set)."
        )
    comp = item.GetFusionCompByIndex(1)
    tools = comp.GetToolList(False, "TextPlus") or {}
    set_count = 0
    for tool in tools.values():
        tool.SetInput("StyledText", args["text"])
        set_count += 1
    if set_count == 0:
        raise ToolError(
            f"{item.GetName()!r} has a Fusion comp but no Text+ (TextPlus) node "
            "(text may live in a macro/published input); text not applied."
        )
    return {
        "ok": True,
        "item": item.GetName(),
        "text": args["text"],
        "text_nodes_set": set_count,
    }


def _hex_to_rgb(s):
    """'#FFD700' or 'FFD700' -> (r, g, b) floats in 0..1."""
    s = str(s).lstrip("#")
    if len(s) != 6:
        raise ToolError(f"color {s!r} must be a 6-digit hex like '#FFD700'.")
    try:
        r, g, b = (int(s[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        raise ToolError(f"color {s!r} is not valid hex.")
    return r, g, b


@register(
    "style_fusion_title",
    "Style + animate an existing Fusion (Text+) title into an 'awesome "
    "opening' by editing its Fusion node graph. Address the clip by trackType "
    "+ trackIndex + itemIndex (1-based). Best-effort: sets font/size/color on "
    "the Text+ node and (optionally) inserts Background + Glow nodes and a "
    "zoom-in Size keyframe animation. MCP-original tool: composes Fusion "
    "AddTool / ConnectInput / SetInput / BezierSpline. The response reports "
    "which steps applied; steps that fail on a given template are skipped, "
    "not fatal. If the font is a known OS font (per list_fonts) but lacks the "
    "requested style, it errors up front — a bad font otherwise produces an "
    "uncatchable Fusion render error. Only works on Fusion titles (Text+), not "
    "basic titles.",
    {
        "type": "object",
        "properties": {
            **_ITEM_ADDR,
            "font": {"type": "string", "default": "Open Sans",
                     "description": "Font family. MUST be installed AND have the "
                     "chosen 'style', or Fusion fails to render the title "
                     "(e.g. 'Impact' has no Bold). 'Open Sans' Bold is bundled "
                     "with Fusion and always works."},
            "style": {"type": "string", "default": "Bold",
                      "description": "Font style/weight (e.g. Bold, Regular). Must "
                      "exist for the chosen font. Pass '' to leave unset."},
            "size": {"type": "number", "default": 0.13,
                     "description": "Text+ Size (0..1), ~0.12-0.15 for big titles."},
            "color": {"type": "string", "default": "#FFD700",
                      "description": "Text color hex (default gold)."},
            "glow": {"type": "boolean", "default": True,
                     "description": "Insert a Glow node before output (neon)."},
            "background": {"type": "boolean", "default": True,
                           "description": "Composite over a black Background node."},
            "animate": {"type": "boolean", "default": True,
                        "description": "Zoom-in reveal: Size 0 -> size over frames."},
            "animate_frames": {"type": "integer", "default": 30},
        },
        "required": ["trackType", "trackIndex", "itemIndex"],
    },
)
def style_fusion_title(resolve, args):
    item = _track_item(resolve, args)
    if item.GetFusionCompCount() < 1:
        raise ToolError(
            f"{item.GetName()!r} has no Fusion composition (not a Fusion title)."
        )
    comp = item.GetFusionCompByIndex(1)
    texts = list((comp.GetToolList(False, "TextPlus") or {}).values())
    if not texts:
        raise ToolError(
            f"{item.GetName()!r} has no Text+ (TextPlus) node to style."
        )
    tp = texts[0]
    r, g, b = _hex_to_rgb(args.get("color", "#FFD700"))
    applied = []

    def step(name, fn):
        try:
            fn()
            applied.append(name)
        except Exception as exc:  # template-specific; skip, don't fail the call
            applied.append(f"{name}:skipped({type(exc).__name__})")

    font = args.get("font", "Open Sans")
    fstyle = args.get("style", "Bold")

    # Pre-validate the style against the OS font database. A bad combo (e.g.
    # Impact has no Bold) otherwise produces an UNCATCHABLE Fusion render error
    # ("Could not find font: Impact: Bold") — the render runs on Fusion's own
    # thread and never reaches this call. We only validate when the family is
    # present in the OS DB: Fusion also ships its own bundled fonts (e.g. the
    # default "Open Sans") which system_profiler does NOT list, so an absent
    # family is not proof the font is invalid — skip rather than false-reject.
    # Same if enumeration is unavailable (blocked / non-macOS).
    try:
        catalog = _load_system_fonts()
    except ToolError:
        catalog = None
    if catalog is not None and fstyle:
        styles = catalog.get(font)
        if styles is not None and fstyle not in styles:
            raise ToolError(
                f"font {font!r} has no style {fstyle!r} (available: "
                f"{', '.join(styles)}). Pass a listed style, or '' for the "
                "default."
            )

    def set_font():
        tp.SetInput("Font", font)
        if fstyle:  # empty -> leave the font's default style untouched
            tp.SetInput("Style", fstyle)

    comp.Lock()
    try:
        step("font", set_font)
        step("size", lambda: tp.SetInput("Size", args.get("size", 0.13)))
        step("color", lambda: (tp.SetInput("Red1", r), tp.SetInput("Green1", g),
                               tp.SetInput("Blue1", b)))

        # Find the MediaOut and the tool currently feeding it, so we can splice
        # Background/Merge and Glow into the chain without guessing names.
        mouts = list((comp.GetToolList(False, "MediaOut") or {}).values())
        mout = mouts[0] if mouts else None
        upstream = None
        if mout is not None:
            out = mout.FindMainInput(1).GetConnectedOutput()
            upstream = out.GetTool() if out else None

        # Idempotency: re-running must not stack duplicate nodes — but we must
        # only skip OUR own nodes, not unrelated Background/Glow tools that a
        # template (e.g. "Background Reveal") or a hand-edited comp already
        # contains. So we name the nodes we insert and look them up by name,
        # rather than matching any tool of that type in the comp.
        BG_NAME, MERGE_NAME, GLOW_NAME = "MCPStyleBG", "MCPStyleMerge", "MCPStyleGlow"
        ours = lambda name: comp.FindTool(name) is not None

        def added(tool, what):
            # AddTool returns None on failure rather than raising; turn that
            # into an exception so step() reports ':skipped' instead of a
            # silent success on a half-built graph.
            if not tool:
                raise ToolError(f"Fusion AddTool failed for {what}.")
            return tool

        if args.get("background", True) and mout is not None and upstream is not None:
            if ours(MERGE_NAME):
                applied.append("background:exists")
            else:
                def add_bg():
                    bg = added(comp.AddTool("Background"), "Background")
                    bg.SetInput("UseFrameFormatSettings", 1)
                    bg.SetInput("TopLeftRed", 0.0)
                    bg.SetInput("TopLeftGreen", 0.0)
                    bg.SetInput("TopLeftBlue", 0.0)
                    bg.SetInput("TopLeftAlpha", 1.0)
                    mrg = added(comp.AddTool("Merge"), "Merge")
                    mrg.ConnectInput("Background", bg)
                    mrg.ConnectInput("Foreground", upstream)
                    mout.ConnectInput("Input", mrg)
                    # Name LAST: the MCPStyle* marker only attaches once the
                    # node is fully wired, so a partial failure above leaves no
                    # marker and the next run retries cleanly (no false
                    # 'exists', no stacked-but-unwired Merge).
                    bg.SetAttrs({"TOOLS_Name": BG_NAME})
                    mrg.SetAttrs({"TOOLS_Name": MERGE_NAME})
                step("background", add_bg)
                # after splice, the tool feeding MediaOut is now our Merge
                our_mrg = comp.FindTool(MERGE_NAME)
                if our_mrg:
                    upstream = our_mrg

        if args.get("glow", True) and mout is not None and upstream is not None:
            if ours(GLOW_NAME):
                applied.append("glow:exists")
            else:
                def add_glow():
                    glow = added(comp.AddTool("Glow"), "Glow")
                    glow.ConnectInput("Input", upstream)
                    mout.ConnectInput("Input", glow)
                    glow.SetAttrs({"TOOLS_Name": GLOW_NAME})  # name last
                step("glow", add_glow)

        if args.get("animate", True):
            frames = int(args.get("animate_frames", 30))
            target = args.get("size", 0.13)

            def add_anim():
                start = comp.GetAttrs()["COMPN_RenderStart"]
                tp.Size = comp.BezierSpline({})
                tp.Size[start] = 0.0
                tp.Size[start + frames] = target
            step("animate", add_anim)
    finally:
        comp.Unlock()

    return {
        "ok": True,
        "item": item.GetName(),
        "color": args.get("color", "#FFD700"),
        "applied": applied,
    }


@register(
    "list_fonts",
    "List installed font families and their English style/weight names so "
    "titles get a valid Font + Style (avoids Fusion's 'Could not find font' "
    "render error — e.g. 'Impact' has only 'Regular', no 'Bold'). macOS only; "
    "reads the OS font database via system_profiler — first call ~8s, cached "
    "after. NOTE: on the Resolve Lite App Sandbox this may be blocked (works "
    "on Studio); it then returns a clear error. Optional 'family' filters to "
    "families whose name contains it (case-insensitive).",
    {
        "type": "object",
        "properties": {
            "family": {
                "type": "string",
                "description": "Substring filter on family name (case-insensitive).",
            }
        },
        "required": [],
    },
)
def list_fonts(resolve, args):
    fams = _load_system_fonts()
    q = (args.get("family") or "").strip().lower()
    if q:
        fams = {k: v for k, v in fams.items() if q in k.lower()}
    return {"ok": True, "count": len(fams), "fonts": fams}


@register(
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


@register(
    "get_current_video_item",
    "Return the video timeline clip currently under the playhead (name + "
    "track type/index), or null if none.",
    None,
)
def get_current_video_item(resolve, args):
    tl = _require_timeline(resolve)
    item = tl.GetCurrentVideoItem()
    if not item:
        return {"item": None}
    track = item.GetTrackTypeAndIndex() or []
    return {
        "item": item.GetName(),
        "trackType": track[0] if len(track) > 0 else None,
        "trackIndex": track[1] if len(track) > 1 else None,
    }


@register(
    "append_clips_to_timeline",
    "Append media-pool clips to the current timeline, by name (current folder) "
    "and/or by id (any bin).",
    {
        "type": "object",
        "properties": {
            "names": {"type": "array", "items": {"type": "string"}},
            "ids": {"type": "array", "items": {"type": "string"}},
        },
    },
)
def append_clips_to_timeline(resolve, args):
    _require_timeline(resolve)
    clips = _resolve_clips(resolve, args.get("names"), args.get("ids"))
    added = _require_project(resolve).GetMediaPool().AppendToTimeline(clips) or []
    return {"ok": True, "appended": len(added)}


@register(
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


def _split_specs(item, frame):
    """Return (left, right) clipInfo halves for splitting one item at timeline
    `frame`, or None if `frame` isn't strictly inside it. Raises if the item has
    no media-pool source. The out-point comes from the TIMELINE duration, not
    GetSourceEndFrame() (whose inclusive/exclusive convention varies and dropped
    the last frame on real clips); endFrame is exclusive."""
    t_start, t_end = item.GetStart(), item.GetEnd()
    if not (t_start < frame < t_end):
        return None
    mp_item = item.GetMediaPoolItem()
    if not mp_item:
        raise ToolError(
            f"{item.GetName()!r} has no media-pool source (compound/generator/"
            "title?) — cannot split."
        )
    track = item.GetTrackTypeAndIndex() or []
    tidx = track[1] if len(track) > 1 else 1
    mt = 1 if (track and track[0] == "video") else 2
    src_in = item.GetSourceStartFrame()
    src_split = src_in + (frame - t_start)
    src_out = src_in + (t_end - t_start)
    return (
        {"mediaPoolItem": mp_item, "startFrame": src_in, "endFrame": src_split,
         "recordFrame": t_start, "trackIndex": tidx, "mediaType": mt},
        {"mediaPoolItem": mp_item, "startFrame": src_split, "endFrame": src_out,
         "recordFrame": frame, "trackIndex": tidx, "mediaType": mt},
    )


@register(
    "split_clip",
    "Blade/razor a timeline clip into two contiguous clips — like the razor "
    "tool. By default it cuts at the PLAYHEAD on the given track (trackType "
    "defaults to 'video', trackIndex to 1), auto-finding the clip under the "
    "playhead — so the usual flow is just set_timecode then split_clip. "
    "Optional overrides: 'frame' (a 0-based timeline frame — relative to the "
    "timeline start, the same space as get_timeline_item_timing's start/end — "
    "instead of the playhead) and 'itemIndex' (target a specific clip instead of "
    "the one under the playhead). By default ('linked' true) it also splits the "
    "clip's LINKED audio/video at the same frame and re-links the halves (like "
    "the UI razor on a linked clip); set linked=false to split only this track. "
    "MCP-original: Resolve's API has no split/blade, so this deletes each clip "
    "and re-adds its two halves from the same media-pool source at the exact "
    "record frames (no gap). TO CUT (remove a range): split_clip at the start "
    "and end, then delete the middle with delete_timeline_item(ripple=true). "
    "LIMITATIONS: only clips with a media-pool source (titles/generators/"
    "compounds/nested cannot be bladed); the re-added halves are fresh items, so "
    "clip-level grade / Fusion / transform / retime are NOT preserved (linkage "
    "IS restored when linked=true).",
    {
        "type": "object",
        "properties": {
            "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"],
                          "default": "video"},
            "trackIndex": {"type": "integer", "minimum": 1, "default": 1},
            "frame": {"type": "integer",
                      "description": "0-based timeline frame to cut at (relative to timeline start, like get_timeline_item_timing start/end). Default: the playhead."},
            "itemIndex": {"type": "integer", "minimum": 1,
                          "description": "1-based clip on the track. Default: the clip under the cut frame."},
            "linked": {"type": "boolean", "default": True,
                       "description": "Also split linked audio/video at the same frame and re-link the halves. false = this track only."},
        },
        "required": [],
    },
)
def split_clip(resolve, args):
    project = _require_project(resolve)
    tl = _require_timeline(resolve)
    ttype = args.get("trackType", "video")
    tidx = args.get("trackIndex", 1)
    linked = args.get("linked", True)
    frame = args.get("frame")
    if frame is None:
        frame = _playhead_frame(tl, project)

    items = tl.GetItemListInTrack(ttype, tidx) or []
    if args.get("itemIndex") is not None:
        ii = args["itemIndex"]
        if ii < 1 or ii > len(items):
            raise ToolError(f"no item #{ii} on {ttype}{tidx} ({len(items)} item(s)).")
        item = items[ii - 1]
    else:
        item = next((it for it in items if it.GetStart() <= frame < it.GetEnd()), None)
        if item is None:
            raise ToolError(
                f"no clip under frame {frame} on {ttype}{tidx} — move the "
                "playhead onto a clip, or pass 'frame'/'itemIndex'."
            )
    if not (item.GetStart() < frame < item.GetEnd()):
        raise ToolError(
            f"split frame {frame} must be strictly inside the clip "
            f"(timeline {item.GetStart()}..{item.GetEnd()})."
        )
    if not item.GetMediaPoolItem():
        raise ToolError(
            f"{item.GetName()!r} has no media-pool source (compound/generator/"
            "title?) — cannot split."
        )
    name = item.GetName()

    # The group to blade: the target + (if linked) its linked items that also
    # span the cut frame (its synced audio/video).
    group = [item]
    if linked:
        for li in (item.GetLinkedItems() or []):
            if li.GetStart() < frame < li.GetEnd() and li.GetMediaPoolItem():
                group.append(li)

    specs = [s for s in (_split_specs(it, frame) for it in group) if s]
    if not tl.DeleteClips(list(group), False):
        raise ToolError("DeleteClips failed; clip not split.")
    mp = project.GetMediaPool()
    clipinfos = []
    for left, right in specs:
        clipinfos.append(left)
        clipinfos.append(right)
    added = mp.AppendToTimeline(clipinfos) or []
    if len(added) < 2 * len(specs):
        raise ToolError(
            f"split re-add returned {len(added)}/{2 * len(specs)} items — the "
            "originals were already deleted; undo in Resolve to recover."
        )
    # re-add order matches clipinfos: [L0, R0, L1, R1, ...] -> link the lefts
    # together and the rights together to restore the A/V link.
    lefts, rights = added[0::2], added[1::2]
    relinked = False
    if linked and len(lefts) > 1:
        tl.SetClipsLinked(lefts, True)
        tl.SetClipsLinked(rights, True)
        relinked = True
    return {
        "ok": True,
        "split": name,
        "frame": frame,
        "halves": [a.GetName() for a in added],
        "split_items": len(specs),
        "relinked": relinked,
    }


def _track_item_at_playhead(resolve, args):
    """Resolve a timeline item from trackType/trackIndex + optional itemIndex,
    defaulting to the clip under the playhead — the split_clip addressing."""
    project = _require_project(resolve)
    tl = _require_timeline(resolve)
    ttype = args.get("trackType", "video")
    tidx = args.get("trackIndex", 1)
    items = tl.GetItemListInTrack(ttype, tidx) or []
    if args.get("itemIndex") is not None:
        ii = args["itemIndex"]
        if ii < 1 or ii > len(items):
            raise ToolError(f"no item #{ii} on {ttype}{tidx} ({len(items)} item(s)).")
        return tl, items[ii - 1]
    frame = _playhead_frame(tl, project)
    item = next((it for it in items if it.GetStart() <= frame < it.GetEnd()), None)
    if item is None:
        raise ToolError(
            f"no clip under the playhead (frame {frame}) on {ttype}{tidx} — move "
            "the playhead onto a clip or pass itemIndex."
        )
    return tl, item


_XFORM_NODE = "MCPXform"
# Fusion Transform inputs that take a scalar and can be static or keyframed.
_XFORM_SCALARS = {"zoom": "Size", "angle": "Angle"}


def _clip_comp(item):
    """Get (or create) the clip's Fusion composition."""
    comp = (
        item.GetFusionCompByIndex(1)
        if item.GetFusionCompCount() >= 1
        else item.AddFusionComp()
    )
    if not comp:
        raise ToolError(f"could not get/create a Fusion comp on {item.GetName()!r}.")
    return comp


def _apply_xform(comp, xf, item, args):
    """Apply zoom/angle/pan to the Transform node. Each scalar aspect is either
    static (`zoom`) or animated (`zoom_from`+`zoom_to`); pan is set statically on
    Center. Returns a dict describing what changed (with keyframe read-backs)."""
    span = args.get("frames")
    if span is None:
        span = item.GetEnd() - item.GetStart()
    span = max(1, int(span))
    start = (comp.GetAttrs() or {}).get("COMPN_RenderStart", 0)
    changed = {}
    for key, inp in _XFORM_SCALARS.items():
        v_from, v_to, v = args.get(f"{key}_from"), args.get(f"{key}_to"), args.get(key)
        if v_from is not None and v_to is not None:
            setattr(xf, inp, comp.BezierSpline({}))
            getattr(xf, inp)[start] = v_from
            getattr(xf, inp)[start + span] = v_to
            changed[key] = {
                "from": v_from, "to": v_to, "frames": span,
                "readback": [xf.GetInput(inp, start), xf.GetInput(inp, start + span)],
            }
        elif v is not None:
            # Detach any BezierSpline from a previous animate call first —
            # otherwise the spline keeps driving the input and the clip stays
            # animated even though we report a static value. SetInput(name, None)
            # removes the modifier; then set the scalar.
            xf.SetInput(inp, None)
            xf.SetInput(inp, v)
            changed[key] = {
                "value": v,
                "readback": xf.GetInput(inp),
                # equal at both times == truly static (animation cleared).
                "static_check": [xf.GetInput(inp, start), xf.GetInput(inp, start + span)],
            }
    px, py = args.get("pan_x"), args.get("pan_y")
    if px is not None or py is not None:
        cur = xf.GetInput("Center") or {1: 0.5, 2: 0.5}
        x = px if px is not None else cur.get(1, 0.5)
        y = py if py is not None else cur.get(2, 0.5)
        xf.SetInput("Center", {1: x, 2: y})
        changed["pan"] = {"x": x, "y": y}
    return changed


_XFORM_ADDR = {
    "trackType": {"type": "string", "enum": ["video"], "default": "video"},
    "trackIndex": {"type": "integer", "minimum": 1, "default": 1},
    "itemIndex": {"type": "integer", "minimum": 1,
                  "description": "1-based clip on the track. Default: clip under the playhead."},
}
_XFORM_VALUES = {
    "zoom": {"type": "number", "description": "Static scale multiplier (1.0 = 100%)."},
    "zoom_from": {"type": "number", "description": "Animate scale: start (with zoom_to)."},
    "zoom_to": {"type": "number", "description": "Animate scale: end (1.6 = punch to 160%)."},
    "angle": {"type": "number", "description": "Static rotation in degrees."},
    "angle_from": {"type": "number", "description": "Animate rotation: start degrees."},
    "angle_to": {"type": "number", "description": "Animate rotation: end degrees."},
    "pan_x": {"type": "number", "description": "Center X, normalized 0..1 (0.5 = center). Static."},
    "pan_y": {"type": "number", "description": "Center Y, normalized 0..1 (0.5 = center). Static."},
    "frames": {"type": "integer",
               "description": "Animation span from the clip start (default: whole clip)."},
}


@register(
    "insert_clip_fusion_transform",
    "Add a Fusion Transform to a timeline clip — the scriptable way to animate "
    "zoom/pan/rotate (the Edit-page transform cannot be keyframed via the API). "
    "Targets the clip under the PLAYHEAD by default (trackType 'video', "
    "trackIndex 1; pass itemIndex to override). Adds a Transform node named "
    f"{_XFORM_NODE!r} spliced before MediaOut; errors if one already exists "
    "(use edit_clip_fusion_transform to change it). Optionally set initial "
    "values: zoom/angle (static) or zoom_from+zoom_to / angle_from+angle_to "
    "(animated over 'frames'), and pan_x/pan_y (Center, normalized 0..1). "
    "Units: zoom = multiplier (1.0=100%), pan = 0..1 frame fraction, angle = "
    "degrees. NOTE: adds a Fusion comp; the move lives in the Fusion layer, so "
    "the Edit-page Inspector ZoomX/ZoomY will NOT reflect it.",
    {"type": "object", "properties": {**_XFORM_ADDR, **_XFORM_VALUES}, "required": []},
)
def insert_clip_fusion_transform(resolve, args):
    tl, item = _track_item_at_playhead(resolve, args)
    comp = _clip_comp(item)
    comp.Lock()
    try:
        if comp.FindTool(_XFORM_NODE) is not None:
            raise ToolError(
                f"{item.GetName()!r} already has a {_XFORM_NODE} transform — use "
                "edit_clip_fusion_transform to change it, or "
                "remove_clip_fusion_transform first."
            )
        # Find MediaOut BEFORE adding anything, so a malformed comp (no
        # MediaOut) fails without leaving an orphan Transform that a retry
        # would stack on.
        mouts = list((comp.GetToolList(False, "MediaOut") or {}).values())
        mout = mouts[0] if mouts else None
        if mout is None:
            raise ToolError("no MediaOut in the clip's Fusion comp.")
        out = mout.FindMainInput(1).GetConnectedOutput()
        upstream = out.GetTool() if out else None
        xf = comp.AddTool("Transform")
        if not xf:
            raise ToolError("Fusion AddTool('Transform') failed.")
        if upstream is not None:
            xf.ConnectInput("Input", upstream)
        mout.ConnectInput("Input", xf)
        xf.SetAttrs({"TOOLS_Name": _XFORM_NODE})  # name last = fully wired marker
        changed = _apply_xform(comp, xf, item, args)
    finally:
        comp.Unlock()
    return {"ok": True, "item": item.GetName(), "node": _XFORM_NODE,
            "inserted": True, "changed": changed}


@register(
    "edit_clip_fusion_transform",
    "Change the Fusion Transform added by insert_clip_fusion_transform on a "
    "timeline clip. Targets the clip under the PLAYHEAD by default. Each aspect "
    "is static (zoom / angle) or animated (zoom_from+zoom_to / angle_from+"
    "angle_to over 'frames'); pan_x/pan_y set Center (normalized 0..1). Zoom = "
    "multiplier (1.0=100%), angle = degrees. Errors if the clip has no "
    f"{_XFORM_NODE} transform yet (insert it first). Re-runnable.",
    {"type": "object", "properties": {**_XFORM_ADDR, **_XFORM_VALUES}, "required": []},
)
def edit_clip_fusion_transform(resolve, args):
    tl, item = _track_item_at_playhead(resolve, args)
    if item.GetFusionCompCount() < 1:
        raise ToolError(f"{item.GetName()!r} has no Fusion comp — insert first.")
    comp = item.GetFusionCompByIndex(1)
    comp.Lock()
    try:
        xf = comp.FindTool(_XFORM_NODE)
        if xf is None:
            raise ToolError(
                f"{item.GetName()!r} has no {_XFORM_NODE} transform — use "
                "insert_clip_fusion_transform first."
            )
        changed = _apply_xform(comp, xf, item, args)
    finally:
        comp.Unlock()
    if not changed:
        raise ToolError("nothing to change — pass zoom/angle/pan values.")
    return {"ok": True, "item": item.GetName(), "node": _XFORM_NODE, "changed": changed}


@register(
    "remove_clip_fusion_transform",
    "Remove the Fusion Transform added by insert_clip_fusion_transform from a "
    "timeline clip, restoring the chain (its upstream reconnects to MediaOut). "
    "Targets the clip under the PLAYHEAD by default. Errors if there is no "
    f"{_XFORM_NODE} transform. (The Fusion comp itself stays on the clip.)",
    {"type": "object", "properties": dict(_XFORM_ADDR), "required": []},
)
def remove_clip_fusion_transform(resolve, args):
    tl, item = _track_item_at_playhead(resolve, args)
    if item.GetFusionCompCount() < 1:
        raise ToolError(f"{item.GetName()!r} has no Fusion comp.")
    comp = item.GetFusionCompByIndex(1)
    comp.Lock()
    try:
        xf = comp.FindTool(_XFORM_NODE)
        if xf is None:
            raise ToolError(f"{item.GetName()!r} has no {_XFORM_NODE} transform.")
        # reconnect the Transform's upstream straight to MediaOut, then delete.
        mouts = list((comp.GetToolList(False, "MediaOut") or {}).values())
        mout = mouts[0] if mouts else None
        out = xf.FindMainInput(1).GetConnectedOutput()
        upstream = out.GetTool() if out else None
        if mout is not None and upstream is not None:
            mout.ConnectInput("Input", upstream)
        xf.Delete()
    finally:
        comp.Unlock()
    return {"ok": True, "item": item.GetName(), "removed": _XFORM_NODE}


@register(
    "cut_range",
    "Cut (remove) a timeline frame range [begin, end) on a track and close the "
    "gap — like marking in/out and doing a ripple delete. begin/end are 0-based "
    "timeline frames (same space as get_timeline_item_timing start/end). "
    "trackType defaults to 'video', trackIndex to 1. Composes split_clip: it "
    "blades at begin and end, removes every clip fully inside the range, and "
    "closes the gap by shifting later clips left by end-begin. (Resolve's "
    "native ripple delete wipes the whole track via the API, so the shift is "
    "done by re-adding the downstream clips — see fallbacks/12.) LIMITATIONS: "
    "clips must have a media-pool source (titles/generators/compounds/nested "
    "cannot be bladed or shifted); the cut and the shifted downstream clips "
    "become fresh items, losing clip-level grade/Fusion/transform/retime; and "
    "only this track shifts, so linked audio on other tracks can desync.",
    {
        "type": "object",
        "properties": {
            "begin": {"type": "integer",
                      "description": "0-based timeline frame where the removed range starts."},
            "end": {"type": "integer",
                    "description": "0-based timeline frame where the removed range ends (exclusive)."},
            "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"],
                          "default": "video"},
            "trackIndex": {"type": "integer", "minimum": 1, "default": 1},
        },
        "required": ["begin", "end"],
    },
)
def cut_range(resolve, args):
    tl = _require_timeline(resolve)
    ttype = args.get("trackType", "video")
    tidx = args.get("trackIndex", 1)
    begin, end = args["begin"], args["end"]
    if ttype not in ("video", "audio"):
        raise ToolError(
            f"cut_range is not supported on {ttype!r} tracks — only video and "
            "audio clips can be bladed and shifted."
        )
    if begin < 0:
        raise ToolError(f"begin ({begin}) must be >= 0.")
    if begin >= end:
        raise ToolError(f"begin ({begin}) must be < end ({end}).")

    # Preflight every clip the cut will touch BEFORE mutating anything, so a
    # non-bladeable clip can't leave the timeline half-modified (with the first
    # boundary already split and its grade/Fusion lost): the clips spanning
    # begin/end must be bladeable, and every downstream clip must be shiftable —
    # all need a media-pool source.
    pre = tl.GetItemListInTrack(ttype, tidx) or []
    for f in (begin, end):
        span = next((it for it in pre if it.GetStart() < f < it.GetEnd()), None)
        if span is not None and not span.GetMediaPoolItem():
            raise ToolError(
                f"cannot cut: the clip spanning frame {f} ({span.GetName()!r}) "
                "has no media-pool source (title/generator/compound/nested) and "
                "cannot be bladed."
            )
    for it in pre:
        if it.GetStart() >= end and not it.GetMediaPoolItem():
            raise ToolError(
                f"cannot cut: downstream clip {it.GetName()!r} (after frame "
                f"{end}) has no media-pool source and cannot be shifted to close "
                "the gap."
            )

    # Blade at each boundary — but only where a clip STRICTLY spans the frame.
    # A frame that already sits on an edit point, on the track tail, or in a
    # gap has no spanning clip and needs no split (e.g. end == last clip's end
    # when removing the final clip).
    for f in (begin, end):
        items = tl.GetItemListInTrack(ttype, tidx) or []
        if any(it.GetStart() < f < it.GetEnd() for it in items):
            # linked=False: cut_range ripples a single track; let it manage
            # only this track's clips, not drag linked audio into the blade.
            split_clip(resolve, {"trackType": ttype, "trackIndex": tidx,
                                 "frame": f, "linked": False})

    items = tl.GetItemListInTrack(ttype, tidx) or []
    to_remove = [it for it in items if begin <= it.GetStart() and it.GetEnd() <= end]
    if not to_remove:
        raise ToolError(
            f"no clip fully inside [{begin}, {end}) to remove (empty range, a "
            "gap, or a non-bladeable clip at a boundary)."
        )
    names = [it.GetName() for it in to_remove]
    project = _require_project(resolve)
    shifted = _ripple_remove(tl, project, ttype, tidx, to_remove, begin, end)
    return {
        "ok": True,
        "removed": names,
        "rippledDownstream": shifted,
        "begin": begin,
        "end": end,
        "removedFrames": end - begin,
    }


@register(
    "detect_scene_cuts",
    "Detect and apply scene cuts along the current timeline. NOTE: Scene Cut "
    "Detection is a Studio-only feature; on the free edition this opens the "
    "upgrade dialog and returns an error.",
    None,
)
def detect_scene_cuts(resolve, args):
    _require_studio(resolve)  # gated: pops the upgrade dialog on free Lite
    tl = _require_timeline(resolve)
    if not tl.DetectSceneCuts():
        raise ToolError("DetectSceneCuts failed.")
    return {"ok": True}


@register(
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


@register(
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


@register(
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


@register(
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
