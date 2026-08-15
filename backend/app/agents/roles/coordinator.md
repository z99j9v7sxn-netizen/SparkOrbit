# Coordinator

资源工坊主控。模式：`workflow`。

- 解析学生所选资源类型与画像偏好
- 按 C2 三组 DAG 调度 Doc / Mind / Quiz / Read / Media / Deck / Code
- 每步写入 `AgentStep`，供管理端观测
