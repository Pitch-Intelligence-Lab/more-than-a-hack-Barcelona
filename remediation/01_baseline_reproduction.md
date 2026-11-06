# 01 — DP-005 基线复现报告

## 目的

在 `research/mo/independent-v1` 上复现冻结 DP-005 基线，确认 worktree、数据入口、依赖和构建脚本与冻结记录一致。

## 命令

```bash
cd E:/mtah2027-research/mo
MTAH_DATA_DIR=E:/mtah2027-data \
  ./.venv/Scripts/python.exe scripts/build_submission.py \
  --output outputs/submission-state-engine.csv \
  --config configs/state-engine.json \
  --health-report outputs/submission-state-engine.health.json \
  --force
```

## 构建输出

```text
OK    wrote 199319 frames to E:\mtah2027-research\mo\outputs\submission-state-engine.csv
      ball visible on 113488 frames
      labels: H=79250, A=73608, D=5999, X=40462
      segments: H=161, A=170, D=20
      observations: observed=113488, interpolated=108, missing=85723
      transitions: D->A=13, A->H=154, H->A=157, H->D=4, D->H=7, A->D=14
      forced D: frames=2934, all_d=True, labels={'H': 0, 'A': 0, 'D': 2934, 'X': 0}
      cleanup removed: {'H': 0, 'A': 0, 'D': 0}
      sha256: 1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401
```

## 与冻结值对照

| 指标 | 冻结值 | 本次结果 | 一致 |
|---|---|---|---|
| Rows | 199319 | 199319 | 是 |
| Frames | 0..199318 | 0..199318 | 是 |
| H | 79250 | 79250 | 是 |
| A | 73608 | 73608 | 是 |
| D | 5999 | 5999 | 是 |
| X | 40462 | 40462 | 是 |
| SHA-256 | `1de626…9401` | `1de626…9401` | 是 |

## Validator

项目 validator：

```text
OK    E:\mtah2027-research\mo\outputs\submission-state-engine.csv
      rows: 199319
      frames: 0..199318
      labels: H=79250, A=73608, D=5999, X=40462
      sha256: 1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401
```

官方 validator（锁定 commit `f8f2629`，脚本哈希 `d716bf…3914`）：

```text
Valid. Note this checks the format only -- it says nothing about whether the labels are right.
```

## 底座测试

```text
pytest -q                 64 passed in 2.62s
ruff check .              All checks passed
ruff format --check .     48 files already formatted
```

## 结论

DP-005 基线复现成功：输出逐字节哈希与冻结记录一致，两个 validator 均通过。可以在此基础上开始候选研究。

## 偏差

- Python 3.12.13，而非工程包锁定的 3.12.10；仅 patch 差异，输出哈希一致。
- 团队仓库初始为空克隆，已修复 HEAD 后创建 worktree。
- 官方 validator 使用本机公开仓库副本（HEAD `f8f2629`），未新下载。
