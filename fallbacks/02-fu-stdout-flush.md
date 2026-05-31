# 02 — `module 'fu_stdout' has no attribute 'flush'`

**Symptom**
```
davinci-resolve-lite-mcp loaded
Traceback (most recent call last):
  ...
    sys.stdout.flush()
AttributeError: module 'fu_stdout' has no attribute 'flush'
```
Script printed the first line, then crashed.

**Cause**
When running a menu script, Resolve replaces `sys.stdout` with a custom object
(`fu_stdout`) that implements `write` (so `print` works) but NOT `flush` or
`reconfigure`. Calling `sys.stdout.flush()` / `sys.stdout.reconfigure()`
directly raises `AttributeError`.

**Fix**
Guard every flush/reconfigure with a capability check:
```python
def safe_flush():
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        try: flush()
        except Exception: pass
```
Use `safe_flush()` instead of `sys.stdout.flush()`, and `getattr(sys.stdout,
"reconfigure", None)` before reconfiguring. (Matches the reference scripts'
`safe_flush_stdout`.)

**Commit** 1502c97
