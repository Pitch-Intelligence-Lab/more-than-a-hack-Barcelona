## Change

Describe the task ID and the engineering change.

## How to run

```powershell
python -m pytest
python scripts\build_submission.py --output outputs\submission.csv --config configs\baseline.json
python scripts\validate_submission.py outputs\submission.csv
```

## Automated checks

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `python -m pytest`
- [ ] Official validator run in the isolated data environment
- [ ] Repeat generation produced the same SHA-256

## Output SHA-256

`pending team-local tactical run`

## Rule and data impact

- [ ] No match data, video, screenshot, or extracted tracking row is committed
- [ ] No public or private ground truth was used for training or tuning
- [ ] The change preserves the 199,319-frame submission contract

## Unresolved risks

List known limitations and decisions that still need PM or QA confirmation.
