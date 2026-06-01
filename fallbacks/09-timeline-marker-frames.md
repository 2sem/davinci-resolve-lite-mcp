# 09 — Timeline markers: absolute frames, start-frame rejected, misleading error

**Symptom**
`add_timeline_marker` fails with "AddMarker failed (a marker may already exist
at that frame)" even when `get_timeline_markers` shows the timeline has **no**
markers — e.g. at frame 108000 on a timeline whose start is 108000.

**Cause**
`Timeline.AddMarker(frameId, ...)` takes an **absolute timeline frame**, not a
0-based offset. The marker must land on actual content and **not** at the very
start frame: a frame `< startFrame`, or exactly `== startFrame`, is rejected and
returns False. The tool's generic message ("may already exist") is misleading —
the real cause is an out-of-range / start-frame position. Use a frame strictly
inside the content, e.g. `get_timeline_info().startFrame + N` (N ≥ 1). Markers
added via the Resolve UI at the start frame exist, but the scripting API will
not re-create one there.

**Fix / guidance**
- Compute marker frames from `get_timeline_info().startFrame` (+ a small offset),
  not from 0.
- `get_timeline_markers` (added alongside this note) lists current markers so you
  can pick a free, in-range frame.

**Process lesson (data loss)**
`delete_timeline_marker {"color": "All"}` (`DeleteMarkersByColor("All")`)
permanently clears **every** marker on the *current* timeline. Ad-hoc
diagnostics must switch to a throwaway/scratch timeline first — running clear-all
against the user's real timeline destroyed a UI-created start-frame marker that
could not be restored via the API (start-frame markers aren't addable). The
live test suite already isolates to a scratch timeline; manual curl checks must
do the same.

**Commit** get_timeline_markers (PR #17)
