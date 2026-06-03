# 10 — subprocess output decodes as ASCII inside Resolve's Python

**Symptom**
`list_fonts` (which shells out to `system_profiler -json SPFontsDataType`)
failed at runtime with:

```
Internal error: 'ascii' codec can't decode byte 0xec in position 653:
ordinal not in range(128)
```

The same code ran fine from a normal terminal Python.

**Cause**
DaVinci Resolve's **embedded Python** runs under an ASCII / `C` locale
(`sys.getfilesystemencoding()` / preferred encoding is ascii, not UTF-8).
`subprocess.run(..., text=True)` decodes the child's stdout using that
preferred encoding — so any non-ASCII byte in the output crashes. The font
database is full of non-ASCII (localized font/style names; byte `0xec` is the
lead byte of a Korean UTF-8 character on this machine).

Notably this is **not** a sandbox block — the App Sandbox on Resolve Lite
*does* allow executing `/usr/sbin/system_profiler`. Only the decoding failed.

**Fix**
Capture **bytes** (drop `text=True`) and decode UTF-8 explicitly:

```python
proc = subprocess.run([...], capture_output=True, timeout=30)   # no text=True
data = json.loads(proc.stdout.decode("utf-8", "replace"))
```

**Lesson (reusable)**
Any tool in this server that runs a subprocess and reads its output must decode
the bytes itself (`bytes.decode("utf-8", "replace")`) — never rely on
`text=True`, because Resolve's interpreter will pick ASCII. Same rule applies to
reading files that may contain non-ASCII.

**Verified (2026-06-03):** with the byte-capture fix, `list_fonts` runs live
inside Resolve Lite and returns e.g. `Impact -> ['Regular']` (which also
explains the `Could not find font: Impact: Bold` render error — Impact has no
Bold face).
