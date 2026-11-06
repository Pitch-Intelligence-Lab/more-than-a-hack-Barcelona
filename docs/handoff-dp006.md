# Engineering Handoff: DP-006

```text
Task: DP-006
Branch: feature/DP-006-generalisation-dead-ball
Commit: feature-branch HEAD reported with the pull request
Pull request: https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona/pull/2
External data licence:
  SkillCorner Open Data, MIT repository licence at commit
  4340d274572876239c154c90bc507a9b3250a656. README explicitly states the
  repository data was open sourced; no separate data-specific licence was found.
  Data remains outside Git and is not redistributed.
External match IDs and split:
  development: 2017461
  validation: none
  holdout: none
  status: diagnostic_only
Proxy mapping:
  home/away possession group -> H/A;
  no possession inside active phase -> X;
  no possession with no phase inside a declared period -> D;
  outside period or missing tracking row -> X.
Tests:
  79 passed
Warning-free tests:
  79 passed with -W error
External validation results:
  DP-001-004 baseline: macroF1=0.6703, segmentF1=0.2038,
    falseD=925, missedD=9153, switches=445
  DP-005: macroF1=0.3265, segmentF1=0.2575,
    falseD=21, missedD=28421, switches=353
  DP-006 phase proxy: macroF1=0.7910, segmentF1=0.3258,
    falseD=2515, missedD=0, switches=311
Target smoke result, if run once:
  unchanged approved v1.2 result: macroF1=0.4998, spellF1=0.3897, D F1=0.
Checksums:
  target output=1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401
  external tracking=59cfa5588efee041da439f44df5b5b92f2b7305571dc831164e3d05f7415787a
  external phases=5331495ecea48056df56dc843864bf36f366f7bca3898d82273eba7a3a54eba5
  external match metadata=db27759bf734dc8e3d9e56f047965cc7c74833bc3d0345ee3821ab97681ce4b9
  external licence=3384cc66ffd008209759af5e6328677eabded72756fb1f56f4f82e68e9b3c6eb
  audit report=38c8d6727b031f7d3eeae9f9c319986498eece505d228c38e0f55c7a2d60bacc
  external comparison=8a9f8d2af046f5271afe7ee6067236c695277e9e52fbbf0b63434abb20e2e699
Changed files:
  provider-neutral and SkillCorner adapters;
  phase/dead-ball layer;
  external proxy evaluation and split validation;
  external audit/evaluation scripts and manifests;
  synthetic tests;
  README and DP-006 documentation.
Known limitations:
  one development match only; no validation or holdout;
  external possession is a proxy, not organiser ground truth;
  DP-006 phase performance is coupled to the phase source used by the proxy;
  no target-equivalent phase-gap source is validated;
  extrapolated external positions are excluded.
Recommended final candidate:
  DP-005 v1.2 remains the provisional target candidate. DP-001-004 remains
  fallback. DP-006 is not promoted as final without a target phase source and
  an untouched external holdout.
Open questions:
  whether a future external dataset provides an independent dead-ball target;
  whether target Smart Tagging can be safely mapped as weak restart evidence
  without target-answer tuning.
```
