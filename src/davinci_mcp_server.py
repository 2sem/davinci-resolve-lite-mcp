#!/usr/bin/env python
"""DaVinci Resolve (Lite) MCP server — launcher.

Launch from DaVinci Resolve: Workspace > Scripts > Utility > davinci_mcp_server

This is a thin launcher. The real code lives in the ``resolve_mcp`` package,
which the installer ships to a NON-menu folder (Scripts/MCP) so its modules do
not clutter the Resolve Scripts menu. This file finds that package on disk, adds
it to sys.path, and runs the server.
"""

import os
import sys


def _bootstrap_sys_path():
    """Put the directory that contains the ``resolve_mcp`` package on sys.path.

    Candidates cover: running straight from the repo (dev), the installed layout
    (entry in Scripts/Utility, package in Scripts/MCP), and direct expanduser
    fallbacks for both Lite (sandbox) and Studio in case __file__ is unavailable.
    """
    candidates = []

    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(here)                                    # dev: package sibling
        candidates.append(os.path.join(os.path.dirname(here), "MCP"))  # installed: <Scripts>/MCP
    except NameError:  # __file__ not defined in some exec contexts
        pass

    home = os.path.expanduser("~")
    candidates.append(os.path.join(
        home, "Library", "Application Support", "Fusion", "Scripts", "MCP"))  # Lite (sandbox ~)
    candidates.append(os.path.join(
        home, "Library", "Application Support", "Blackmagic Design",
        "DaVinci Resolve", "Fusion", "Scripts", "MCP"))             # Studio

    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "resolve_mcp")) and path not in sys.path:
            sys.path.insert(0, path)


_bootstrap_sys_path()

try:
    from resolve_mcp.server import main
except ImportError as exc:  # package not found on any candidate path
    print(f"[davinci-mcp] FATAL: could not import resolve_mcp package: {exc}")
    print("[davinci-mcp] Re-run ./install.sh so the package is deployed next to this launcher.")
else:
    main()
