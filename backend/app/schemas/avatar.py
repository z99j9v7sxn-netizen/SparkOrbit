from typing import Optional

from pydantic import BaseModel, Field


class AvatarGenerateResponse(BaseModel):
    status: str = Field(description="success / error")
    cartoon_url: Optional[str] = Field(default=None, description="Qwen 卡通化 2D 图 URL")
    prompt: Optional[str] = Field(default=None, description="DeepSeek 生成的卡通化指令")
    msg: str = Field(default="", description="状态说明或错误信息")
