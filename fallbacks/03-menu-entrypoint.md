# 03 — Menu launch and `if __name__ == "__main__"`

**Symptom**
Logic gated behind `if __name__ == "__main__": main()` did not run reliably
when launched from the Workspace > Scripts menu.

**Cause**
Resolve executes menu scripts via `exec` in an environment where `__name__` is
not guaranteed to be `"__main__"`. The reference menu scripts never rely on it —
they run their logic at module top level.

**Fix**
Run at top level via a `bootstrap()` called unconditionally at the bottom of the
file. Decide what to do based on whether a Resolve object is reachable:
- inside Resolve → `get_resolve()` succeeds → run.
- imported by tests (different module name, no injected `resolve`) → stays inert.

For the stop script (which needs no Resolve object), detect a menu launch by
checking `__main__` for injected scripting globals:
```python
def _inside_resolve():
    import __main__
    return any(getattr(__main__, n, None) for n in ("resolve","bmd","app","fu"))
```

**Commit** b2385e1
