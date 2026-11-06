# 00 — 整改前基线冻结记录（研究 worktree）

- 日期：2026-11-06
- 仓库：`E:\mtah2027-code`
- 远端：`https://github.com/Pitch-Intelligence-Lab/more-than-a-hack-Barcelona.git`
- 研究 worktree：`E:\mtah2027-research\mo`
- 研究分支：`research/mo/independent-v1`
- HEAD：`c4b80a99695fa89f97d9a4a8296f249493bdd278`
- Stable tag：`foundation-stable-dp005-v1.2.0-2026-11-06`（tag object `930cdd9d6acf4d4803043d31ef23fd6b65fdc7d2`）
- Research tag：`foundation-research-dp006a-v1.1.0-2026-11-06`（tag object `085a2bd7208bafe60b83c9f43708ebb3228def58`，commit `cdfeaf3d1f06914a255c291859315f766eb8a945`）
- Main commit：`7a05ab7868b4757883781649979d50671d5c3088`

## 数据入口

- `MTAH_DATA_DIR=E:\mtah2027-data`
- `E:\mtah2027-data` 是指向 `E:\more-than-a-hack-2027\data` 的 junction，未复制 19 GB 数据
- 数据目录含 `tactical/`、`broadcast/`、`README.md`

## 运行环境

| 项 | 工程包要求 | 本机实际 | 偏差 |
|---|---|---|---|
| Python | 3.12.10 | 3.12.13（uv CPython） | patch 版本差异 |
| numpy | 2.5.4 | 2.5.4 | 无 |
| pytest | 9.2.0 | 9.2.0 | 无 |
| ruff | 0.17.3 | 0.17.3 | 无 |
| pandas | 3.1.0（validator 用） | 3.1.0（独立 validator venv） | 无 |

- 研究 venv：`E:\mtah2027-research\mo\.venv`
- 官方 validator venv：`E:\mtah2027-research\official-validator-venv`

## 冻结输出

```text
File: outputs/submission-state-engine.csv
Rows: 199319
Frames: 0..199318
H: 79250
A: 73608
D: 5999
X: 40462
SHA-256: 1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401
```

与工程包 `00_README_交付说明.md` 的冻结值逐项一致。

## 保存策略

- 不修改 `dev`、`main`、stable tag、research tag。
- 研究只在 `E:\mtah2027-research\mo` 的 `research/mo/independent-v1` 上开展。
- 不把研究分支合并到 `dev/main`。
- 赛事数据、视频、生成 CSV、大日志不进入 Git。
- 研究产物放 `E:\mtah2027-research-artifacts\mo`。

## 已知偏差

- 团队仓库 `E:\mtah2027-code` 初始为空克隆（`.git/HEAD` 指向 `refs/heads/.invalid`，无远程分支 refs）；已通过 fetch、update-ref、symbolic-ref 修复，再建立 worktree。
- Python 使用 3.12.13 而非 3.12.10；未安装旧 patch 版本，避免改动系统环境。
- 官方 validator 使用本机 `E:\more-than-a-hack-2027`（HEAD `f8f2629`，与锁定 commit 一致），未重新 clone。
