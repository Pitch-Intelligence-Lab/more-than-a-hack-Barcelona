# 04 — 候选 A 合成测试计划

## 目标

在不读取公开/私有 GT 的前提下，验证候选 A 的三条死球证据与冻结状态机的交互。

## 测试文件

- `tests/test_dead_ball_evidence.py`：7 个单元/集成测试
- `tests/test_candidate_scenarios.py`：11 个边界与组合场景

## 覆盖映射

| 场景 | 覆盖 |
|---|---|
| S03/S04 直接 H↔A | `test_candidate_config_keeps_direct_team_changes` |
| S05 crowded box | `test_crowded_box_does_not_trigger_dead` |
| S08 静止球但活球 | `test_still_ball_with_fast_team_is_not_dead_by_motion`、`test_still_ball_with_slow_team_is_dead_by_motion` |
| S09 出界 | `test_out_of_play_uses_a_metric_margin`、`test_out_of_play_y_axis_and_exact_line` |
| S10 出界未开球 | `test_out_of_play_then_return_recovers`（D 段） |
| S11 重新进场 | `test_out_of_play_then_return_recovers`（离开 D） |
| S12 短时丢失 | `test_short_ball_loss_is_not_out_of_play_or_dead` |
| S13 长时丢失 | `test_long_ball_loss_is_not_treated_as_out_of_play`（仅验证不误判出界） |
| S14 球员追踪缺失 | `test_team_motion_accepts_no_speed_channel`、`test_team_motion_is_the_mean_tracked_speed` |
| S16 快速转换 | `test_candidate_config_keeps_direct_team_changes` |
| S18 死球恢复 | `test_restart_zone_requires_proximity_and_rest` |

未在候选测试中单独覆盖：

- S01/S02 稳定控球：由冻结底座 `tests/test_state_engine.py` 和 `tests/test_possession.py` 部分覆盖；
- S06 正常传球、S07 反弹/折射：由冻结底座 `test_state_engine.py::test_rapid_one_frame_pass_near_opponent_does_not_switch` 覆盖简化情形；
- S15 身份/轨迹变化：仍为 `BLOCKED`，需要合成 ATD 身份切换；
- S17 极短控球：由冻结底座 `test_state_engine.py::test_short_team_flicker_is_cleaned_but_d_is_preserved` 覆盖。

## 约束

- 所有输入由代码构造，不从公开 GT 截取。
- 不读取 `evaluation/gt/`。
- 不把测试结果用于模型/版本选择。
- 参数敏感性测试只用合成数据。
