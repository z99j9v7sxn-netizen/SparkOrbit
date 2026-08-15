---
description: 费曼讲闸评分与画像回流。
---

- score≥explain_pass_threshold（默认约 0.75）→ `pass_explain_gate`
- 记录 `feynman_explain` 学习事件并 `refresh_profile_from_events`
- 讲闸通过后可尝试 `try_light_planet`，并触发路径同步
