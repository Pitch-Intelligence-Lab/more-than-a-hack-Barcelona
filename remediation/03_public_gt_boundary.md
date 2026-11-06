# 03 — 公开 GT 使用边界（研究 worktree）

## 允许的用途

公开 5 分钟 GT 只允许在个人仓库的 smoke-only 入口用于：

- 帧对齐；
- 文件格式、行数、帧号；
- 标签词表；
- validator 连通性。

## 禁止的用途

- 训练、调参、阈值选择；
- 模型/版本选择；
- 公开窗口错例分析并据此改算法；
- 用公开分数判断版本优劣。

## 本候选的实际使用

- `src/`、`tests/`、`scripts/`、`configs/` 中没有读取 `evaluation/gt` 的路径。
- 检索 `evaluation/gt|possession_gt|ground.?truth` 只命中：
  - `tests/test_candidate_scenarios.py` 的注释“no competition ground truth is read”；
  - `tests/test_algorithm_config.py` 用非法 source 字符串 `target-ground-truth` 测试配置拒绝；
  - `features/possession.py` 的注释“No label is chosen using this match's ground truth”。
- 本地 tactical ATD 只用于工程构建和输出校验，不用于训练/调参。
- 没有计算公开窗口分数。
- 外部数据未批准，未下载、未读取、未使用。

## 隔离

- 研究 worktree 不包含 `evaluation/gt/`。
- 合成测试只用代码构造的轨迹。
- 公开 GT 的 smoke-only 入口在个人仓库 `E:\makalofusiki-competition-v1\evaluation\smoke_only\`，不在研究 worktree。
- 研究流程不 import 评分器。

## 风险

- 开发者仍可手工运行 evaluator 看到公开分数；隔离依赖流程，不是沙箱。
- 如果未来接入外部数据，必须先走 `05_external_data_request.md` 审批。
