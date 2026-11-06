# Module Card — Tang Candidate B

## 模块名称

Tang Candidate B: Evidence → H/A/D Emission → Viterbi Adapter

## 功能层

- L1 Feature: 复用冻结 tracking/ball observation，构建逐帧证据和 validity。
- L2 Observation: 输出逐帧 `[s_H, s_A, s_D]` 概率、置信度和有效性。
- L3 Decoder: 用三状态 Viterbi 解码 H/A/D，X 只用于冻结的 ungraded blocks。
- L0/L4: 完全复用冻结底座；不修改 `configs/state-engine.json`、冻结 pipeline 或 validator。

## 职责

1. 从冻结输入提取弱/强证据，并明确每个证据的缺失语义。
2. 将证据融合为可比较、可消融的逐帧 H/A/D 概率。
3. 用时间转移约束解码，减少短碎片和错误切换，同时保留死球与 restart。
4. 通过独立 Adapter 输出 199,319 行 CSV 和聚合健康报告。

## 输入

- `MTAH_DATA_DIR/tactical/BAR-ATH_tactical_atd.xml`
- `MTAH_DATA_DIR/tactical/BAR-ATH_tactical_atd.txt`
- `MTAH_DATA_DIR/tactical/BAR-ATH_tactical_smart_tagging.xml`
- Candidate config: `configs/candidates/tang/candidate-b.json`

## 输出

- `frame,label` CSV，frame 0..199318，label ∈ {H, A, D, X}
- 聚合 health JSON：标签计数、段统计、转移统计、输入/输出 SHA-256、emission validity、
  Smart Tagging 冲突计数
- 不输出原始比赛行、截图或视频内容

## Schema

### L1 Feature

```text
frame_index: int
ball_usable: bool
home_distance_m: float | nan
away_distance_m: float | nan
home_votes: int
away_votes: int
tracking_candidate: H | A | none
ball_speed_mps: float | nan
ball_rest_s: float
out_of_bounds: bool
smart_team: H | A | none
smart_restart: bool
smart_dead: bool
smart_conflict: bool
```

### L2 Emission

```text
frame_index: int
p_H: float
p_A: float
p_D: float
confidence: float
valid: bool
score_semantics: normalized probability
```

### L3 Decoder

```text
frame_index: int
label: H | A | D | X
decoder_state: H | A | D
confidence: float
```

## 帧对齐

ATD `frame_id` 1..199319 转为视频 frame 0..199318。Smart Tagging 使用
`round(seconds * 25)`。所有输出必须与冻结 L4 契约一致。

## 缺失值语义

- 球缺失：不生成 nearest/vote 候选；不得因为“缺失”本身产生 D。
- 球员缺失：只使用有限可见 slot；不把 NaN 当作距离。
- Smart Tagging `N/A`：team prior 为 none，不默认到 H 或 A。
- Smart Tagging 与 tracking 冲突：保留 tracking 强证据，记录 conflict，不用弱先验覆盖。
- Emission 无效：输出 uniform 概率且 `valid=False`，由解码器的状态持续性处理，不静默填标签。

## 依赖

- Python 3.12
- NumPy 2.5.4
- pytest 9.2.0
- Ruff 0.17.3

不依赖 pandas、外部 API、网络模型或 SkillCorner。

## 运行命令

```bash
MTAH_DATA_DIR=/mnt/d/mtah2027-data \
  .venv/bin/python scripts/build_candidate_tang.py \
  --output outputs/candidate-b.csv \
  --config configs/candidates/tang/candidate-b.json \
  --health-report outputs/candidate-b.health.json \
  --force
```

消融配置：

```bash
MTAH_DATA_DIR=/mnt/d/mtah2027-data \
  .venv/bin/python scripts/build_candidate_tang.py \
  --output outputs/candidate-b-no-smart.csv \
  --config configs/candidates/tang/candidate-b-no-smart.json \
  --health-report outputs/candidate-b-no-smart.health.json \
  --force
```

## 当前优化迭代

以下数字是结构对照，不是准确率或泛化结论：

| 迭代 | H/A possession | D 段 | H/A 平均时长 | D 平均时长 | SHA-256 |
|---|---:|---:|---:|---:|---|
| 初版 emission + Viterbi | 436 | 69 | 12.2 s | 15.1 s | `866f…` |
| + 争夺球权门控 + 有效性清理 + D 锐化 | 410 | 107 | 12.7 s | 10.6 s | `3ec2…` |
| + D 独立短时平滑 | 406 | 101 | 12.9 s | 11.2 s | `42e0…` |
| + 低置信短片段过滤 | 406 | 101 | 12.9 s | 11.2 s | `42e0…` |
| + 5 m 控制区上限 | 384 | 96 | 13.5 s | 12.3 s | `db24…` |
| 关闭 Smart Tagging 消融 | 333 | 72 | 17.6 s | 6.7 s | `8f2a…` |

夺权门控参数为 `contest_margin_m=1.5`：双方离球都近且可见投票分裂时，不强行给 H/A
候选，由解码器保持上一状态。H/A 使用 50 帧平滑，D 使用 5 帧短平滑。最近球员超过
`max_control_distance_m=5` 时，球被视为不在明确控制区内，同样不强行给 H/A。

## 文献依据

- R-01 `arXiv:2202.00804`：possession zone / duel zone，支持控制区和争抢门控。
- R-02 `arXiv:2005.04020`：possession interval 和 duel 作为控球变化事件。
- R-03 `arXiv:2311.18028`：segment-level duration/confidence filtering。
- R-04 `arXiv:2206.10926`：change-point segmentation，作为后续 L3 比较方向。

详见 `docs/research/reference-register-tang.md`。这些只用于方法启发，没有复制代码、外部标签或
比赛数据。

## 单元测试

- 直接 H→A / A→H 切换
- 短球遮挡不切状态
- 长球缺失不因缺失本身产生 D
- 球静止 + restart 进入/离开 D
- 越界球产生 D
- Smart Tagging team 与 tracking 冲突时 tracking 优先
- ungraded 输出 X，forced-dead 输出 D
- 输出 199,319 行并通过冻结 validator
- 重复运行字节一致

## 上下游接口

- 上游：冻结 `load_tactical_tracking`、`prepare_ball_observations`、L0 数据路径。
- 下游：冻结 `write_submission_atomic`、`validate_submission`、L4 CSV。
- Candidate 自身是独立 Adapter；不修改冻结 `pipeline.build_submission` 或稳定配置。

## 替换方式

- `emission.py` 可替换为其他 H/A/D 评分器。
- `decoder.py` 可替换为 HMM、CRF、DP 或端到端序列模型。
- 只要保持 L2/L3 schema 和 L4 输出契约，其他模块可独立替换。

## 已知限制

- 没有合法独立评价数据，结论必须标记 `GENERALISATION NOT ESTABLISHED`。
- Smart Tagging 是自动推断，不是 ground truth；team 标签不代表 possession。
- 球缺失比例高；缺失语义和状态持续性仍是主要误差源。
- 当前不训练任何模型，不做参数搜索；参数只记录工程假设与通用足球先验。
