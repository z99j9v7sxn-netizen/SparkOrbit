# 评分证据包使用说明

固定演示账号（仓库 seed；**队内备忘**，正式设计文档附录不写明文口令）：

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 学生 | `student001` | `123456` |
| 教师 | `teacher001` | `123456` |
| 管理员 | `admin001` | `123456` |

## 截图目录规范

将截图放入本目录下 `screenshots/`（可自建），命名约定：

```
screenshots/
  resource_doc_01.png
  resource_mindmap_01.png
  resource_quiz_01.png
  resource_reading_01.png
  resource_media_01.png      # 含视频播放器画面
  resource_code_01.png
  path_before_01.png
  path_after_01.png
  tutor_socratic_01.png … tutor_socratic_05.png
  eval_report_01.png … eval_report_03.png
  resource_deck_01.png       # 教学课件翻页 + TTS
  viz_graph_01.png           # 演武场图结构可视化
  resource_media_provenance_01.png  # media 溯源 / provider 标签
  digital_tutor_planet_01.png
  digital_tutor_mistake_gsap_01.png
  starlib_selection_ask_01.png
  codelab_server_run_01.png
  hallu_ticket_teacher_01.png
```

### 当前入库（2026-07-17）

| 文件 | 状态 |
|------|------|
| 六类资源 ×6 | ✅ |
| 路径 before×1 + after×3 | ✅（#2/#3 无单独 before） |
| 苏格拉底 ×5 | ✅ |
| 成长报告 ×1 | ✅（建议再补 2 阶段） |
| 演武图可视化 | ⬜ `viz_graph_01.png` |
| media 溯源 | ⬜ `resource_media_provenance_01.png` |
| 教学课件 deck | ⬜ `resource_deck_01.png` |
| 教师低置信工单 ×1 | ✅ |

## 建议操作顺序（学生 → 教师）

1. 登录 `student001` → 学习区 → 镜像画像对话补齐六维。
2. 资源工坊：对同一行星依次生成 doc / mindmap / quiz / reading / media / deck / code；**media 须可播 Seedance 短视频**（截「Seedance 生成」+ 质量评分），填 [`resource_cases.md`](resource_cases.md)。
3. 记录当前学习路径截图 → 修改/刷新画像（或从成长评估点「按评估重排路径」）→ 再截路径，填 [`path_cases.md`](path_cases.md)。
4. 行星面板「苏格拉底 / 费曼」Tutor 录对话，填 [`tutor_cases.md`](tutor_cases.md)。
5. 成长报告截 3 份（不同掌握阶段更佳），填 [`eval_cases.md`](eval_cases.md)。
6. 挑战提交后确认「依据知识点」展示；触发低置信后用 `teacher001` 打开风险/工单，截图。
7. 按 [`demo_script.md`](demo_script.md) 录制 **8–10 分钟**实操视频（系统演示占比 ≥60%；休闲区 ≤10%）。

## 清单勾选

- [x] `resource_cases.md` 六类各 ≥1 + 自评表（deck 行已加，截图待补）
- [x] `path_cases.md` 3–5 条换画像前后对比（3 条已填；可选 4–5 未截）
- [x] `tutor_cases.md` 5 段苏格拉底对话
- [ ] `eval_cases.md` 3 份评估报告（已有 1 份含雷达；建议再补 2 阶段 + 划词热力）
- [ ] `screenshots/viz_graph_01.png` 演武场图可视化
- [ ] `screenshots/resource_media_provenance_01.png` media 溯源
- [ ] `screenshots/resource_deck_01.png` 教学课件
- [ ] `screenshots/eval_report_02.png` / `eval_report_03.png`
- [ ] 星库划词 `starlib_selection_ask_01.png`
- [ ] 数字人行星/错题分镜截图（见 SCREENSHOT_SLOTS）
- [x] 教师低置信工单 `hallu_ticket_teacher_01.png`
- [ ] `interview_cases.md` 模拟面试 6 条（截图待补）
- [ ] `pitch_60s.md` 队员已背诵
- [ ] 待补槽位见 [`screenshots/SCREENSHOT_SLOTS.md`](screenshots/SCREENSHOT_SLOTS.md)
