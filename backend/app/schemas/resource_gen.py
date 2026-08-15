from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

ResourceKind = Literal["doc", "mindmap", "quiz", "reading", "media", "deck", "code"]


class ResourceGenerateRequest(BaseModel):
    planet_slug: str
    kinds: List[ResourceKind] = Field(
        default_factory=lambda: ["doc", "mindmap", "quiz", "reading", "media", "deck", "code"]
    )
    extra_requirements: str = ""
    # 练习题题型：choice|blank|essay|code（essay 与历史 case 等价）
    quiz_types: List[str] = Field(default_factory=list)
    deck_template: str = Field(default="orbit", max_length=32)


class ResourceGenerateResponse(BaseModel):
    run_id: str
    status: str = "running"


class GeneratedResourceOut(BaseModel):
    id: str
    planet_slug: str
    planet_name: str
    kind: str
    title: str
    content: str
    meta_json: dict = Field(default_factory=dict)
    created_at: str = ""


class LearningPathGenerateRequest(BaseModel):
    goal: str = ""
    use_evaluation: bool = True


class LearningPathStepOut(BaseModel):
    planet_slug: str
    planet_name: str
    action: str
    resource_kinds: List[str] = Field(default_factory=list)
    reason: str = ""
    estimated_minutes: int = 30
    completed: bool = False
    mounted: List[dict[str, Any]] = Field(default_factory=list)
    weak_dims: List[str] = Field(default_factory=list)
    # 冲刺路径：第几天 / 对应日期（常规路径为 0 / 空）
    day: int = 0
    date: str = ""


class LearningPathOut(BaseModel):
    id: str
    title: str
    goal: str
    steps: List[LearningPathStepOut]
    status: str
    progress: float = 0.0
    created_at: str = ""
    kind: str = "standard"
    meta: dict[str, Any] = Field(default_factory=dict)


class PathMountRequest(BaseModel):
    kind: str
    id: str
    title: str = ""
    reason: str = ""
    unmount: bool = False


class RecommendationItem(BaseModel):
    kind: str
    title: str
    reason: str
    resource_id: str = ""
    planet_slug: str = ""
    planet_name: str = ""


class EvaluationReportOut(BaseModel):
    summary: str
    dimensions: dict[str, Any] = Field(default_factory=dict)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    mastery_rate: float = 0.0
    quiz_accuracy: float = 0.0
    selection_ask_count: int = 0
    learn_heatmap_summary: dict[str, Any] = Field(default_factory=dict)


class ProfileTimelineItem(BaseModel):
    id: str
    student_name: str
    summary: str
    scores: dict[str, int]
    created_at: Optional[str] = None
    source: str = "profiler"
