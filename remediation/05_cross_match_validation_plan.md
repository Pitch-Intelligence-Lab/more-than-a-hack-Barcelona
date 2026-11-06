# 05 — 跨比赛验证计划（候选 A）

- 状态：`BLOCKED / PENDING DATA APPROVAL`
- 日期：2026-11-06
- 范围：`research/mo/independent-v1`

## 目标

验证候选 A 的死球证据是否可迁移到其他比赛，而不是只适配 BAR-ATH 或合成轨迹。

## 数据 Gate

- 未获项目负责人明确批准前，不下载、不读取、不训练、不调参、不验证任何外部比赛数据。
- SkillCorner 当前暂停，不得使用。
- Metrica Sports Sample Data 需先核对许可证、字段、标签定义和 D/X 可映射性。
- 任何数据使用必须先提交 `05_external_data_request.md`。

## 划分

- 采用整场比赛级 train / validation / holdout，禁止按帧随机拆分。
- 6 场研发 / 2 场验证 / 2 场 holdout 仅作讨论，不构成泛化证明。
- 同一比赛、同一球队、相邻片段不得跨 split 泄漏。
- 接触 holdout 前冻结代码 commit、参数、配置、依赖和评价脚本。

## 指标

- spellF1、macroF1；
- H/A/D 各类 Precision / Recall / F1；
- D 类 Precision / Recall / F1；
- False Merge、False Split；
- possession fragmentation；
- 每场独立结果与跨场波动；
- 数据来源、标签定义、质量限制。

不同来源标签不可比时分开报告，不混合成单一总分。

## 标签映射

- 先核对外部数据的 possession 定义是否与 H/A/D/X 一致。
- 若没有 D 或 X 参考标签，不得假定等价；需单独说明评价范围或设计人工标注方案（需另行批准）。

## 当前阻塞

- 没有已批准的外部数据源。
- 未提交数据申请。
- 本阶段只完成计划与申请模板，没有执行外部数据实验。
- 候选泛化状态仍为 `GENERALISATION NOT ESTABLISHED`。
