# 11 — TimelineItem frames are 0-based, but timecode is absolute

**Symptom**
`split_clip` in playhead mode reported "no clip under frame 108000" and a
hand-built `set_timecode("00:00:01:00")` was rejected as "out of timeline
range", even though the clip was clearly under the playhead.

**Cause**
Two different frame coordinate systems on the same timeline:

- `TimelineItem.GetStart()` / `GetEnd()` are **0-based** — relative to the
  timeline start. A clip at the very start reports `start = 0`.
- `Timeline.GetStartFrame()`, `GetCurrentTimecode()` and markers are
  **absolute** — they include the start-timecode offset. A timeline whose start
  timecode is `01:00:00:00` has `GetStartFrame() = 108000` (at 30 fps), and its
  playhead timecode runs `01:00:00:00`+, not `00:00:00:00`.

So converting the current timecode straight to frames gives an absolute number
(108000+) that does **not** match `item.GetStart()` (0..n). Comparing them finds
no clip; building a `00:00:..` timecode lands before the timeline start.

**Fix**
When you need a playhead position in the same space as `item.GetStart()`,
subtract the start frame:

```python
abs_frame = tc_to_frames(tl.GetCurrentTimecode(), fps)
rel_frame = abs_frame - (tl.GetStartFrame() or 0)   # 0-based, matches items
```

And when building a timecode to seek to a 0-based item frame, add the start
frame back before formatting (`absf = startFrame + rel_frame`).

**Related:** fallback 09 (markers take an **absolute** frame). Markers and
`GetStartFrame()` live in absolute space; `TimelineItem` bounds live in 0-based
space — don't mix them.

**Verified (2026-06-03):** scratch timeline start `01:00:00:00`
(`GetStartFrame() = 108000`), clip `GetStart()/GetEnd() = 0/60`. `split_clip` at
the playhead now finds the clip and cuts at the correct 0-based frame.
