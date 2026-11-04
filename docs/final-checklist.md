# Final Submission Checklist

## Rules

- [ ] No competition data is committed or available in cloud AI, Notion or CI.
- [ ] No output was checked against the video by hand.
- [ ] No hand labels or manual corrections were used.
- [ ] Training and tuning use external, licensed data only.
- [ ] The code uses provided data only as an inference input.

## CSV

- [ ] Header is exactly `frame,label`.
- [ ] There are exactly 199,319 data rows.
- [ ] Frames are 0 through 199318 in order.
- [ ] Labels are H, A, D or X.
- [ ] Official validator passes.
- [ ] Final file SHA-256 is recorded.

## Repository

- [ ] Repository is public.
- [ ] It contains source, pinned dependencies and run instructions.
- [ ] One command regenerates the exact submitted CSV.
- [ ] A clean-environment run has been completed.
- [ ] No data, download links or credentials are present.

## Technical report

- [ ] Method and rationale are explained.
- [ ] Used and rejected assets are listed.
- [ ] External data and licences are disclosed.
- [ ] Possession and dead-ball rules are explicit.
- [ ] Limitations and reproduction commands are included.

## Submission

- [ ] Official submission email has been checked.
- [ ] Form uses the registered team name.
- [ ] CSV and report follow required naming.
- [ ] Submission person and independent verifier are different.
- [ ] Receipt is stored.
