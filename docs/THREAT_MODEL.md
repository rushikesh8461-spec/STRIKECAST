# StrikeCast threat model

Scope: local repository, data intake, demo API, model artifact handling, and frontend. This is a working threat model, not a security certification.

| Threat | Attack surface | Impact | Mitigation | Verification | Residual risk |
|---|---|---|---|---|---|
| Malicious/corrupt scientific data | NetCDF, GRIB, NPZ, manifests | Wrong labels, resource exhaustion, code execution through unsafe formats | Safe NPZ loading, schema and checksum checks; raw parser isolation still needed | Dataset contract adversarial tests | Provider parsers may contain vulnerabilities; source claims need independent review |
| Archive traversal / decompression bomb | ZIP inputs | Write outside intake or exhaust disk/RAM | Current inventory does not extract archives | Confirm no extraction calls; add tests before extractor adoption | Future utility may introduce extraction without controls |
| Poisoned or mislabeled training data | Provider records and target generation | Misleading model skill or operational harm | Explicit UNKNOWN mask; quality flags and provenance required; training blocked | Target mask and strict-loader tests | Observation policy still needs LIS product expert review |
| Train/test or future leakage | Alignment, windows, normalization, calibration | Inflated evaluation | Availability timestamps, chronological whole-window splits, train-only normalization contract | `scripts/ml/leakage_audit.py`; preprocessing tests | External availability evidence cannot be inferred from arrays alone |
| Checkpoint corruption/replacement | Artifact registry | Arbitrary or changed inference behavior | Pinned digest, safe weights-only deserialization, strict metadata/state dict | Checkpoint validation and artifact tests | Runtime pin currently hardcodes only demo artifact; rotation requires reviewed registry change |
| Dependency compromise | Python/npm supply chain and CI | Code execution/data theft | Lockfile/requirements and scheduled scanners | pip-audit/npm audit when registry reachable | Python dependencies are not fully locked; audit reachability and action pinning need work |
| Secret leakage | Source, configs, CI, logs, built frontend | Account or data compromise | `.env.example`, ignore rules, secret scan | `SECRET_SCAN_REPORT.md` | Heuristic scan may miss encoded/novel secret forms |
| API flooding | HTTP endpoints | Service outage/cost | Body limit and process-local rate limit | API tests | No distributed limiter, queue or edge-level volumetric control |
| Malformed inputs | API request schemas and parsers | Crashes or resource use | Pydantic bounds, finite checks, payload/grid limits | API adversarial tests | Reverse-proxy limits/timeouts require deployment verification |
| Model/API status misrepresentation | Metadata and outputs | Users over-trust demo forecast | `DEMO_ONLY` and provisional calibration status | API metadata tests | UI copy and downstream integrations need continual review |
| Model/config tampering | Filesystem and deployment | Unauthorized behavior change | Artifact checksums; read-only deployment recommended | Integrity checks | No signed release provenance or immutable registry configured |
| CORS/browser attacks | API and web server | Cross-origin abuse or content injection | Explicit origins, CSP and baseline headers | CORS/API and browser tests | Actual HTTPS/proxy and CSP compatibility not verified in all deployments |
| Path traversal | Manifests and CLI paths | Read arbitrary files | Direct-child payload restriction and checkpoint allowlist | Loader/checkpoint tests | Other scripts accepting filesystem arguments require review |

## Assets

Model checkpoints, source datasets and hashes, forecast outputs, configuration, secrets, API availability, code, and dataset/model provenance.

## Assumptions

The current hosted inference is a demo; no real-data candidate or production artifact is approved. Operators control deployment environment variables and HTTPS termination. Dataset providers and licenses have not yet been fully independently attested.
