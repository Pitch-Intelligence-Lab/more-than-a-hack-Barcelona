# 06 — Experiment Log: Candidate A dead-ball evidence

- Experiment ID：E-A-001
- 日期：2026-11-06
- 研究问题：能否用多个独立证据替代单一 ball-rest，提高 D 识别？
- 假设：出界是高精度证据；重启区+静止、全队低速+静止是中等/弱证据；组合后覆盖更多死球形态。
- 功能层：L2 Observation
- 数据来源：tactical ATD（`MTAH_DATA_DIR=E:\mtah2027-data`）用于工程构建；合成轨迹用于测试
- 许可证/用途：比赛数据仅用于本地工程运行；不用于训练/调参；未读取公开或私有 GT
- train/validation/holdout：不适用（规则模型，无训练）
- 代码版本：`research/mo/independent-v1`（候选提交见 Handover Card）
- 配置：`configs/candidate-a.json`
- 运行命令：

```bash
cd E:/mtah2027-research/mo
MTAH_DATA_DIR=E:/mtah2027-data \
  ./.venv/Scripts/python.exe scripts/build_submission.py \
  --output outputs/submission-candidate-a.csv \
  --config configs/candidate-a.json \
  --health-report outputs/submission-candidate-a.health.json \
  --force
```

## 实际结果

```text
Rows: 199319
H: 75453
A: 70626
D: 12778
X: 40462
Segments: H=171, A=176, D=52
Transitions: D->A=27, A->H=147, H->A=149, H->D=22, D->H=24, A->D=28
Forced D block: 2934/2934 D
Cleanup removed: H=1, A=0, D=0
SHA-256: 23089351f6279c887465eb66c32b94a143acdeaf339a240babe659833ad4e23e
```

## 与冻结 DP-005 对照

| 指标 | DP-005 | Candidate A | 变化 |
|---|---:|---:|---|
| H | 79,250 | 75,453 | −3,797 |
| A | 73,608 | 70,626 | −2,982 |
| D | 5,999 | 12,778 | **+6,779** |
| X | 40,462 | 40,462 | 0 |
| D segments | 20 | 52 | +32 |
| Rows | 199,319 | 199,319 | 0 |

默认配置重建哈希仍为 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`，说明新证据在冻结配置中完全关闭。

## 修正记录

- 首轮候选输出为 D=12,335；随后发现团队运动门控符号写反（高速被判死、低速反而没死），已修正为低运动才提高死球门控。
- 修正后重建：D=12,778，哈希 `23089351…`。
- 新增 11 个合成场景，覆盖出界回场、直接攻守转换、crowded box、静止球、短/长缺失、重启区隔离。

## 验证

```text
pytest -q                 82 passed
pytest -W error -q        82 passed
ruff check .              All checks passed
ruff format --check .     56 files already formatted
project validator         OK
official validator        Valid
```

## 主要发现

1. 组合证据把 D 从 5,999 提升到 12,778 帧，且 X 未泄漏到评分块。
2. H/A 相应下降，说明新增 D 主要来自原先被判为 H/A 的帧。
3. 默认 DP-005 输出不变，说明可选参数的注入没有改变冻结行为。
4. 修正后的团队运动门控只在“球静止且全队低速”时触发；高速比赛不会被误判为死球。
5. 出界回场后可以从 D 恢复到球队状态；直接 H↔A 转换不会被新增证据阻断。

## 失败类型与限制

- 没有独立评价数据；`GENERALISATION NOT ESTABLISHED`。
- 没有计算公开窗口分数；不得用公开窗口选择阈值或版本。
- 出界证据可能受追踪噪声影响，边线附近的误判需要外部数据验证。
- 全队低速可能把“控球方回撤/等待”误判为死球；当前只在球静止时组合使用。
- 重启区距离使用通用锚点，不等于真实重启发生。
- 新增 D 段是否对应真实死球，无法在没有外部标签的情况下确认。

## 可复现性

- 相同代码、配置和数据生成相同哈希。
- 候选输出与健康报告位于 `outputs/`（本地，不提交）。
- 测试不读取比赛数据或 GT。
