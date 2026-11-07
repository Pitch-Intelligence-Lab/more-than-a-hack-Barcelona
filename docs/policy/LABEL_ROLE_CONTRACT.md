# Label Role Contract

## Roles

```text
MODEL_INPUT
TRAINING_TARGET
AUXILIARY_TRAINING_TARGET
EVALUATION_REFERENCE
POST_INFERENCE_DIAGNOSTIC
```

## Boundaries

- Possession group and player ID never enter `ModelInput`.
- Team-in-possession, player-possession count and phase-team fields cannot bypass the allowlist.
- Training targets and model inputs are separate types.
- Evaluation references are read only after prediction.
- Diagnostic labels cannot select features, parameters or candidates.
- Every external label has a provider definition ID and mapping evidence.
- A proxy remains labeled as proxy.
- Phase gaps do not automatically become D or X.
- Future event outcomes are not current-frame features.

## ModelInput allowlist

`ModelInput` permits tracking geometry, observation quality, team-slot mapping, frame metadata and explicitly approved phase/restart masks. It rejects possession, player-possession, phase-team and future-result fields.

