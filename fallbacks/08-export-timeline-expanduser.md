# 08 — `export_timeline` fails with a `~` path

**Symptom**
`export_timeline {"filePath": "~/Movies/x.fcpxml", ...}` → `Timeline Export
failed.` The same call with an absolute path (`/Users/<me>/Movies/x.fcpxml`)
succeeds.

**Cause**
`Timeline.Export()` does not expand `~`; it received the literal tilde path and
failed. The `export_current_frame_as_still` tool already expanded `~`, but
`export_timeline` did not — the inconsistency hid the bug until that tool was
tested.

**Fix**
Expand and create the directory before exporting (same as the still tool):
```python
path = os.path.expanduser(args["filePath"])
os.makedirs(os.path.dirname(path), exist_ok=True)
ok = tl.Export(path, etype, resolve.EXPORT_NONE)
```
Lesson: every tool that takes a filesystem path must `expanduser` (and usually
`makedirs`) it. (Sandbox note: `~` inside Resolve maps to the container, which
is itself mapped to the real `~/Movies` for the movies entitlement — see #01.)

**Commit** (pending)
