# 05 — Getting the Resolve object from a menu script

**Symptom**
Need a reliable `resolve` object across menu launch, Console, and external runs.

**Cause**
Resolve injects scripting objects into the script's `__main__` namespace
(`resolve`, or `bmd` / `app` / `fu`), not as importable module globals. External
runs instead need the `DaVinciResolveScript` module on `PYTHONPATH`.

**Fix**
Look up `__main__` first (mirrors `_resolve_menu_helpers.get_resolve`), then
fall back to importing `DaVinciResolveScript`:
```python
import __main__
obj = getattr(__main__, "resolve", None)            # menu launch
# else __main__.bmd.scriptapp("Resolve")
# else __main__.app/fu .GetResolve()
# else import DaVinciResolveScript; dvr.scriptapp("Resolve")  # console/external
```

**Commit** be751b2
