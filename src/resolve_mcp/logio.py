"""Console + file logging.

Menu scripts DO print to the Resolve Console, but a long-running script's stdout
can buffer until it exits, so every line is also mirrored to a logfile. The Lite
app is sandboxed; ~/Movies is writable from inside it (the assets.movies
entitlement) and is easy to find, so it is the primary log location.
"""

import os
import sys
import tempfile
import time

from .config import LOG_FILENAME


def _real_home():
    """Real home dir even under the sandbox (HOME is redirected there)."""
    try:
        import pwd  # noqa: WPS433

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # noqa: BLE001
        return os.path.expanduser("~")


def _resolve_log_path():
    candidates = [
        os.environ.get("DAVINCI_MCP_LOG_DIR"),
        os.path.join(_real_home(), "Movies"),
        tempfile.gettempdir(),
    ]
    for directory in candidates:
        if not directory:
            continue
        try:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, LOG_FILENAME)
            with open(path, "a", encoding="utf-8"):
                pass
            return path
        except OSError:
            continue
    return os.path.join(tempfile.gettempdir(), LOG_FILENAME)


LOG_PATH = _resolve_log_path()


def safe_flush():
    """Flush stdout if possible. Resolve replaces sys.stdout with a custom
    object (``fu_stdout``) that has no ``flush``/``reconfigure``, so guard it."""
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        try:
            flush()
        except Exception:  # noqa: BLE001
            pass


def log(message=""):
    """Print to the Resolve Console and append to the logfile (timestamped)."""
    print(message)
    safe_flush()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"{stamp}  {message}\n")
    except OSError:
        pass
