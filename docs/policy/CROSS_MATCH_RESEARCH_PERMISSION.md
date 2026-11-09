# Cross-Match Research Permission

```text
EXTERNAL_SUPERVISION_LEGAL_MODEL: ALLOWED_IF_RIGHTS_AND_ACCESS
EXTERNAL_DATA_RESEARCH_ACTIVATION: HOLD
INDEPENDENT_HOLDOUT: NOT_ACTIVATED
```

Research may begin only when the machine-readable policy marks the exact provider/use pair `PASS`.

Required identity:

- provider and pinned source revision;
- source file hashes;
- label definition ID;
- label role and requested use;
- split assignment;
- model and code commit;
- evidence IDs;
- owner approval.

A policy PASS does not imply permission for target ground truth, cloud upload, publication, redistribution or access to a provider whose own status is HOLD.

