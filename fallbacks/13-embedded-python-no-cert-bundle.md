# 13 — Resolve's required Python framework has no CA bundle (HTTPS fails)

**Symptom**
The startup update check (`update_check.py`, added in 0.18.0) logged this on
every launch instead of ever finding a version:

```
[davinci-mcp] update check failed: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)>
```

**Cause**
DaVinci Resolve's scripting API links against a specific `python.org`
`/Library/Frameworks/Python.framework` build (historically 3.6; check which
version is actually installed on a given machine). That framework's
`etc/openssl/` directory ships **empty** — python.org's macOS installer never
auto-populates a CA bundle. python.org ships a separate
`/Applications/Python X.Y/Install Certificates.command` helper
(`pip install --upgrade certifi` + symlink) for exactly this, but almost nobody
runs it for a framework that exists solely to satisfy Resolve's scripting
requirement — there's no other reason to touch it.

Practical effect: **any HTTPS call from inside a Resolve menu script fails
with `CERTIFICATE_VERIFY_FAILED` on essentially every fresh macOS install**,
not as a rare edge case. Confirmed by checking `etc/openssl/` on both the 3.6
and 3.12 frameworks present on a real dev machine — both empty.

**Fix**
For low-stakes cases (a public, non-sensitive, read-only value that's only
ever used for display text, never executed or trusted for anything else — see
`update_check._fetch_latest_version`): try a normal verified request first,
and only on a cert-verification failure fall back to
`ssl._create_unverified_context()`. Log the fallback (file-only, not Console)
so it's visible in `~/Movies/davinci-resolve-lite-mcp.log` without being noisy,
and mention `Install Certificates.command` as the real fix for anyone who
wants full verification.

**Gotcha within the gotcha**: `urllib.request.urlopen()` never raises
`ssl.SSLCertVerificationError` directly on a cert failure — it catches the
underlying `OSError`/`SSLError` during connect and re-raises it wrapped as
`urllib.error.URLError`, with the original exception on `.reason`. Matching
`except ssl.SSLCertVerificationError` on the call directly silently never
fires; the first attempt at this fix shipped exactly that bug; live-testing
against the real Resolve process (not just the mocked unit test) caught it.
Correct form:

```python
except urllib.error.URLError as exc:
    if not isinstance(exc.reason, ssl.SSLCertVerificationError):
        raise
    ...  # fall back to an unverified context
```

If you write a test for this, mock `urlopen` to raise the *wrapped* form
(`urllib.error.URLError(ssl.SSLCertVerificationError(...))`), not the bare
exception — a mock of the bare exception passes even when the real code is
broken, which is exactly what happened here.

For anything security-sensitive, do **not** apply this pattern — this project
has no other outbound HTTPS calls, and any future one carrying meaningful data
should get proper certificate verification (e.g. by shelling out to the
`security` CLI to export the system trust store, or documenting the manual
`Install Certificates.command` step as a hard requirement) rather than the
graceful-degrade shortcut used here.

**Lesson (reusable)**
Never assume a normal-terminal `python3`'s TLS behavior applies inside
Resolve's embedded interpreter — it's a different, separately-installed
framework build with its own (frequently unconfigured) cert store. Test
network code by tailing the real logfile after a real Resolve restart, not by
running the equivalent snippet in a terminal.

**Verified (2026-08-24):** root-caused via `ssl.get_default_verify_paths()`
pointing at `.../etc/openssl/cert.pem`, confirmed missing on disk for both
installed frameworks; `/Applications/Python 3.6/Install Certificates.command`
confirmed present as the standard fix.
