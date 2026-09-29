# Security controls and verification

## Current controls

- API requests use strict Pydantic fields, finite/range checks, body byte limits, request IDs, generic client-facing errors, explicit CORS origins, and baseline security headers.
- Checkpoint loading uses a single expected demo path, a pinned SHA-256, `torch.load(..., weights_only=True)`, metadata equality checks, and strict state-dict loading.
- Prepared real data is loaded from a direct-child NPZ with `allow_pickle=False`, SHA-256 verification, path containment, and manifest/schema checks.
- No raw archive extraction is part of the canonical data workflow. Inventory reads ZIP metadata/CRC; it does not extract archive members.

## Limits and unresolved findings

- API rate limiting is in-process memory and is not reliable across multiple workers or restarts.
- The API buffers up to a configured bounded request body and logs rounded lat/lon buckets; review deployment privacy and resource limits.
- `run_api.py` enables reload and binds `0.0.0.0`; it is a development launcher and must not be used as a production command.
- HSTS is not emitted by the application; enable it only at a verified HTTPS termination layer.
- CSP and headers require deployment/browser testing; API headers do not establish web-host security.
- CORS defaults are local development origins; production origin configuration and reverse-proxy behavior need deployment-specific verification.
- No full security review, penetration test, SBOM attestation, or current dependency-vulnerability scan is claimed by this document.
- Archive extraction attacks are not applicable to current ZIP inventory because no extraction is performed; any future extractor needs separate safe extraction and adversarial tests before use.

## Operational rules

- Do not turn off TLS verification or weaken a gate to make a check pass.
- Do not accept request-selected model paths.
- Do not promote a candidate without a completed acceptance record.
- Keep credentials in deployment secret storage or environment injection; frontend variables are public.
- Do not log tokens, request bodies, full local paths, or secrets.

See [THREAT_MODEL.md](THREAT_MODEL.md) and the generated [dependency report](../artifacts/reports/DEPENDENCY_SECURITY_REPORT.md) and [secret scan report](../artifacts/reports/SECRET_SCAN_REPORT.md).
