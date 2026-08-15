from __future__ import annotations

from pydantic import BaseModel, Field


class InterviewStartIn(BaseModel):
    scenario: str = Field(default="job", max_length=24)
    job_role: str = Field(min_length=1, max_length=64)
    difficulty: str = Field(default="medium", max_length=16)
    question_count: int = Field(default=4, ge=2, le=8)
    resume_url: str = Field(default="", max_length=1024)
    resume_profile: dict = Field(default_factory=dict)
    assignment_id: str = Field(default="", max_length=36)
    consent: bool = True


class InterviewSessionBriefOut(BaseModel):
    id: str
    scenario: str
    job_role: str
    job_role_label: str = ""
    difficulty: str
    question_count: int
    status: str
    overall_score: float | None = None
    current_turn: int = 0
    created_at: str = ""
    finished_at: str = ""
    user_id: str = ""
    assignment_id: str = ""
    student_name: str = ""
    review_status: str = ""


class InterviewQuestionOut(BaseModel):
    index: int
    kind: str
    kind_label: str = ""
    question: str
    followup_of: str = ""


class InterviewTurnOut(BaseModel):
    id: str
    turn_index: int
    question: str
    question_kind: str
    transcript: str = ""
    audio_url: str = ""
    frame_urls: list[str] = []
    semantic_score: float | None = None
    prosody_score: float | None = None
    visual_score: float | None = None
    fused_score: float | None = None
    prosody_detail: dict = {}
    feedback: str = ""
    followup_strategy: str = "next"
    duration_sec: float = 0.0


class InterviewReportOut(BaseModel):
    id: str
    session_id: str
    dimension_scores: dict[str, float] = {}
    dimension_labels: dict[str, str] = {}
    key_issues: list[str] = []
    suggestions: list[str] = []
    resource_refs: list[dict] = []
    council_views: dict = {}
    teacher_comment: str = ""
    teacher_score: float | None = None
    review_status: str = "pending"
    degraded_modalities: list[str] = []
    summary: str = ""
    created_at: str = ""


class InterviewSessionDetailOut(InterviewSessionBriefOut):
    class_id: str = ""
    resume_url: str = ""
    resume_profile: dict = {}
    questions: list[InterviewQuestionOut] = []
    turns: list[InterviewTurnOut] = []
    report: InterviewReportOut | None = None
    prep_run_id: str = ""
    prep_intel: dict = {}
    dimension_labels: dict[str, str] = {}


class InterviewResumeOut(BaseModel):
    url: str
    profile: dict = {}
    text_preview: str = ""


class InterviewJobRoleOut(BaseModel):
    key: str
    label: str
    scenario: str
    family: str = ""
    description: str = ""


class InterviewTaskOut(BaseModel):
    assignment_id: str
    title: str
    description: str = ""
    due_at: str = ""
    scenario: str = "job"
    job_role: str = ""
    question_count: int = 4
    difficulty: str = "medium"
    stem: str = ""
    my_status: str = "pending"
    my_score: int | None = None


class InterviewTeacherReviewIn(BaseModel):
    comment: str = Field(default="", max_length=2000)
    score: float | None = Field(default=None, ge=0, le=100)
    status: str = Field(default="reviewed", max_length=24)


class InterviewOverviewOut(BaseModel):
    total: int = 0
    completed: int = 0
    pending_review: int = 0
    avg_score: float | None = None
    job_count: int = 0
    academic_count: int = 0


class InterviewPracticeQuestionOut(BaseModel):
    question: str
    kind: str
    kind_label: str = ""
    scenario: str = "job"
    job_role: str = ""
    job_role_label: str = ""


class InterviewPracticeAnswerIn(BaseModel):
    scenario: str = Field(default="job", max_length=24)
    job_role: str = Field(default="", max_length=64)
    kind: str = Field(default="", max_length=32)
    question: str = Field(min_length=1, max_length=2000)
    transcript: str = Field(default="", max_length=4000)


class InterviewPracticeAnswerOut(BaseModel):
    id: str
    score: float | None = None
    feedback: str = ""
    star_hit: dict[str, bool] = {}
    reasons: list[str] = []
    created_at: str = ""


class InterviewPracticeRecordOut(BaseModel):
    id: str
    scenario: str = "job"
    job_role: str = ""
    job_role_label: str = ""
    kind: str = ""
    kind_label: str = ""
    question: str = ""
    transcript: str = ""
    score: float | None = None
    feedback: str = ""
    star_hit: dict[str, bool] = {}
    created_at: str = ""


class InterviewPortraitLatestOut(BaseModel):
    id: str
    scenario: str
    job_role: str
    job_role_label: str = ""
    overall_score: float | None = None
    created_at: str = ""


class InterviewPortraitScenarioOut(BaseModel):
    count: int = 0
    avg_score: float | None = None
    dimension_avg: dict[str, float] = {}
    dimension_latest: dict[str, float] = {}
    dimension_labels: dict[str, str] = {}
    latest_id: str = ""
    latest_job_role: str = ""
    latest_job_role_label: str = ""


class InterviewPortraitRoleOut(BaseModel):
    job_role: str
    job_role_label: str = ""
    scenario: str = "job"
    count: int = 0
    avg_score: float | None = None


class InterviewPortraitTrendOut(BaseModel):
    id: str
    at: str = ""
    overall_score: float | None = None
    scenario: str = "job"
    job_role_label: str = ""


class InterviewPortraitWeakDimOut(BaseModel):
    key: str
    label: str
    avg: float
    scenario: str


class InterviewPortraitOut(BaseModel):
    session_count: int = 0
    avg_score: float | None = None
    latest: InterviewPortraitLatestOut | None = None
    job: InterviewPortraitScenarioOut = Field(default_factory=InterviewPortraitScenarioOut)
    academic: InterviewPortraitScenarioOut = Field(default_factory=InterviewPortraitScenarioOut)
    by_role: list[InterviewPortraitRoleOut] = []
    trend: list[InterviewPortraitTrendOut] = []
    weak_dims: list[InterviewPortraitWeakDimOut] = []
    loop_counts: dict[str, int] = {}
    recent_refs: list[dict] = []


class InterviewResumeCoachIn(BaseModel):
    text: str = Field(default="", max_length=8000)
    profile: dict = Field(default_factory=dict)
    target_role: str = Field(default="", max_length=64)
    jd: str = Field(default="", max_length=4000)


class InterviewResumeOptimizeOut(BaseModel):
    score: int = 0
    issues: list[str] = []
    rewritten_markdown: str = ""
    ats_keywords: list[str] = []
    degraded: bool = False


class InterviewResumeMatchOut(BaseModel):
    score: int = 0
    matched: list[str] = []
    gaps: list[str] = []
    prep_suggestions: list[str] = []
    recommended_portals: list[dict] = []
    degraded: bool = False


class InterviewResumeDocxIn(BaseModel):
    template_id: str = Field(default="editorial", max_length=64)
    fields: dict = Field(default_factory=dict)
    format: str = Field(default="docx", max_length=16)


class InterviewApplicationIn(BaseModel):
    company: str = Field(default="", max_length=128)
    role: str = Field(default="", max_length=128)
    portal_url: str = Field(default="", max_length=1024)
    status: str = Field(default="wishlist", max_length=24)
    notes: str = Field(default="", max_length=2000)


class InterviewApplicationPatch(BaseModel):
    company: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=128)
    portal_url: str | None = Field(default=None, max_length=1024)
    status: str | None = Field(default=None, max_length=24)
    notes: str | None = Field(default=None, max_length=2000)


class InterviewApplicationOut(BaseModel):
    id: str
    company: str = ""
    role: str = ""
    portal_url: str = ""
    status: str = "wishlist"
    notes: str = ""
    applied_at: str = ""
    created_at: str = ""
    updated_at: str = ""
