#!/usr/bin/env python
"""Offline tests for resolve_mcp.installer — no DaVinci Resolve required.

Run:  python3 tests/test_installer.py

Exercises the pip-based installer (davinci-mcp-install / davinci-mcp-uninstall)
against a fake Lite and a fake Studio Scripts folder under a tempdir, so it
never touches a real Resolve install.
"""

import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))

from resolve_mcp import installer  # noqa: E402


def _run_case(label, scripts_attr):
    tmp = tempfile.mkdtemp(prefix="resolve-mcp-installer-test-")
    fake_scripts = os.path.join(tmp, "Scripts")
    os.makedirs(fake_scripts)

    other_attr = "STUDIO_SCRIPTS" if scripts_attr == "LITE_SCRIPTS" else "LITE_SCRIPTS"
    original = getattr(installer, scripts_attr)
    original_other = getattr(installer, other_attr)
    setattr(installer, scripts_attr, fake_scripts)
    # Point the other candidate somewhere that can't exist, so detection is unambiguous.
    setattr(installer, other_attr, os.path.join(tmp, "does-not-exist"))
    try:
        installer.install_main()

        target_dir = os.path.join(fake_scripts, "Utility")
        modules_dir = os.path.join(fake_scripts, "MCP", "resolve_mcp")
        for name in installer.ENTRY_MODULES:
            path = os.path.join(target_dir, name + ".py")
            assert os.path.exists(path), "{0}: missing {1}".format(label, path)
        assert os.path.isdir(modules_dir), "{0}: missing package dir {1}".format(label, modules_dir)
        assert os.path.exists(os.path.join(modules_dir, "config.py")), (
            "{0}: package dir looks empty".format(label)
        )

        installer.uninstall_main()
        for name in installer.ENTRY_MODULES:
            path = os.path.join(target_dir, name + ".py")
            assert not os.path.exists(path), "{0}: {1} survived uninstall".format(label, path)
        assert not os.path.exists(modules_dir), "{0}: {1} survived uninstall".format(label, modules_dir)

        print("PASS: {0}".format(label))
    finally:
        setattr(installer, scripts_attr, original)
        setattr(installer, other_attr, original_other)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    _run_case("Lite (copy mode)", "LITE_SCRIPTS")
    _run_case("Studio (symlink mode)", "STUDIO_SCRIPTS")
    print("installer: all cases passed")


if __name__ == "__main__":
    main()
