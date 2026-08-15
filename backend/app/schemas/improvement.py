"""画像改进闭环 API schemas。"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlanStepUpdate(BaseModel):
    done: Optional[bool] = None
    evidence_text: Optional[str] = None


class ImprovementSubmitRequest(BaseModel):
    reflection: str = Field(..., min_length=1, description="改进反思/感想")


class ImprovementOverrideRequest(BaseModel):
    grade: str = Field(..., description="excellent | pass | fail")
    feedback: str = Field(default="")


class ProfileMetaOut(BaseModel):
    warnings: list[Any] = Field(default_factory=list)
    floors: dict[str, Any] = Field(default_factory=dict)
    has_profile: bool = False
    profile_id: Optional[str] = None
    summary: str = ""
    last_sources: dict[str, str] = Field(default_factory=dict)
    pending_events: int = 0
    layers: dict[str, int] = Field(default_factory=dict)
    layer_summaries: dict[str, str] = Field(default_factory=dict)
    update_source: str = ""
    updated_at: str = ""
