# Split and Holdout Contract

## Split rules

- One whole match belongs to exactly one split.
- Frame-level random splits are prohibited.
- Match overlaps are prohibited.
- `2017461` remains development-only.
- A vendor test split is not automatically a project holdout.

## Holdout states

```text
unassigned
sealed
unsealed
compromised
```

## Unseal requirements

- evaluation use is licensed;
- match exposure is verified;
- model, features, configuration and hyperparameters are frozen;
- evaluation script and metric contract are frozen;
- evaluation is independent and read-only.

If holdout results influence model, feature, parameter or threshold changes, the holdout becomes `compromised` and cannot be described as independent.

