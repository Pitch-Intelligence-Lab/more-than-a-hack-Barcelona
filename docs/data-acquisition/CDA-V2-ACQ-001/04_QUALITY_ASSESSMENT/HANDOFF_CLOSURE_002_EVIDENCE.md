# Handoff Closure 002 Evidence

```text
Task: CDA-V2-ACQ-001-HANDOFF-CLOSURE-002
Baseline: e1b85eaca948f9fe348403c42ec07d1d59afb84a
Closure implementation commit: 0654639a680daeb177bb33ad6cddc720c9309d0c
Final implementation commit: a70e7df9057ba1118ac5d85f6391734166a6d98c
Final status: CLOSURE_002_IMPLEMENTATION_COMPLETE
PM gate: READY_FOR_PM_RE_VERIFICATION
```

No source file was downloaded, replaced, re-encoded or edited in this closure.
DP-005, DP-006 Policy v2.1, Holdout and data-use authorization were untouched.

## Gate C Reader closure

```text
indexed=3961
unindexed=274
total=4235
duplicate_ids=0
missing_indexed_event_files=0
unknown competition/season=explicit
unindexed examples=7298, 69143, 3890259, 3890261, 3890262
```

The Reader now scans `data/events/*.json` and merges those IDs into the
competition-index enumeration. The synthetic regression adds a new unindexed
event file after the first enumeration and verifies that it is discovered
without changing the expected count constant.

IDSSE full position streams:

```text
DFL-MAT-J03WMX: 3,795,142 frames
DFL-MAT-J03WN1: 3,549,641 frames
DFL-MAT-J03WOH: 3,155,922 frames
DFL-MAT-J03WOY: 3,278,328 frames
DFL-MAT-J03WPY: 3,362,853 frames
DFL-MAT-J03WQQ: 3,220,946 frames
DFL-MAT-J03WR9: 3,376,630 frames

Total frames: 23,739,462
Elapsed: 296.914 s
Tracemalloc peak: 6.240 MiB
Parse errors: 0
```

## Gate D portability closure

```text
Manifest cache entries: 0
Metadata ZIP cache entries: 0
Reader then same Manifest: PASS
Five archive SHA-256 precheck: PASS
ZIP CRC test: PASS
ZIP path traversal rejection: PASS
Reassembly from empty output: PASS
Portable source identity without .git: PASS
ZIP_INDEX absolute paths: 0
--archive-root honored: PASS
Quickstart exit: 0
cache files after Quickstart: 0
```

Portable source identity files are under
`00_SOURCE_REGISTRY/PORTABLE_TREES/`. They include source URL, ref, commit,
file size, Git blob SHA-1 and actual SHA-256. SkillCorner LFS entries also retain
the official LFS SHA-256. IDSSE and StatsBomb pinned tree records are embedded in
the same portable registry, so verification does not need `.git`.

## From-zero rehearsal

The rehearsal used a new empty output directory and all five archives:

```text
SkillCorner: 139 members
IDSSE: 23 members
StatsBomb: 8988 members
Wyscout: 3892 members
Metadata/Tools: 6266 members

first Manifest verification: PASS
StatsBomb enumeration: 4235
Quickstart: exit 0
source identity: PASS
Manifest after Reader: PASS
ZIP testzip/SHA: PASS
```

The production target is rebuilt again from the same process after final
metadata is committed; final command-level evidence is recorded in the delivery
receipt.

## Migration

```text
old package root: code-workspace/outputs/Cross-Match-Open-Data-v2
new package root: controlled-data-root/package
files before: 19311
files after: 19311
bytes before: 22794876242
bytes after: 22794876242
raw files before: 13042
raw files after: 13042
raw bytes before: 22756760098
raw bytes after: 22756760098
manifest before move: PASS
manifest after reconstruction: PASS
old code-workspace root removed: yes
recoverable pre-closure backup retained in controlled incomplete storage
```

## Source counts

```text
Raw files: 13,042
Raw bytes: 22,756,760,098
Matches: 6,203
Tracking matches: 27
Event-only matches: 6,176
```

## Boundary

This closure is implementation-complete and ready for PM re-verification. It is
not a technical research handoff approval and does not authorize training,
evaluation, publication or redistribution.
