# 资源生成案例（六类各 ≥1）+ 质量自评

固定账号：`student001`。行星：计算机网络星系（`osi-model` / `tcp-protocol`）或数据结构（`array-linkedlist`）。

评分维度（1–5）：准确性 A / 贴合画像 P / 可用性 U（系统另有 DeepSeek 自动质量分 A/P/C/H，可对照工坊界面）。

| # | 类型 kind | 行星 slug | 资源标题 | 截图文件 | A | P | U | 备注（幻觉/错误？） |
|---|-----------|-----------|----------|----------|---|---|---|---------------------|
| 1 | doc | osi-model | OSI 七层模型 讲解文档 | `resource_doc_01.png` | 4 | 4 | 5 | 七层定义与分层职责正确，未见明显幻觉 |
| 2 | mindmap | osi-model | OSI 七层模型 思维导图 | `resource_mindmap_01.png` | 4 | 4 | 5 | 七层分支完整；物理/链路/网络要点正确 |
| 3 | quiz | osi-model | OSI 七层模型 练习题 | `resource_quiz_01.png` | 4 | 4 | 5 | choice/blank/code/case 四型；答案与知识点一致 |
| 4 | reading | osi-model | OSI 七层模型 拓展阅读 | `resource_reading_01.png` | 3 | 4 | 4 | 结合队列/栈讲协议缓冲，贴合实践；跨学科略杂 |
| 5 | media | tcp-protocol / array-linkedlist | 教学短视频（Seedance） | `resource_media_01.png` | 4 | 4 | 5 | provider=`seedance_1_0_pro_fast`；可播；工坊显示「Seedance 生成」 |
| 6 | code | tcp-protocol | TCP 协议 代码实操 | `resource_code_01.png` | 4 | 4 | 5 | Python socket 客户端/服务端样例可运行级 |
| 7 | deck | osi-model | 教学课件（翻页 + TTS + PPTX） | `resource_deck_01.png` | 4 | 4 | 5 | kind=`deck`；工坊翻页讲解；可下载 `.pptx` |
| 8 | viz | array-linkedlist / graph | 演武场图结构可视化 | `viz_graph_01.png` | — | — | — | **待补截图**；AlgoViz 含 BFS/DFS/Dijkstra 步进 + predict |
| 9 | media_prov | tcp-protocol | media 溯源 / provider 标签 | `resource_media_provenance_01.png` | — | — | — | **待补截图**；工坊显示 Seedance provider + A/P/C/H |

## 质量自评小结（答辩可用 30 秒）

- 六类是否均成功落库并在资源工坊可回看：**是**（另含 deck 教学课件）
- media 是否可播放短视频：**是**（已开通火山方舟 **Seedance 1.0 Pro Fast**，经接入点生成并本地下载；失败时降级 GSAP/缓存片）
- deck 是否可翻页并 TTS 讲解：**是**（`/api/tts`；失败回退浏览器朗读；可导出 PPTX）
- 质量评分：生成后自动展示 A/P/C/H；低分可重试
- 发现的主要问题与已采取修正：reading 偶发跨学科延伸（队列/栈），答辩时强调「拓展阅读」属性即可
