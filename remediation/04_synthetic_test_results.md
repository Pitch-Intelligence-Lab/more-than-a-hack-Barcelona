# 04 — 候选 A 合成测试结果

## 执行环境

```text
仓库：E:\mtah2027-research\mo
分支：research/mo/independent-v1
Python：3.12.13
numpy：2.5.4
pytest：9.2.0
ruff：0.17.3
```

## 命令与结果

```text
pytest -q                 82 passed
pytest -W error -q        82 passed
ruff check .              All checks passed
ruff format --check .     56 files already formatted
```

候选测试：

- `tests/test_dead_ball_evidence.py`：7 passed
- `tests/test_candidate_scenarios.py`：11 passed
- 其余为冻结底座原有测试。

## 发现并修复的问题

- 首轮候选的团队运动门控符号写反：高速被判死、低速反而没死。
- 已修正为“低运动才提高死球门控”，并加入高速反例测试。
- 修正后重建候选：D=12,778，输出哈希 `23089351f6279c887465eb66c32b94a143acdeaf339a240babe659833ad4e23e`。

## 已知限制

- 没有独立比赛数据；`GENERALISATION NOT ESTABLISHED`。
- S15（身份切换）仍未覆盖。
- S13 只验证“长缺失不被当成出界”，没有验证不确定性表达。
- 出界、重启区、全队运动阈值都是工程假设，需要外部数据验证。
- 合成测试不能替代跨比赛验证。
