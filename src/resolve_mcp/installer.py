"""Console-script installer for pip-based installs.

Ports ``install.sh`` / ``uninstall.sh`` to pure Python so a ``pip install
davinci-resolve-lite-mcp`` user can run ``davinci-mcp-install`` instead of
cloning the repo and running the shell script. Same two constraints drive the
logic (see install.sh's header for the full explanation):

1. Resolve's Scripts menu only scans category folders (Utility / Comp / Tool /
   Edit / Color / Deliver) — entry scripts must live directly under one.
2. The sandboxed Lite app cannot follow a symlink outside its container, so on
   Lite the files are COPIED; the non-sandboxed Studio build gets a symlink so
   edits to the installed package are picked up without re-running this.

This does not remove the one unavoidable manual step: starting the server from
Resolve's own Scripts menu. No MCP client can do that for you — Lite blocks
all external scripting, which is the entire reason this project exists.
"""

import importlib.util
import os
import shutil
import sys

ENTRY_MODULES = ("davinci_mcp_server", "stop_davinci_mcp_server")
PACKAGE_NAME = "resolve_mcp"

LITE_SCRIPTS = os.path.expanduser(
    "~/Library/Containers/com.blackmagic-design.DaVinciResolveLite"
    "/Data/Library/Application Support/Fusion/Scripts"
)
STUDIO_SCRIPTS = os.path.expanduser(
    "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"
)


def _module_path(name):
    spec = importlib.util.find_spec(name)
    if spec is None or spec.origin is None:
        raise SystemExit(
            "Could not locate installed module '{0}' — is the package "
            "installed correctly (pip install davinci-resolve-lite-mcp)?".format(name)
        )
    return spec.origin


def _package_dir():
    spec = importlib.util.find_spec(PACKAGE_NAME)
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("Could not locate the installed '{0}' package.".format(PACKAGE_NAME))
    return spec.submodule_search_locations[0]


def _detect_target():
    if os.path.isdir(LITE_SCRIPTS):
        return LITE_SCRIPTS, "copy", "DaVinci Resolve Lite (sandboxed)"
    if os.path.isdir(STUDIO_SCRIPTS):
        return STUDIO_SCRIPTS, "symlink", "DaVinci Resolve (standard install)"
    raise SystemExit(
        "Could not find a DaVinci Resolve Fusion/Scripts folder.\n"
        "Open Resolve once so it creates it, then retry."
    )


def _deploy(src, dest, mode):
    if os.path.islink(dest) or os.path.exists(dest):
        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)
    if mode == "symlink":
        os.symlink(src, dest)
    elif os.path.isdir(src):
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def install_main():
    scripts, mode, label = _detect_target()
    print("Detected {0} -> {1} install.".format(label, "COPY" if mode == "copy" else "symlink"))

    target_dir = os.path.join(scripts, "Utility")
    modules_dir = os.path.join(scripts, "MCP", PACKAGE_NAME)
    os.makedirs(target_dir, exist_ok=True)

    # Clean any previous installs (old Edit-folder copies, current Utility copies).
    for stale_dir in (os.path.join(scripts, "Edit"), target_dir):
        for name in ENTRY_MODULES:
            stale = os.path.join(stale_dir, name + ".py")
            if os.path.islink(stale) or os.path.exists(stale):
                os.remove(stale)

    for name in ENTRY_MODULES:
        src = _module_path(name)
        dest = os.path.join(target_dir, name + ".py")
        _deploy(src, dest, mode)

    os.makedirs(os.path.dirname(modules_dir), exist_ok=True)
    _deploy(_package_dir(), modules_dir, mode)
    print("Modules ({0}) -> {1}  (hidden from menu)".format(PACKAGE_NAME, modules_dir))

    print("Installed ({0}) into: {1}".format(mode, target_dir))
    for name in ENTRY_MODULES:
        print("  {0}.py".format(name))
    print()
    print("Next:")
    print("  1. Workspace > Scripts > Utility > davinci_mcp_server   (shows on every page)")
    print("  2. Console / logfile prints the MCP endpoint + port.")
    print("  3. claude mcp add --transport http davinci http://127.0.0.1:8765/mcp")
    print("  4. Stop:  Workspace > Scripts > Utility > stop_davinci_mcp_server")
    print()
    if mode == "copy":
        print("NOTE: Lite install is a COPY. Re-run 'davinci-mcp-install' after upgrading the package.")


def uninstall_main():
    scripts, _mode, label = _detect_target()
    print("Detected {0}.".format(label))

    removed = False
    for stale_dir in (os.path.join(scripts, "Edit"), os.path.join(scripts, "Utility")):
        for name in ENTRY_MODULES:
            path = os.path.join(stale_dir, name + ".py")
            if os.path.islink(path) or os.path.exists(path):
                os.remove(path)
                print("Removed: {0}".format(path))
                removed = True

    modules_dir = os.path.join(scripts, "MCP", PACKAGE_NAME)
    if os.path.islink(modules_dir) or os.path.exists(modules_dir):
        if os.path.isdir(modules_dir) and not os.path.islink(modules_dir):
            shutil.rmtree(modules_dir)
        else:
            os.remove(modules_dir)
        print("Removed: {0}".format(modules_dir))
        removed = True

    if not removed:
        print("Nothing to remove.")


if __name__ == "__main__":
    sys.exit(install_main())
