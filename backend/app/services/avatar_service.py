"""认知孪生体生成：自拍 -> DeepSeek 卡通化指令 -> Qwen 图生图 -> 2D 卡通形象。"""
import base64
import io
import logging
from typing import Dict, Optional, Tuple

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.schemas.student_profile import StudentProfileExtract
from app.services.llm import llm_available, llm_chat

logger = logging.getLogger(__name__)

DEFAULT_CARTOON_PROMPT = (
    "将人物转换为盲盒潮玩风格的 Q 版卡通形象，大头比例，圆润可爱，"
    "干净纯色背景，色彩明亮，保留人物主要面部特征。"
)

CARTOON_SYSTEM = """你是 SparkOrbit 星轨学图的 Avatar Prompt 设计师。
根据学生的自我描述和可选的认知画像，生成一段用于 Qwen 图像编辑模型的中文卡通化指令。
要求：
- 输出盲盒/Q 版/潮玩卡通风格
- 保留人物主要面部特征
- 干净背景，色彩明亮
- 只输出指令正文，不要 Markdown，不要解释，控制在 150 字以内"""


def _profile_brief(profile: StudentProfileExtract) -> str:
    return (
        f"专业背景：{profile.major_background.value or '未知'}；"
        f"认知风格：{profile.cognitive_style.value or '未知'}；"
        f"学习目标：{profile.learning_goal.value or '未知'}"
    )


async def build_cartoon_prompt(
    description: str = "",
    profile: Optional[StudentProfileExtract] = None,
) -> str:
    if not llm_available():
        return DEFAULT_CARTOON_PROMPT

    user_parts = []
    if description:
        user_parts.append(f"学生描述：{description}")
    if profile is not None:
        user_parts.append(f"六维画像摘要：{_profile_brief(profile)}")
    if not user_parts:
        user_parts.append("学生未提供额外描述，请生成通用的盲盒卡通化指令。")

    content = await llm_chat(
        [
            {"role": "system", "content": CARTOON_SYSTEM},
            {"role": "user", "content": "\n".join(user_parts)},
        ],
        temperature=0.7,
        thinking=True,
    )
    return content.strip() if content else DEFAULT_CARTOON_PROMPT


def _normalize_photo(image_bytes: bytes, content_type: str = "image/jpeg") -> Tuple[str, str]:
    """将上传图片规范化为 Qwen 可接受的 JPEG data URI（限制尺寸与体积）。"""
    max_bytes = 9 * 1024 * 1024
    max_edge = 2048

    if len(image_bytes) > 20 * 1024 * 1024:
        raise ValueError("图片过大，请上传 20MB 以内的自拍（建议 JPG/PNG）")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.load()
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            width, height = img.size
            longest = max(width, height)
            if longest > max_edge:
                scale = max_edge / longest
                img = img.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    Image.Resampling.LANCZOS,
                )

            buf = io.BytesIO()
            quality = 92
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            while buf.tell() > max_bytes and quality > 55:
                quality -= 8
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)

            if buf.tell() > max_bytes:
                raise ValueError("图片分辨率过高，请换一张更小的自拍后重试")

            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64}", "image/jpeg"
    except UnidentifiedImageError as exc:
        raise ValueError(
            "无法识别图片格式，请上传 JPG/PNG/WebP 自拍（iPhone 请在设置中关闭 HEIC 格式）"
        ) from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"图片预处理失败：{exc}") from exc


def _parse_qwen_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text[:500] or f"HTTP {response.status_code}"

    if isinstance(data, dict):
        if data.get("message"):
            return str(data["message"])
        if data.get("code"):
            return f"{data['code']}: {data.get('message', '')}".strip(": ")
    return response.text[:500] or f"HTTP {response.status_code}"


async def stylize_to_cartoon(image_base64: str, prompt: str) -> str:
    """调用 Qwen 多模态端点，将自拍转为 2D 卡通图，返回图片 URL。"""
    from app.services.llm import resolve_conf

    settings = get_settings()
    qwen_key = resolve_conf("qwen_api_key")
    if not qwen_key:
        raise RuntimeError("未配置 QWEN_API_KEY")

    if not image_base64.startswith("data:"):
        image_base64 = f"data:image/jpeg;base64,{image_base64}"

    url = f"{settings.qwen_base_url.rstrip('/')}/api/v1/services/aigc/multimodal-generation/generation"
    payload = {
        "model": settings.qwen_image_model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": image_base64},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "n": 1,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    headers = {
        "Authorization": f"Bearer {qwen_key}",
        "Content-Type": "application/json",
    }

    logger.info("Qwen 卡通化请求 model=%s prompt_len=%d", settings.qwen_image_model, len(prompt))

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            detail = _parse_qwen_error(response)
            logger.error("Qwen 卡通化失败 status=%s detail=%s", response.status_code, detail)
            raise RuntimeError(f"Qwen 卡通化失败：{detail}")
        data = response.json()

    if data.get("code"):
        raise RuntimeError(f"Qwen 卡通化失败：{data.get('message', data.get('code'))}")

    choices = data.get("output", {}).get("choices", [])
    if not choices:
        raise RuntimeError("Qwen 未返回生成结果")

    content = choices[0].get("message", {}).get("content", [])
    for item in content:
        if isinstance(item, dict) and item.get("image"):
            return str(item["image"])

    raise RuntimeError("Qwen 响应中未找到图片 URL")


async def generate_avatar(
    image_bytes: bytes,
    *,
    content_type: str = "image/jpeg",
    description: str = "",
    profile: Optional[StudentProfileExtract] = None,
) -> Dict[str, str]:
    """串联 DeepSeek + Qwen，返回 2D 卡通图 URL 与生成指令。"""
    data_uri, _ = _normalize_photo(image_bytes, content_type)

    prompt = await build_cartoon_prompt(description, profile)
    cartoon_url = await stylize_to_cartoon(data_uri, prompt)

    return {
        "cartoon_url": cartoon_url,
        "prompt": prompt,
    }
