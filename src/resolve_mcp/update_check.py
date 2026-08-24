"""Startup update check against PyPI (brew/pod-style "new version available").

Runs once per server launch, on its own daemon thread, and is best-effort in
every sense: a slow/blocked/failed network call never delays startup and never
crashes the server. Only an actual newer version reaches the Resolve Console;
every other outcome (up to date, network unreachable, PyPI down) is recorded to
the logfile only. Set DAVINCI_MCP_SKIP_UPDATE_CHECK=1 to disable outright.
"""

import json
import os
import threading
import urllib.request

from .config import SERVER_NAME, SERVER_VERSION
from .logio import log, log_file

PYPI_URL = "https://pypi.org/pypi/{0}/json".format(SERVER_NAME)
CHANGELOG_URL = "https://github.com/2sem/davinci-resolve-lite-mcp/blob/main/CHANGELOG.md"
TIMEOUT_SECONDS = 3


def _version_tuple(version):
    parts = []
    for chunk in str(version).split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_newer(candidate, current):
    return _version_tuple(candidate) > _version_tuple(current)


def _fetch_latest_version():
    request = urllib.request.Request(
        PYPI_URL,
        headers={"User-Agent": "{0}/{1}".format(SERVER_NAME, SERVER_VERSION)},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = json.load(response)
    return data["info"]["version"]


def _run(bridge):
    try:
        latest = _fetch_latest_version()
    except Exception as exc:  # noqa: BLE001 — never let this affect the server
        log_file("[davinci-mcp] update check failed: {0}".format(exc))
        return

    if not _is_newer(latest, SERVER_VERSION):
        log_file("[davinci-mcp] update check: up to date (latest {0})".format(latest))
        return

    message = (
        "[davinci-mcp] Update available: v{0} -> v{1}. Upgrade: "
        "pip install --upgrade {2} && davinci-mcp-install (or git pull && "
        "./install.sh). Changelog: {3}"
    ).format(SERVER_VERSION, latest, SERVER_NAME, CHANGELOG_URL)
    try:
        # Console writes must happen on the main thread (see bridge.py) — route
        # through the same command queue tool calls use, even though this has
        # nothing to do with the resolve object.
        bridge.call(lambda resolve: log(message))
    except Exception:  # noqa: BLE001 — e.g. server already stopping
        log_file(message)  # still land it in the logfile


def check_async(bridge):
    """Fire-and-forget: spawn the background check thread, or skip via env var."""
    if os.environ.get("DAVINCI_MCP_SKIP_UPDATE_CHECK"):
        return
    threading.Thread(target=_run, args=(bridge,), name="mcp-update-check", daemon=True).start()
