"""教师端扩展接口的输入模型（输出以 dict 为主，与现有教师端接口风格一致）。"""
from typing import Optional

from pydantic import BaseModel, Field


class QuestionIn(BaseModel):
    stem: str = Field(min_length=1, max_length=4000)
    kind: str = "choice"
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    difficulty: str = "medium"
    galaxy_slug: str = ""
    planet_slug: str = ""
    tags: list[str] = Field(default_factory=list)
    class_id: str = ""
    source: str = "manual"


class QuestionUpdateIn(BaseModel):
    stem: Optional[str] = None
    kind: Optional[str] = None
    options: Optional[list[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    galaxy_slug: Optional[str] = None
    planet_slug: Optional[str] = None
    tags: Optional[list[str]] = None


class QuestionBulkIn(BaseModel):
    class_id: str = ""
    galaxy_slug: str = ""
    source: str = "ai"
    questions: list[QuestionIn] = Field(default_factory=list)


class QuestionAiGenerateIn(BaseModel):
    topic: str = Field(min_length=1, max_length=256)
    count: int = Field(default=5, ge=1, le=20)
    difficulty: str = "medium"
    galaxy_slug: str = ""


class QuestionImportAssignmentIn(BaseModel):
    assignment_id: str = Field(min_length=1)
    class_id: str = ""


class DirectMessageSendIn(BaseModel):
    student_id: str = Field(min_length=1)
    body: str = Field(min_length=1, max_length=4000)


class ResourceReviewIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    comment: str = ""


class ResourceRecommendIn(BaseModel):
    class_id: str = ""
    galaxy_slug: str = ""


class MistakeDispatchIn(BaseModel):
    class_id: str = Field(min_length=1)
    planet_slug: str = Field(min_length=1)
    message: str = "老师发现这颗行星是班级共性薄弱点，为你安排了针对性复习任务。"


class GroupIn(BaseModel):
    class_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=128)
    member_ids: list[str] = Field(default_factory=list)
    note: str = ""


class GroupUpdateIn(BaseModel):
    name: Optional[str] = None
    member_ids: Optional[list[str]] = None
    note: Optional[str] = None


class GroupDispatchIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    planet_slug: str = ""


class PraiseIn(BaseModel):
    student_id: str = Field(min_length=1)
    class_id: str = ""
    badge: str = Field(min_length=1, max_length=64)
    points: int = Field(default=5, ge=0, le=100)
    message: str = ""


class CalendarEventIn(BaseModel):
    class_id: str = ""
    title: str = Field(min_length=1, max_length=256)
    event_date: str = Field(min_length=10, max_length=10, description="YYYY-MM-DD")
    kind: str = "custom"
    note: str = ""
