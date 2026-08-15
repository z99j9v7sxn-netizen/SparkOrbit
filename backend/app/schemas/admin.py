from typing import List, Optional

from pydantic import BaseModel, Field


class StudentSummary(BaseModel):
    id: str
    display_name: str
    username: str
    role: str


class AlertSummary(BaseModel):
    id: str
    alert_type: str
    alert_level: str
    message: str
    resolved: bool


class ImportStudentItem(BaseModel):
    username: str
    display_name: str
    password: str = "123456"


class ImportStudentsRequest(BaseModel):
    students: List[ImportStudentItem]
    class_id: str = ""
    teacher_id: str = ""


class ImportStudentsResponse(BaseModel):
    created: int
    skipped: int


class GalaxyUpsertRequest(BaseModel):
    slug: str
    name: str
    description: str = ""
    color: str = "#2779a7"
    orbit_radius: float = 12.0
    sort_order: int = 0


class PlanetUpsertRequest(BaseModel):
    galaxy_slug: str
    slug: str
    name: str
    description: str = ""
    difficulty: str = "medium"
    orbit_index: int = 1
    angle_deg: float = 0.0
    prerequisites: List[str] = Field(default_factory=list)
    question_tags: List[str] = Field(default_factory=list)


class ApiQuotaOut(BaseModel):
    deepseek_configured: bool
    deepseek_model: str
    deepseek_base_url: str
    total_extractions: int
    total_challenges: int
    total_tokens_7d: int = 0
    total_calls_7d: int = 0


class GalaxyBrief(BaseModel):
    id: str
    slug: str
    name: str
    description: str = ""
    planet_count: int = 0
    is_active: bool = True


class PlanetBrief(BaseModel):
    id: str
    slug: str
    name: str
    galaxy_slug: str
    galaxy_name: str
    difficulty: str = "medium"
    orbit_index: int = 1


class MaintenanceOut(BaseModel):
    enabled: bool
    message: str
    features: dict = Field(default_factory=dict)


class MaintenanceUpdateRequest(BaseModel):
    enabled: bool
    message: Optional[str] = None


class UserAdminItem(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    class_id: str = ""
    teacher_id: str = ""
    is_active: bool = True
    created_at: str = ""


class UserAdminUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    display_name: Optional[str] = None
    role: Optional[str] = None


class ApiUsageSummary(BaseModel):
    endpoint: str
    calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int


class ApiErrorItem(BaseModel):
    id: str
    endpoint: str
    model: str
    user_id: str
    error_message: str
    created_at: str


class ModelConfigItem(BaseModel):
    key: str
    name: str
    model: str
    configured: bool


class SystemOverviewOut(BaseModel):
    deepseek_configured: bool
    deepseek_model: str
    models: list[ModelConfigItem] = []
    maintenance_enabled: bool
    maintenance_message: str
    today_calls: int
    today_tokens: int
    today_errors: int
    user_count: int


class AgentStepOut(BaseModel):
    id: str
    step_index: int
    agent_role: str
    status: str
    parallel_group: str = ""
    summary: str = ""
    payload: dict = Field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""


class AgentRunOut(BaseModel):
    id: str
    user_id: str
    user_name: str = ""
    scene: str
    mode: str
    status: str
    topic: str = ""
    graph_plan: dict = Field(default_factory=dict)
    current_step: int = 0
    current_agent: str = ""
    error_message: str = ""
    created_at: str = ""
    finished_at: str = ""
    steps: list[AgentStepOut] = Field(default_factory=list)
