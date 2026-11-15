# Independent Validation Download Log

## 2026-11-16 preflight

```text
Task: MTAH-IND-DATA-001
Repository baseline: 8801ac724ae3d8cc14fdeb5bc5d55493030b53b8
Working branch: data/MTAH-IND-DATA-001
```

Commands/checks:

```text
Hugging Face dataset metadata API: HTTP 200
Pinned tree API, 5 pages: HTTP 200
Remote tree entries: 244
Remote file entries: 197
Remote tree bytes: 144,847,069,949
Dataset reported SHA: 325bd4c57ee8e135ab652f3921d274526ada496b
README HEAD: HTTP 200
Gated file ball/128057_1st_ball.npz HEAD: HTTP 401
HF_TOKEN/HUGGINGFACE_HUB_TOKEN present: no
Cached HF token files present: no
```

Policy decision:

```text
SoccerTrack acquisition: BLOCKED
Afriskaut acquisition: DEFERRED
Metrica acquisition: DEFERRED
Mirror use: NONE
Payload downloads: 0
```

No token value was written to logs, repository files or reports.

## Storage snapshot before delivery

```text
D: 151,844,147,200 bytes free at preflight
E: 122,390,708,224 bytes free at preflight
```

The expected split remains feasible only after account/token gate access is
confirmed. No downloader cache was created.
