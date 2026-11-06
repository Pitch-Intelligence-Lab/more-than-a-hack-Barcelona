# Research Card — Tang Candidate B

## 研究问题

在冻结 L0/L4、冻结输入和冻结 DP-005 基线的前提下，能否用统一的逐帧 H/A/D
emission 分数 `[s_H, s_A, s_D]` 加轻量时序解码，替代当前“离散候选 + 硬规则组合”的证据链，
在减少 H/A possession 碎片化的同时保留真实的死球与 restart 边界？

## 研究假设

连续、可校准的 H/A/D 分数，配合显式的缺失/质量不确定性和时序转移约束，会比当前硬规则状态机
更稳定。Smart Tagging 只能作为弱先验：tracking 有候选时不得被 Smart Tagging 覆盖；两者冲突
必须保留强证据并记录诊断。

## 功能层

- L1：复用冻结底座的特征与输入，不修改 L0。
- L2：新增统一的逐帧 H/A/D emission 接口，输出分数、语义和 validity。
- L3：新增可替换的时序解码器（例如动态规划/Viterbi 风格的候选），输出最终 H/A/D/X。
- L4：完全复用冻结 CSV、validator、确定性和交付语义。

## 参考论文 / 项目

- 官方 More Than a Hack 2027 baseline 与评分器。
- 冻结 DP-005 技术报告和 decision log。
- 具体论文/开源实现待进入 Development 前补入 `reference-register`，并记录许可证与适用性。

## 核心方法

1. 从冻结输入构建逐帧 feature/evidence 向量，并显式携带缺失与质量。
2. 将 tracking、球速/静止、越界、Smart Tagging team/restart 等证据融合为 H/A/D 分数。
3. 用可替换解码器利用时间上下文，显式建模 D 与 restart，不允许用 D 自动连接 H/A。
4. 通过 candidate adapter 接入，不修改冻结 `configs/state-engine.json`、冻结 pipeline 或 L4。
5. 先做合成测试和聚合诊断，再做合法独立评价；没有外部数据就标记
   `GENERALISATION NOT ESTABLISHED`。

## 预期优势

- 每个特征对 H/A/D 的贡献可比较、可消融、可校准。
- 解码器可替换，不再把 evidence 冲突隐藏在硬规则里。
- H/A possession 更平滑，减少短碎片和错误切换。
- 死球与 restart 通过分数和转移约束处理，而不是通过无限增加布尔信号。

## 失效条件

- 需要修改冻结 L0/L4、冻结接口或稳定配置才能接入。
- 需要读取本场答案、视频、人工标注或未获批准的外部数据。
- 需要靠公开五分钟 ground truth 调参或选择模型。
- 不能生成 199,319 行、不能通过 validator、不能确定性复现。
- 聚合结果显示 H/A 碎片化反而增加，或 D 误判无法解释。

## 验证方式

- 冻结底座 64 项测试继续全部通过。
- 新增合成测试覆盖：短遮挡、长缺失、直接 H/A 切换、死球/restart、短 flicker、
  X 边界、缺失 slot、Smart Tagging 冲突和确定性。
- 生成完整 199,319 行 CSV，通过项目和官方格式 validator，记录 SHA-256。
- 只做聚合统计和来源分解；公开五分钟只用于 pipeline smoke，不用于模型选择。
- 在没有合法独立评价数据前，明确写 `GENERALISATION NOT ESTABLISHED`。

## 数据合规状态

- 只使用冻结 local tactical 数据，通过 `MTAH_DATA_DIR` 读取。
- 不使用 SkillCorner，不读取/下载新的外部比赛。
- 不使用本场答案、视频、人工标注或手工修正。
- 赛事数据、生成 CSV、大日志不进入 Git/Notion/云端 AI。

## 是否需要外部数据批准

第一阶段不需要外部数据。若后续需要跨比赛验证，先按 Common Governance 的 External Data
Gate 向何提交申请，未批准前不启动。

## 时间盒

```text
Start: 2026-11-07
Research question: unified H/A/D emission + temporal decoding
Expected time: 1-2 focused days for interface + synthetic evaluation
Stop condition: requires frozen-interface change, external data, or public-GT tuning
Next decision: PM review of the Research Card before promotion to a candidate gate
```
