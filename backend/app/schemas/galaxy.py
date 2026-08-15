from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class PlanetOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    difficulty: str
    orbit_index: int
    angle_deg: float
    radius_offset: float
    prerequisites: List[str] = Field(default_factory=list)
    # 学生态：locked / dim / lit / fading / meteor
    status: str = "dim"
    score: int = 0
    attempts: int = 0
    decay_state: str = "lit"
    is_permanent: bool = False


class GalaxyOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    color: str
    orbit_radius: float
    sort_order: int
    planet_count: int = 0
    lit_count: int = 0


class GalaxyDetailOut(GalaxyOut):
    planets: List[PlanetOut] = Field(default_factory=list)


class ChallengeOption(BaseModel):
    key: str
    text: str


class ChallengeOut(BaseModel):
    challenge_id: str
    planet_id: str
    planet_name: str
    question: str
    options: List[ChallengeOption]
    difficulty: str
    # 教导摘要 + 练闸会话（默认 5 题，答对 ≥4 过练闸；四闸齐备才点亮）
    teaching_summary: str = ""
    session_id: str = ""
    question_index: int = 1
    total_questions: int = 5
    min_correct_to_lit: int = 4
    mastery_phase: str = "dim"
    gates: dict = Field(default_factory=dict)
    can_challenge: bool = True
    lit_ready: bool = False


class SubmitChallengeRequest(BaseModel):
    challenge_id: str
    selected_key: str
    force_human_review: bool = Field(default=False, description="演示：强制低置信转教师工单")
    self_confidence: str = Field(
        default="",
        description="学生自评确信度：sure | hesitant | unknown",
    )


class SubmitChallengeResult(BaseModel):
    correct: bool
    answer_key: str
    explanation: str
    planet_status: str
    lit: bool
    points: int
    mood: str
    constellation: Optional[Dict[str, Any]] = None
    consecutive_fails: int = 0
    can_emit_sos: bool = False
    session_id: str = ""
    session_correct: int = 0
    session_answered: int = 0
    total_questions: int = 5
    min_correct_to_lit: int = 4
    session_done: bool = False
    question_index: int = 1
    next_challenge: Optional[ChallengeOut] = None
    knowledge_point_id: str = ""
    cited_knowledge_point_id: str = ""
    confidence: float = 1.0
    human_review_required: bool = False
    review_ticket_id: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)
    mastery_phase: str = "dim"
    gates: dict = Field(default_factory=dict)
    practice_passed: bool = False
    lit_ready: bool = False


class LessonPlanOut(BaseModel):
    planet_slug: str
    planet_name: str
    learning_goals: List[str] = Field(default_factory=list)
    teaching_approach: str = ""
    example_problems: List[str] = Field(default_factory=list)
    common_mistakes: List[str] = Field(default_factory=list)
    practice_plan: List[str] = Field(default_factory=list)
    self_check: List[str] = Field(default_factory=list)


class FragmentItem(BaseModel):
    id: str
    name: str
    icon: str
    collected: bool = False


class FragmentProgress(BaseModel):
    fragments: List[FragmentItem] = Field(default_factory=list)
    collected_count: int = 0
    total: int = 0
    complete: bool = False
    halo: bool = False
    burst: bool = False
    message: Optional[str] = None


class TutorSourceRef(BaseModel):
    galaxy: str = ""
    source: str = ""
    snippet: str = ""
    knowledge_point_id: str = ""


class CompanionChatResponse(BaseModel):
    reply: str
    mode: str
    fragment_progress: Optional[Dict[str, Any]] = None
    socratic: bool = False
    sources: Optional[List[TutorSourceRef]] = None
    # 费曼讲闸结构化评分（0~1）；非 feynman 模式为 None
    explain_score: Optional[float] = None
    explain_rubric: Optional[Dict[str, Any]] = None
    # supervisor 编排观测
    run_id: Optional[str] = None
    intent: Optional[str] = None
    next_actions: Optional[List[Dict[str, Any]]] = None
    path_id: Optional[str] = None
    resource_run_id: Optional[str] = None
    explain_gate: Optional[Dict[str, Any]] = None


class CompanionChatRequest(BaseModel):
    message: str
    mode: str = Field(
        default="companion",
        description="companion 情绪疏导 / tutor 学习答疑 / feynman 费曼讲解",
    )
    planet_slug: Optional[str] = None
    socratic: bool = Field(default=True, description="tutor 模式是否启用苏格拉底式先问后讲")
    supervise: bool = Field(
        default=False,
        description="为 true 时走 supervisor 意图路由与 AgentStep 落库",
    )


class SelectionAskIn(BaseModel):
    quote: Optional[str] = Field(default=None, max_length=4000)
    asset_id: Optional[str] = None
    page_no: Optional[int] = None
    planet_slug: Optional[str] = None
    question: Optional[str] = None
    image_base64: Optional[str] = Field(default=None, max_length=6_000_000)
    image_mime: Optional[str] = Field(default="image/jpeg", max_length=64)
    mode: str = Field(default="tutor", description="tutor 学习答疑 / feynman 费曼讲解")
    socratic: bool = Field(default=True, description="tutor 模式是否启用苏格拉底式先问后讲")

    @model_validator(mode="after")
    def require_quote_or_image(self) -> "SelectionAskIn":
        q = (self.quote or "").strip()
        img = (self.image_base64 or "").strip()
        if not q and not img:
            raise ValueError("quote 与 image_base64 至少提供一个")
        return self


class SelectionAskOut(BaseModel):
    answer: str
    citations: Optional[List[TutorSourceRef]] = None
    gates: Optional[Dict[str, Any]] = None
    explain_score: Optional[float] = None
    explain_rubric: Optional[Dict[str, Any]] = None


class ReviewPlanetRequest(BaseModel):
    correct: bool = True


class ReviewPlanetResult(BaseModel):
    success: bool
    supernova: bool = False
    is_permanent: bool = False
    points: int = 0
    message: str = ""


class AssessmentStartOut(BaseModel):
    assessment_id: str
    galaxy_slug: str
    galaxy_name: str
    total: int
    current_index: int
    question: str
    options: List[ChallengeOption]
    planet_name: str


class AssessmentSubmitRequest(BaseModel):
    assessment_id: str
    selected_key: str


class AssessmentSubmitOut(BaseModel):
    done: bool
    correct: Optional[bool] = None
    current_index: Optional[int] = None
    total: Optional[int] = None
    question: Optional[str] = None
    options: Optional[List[ChallengeOption]] = None
    planet_name: Optional[str] = None
    correct_count: Optional[int] = None
    lit_planets: Optional[List[str]] = None
    message: Optional[str] = None


class SosEmitRequest(BaseModel):
    planet_slug: str


class SosRespondRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class ConstellationOut(BaseModel):
    slug: str
    name: str
    description: str
    badge_icon: str
    planet_slugs: List[str]
    lit_count: int
    total: int
    completed: bool


class LeaderboardItem(BaseModel):
    rank: int
    user_id: str
    display_name: str
    lit_count: int
    points: int
    is_me: bool = False


class FriendItem(BaseModel):
    user_id: str
    display_name: str
    username: str
    lit_count: int
    points: int


class AddFriendRequest(BaseModel):
    username: str


class WormholeSendRequest(BaseModel):
    receiver_id: str
    content: str = Field(min_length=1, max_length=200)


class WormholeMessageOut(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    receiver_id: str
    content: str
    created_at: Optional[str] = None


class AvatarStateOut(BaseModel):
    display_name: str
    points: int
    mood: str
    streak_days: int
    lit_count: int
    total_planets: int
    mastery_rate: int
    avatar_cartoon_url: Optional[str] = None


class WeeklyActivityOut(BaseModel):
    labels: list[str]
    hours: list[float]


class MasteryTrendOut(BaseModel):
    labels: list[str]
    scores: list[int]


class MasterySeriesOut(BaseModel):
    planet_slug: str
    planet_name: str
    labels: list[str]
    scores: list[int]
    sample_sparse: bool = False


class GalaxyMasteryOut(BaseModel):
    galaxy_name: str
    avg_score: float
    planet_count: int


class AccuracyDailyOut(BaseModel):
    date: str
    correct_rate: float
    attempts: int


class WeakPlanetOut(BaseModel):
    planet_slug: str
    planet_name: str
    galaxy_name: str
    score: int
    status: str
    recent_accuracy: float
    trend: str
    last_practiced_at: Optional[str] = None


class MasteryOverviewOut(BaseModel):
    series: list[MasterySeriesOut]
    by_galaxy: list[GalaxyMasteryOut]
    accuracy_daily: list[AccuracyDailyOut]
    weak_planets: list[WeakPlanetOut]


class StudentAlertOut(BaseModel):
    id: str
    alert_type: str
    title: str
    message: str
    level: str = "info"
    planet_slug: Optional[str] = None
    created_at: Optional[str] = None


class OrbitPlanetSnapshot(BaseModel):
    slug: str
    status: str
    score: int
    attempts: int


class OrbitSnapshotOut(BaseModel):
    planets: list[OrbitPlanetSnapshot]
    synced_at: str
