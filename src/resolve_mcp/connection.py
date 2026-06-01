"""Locate the DaVinci Resolve scripting object."""

import sys


def get_resolve():
    """Return (resolve, how) or (None, None).

    Resolve injects the scripting objects into the ``__main__`` namespace of a
    menu-launched script (``resolve``, or ``bmd`` / ``app`` / ``fu``), so look
    there first. This mirrors the proven pattern from the reference helper
    ``_resolve_menu_helpers.py``. Fall back to importing DaVinciResolveScript
    for the Console / external use.
    """
    import __main__  # noqa: WPS433

    obj = getattr(__main__, "resolve", None)
    if obj:
        return obj, "__main__.resolve"

    bmd = getattr(__main__, "bmd", None)
    if bmd:
        try:
            obj = bmd.scriptapp("Resolve")
            if obj:
                return obj, "__main__.bmd.scriptapp(Resolve)"
        except Exception:  # noqa: BLE001
            pass

    for global_name in ("app", "fu"):
        host = getattr(__main__, global_name, None)
        get_resolve_fn = getattr(host, "GetResolve", None) if host else None
        if callable(get_resolve_fn):
            try:
                obj = get_resolve_fn()
                if obj:
                    return obj, f"__main__.{global_name}.GetResolve()"
            except Exception:  # noqa: BLE001
                pass

    module_paths = [
        "/Applications/DaVinci Resolve.app/Contents/Resources/Developer/Scripting/Modules",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
    ]
    try:
        import DaVinciResolveScript as dvr  # noqa: WPS433

        obj = dvr.scriptapp("Resolve")
        if obj:
            return obj, "DaVinciResolveScript.scriptapp(Resolve)"
    except Exception:  # noqa: BLE001
        pass

    for path in module_paths:
        if path not in sys.path:
            sys.path.append(path)
        try:
            import DaVinciResolveScript as dvr  # noqa: WPS433

            obj = dvr.scriptapp("Resolve")
            if obj:
                return obj, f"DaVinciResolveScript from {path}"
        except Exception:  # noqa: BLE001
            continue

    return None, None
