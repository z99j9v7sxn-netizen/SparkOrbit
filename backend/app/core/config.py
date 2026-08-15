from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SparkOrbit 星轨学图 API"
    api_prefix: str = "/api"
    database_url: str = "mysql+aiomysql://root:Aa040330@127.0.0.1:3306/sparkorbit?charset=utf8mb4"

    # DeepSeek — 全系统智能体大脑
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 思想防火墙：默认仅关键词快筛；设为 true 时对每条输出额外调用 LLM 审核（更慢）
    shield_use_llm: bool = False

    # 通义千问 — 自拍卡通化（DashScope 多模态端点）
    qwen_api_key: str = ""
    qwen_base_url: str = "https://ws-eabsfkhsqysf9ux7.cn-beijing.maas.aliyuncs.com"
    qwen_image_model: str = "qwen-image-edit"

    # 讯飞 — 语音听写 IAT / 口语评测 ISE / 在线 TTS
    xf_app_id: str = ""
    xf_api_key: str = ""
    xf_api_secret: str = ""
    xf_tts_vcn: str = "xiaoyan"

    # 讯飞 — 数字人视频大模型（优先；未填时回退到上方 XF_*）
    xf_dh_app_id: str = ""
    xf_dh_api_key: str = ""
    xf_dh_api_secret: str = ""
    xf_dh_host: str = "vms.cn-huadong-1.xf-yun.com"
    xf_dh_word_count: int = 80
    xf_dh_poll_interval: int = 5
    xf_dh_timeout: int = 900  # 秒；与前端 DigitalTutorPanel 轮询超时对齐

    # 讯飞 — 虚拟人交互平台（avatar-sdk-web，按 WS 展示时长计费）
    xf_vms_app_id: str = ""
    xf_vms_api_key: str = ""
    xf_vms_api_secret: str = ""
    xf_vms_scene_id: str = ""
    xf_vms_avatar_id: str = "201293001"
    xf_vms_vcn: str = "x7_langxiao_pro"
    xf_vms_server_url: str = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"
    xf_vms_idle_sec: int = 90

    # cantonese.ai — 粤语 STT + 发音评分
    cantonese_ai_api_key: str = ""
    cantonese_ai_base_url: str = "https://cantonese.ai/api"

    # ffmpeg — 口语录音转码（webm→ogg/aac、16kHz PCM）；可填 bin 目录或 ffmpeg.exe 完整路径
    ffmpeg_path: str = ""

    # 火山方舟 Seedance — 视频生成（优先填接入点 ID ep-...；官方示例参数写在 prompt 里）
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_seedance_model: str = "ep-20260719092103-fd5fj"
    ark_seedance_foundation_model: str = "doubao-seedance-1-0-pro-fast-251015"
    ark_seedance_duration: int = 12
    ark_seedance_resolution: str = "720p"
    ark_seedance_ratio: str = "16:9"
    ark_seedance_poll_interval: int = 10
    ark_seedance_timeout: int = 480
    # 图生视频封面（公网 URL）；空则走文生视频，不用官方示例图
    ark_seedance_image_url: str = ""

    # 火山方舟视觉 — PDF 画笔问伴学 / 错题识图（model 填接入点 ID ep-...）
    ark_vision_model: str = ""
    ark_vision_foundation_model: str = "Doubao-Seed-2.1-pro"

    # 火山方舟文本（豆包）— 未配 DeepSeek 时作为智能体文本兜底；也可优先使用
    # 填接入点 ID；空则回退到 ark_vision_model
    ark_chat_model: str = ""
    # deepseek | doubao | auto（有 DeepSeek 用 DeepSeek，否则豆包）
    llm_provider: str = "auto"

    # 代码舱远程执行（Docker sidecar）；空则本地 subprocess 沙箱
    codelab_runner_url: str = ""

    # JWT 会话（替代 token-{user_id}）；生产请覆盖 JWT_SECRET
    jwt_secret: str = "sparkorbit-dev-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72


@lru_cache
def get_settings() -> Settings:
    return Settings()
