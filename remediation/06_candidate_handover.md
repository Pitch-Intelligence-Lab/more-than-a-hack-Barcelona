# 06 — Candidate Handover Card（候选 A）

- 候选名称：Candidate A — dead-ball evidence expansion
- Git Commit：`a4cec76`
- 工作分支：`research/mo/independent-v1`
- 工作区：`E:\mtah2027-research\mo`
- 功能层：L2 Observation

## 模型概述

在冻结 DP-005 规则状态机上增加三条**可选**死球证据：

1. 球出界（球心越过边线/端线，含 0.3 m 余量）；
2. 重启区附近 + 球持续静止；
3. 全队平均速度低 + 球持续静止。

默认配置（`configs/state-engine.json`）全部关闭，DP-005 输出哈希保持 `1de626…9401`。
候选配置（`configs/candidate-a.json`）开启三条证据。

## 模块结构

| 文件 | 作用 |
|---|---|
| `src/mtah_possession/features/dead_ball.py` | 出界证据、全队运动证据 |
| `src/mtah_possession/features/evidence.py` | 在 `build_evidence_series` 中组合可选证据 |
| `src/mtah_possession/algorithm_config.py` | 可选参数注入与校验（旧配置自动使用默认值） |
| `configs/candidate-a.json` | 候选 A 配置 |
| `tests/test_dead_ball_evidence.py` | 合成单元与集成测试 |
| `tests/test_candidate_scenarios.py` | 出界回场、直接转换、crowded box、缺失球、重启区隔离等 11 个场景 |

## 运行环境与依赖

```text
Python 3.12.13
numpy 2.5.4
pytest 9.2.0
ruff 0.17.3
```

未使用 pandas、视频、广播追踪、homography、外部数据或云端模型。

## 输入与输出

- 输入：tactical ATD，经 `MTAH_DATA_DIR=E:\mtah2027-data`
- 输出：`frame,label`，199,319 行，标签 `H/A/D/X`
- 候选输出：`outputs/submission-candidate-a.csv`
- SHA-256：`23089351f6279c887465eb66c32b94a143acdeaf339a240babe659833ad4e23e`

## 复现命令

```bash
cd E:/mtah2027-research/mo
MTAH_DATA_DIR=E:/mtah2027-data \
  ./.venv/Scripts/python.exe scripts/build_submission.py \
  --output outputs/submission-candidate-a.csv \
  --config configs/candidate-a.json \
  --health-report outputs/submission-candidate-a.health.json \
  --force
```

## 测试与校验

```text
pytest -q                 82 passed
pytest -W error -q        82 passed
ruff check .              All checks passed
ruff format --check .     56 files already formatted
project validator         OK
official validator        Valid
```

## 结果摘要

| 指标 | DP-005 | Candidate A |
|---|---:|---:|
| H | 79,250 | 75,453 |
| A | 73,608 | 70,626 |
| D | 5,999 | **12,778** |
| X | 40,462 | 40,462 |
| D segments | 20 | 52 |

## 修正记录

- 首轮候选输出 D=12,335；团队运动门控符号写反（高速被判死、低速反而没死），已修正为低运动才提高死球门控。
- 修正后重建：D=12,778，哈希 `23089351…`。
- 新增 11 个合成场景；全量测试从 71 增至 82 passed。

## 合法评价证据

- 只有合成测试；没有独立比赛数据。
- 没有计算公开窗口分数，也没有用公开/私有 GT 调参。
- 因此必须标记：

```text
GENERALISATION NOT ESTABLISHED
```

## 主要失败与已知限制

- 出界证据可能受追踪噪声影响，边线附近可能误判。
- 全队低速可能把“回撤/等待”误判为死球；当前只在球静止时组合。
- 重启区使用通用锚点，不等于真实重启发生。
- 新增 D 段是否对应真实死球，没有外部标签无法确认。
- 未验证不同数据供应商、不同 fps 和真实拥挤禁区。

## 与冻结底座的接口关系

- 修改 L2 证据层，未修改冻结 L0/L4、CSV 契约、validator 或状态机接口。
- 默认配置输出与 DP-005 完全一致。
- 候选配置通过新增可选参数启用；旧配置无需改动。

## 自检结论

- 工程完整性：通过（测试、validator、确定性哈希）。
- 合规性：本阶段未使用公开/私有 GT、外部数据、视频或人工标注。
- 能力证据：仅合成场景；泛化未建立。
- 建议状态：`READY FOR REVIEW / NOT FOR PROMOTION`。
