# Dependency security report

Audit date: 2026-09-29. Status: **NOT_VERIFIED — vulnerability feeds could not be reached with TLS verification enabled**. No dependency vulnerability result is claimed.

| Ecosystem/input | Locking state | Scan attempted | Result | Follow-up |
|---|---|---|---|---|
| Python root `requirements.txt` and included requirements | Ranges and editable/local includes; no complete hash lock | `python -m pip_audit -r requirements.txt` | Scanner failed while bootstrapping/upgrading pip in a temporary environment. | Produce a reviewed, platform-aware lock with hashes; rerun scanner in trusted CI. |
| Python installed environment | Environment inventory, not a source lock | `python -m pip_audit --local` | PyPI vulnerability lookup failed certificate verification (`CERTIFICATE_VERIFY_FAILED`). | Repair trusted CA configuration and rerun; TLS verification was not disabled. |
| Web `apps/web/package-lock.json` | Lockfile present; `package.json` uses semver ranges resolved by lock | `npm audit --json` | npm audit endpoint failed certificate verification. | Rerun `npm audit --audit-level=moderate` after trusted registry CA is available. |

Known vulnerability count: **UNKNOWN**. Scanner/network failures are not a clean bill of health. The web CI workflow runs npm audit; the scheduled security workflow runs Python and npm audits. GitHub Actions are referenced by mutable major tags rather than pinned commit SHAs and should be reviewed/pinned in a separately verified change.

No TLS bypass, `--trusted-host`, or insecure registry workaround was used. No package versions were upgraded as part of this audit.
