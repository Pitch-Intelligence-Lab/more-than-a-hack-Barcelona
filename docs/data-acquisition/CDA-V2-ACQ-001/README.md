# Cross-Match Open Data v2

Status: `CLOSURE_002_IMPLEMENTATION_COMPLETE / READY_FOR_PM_RE_VERIFICATION`

This package contains actual pinned files from four public sources:
SkillCorner, IDSSE/Sportec, StatsBomb and Wyscout. Raw data remain separate from
derived indexes, schemas, readers and quality reports.

```text
Sources: 4
Matches: 6203
Raw files: 13042
Raw size: 21.194 GiB
Q1: 4242
Q2: 1961
Q3: 0
Q4: 0
```

This status requests PM re-verification only. It does not approve technical
research handoff and does not grant training, evaluation, publication or
redistribution rights.

ZIP archives are resolved through the `--archive-root` argument and the
relative names in `archives/ZIP_INDEX.csv`. The archives may be relocated to any
Windows or POSIX path without regenerating the index.

Rebuild the portable package with:

```text
python tools/cda_v2/reassemble_package.py --archive-root <ARCHIVE_ROOT> --output <EMPTY_OUTPUT>
```
