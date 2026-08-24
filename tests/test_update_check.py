#!/usr/bin/env python
"""Offline tests for resolve_mcp.update_check — no network, no DaVinci Resolve.

Run:  python3 tests/test_update_check.py
"""

import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
os.environ.setdefault("DAVINCI_MCP_LOG_DIR", tempfile.mkdtemp())

from resolve_mcp import update_check  # noqa: E402


class FakeBridge:
    """Runs jobs inline, like the main thread would, without real threading."""

    def call(self, func):
        return func(None)


def test_version_tuple_and_is_newer():
    need(update_check._version_tuple("0.17.0") == (0, 17, 0))
    need(update_check._version_tuple("1.2") == (1, 2))
    need(update_check._is_newer("0.18.0", "0.17.0"))
    need(not update_check._is_newer("0.17.0", "0.17.0"))
    need(not update_check._is_newer("0.16.9", "0.17.0"))
    need(update_check._is_newer("0.17.1", "0.17.0"))
    print("PASS: version_tuple / is_newer")


def test_run_reports_newer_version():
    original_fetch = update_check._fetch_latest_version
    seen = []
    original_log = update_check.log
    update_check._fetch_latest_version = lambda: "99.0.0"
    update_check.log = lambda message: seen.append(message)
    try:
        update_check._run(FakeBridge())
    finally:
        update_check._fetch_latest_version = original_fetch
        update_check.log = original_log
    need(len(seen) == 1, "expected exactly one Console message")
    need("99.0.0" in seen[0] and "Update available" in seen[0])
    print("PASS: run reports newer version to console")


def test_run_stays_quiet_when_up_to_date():
    original_fetch = update_check._fetch_latest_version
    original_log = update_check.log
    update_check._fetch_latest_version = lambda: update_check.SERVER_VERSION
    update_check.log = lambda message: need(False, "should not touch Console when up to date")
    try:
        update_check._run(FakeBridge())  # must not raise, must not call log()
    finally:
        update_check._fetch_latest_version = original_fetch
        update_check.log = original_log
    print("PASS: run stays quiet when already up to date")


def test_run_swallows_network_failure():
    original_fetch = update_check._fetch_latest_version
    original_log = update_check.log

    def boom():
        raise OSError("network unreachable")

    update_check._fetch_latest_version = boom
    update_check.log = lambda message: need(False, "should not touch Console on failure")
    try:
        update_check._run(FakeBridge())  # must not raise
    finally:
        update_check._fetch_latest_version = original_fetch
        update_check.log = original_log
    print("PASS: run swallows network failure without touching Console")


def need(cond, msg="assertion failed"):
    if not cond:
        raise AssertionError(msg)


def main():
    test_version_tuple_and_is_newer()
    test_run_reports_newer_version()
    test_run_stays_quiet_when_up_to_date()
    test_run_swallows_network_failure()
    print("update_check: all cases passed")


if __name__ == "__main__":
    main()
