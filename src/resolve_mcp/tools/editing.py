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
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace")[:160].strip()
        raise ToolError(f"system_profiler failed (rc={proc.returncode}): {err}")
    data = _json.loads(proc.stdout.decode("utf-8", "replace")).get(
        "SPFontsDataType", []
    )
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
    if not tl.DeleteClips([item], bool(args.get("ripple", False))):
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
    "not fatal. Only works on Fusion titles (Text+), not basic titles.",
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

        if args.get("background", True) and mout is not None and upstream is not None:
            def add_bg():
                bg = comp.AddTool("Background")
                bg.SetInput("UseFrameFormatSettings", 1)
                bg.SetInput("TopLeftRed", 0.0)
                bg.SetInput("TopLeftGreen", 0.0)
                bg.SetInput("TopLeftBlue", 0.0)
                bg.SetInput("TopLeftAlpha", 1.0)
                mrg = comp.AddTool("Merge")
                mrg.ConnectInput("Background", bg)
                mrg.ConnectInput("Foreground", upstream)
                mout.ConnectInput("Input", mrg)
            step("background", add_bg)
            # after splice, the tool feeding MediaOut is now the Merge
            mrg_list = list((comp.GetToolList(False, "Merge") or {}).values())
            if mrg_list:
                upstream = mrg_list[-1]

        if args.get("glow", True) and mout is not None and upstream is not None:
            def add_glow():
                glow = comp.AddTool("Glow")
                glow.ConnectInput("Input", upstream)
                mout.ConnectInput("Input", glow)
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
