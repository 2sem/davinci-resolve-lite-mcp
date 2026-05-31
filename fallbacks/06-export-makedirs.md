# 06 — `ExportCurrentFrameAsStill` fails silently when the dir is missing

**Symptom**
Exporting the current frame returned False / failed when the target folder did
not already exist.

**Cause**
`Project.ExportCurrentFrameAsStill(path)` does not create intermediate
directories and just returns False on failure. The reference script
`08-export-current-frame-and-call-09.py` always `os.makedirs(OUTPUT_DIR,
exist_ok=True)` first.

**Fix**
In the `export_current_frame_as_still` tool: `expanduser` the path,
`os.makedirs(os.path.dirname(path), exist_ok=True)`, capture the current
timecode, then export. Remember the sandbox: the path must be under `~/Movies`
or a granted location (see #01).

**Commit** be751b2
