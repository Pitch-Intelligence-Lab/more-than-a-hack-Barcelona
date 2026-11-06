# 02 — 候选 A 算法与设计审查

## 1. 出界证据

实现：`src/mtah_possession/features/dead_ball.py`。

- 坐标归一化到 `0..1`；`margin_m` 按轴换算为归一化余量。
- 球心越线超过余量即判出界；缺失球不参与。
- 这是规则先验：球出界后比赛通常死球，直到重新开球。
- 风险：追踪噪声、边线附近误判、球被遮挡但实际未出界。
- 处置：`REVIEW`；需要外部数据验证边线附近误判率。

## 2. 重启区 + 静止证据

实现：`features/evidence.py` 的 `use_restart_zone_dead_ball` 分支。

- 球在通用重启锚点 8 m 内，且球已静止 ≥1.5 s。
- 通用锚点包括角旗、端线中点、中线中点；不等于真实重启事件。
- 风险：中场静止球靠近中线锚点时可能误判；锚点不覆盖所有重启类型。
- 处置：`REVIEW`；合成测试只验证“角旗区静止”和“非重启区静止”。

## 3. 全队运动证据

实现：`features/dead_ball.py::team_motion_evidence` 与 `evidence.py` 的 `use_team_motion_dead_ball`。

- 每帧对所有可见槽位的速度取均值；全 NaN 返回 NaN。
- 只有“球静止 ≥1.5 s 且全队平均速度低”才组合成死球。
- 初版门控符号写反（高速被判死、低速反而没死），已修正为低运动才提高死球概率。
- 风险：控球方回撤/等待、比分领先时的控球可能被误判。
- 处置：`REVIEW`；需要外部数据验证。

## 4. 组合逻辑

```text
dead = ball_rest
       OR out_of_play
       OR (restart_zone & ball_rest)
       OR (low_team_motion & ball_rest)
```

- 所有新证据默认关闭；冻结 `state-engine.json` 输出不变（哈希 `1de626…9401`）。
- 候选配置 `configs/candidate-a.json` 开启三条新证据。
- 不改冻结 L0/L4、CSV 契约、validator 或状态机接口。

## 5. 与冻结底座的接口

- 只修改 L2 证据层 `features/evidence.py`，新增 `features/dead_ball.py`。
- `algorithm_config.py` 增加可选参数注入；旧配置缺少新参数时使用默认值。
- 未修改 L0 数据加载、L4 输出/校验。

## 6. 主要风险

- 没有独立评价数据，所有阈值都是工程假设。
- 出界证据对追踪噪声敏感。
- 重启区锚点是通用几何点，不是事件数据。
- 全队运动可能把战术回撤误判为停摆。
- 长时球丢失仍没有 X 弃权机制。

## 7. 结论

候选 A 是结构上可解释的 L2 扩展，能提高合成场景中的死球覆盖，并且不改变冻结基线。它**没有**独立数据支持泛化，状态应为 `READY FOR REVIEW / NOT FOR PROMOTION`。
