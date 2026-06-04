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


# ---- editing (operate on scratch V1 item #1) ----
@test("add_clip_to_timeline")
def _():
    goto_scratch(); s = src_required()
    n0 = len(call("get_track_items", trackType="video", index=1)["items"])
    call("add_clip_to_timeline", name=s, startFrame=0, endFrame=30, recordFrame=300)
    n1 = len(call("get_track_items", trackType="video", index=1)["items"])
    need(n1 == n0 + 1)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n1)

@test("append_clips_to_timeline")
def _():
    goto_scratch(); s = src_required()
    r = call("append_clips_to_timeline", names=[s]); need(r["appended"] >= 1)
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("delete_timeline_item")
def _():
    goto_scratch(); s = src_required()
    call("append_clips_to_timeline", names=[s])
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    need(call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)["ok"])

@test("split_clip")
def _():
    goto_scratch(); src_required()
    items = call("get_track_items", trackType="video", index=1)["items"]
    need(len(items) >= 1)
    t = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    start, end = t["start"], t["end"]
    need(end - start >= 4)
    mid = start + (end - start) // 2
    n0 = len(items)
    # explicit frame + itemIndex override; linked=False to test this track only
    r = call("split_clip", trackType="video", trackIndex=1, itemIndex=1, frame=mid, linked=False)
    need(len(r["halves"]) == 2); need(r["frame"] == mid)
    n1 = len(call("get_track_items", trackType="video", index=1)["items"])
    need(n1 == n0 + 1)
    # contiguity: halves cover the original range with no gap/overlap.
    a = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    b = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=2)
    need(a["start"] == start); need(b["start"] == a["end"]); need(b["end"] == end)
    # cleanup: remove the two new halves
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=2)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=1)

@test("split_clip_at_playhead")
def _():
    # Default mode: cut at the playhead, auto-finding the clip — no frame/index.
    goto_scratch(); src_required()
    t = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    start, end = t["start"], t["end"]
    need(end - start >= 4)
    mid = start + (end - start) // 2
    fps = int(round(float(call("get_project_info")["framerate"])))
    absf = call("get_timeline_info")["startFrame"] + mid  # timecode is absolute
    hh, rem = divmod(absf, 3600 * fps)
    mm, rem = divmod(rem, 60 * fps)
    ss, ff = divmod(rem, fps)
    call("set_timecode", timecode=f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}")
    r = call("split_clip", trackType="video", trackIndex=1, linked=False)  # playhead + auto-find
    need(len(r["halves"]) == 2); need(r["frame"] == mid)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=2)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=1)

@test("split_clip_linked")
def _():
    # Default linked=true: blading a clip with linked audio splits BOTH tracks
    # at the same frame and re-links the halves.
    goto_scratch(); src_required()
    v0 = call("get_track_items", trackType="video", index=1)["items"]
    a0 = call("get_track_items", trackType="audio", index=1)["items"]
    if not a0:
        raise Skip("scratch clip has no linked audio on A1")
    t = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    mid = t["start"] + (t["end"] - t["start"]) // 2
    r = call("split_clip", trackType="video", trackIndex=1, frame=mid)  # linked default
    need(r["split_items"] >= 2)   # video + its linked audio
    need(r["relinked"])
    v1 = call("get_track_items", trackType="video", index=1)["items"]
    a1 = call("get_track_items", trackType="audio", index=1)["items"]
    need(len(v1) == len(v0) + 1)  # video bladed
    need(len(a1) == len(a0) + 1)  # linked audio bladed too
    # cleanup: drop the new halves on both tracks
    for tt in ("video", "audio"):
        n = len(call("get_track_items", trackType=tt, index=1)["items"])
        for i in range(n, 0, -1):
            call("delete_timeline_item", trackType=tt, trackIndex=1, itemIndex=i)

@test("cut_range")
def _():
    goto_scratch(); src_required()
    t = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    start, end = t["start"], t["end"]
    need(end - start >= 8)
    a = start + (end - start) // 4
    b = start + (end - start) // 2
    r = call("cut_range", begin=a, end=b)  # remove [a, b), ripple-close
    need(r["removedFrames"] == b - a)
    items = call("get_track_items", trackType="video", index=1)["items"]
    # remaining clips contiguous from start, total length reduced by (b - a)
    last = call("get_timeline_item_timing", trackType="video", trackIndex=1,
                itemIndex=len(items))
    first = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    need(first["start"] == start)
    need(last["end"] == end - (b - a))  # ripple shifted the tail left
    for i in range(1, len(items)):
        ti = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=i)
        tj = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=i + 1)
        need(tj["start"] == ti["end"])  # no gaps
    # cleanup
    for i in range(len(items), 0, -1):
        call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=i)

@test("cut_range_tail")
def _():
    # end == the last clip's end (cut through the tail) must NOT error on the
    # missing edit point — that boundary already exists.
    goto_scratch(); src_required()
    t = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=1)
    start, end = t["start"], t["end"]
    need(end - start >= 8)
    a = start + (end - start) // 2
    r = call("cut_range", begin=a, end=end)  # remove the tail half
    need(r["removedFrames"] == end - a)
    items = call("get_track_items", trackType="video", index=1)["items"]
    last = call("get_timeline_item_timing", trackType="video", trackIndex=1, itemIndex=len(items))
    need(last["end"] == a)  # timeline now ends where the cut began
    for i in range(len(items), 0, -1):
        call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=i)

@test("clip_fusion_transform")
def _():
    # insert -> edit (animated zoom + angle, static pan) -> remove, with
    # keyframe read-backs and CRUD-guard checks.
    goto_scratch(); src_required()
    A = dict(trackType="video", trackIndex=1, itemIndex=1)
    r = call("insert_clip_fusion_transform", **A)
    need(r["inserted"]); need(r["node"] == "MCPXform")
    z = call("edit_clip_fusion_transform", **A, zoom_from=1.0, zoom_to=1.6, frames=20)["changed"]["zoom"]
    need(z["readback"] == [1.0, 1.6])  # spline really took
    a = call("edit_clip_fusion_transform", **A, angle_from=0, angle_to=20, frames=20)["changed"]["angle"]
    need(a["readback"] == [0.0, 20.0])
    p = call("edit_clip_fusion_transform", **A, pan_x=0.65)["changed"]["pan"]
    need(p["x"] == 0.65)
    # animate -> static must clear the spline (no lingering animation).
    s = call("edit_clip_fusion_transform", **A, zoom=1.3)["changed"]["zoom"]
    need(s["static_check"] == [1.3, 1.3])
    err("insert_clip_fusion_transform", **A)            # already exists -> error
    need(call("remove_clip_fusion_transform", **A)["removed"] == "MCPXform")
    err("edit_clip_fusion_transform", **A, zoom=1.2)    # gone -> error
    _delete_last_video_item()

def _delete_last_video_item():
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    if n >= 1:
        call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("insert_title")
def _():
    goto_scratch(); call("set_timecode", timecode=call("get_timecode")["timecode"])
    try:
        call("insert_title", title="Text"); _delete_last_video_item()
    except AssertionError:
        raise Skip("'Text' title not available")

@test("insert_fusion_title")
def _():
    goto_scratch()
    call("insert_fusion_title", title="Text+"); _delete_last_video_item()

@test("insert_fusion_title_with_text")
def _():
    goto_scratch()
    r = call("insert_fusion_title", title="Text+", text="GameHelper")
    need(r["text"] == "GameHelper"); need(r["text_nodes_set"] >= 1)
    _delete_last_video_item()

@test("set_fusion_title_text")
def _():
    goto_scratch()
    call("insert_fusion_title", title="Text+")
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    r = call("set_fusion_title_text", trackType="video", trackIndex=1,
             itemIndex=n, text="GameHelper")
    need(r["text"] == "GameHelper"); need(r["text_nodes_set"] >= 1)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("style_fusion_title")
def _():
    goto_scratch()
    call("insert_fusion_title", title="Text+", text="GameHelper")
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    r = call("style_fusion_title", trackType="video", trackIndex=1, itemIndex=n,
             font="Open Sans", style="Bold", size=0.14, color="#FFD700",
             glow=True, background=True, animate=True, animate_frames=30)
    # core text styling must apply; node-graph steps may skip per template.
    for core in ("font", "size", "color"):
        need(core in r["applied"])
    # idempotent: styling the same clip again must not stack bg/glow nodes.
    if "background" in r["applied"] or "glow" in r["applied"]:
        r2 = call("style_fusion_title", trackType="video", trackIndex=1, itemIndex=n,
                  font="Open Sans", style="Bold", background=True, glow=True, animate=False)
        if "background" in r["applied"]:
            need("background:exists" in r2["applied"])
        if "glow" in r["applied"]:
            need("glow:exists" in r2["applied"])
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("style_fusion_title_template_bg")
def _():
    # A template that already ships a Background/Glow node must NOT false-trip
    # the idempotency guard — our styling must still apply on the first call.
    goto_scratch()
    try:
        call("insert_fusion_title", title="Background Reveal", text="GameHelper")
    except AssertionError:
        raise Skip("'Background Reveal' template not available")
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    r = call("style_fusion_title", trackType="video", trackIndex=1, itemIndex=n,
             font="Open Sans", style="Bold", background=True, glow=True, animate=False)
    # first-ever style of this clip: our nodes did not exist yet, so they must
    # be ADDED (not reported as :exists) despite the template's own Background.
    need("background" in r["applied"]); need("background:exists" not in r["applied"])
    need("glow" in r["applied"]); need("glow:exists" not in r["applied"])
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("style_fusion_title_bad_font")
def _():
    # An invalid font+style (Impact has no Bold) must error up front, not
    # silently produce an uncatchable Fusion render failure. Validation only
    # works when font enumeration is available AND Impact is an OS font without
    # a Bold face — otherwise the tool intentionally skips the check, so skip
    # the test too rather than expect an error it cannot produce.
    try:
        styles = call("list_fonts", family="Impact")["fonts"].get("Impact")
    except AssertionError as e:
        raise Skip(f"font enumeration unavailable: {str(e)[:60]}")
    if not styles or "Bold" in styles:
        raise Skip("Impact not installed, or has a Bold face here")
    goto_scratch()
    call("insert_fusion_title", title="Text+", text="GameHelper")
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    msg = err("style_fusion_title", trackType="video", trackIndex=1, itemIndex=n,
              font="Impact", style="Bold", background=False, glow=False, animate=False)
    need("Impact" in msg and "Bold" in msg)
    call("delete_timeline_item", trackType="video", trackIndex=1, itemIndex=n)

@test("list_fonts")
def _():
    try:
        r = call("list_fonts", family="Arial")
    except AssertionError as e:
        raise Skip(f"font enumeration unavailable: {str(e)[:60]}")
    need(r["ok"]); need("Arial" in r["fonts"])
    need("Regular" in r["fonts"]["Arial"])  # English style, not localized

@test("insert_generator")
def _():
    goto_scratch()
    try:
        call("insert_generator", name="Solid Color"); _delete_last_video_item()
    except AssertionError:
        raise Skip("'Solid Color' generator not available")

@test("create_compound_clip")
def _():
    goto_scratch(); src_required()
    items = call("get_track_items", trackType="video", index=1)["items"]
    need(len(items) >= 1)
    name = call("create_compound_clip", trackType="video", trackIndex=1,
                itemIndices=[1], name="__mcp_comp")["created"]
    _delete_last_video_item()
    try:
        call("delete_clip", names=[name])
    except AssertionError:
        pass

@test("create_fusion_clip")
def _():
    goto_scratch(); src_required()
    call("append_clips_to_timeline", names=[CTX["src"]])
    n = len(call("get_track_items", trackType="video", index=1)["items"])
    call("create_fusion_clip", trackType="video", trackIndex=1, itemIndices=[n])
    _delete_last_video_item()

@test("get_timeline_item_property")
def _():
    goto_scratch(); need("value" in call("get_timeline_item_property", VID1 | {"property": "ZoomX"}))

@test("set_timeline_item_property")
def _():
    goto_scratch()
    call("set_timeline_item_property", VID1 | {"property": "ZoomX", "value": 1.2})
    call("set_timeline_item_property", VID1 | {"property": "ZoomX", "value": 1.0})

@test("get_timeline_item_timing")
def _():
    goto_scratch(); need("sourceStartFrame" in call("get_timeline_item_timing", VID1))

@test("get_current_video_item")
def _():
    goto_scratch(); call("set_timecode", timecode=call("get_timecode")["timecode"])
    need("item" in call("get_current_video_item"))

@test("set_clip_enabled")
def _():
    goto_scratch()
    call("set_clip_enabled", VID1 | {"enabled": False})
    call("set_clip_enabled", VID1 | {"enabled": True})

@test("get_clip_tags")
def _():
    goto_scratch(); need("clipColor" in call("get_clip_tags", VID1))

@test("set_clip_color")
def _():
    goto_scratch()
    call("set_clip_color", VID1 | {"color": "Orange"}); call("set_clip_color", VID1 | {"color": ""})

@test("add_clip_flag")
def _():
    goto_scratch(); call("add_clip_flag", VID1 | {"color": "Blue"}); call("clear_clip_flags", VID1)

@test("clear_clip_flags")
def _():
    goto_scratch(); call("add_clip_flag", VID1 | {"color": "Red"})
    need(call("clear_clip_flags", VID1)["ok"])

def _clear_clip_markers():
    try:
        call("delete_clip_marker", VID1 | {"color": "All"})
    except AssertionError:
        pass

@test("add_clip_marker")
def _():
    goto_scratch(); _clear_clip_markers()
    try:
        call("add_clip_marker", VID1 | {"frame": 10, "color": "Green"})
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    call("delete_clip_marker", VID1 | {"color": "All"})

@test("delete_clip_marker")
def _():
    goto_scratch(); _clear_clip_markers()
    try:
        call("add_clip_marker", VID1 | {"frame": 12})
    except AssertionError as e:
        skip_if(e, "AddMarker failed", MARKER_FLAKE)
    need(call("delete_clip_marker", VID1 | {"frame": 12})["ok"])
