# 教学短视频

## 生成产物（主路径）

MediaAgent 调用火山方舟 **Seedance 1.0 Pro Fast**（接入点 ID）。

当前项目配置示例：

| 项 | 值 |
|----|-----|
| Model ID | `doubao-seedance-1-0-pro-fast-251015` |
| 接入点 ID（写入 `ARK_SEEDANCE_MODEL`） | `ep-m-...` |
| 默认时长 | `12` 秒（模型上限 2–12） |
| 分辨率 / 比例 | `720p` / `16:9` |

请求格式（对齐官方 Rest）：

- `model`：接入点 ID（`ep-...`）
- `content[0].text`：教学提示词 + `--resolution 720p --ratio 16:9 --duration 12 --camerafixed false --watermark false`
- 有 `ARK_SEEDANCE_IMAGE_URL` 时附加 `content[1].image_url`（图生视频）；否则仅 text（文生视频）

产物：`generated/{planet_slug}_{uuid}.mp4`（成功烧录字幕后为 `*_cap.mp4`）  
访问：`/static/media/generated/<filename>.mp4`

说明：Seedance 1.0 无法可靠渲染中文，请求侧**禁止片内文字**；可读中文字幕由分镜旁白生成，经 ffmpeg 烧录，前端播放时同步叠加。

未配置密钥或调用失败时，降级为 DeepSeek 分镜动画 / 精确 slug 预置缓存。

## 预置缓存（降级加速）

根目录下与行星 `slug` **精确同名** 的 `.mp4` 仅作缓存加速（`provider=cache_mp4`）。

| 文件 | 知识点 |
|------|--------|
| `tcp-protocol.mp4` | TCP 协议 |
| `osi-model.mp4` | OSI 七层模型 |
| `process-thread.mp4` | 进程与线程 |

