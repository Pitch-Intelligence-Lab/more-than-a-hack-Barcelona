# 06 — PM Review Card（候选 A）

- 候选名称：Candidate A — dead-ball evidence expansion
- 候选提交：`81bdaf1`（研究分支 `research/mo/independent-v1`）
- 审查日期：2026-11-06
- 审查状态：`PENDING PROJECT OWNER REVIEW`

## 合规审查

- 未读取公开 5 分钟 GT、私有全场 GT、视频、人工标注或外部比赛数据。
- 未计算公开窗口分数，未用公开窗口调参或选版。
- 本地 tactical ATD 仅用于工程构建和输出校验。
- 研究 worktree 无 `evaluation/gt/` 引用；合成测试只用代码构造轨迹。
- 结论：本阶段合规；历史公开 GT 选版问题已在个人仓库 `docs/compliance.md` 披露，属于另一仓库整改线。

## 工程完整性

- `pytest -q`：82 passed。
- `pytest -W error -q`：82 passed。
- `ruff check .` / `ruff format --check .`：通过。
- 项目 validator：OK。
- 官方 validator：Valid。
- 默认 DP-005 输出未被改变（`1de626…9401`）。
- 候选输出 199,319 行、标签合法、确定性哈希 `23089351…4e23e`。

## 接口契约

- 只修改 L2 证据层；未修改 L0/L4、CSV 契约、validator 或状态机接口。
- 新增参数为可选项；旧配置缺少时使用默认值。
- 候选配置 `configs/candidate-a.json` 显式开启三条证据。

## 测试完整性

- 候选测试：`tests/test_dead_ball_evidence.py` 7 个，`tests/test_candidate_scenarios.py` 11 个。
- 覆盖出界、回场、直接转换、crowded box、静止球、短/长缺失、重启区隔离。
- 缺口：S15 身份切换未覆盖；S13 仅验证“长缺失不被当出界”，未验证不确定性表达。
- 合成测试不能替代外部验证。

## 复现结果

- 冻结基线：199,319 行，哈希 `1de6261504c7cb539a4e78f42f18011c692b9bd148ea3e77fbca44df9c0b9401`。
- 候选：H=75,453，A=70,626，D=12,778，X=40,462；哈希 `23089351f6279c887465eb66c32b94a143acdeaf339a240babe659833ad4e23e`。
- 候选 D 从 5,999 增至 12,778；结构变化需要外部数据验证。

## 独立评价证据

- 无。没有合法独立比赛数据。
- 泛化状态：`GENERALISATION NOT ESTABLISHED`。

## 失败分析

- 初版团队运动门控符号写反，已修正并加入反例测试。
- 出界证据对追踪噪声敏感，边线附近可能误判。
- 重启区锚点是通用几何点，不是事件数据。
- 全队低速可能把战术回撤误判为停摆。
- 长时球丢失没有 X 弃权机制。

## 未解决问题

- 外部数据未申请、未批准；跨比赛验证 `BLOCKED`。
- S15 身份切换场景未覆盖。
- 候选阈值全部是工程假设，未在独立数据上验证。
- 未验证不同供应商、不同 fps、真实拥挤禁区。

## Candidate Gate 结论

| Gate | 结论 |
|---|---|
| Gate 1 合规 | 通过（本阶段） |
| Gate 2 接口 | 通过 |
| Gate 3 工程 | 通过 |
| Gate 4 能力证据 | 未建立（无独立数据） |
| Gate 5 解释 | 部分通过（研究卡/实验记录/交接卡已有） |

## 是否建议进入后续比较

不建议。等待项目负责人审阅，并在外部数据批准后完成跨比赛验证。

## PM 结论

待填写。

## 项目负责人最终决定

待填写。

> 本卡片不构成模型晋级、稳定分支合并或泛化结论。
