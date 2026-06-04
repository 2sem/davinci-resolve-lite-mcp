# 12 — DeleteClips(ripple=True) wipes the whole track

**Symptom**
`cut_range` (and `delete_timeline_item` with `ripple=true`) left the timeline
**empty**. Removing one clip reported the single clip removed, yet every clip on
the track was gone.

**Cause**
`Timeline.DeleteClips([items], True)` — the documented **ripple delete** — does
not just close the gap on Resolve Lite (verified 20.x): it deletes the whole
track. Reproduced on a plain two-clip timeline `[0..60][60..120]`:

- `DeleteClips([item1], True)` → 0 items (expected `[0..60]`).
- `DeleteClips([item2], True)` → 0 items (expected `[0..60]`).
- `DeleteClips([item], False)` (non-ripple) → correct: removes only that clip,
  leaves a gap.

So **non-ripple delete works**; the `ripple=True` form is broken.

**Fix**
Don't use native ripple delete. Close the gap by hand (`_ripple_remove` in
`tools/editing.py`):

1. Pick the contiguous block to remove `[rstart, rend)` and the downstream
   clips (`GetStart() >= rend`).
2. Capture each downstream clip's source in/out, track and record frame.
3. `DeleteClips(block + downstream, False)` (non-ripple).
4. Re-add the downstream clips via `AppendToTimeline` at `recordFrame - (rend -
   rstart)` — i.e. shifted left to close the gap.

**Caveats of the workaround**
- Re-added downstream clips are fresh timeline items → lose clip-level
  grade / Fusion / transform / retime (same as `split_clip`).
- Only the operated track is shifted, so linked audio on other tracks can
  desync. A grade/sync-faithful ripple would need a full timeline rebuild.
- Downstream clips with no media-pool source (titles/generators/compounds)
  can't be re-added → `_ripple_remove` raises instead of corrupting the
  timeline.

**Verified (2026-06-03):** `cut_range` and `delete_timeline_item(ripple=true)`
now close the gap correctly via `_ripple_remove`; the native ripple path is no
longer used.
