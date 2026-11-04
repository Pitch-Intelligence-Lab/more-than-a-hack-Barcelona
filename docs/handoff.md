# Engineering handoff

```text
Task ID: DP-001 through DP-004 (first milestone)
Branch: feature/DP-001-DP-004-tactical-baseline
Commit: feature-branch HEAD reported in the pull request
Changed files: src/, scripts/, tests/, configs/, docs/, CI workflow
How to run: see README.md
Tests run: 30 synthetic tests; ruff check and format check pass
Validation result: project and official validators pass on the team-local tactical output
Output SHA-256: caf42b0775d695e29859f775c67d42162a92d32655facb202c548b3b59fb220f
Algorithm or interface change: tactical ATD -> nearest-player candidate ->
  centred majority vote -> atomic validated CSV
Parameters and source: 25 fps and frame contract are official;
  105.3 x 68.0 m pitch and 50-frame pre-registered window are documented
Rule/data compliance: no match data, video, ground truth, or broadcast used
Known limitations: no true dead-ball or controlled-possession model
Open questions: DP-005/DP-006 football-semantic thresholds require PM/QA
```

The patch was integrated into the private team repository on the feature branch,
reviewed against the existing collaboration documents, and tested with the
team-local tactical data.

