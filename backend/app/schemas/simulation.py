from typing import Dict, Optional

from pydantic import BaseModel, Field


class MirrorSimulationRequest(BaseModel):
    user_id: str = Field(default="", description="目标学生 user_id；教师沙盘指定真实学生时传入")
    student_profile_id: Optional[str] = Field(default=None, description="指定画像；缺省取最新一条")
    topic: str = Field(default="数据结构与算法基础", description="推演的知识点/主题，来自前端点击的行星")
    planet_slug: str = Field(default="", description="行星 slug，用于预演对照落库")
    target_dimension: Optional[str] = Field(
        default=None,
        description="薄弱维度 key，如 prior_knowledge；用于改进加分对齐",
    )
    # 教师端「时空扭曲」沙盘：手动覆盖某些维度的分数（0-100），预演不同画像下的风险
    dimension_overrides: Dict[str, int] = Field(
        default_factory=dict,
        description="维度分数覆盖，如 {'learning_goal': 100, 'prior_knowledge': 40}",
    )


class MirrorSimulationResponse(BaseModel):
    run_id: str
    status: str
    topic: str = ""
    mode: str = "mirror"
