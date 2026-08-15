from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ClassBriefOut(BaseModel):
    id: str
    name: str
    invite_code: str = ""


class GatePolicyOut(BaseModel):
    id: str = ""
    class_id: str
    galaxy_slug: str = ""
    practice_questions: int = 5
    practice_min_correct: int = 4
    explain_pass_threshold: float = 0.7
    apply_required_default: bool = True
    learn_evidence_min: int = 1
    decay_days: dict[str, Any] = Field(default_factory=lambda: {"fading": 7, "meteor": 14, "dim": 30})
    created_at: str = ""
    updated_at: str = ""


class GatePolicyUpdate(BaseModel):
    class_id: str
    galaxy_slug: str = ""
    practice_questions: Optional[int] = None
    practice_min_correct: Optional[int] = None
    explain_pass_threshold: Optional[float] = None
    apply_required_default: Optional[bool] = None
    learn_evidence_min: Optional[int] = None
    decay_days: Optional[dict[str, Any]] = None


class GalaxyHeatItem(BaseModel):
    galaxy_slug: str
    galaxy_name: str
    planet_slug: str
    planet_name: str
    lit_count: int
    total_students: int
    mastery_rate: int


class ClassOverviewOut(BaseModel):
    total_students: int
    total_planets: int
    avg_mastery_rate: int
    weakest_planets: List[GalaxyHeatItem] = Field(default_factory=list)
    heatmap: List[GalaxyHeatItem] = Field(default_factory=list)


class StudentRiskItem(BaseModel):
    user_id: str
    display_name: str
    username: str
    lit_count: int
    total_planets: int
    mastery_rate: int
    recent_wrong: int
    risk_level: str


class DispatchTaskRequest(BaseModel):
    student_id: str
    planet_slug: Optional[str] = None
    message: str = "老师为你安排了一次复习任务，加油点亮这颗行星！"


class DispatchTaskResponse(BaseModel):
    ok: bool
    alert_id: str


class ReviewScanRequest(BaseModel):
    class_id: str


class ReviewScanStudentOut(BaseModel):
    user_id: str
    display_name: str = ""
    review_planets: int = 0
    tasks_created: int = 0


class ReviewScanOut(BaseModel):
    ok: bool = True
    class_id: str
    students_scanned: int = 0
    students_needing_review: int = 0
    tasks_created: int = 0
    planets_flagged: int = 0
    details: List[ReviewScanStudentOut] = Field(default_factory=list)

class ProfileMatrixOut(BaseModel):
    total_students: int
    profile_count: int
    dimension_averages: dict[str, int] = Field(default_factory=dict)
    explore_score: int = 50
    conservative_score: int = 50
    class_tendency: str = "balanced"
    class_tendency_label: str = "均衡型"


class GravityWellItem(BaseModel):
    galaxy_slug: str
    galaxy_name: str
    planet_slug: str
    planet_name: str
    stuck_count: int
    total_students: int
    stuck_rate: int
    severity: str = "high"


class InterventionRequest(BaseModel):
    student_id: str
    planet_slug: Optional[str] = None
    message: str = "老师已为你派遣专属救援助手，请聚焦薄弱点逐步突破。"


class InterventionResponse(BaseModel):
    ok: bool
    alert_id: str = ""
    message: str = ""
