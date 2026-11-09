# Acquisition Log

## 2026-11-10

- SkillCorner: official GitHub repository cloned at pinned commit
  `4340d274572876239c154c90bc507a9b3250a656`; 20 LFS tracking bodies fetched.
  README says 10 matches, but pinned `data/matches.json` contains 20; the manifest
  count is authoritative.
- Wyscout: official GitHub repository cloned at
  `ebc4c54c1093c420a81ce442c69e4186fab33bb4`; `processed-v2/files` contains 1,941
  match JSON files, matching the claimed count.
- IDSSE: Figshare API/download host returned AWS WAF 403 and the official
  Hugging Face hostname was not resolvable from this network. The same official
  repository commit `a715a38dfbaf5f58e431727c2b78d174101a703c` was retrieved through
  `hf-mirror.com`; all seven large position files match the official LFS SHA-256,
  all 23 files match the official pinned tree sizes, and the 1,827-byte README
  matches its official Git blob SHA-1 after mirror retry.
- StatsBomb: shallow Git clone stalled and codeload does not support byte-range
  resume. The pinned GitHub codeload tarball was retried from the start until
  complete (1,681,123,103 bytes). Extraction produced exactly 8,988 files and
  16,128,701,593 bytes, matching the pinned GitHub tree.
  `competitions.json` enumerates 3,961 matches, while `data/events` and
  `data/lineups` contain 4,235 files. The 274 additional event/lineup files are
  inventoried with unknown competition/season rather than inferred. One optional
  360 JSON file (`3845506.json`) had an official-source NUL corruption and is retained
  unchanged with the parse failure recorded in quality reasons.
- PyPI was unreachable, so dependency-free source readers and recorded equivalent
  parsing methods are used instead of Kloppy.
- SkillCorner full bodypose for matches 1925299 and 1996435 was deferred as required;
  their ordinary tracking/event/phase files are present.

## Final source totals

```text
SkillCorner: 20 matches, 20 tracking, 0 event-only
IDSSE:        7 matches,  7 tracking, 0 event-only
StatsBomb: 4235 matches,  0 tracking, 4235 event-only
Wyscout:   1941 matches,  0 tracking, 1941 event-only
All:       6203 matches, 27 tracking, 6176 event-only
```

The 274 StatsBomb files absent from the competition index are included in the
StatsBomb count and explicitly identified by an `unindexed public event file`
competition value.
