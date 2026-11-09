# HOLD Use Evidence Policy

Effective for DP-006 Policy v2.1 and all production authorization paths.

| Use status | evidence_ids | Required result |
|---|---|---|
| `PASS` | empty | Reject at policy load because evidence is mandatory |
| `PASS` | non-empty | Every evidence ID must belong to provider `source_evidence` |
| `HOLD` | empty | Evidence structure is valid; scoped internal risk may authorize eligible read/store uses |
| `HOLD` | non-empty | Every evidence ID must belong to provider `source_evidence`; otherwise reject before scoped fallback |
| `FAIL` | any | Reject permanently |

Malformed policy structure, source revision mismatch, unknown evidence,
permission `FAIL`, and source identity errors are hard failures. They never enter
the scoped internal-risk fallback.

Scoped internal-risk fallback is limited to:

```text
EXTERNAL_LICENSE_HOLD
INTERNAL_RESEARCH_HOLD
USE_PERMISSION_HOLD
```

It remains limited to `download_store` and `read_preprocess`, and cannot
authorize model input, evaluation reference, final candidate, publication or
redistribution.
