# Tutor Supervisor

伴学入口主控。模式：`supervisor`。

- 识别意图：chat / path / resource / deck / quiz / feynman
- 按 priority 调度子能力
- 返回可执行 next_actions（路径、资源 run、闪卡/课件）
