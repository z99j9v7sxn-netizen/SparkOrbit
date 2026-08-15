from typing import Literal

from pydantic import BaseModel, Field

PROFILE_DIMENSION_KEYS = Literal[
    "major_background",
    "prior_knowledge",
    "cognitive_style",
    "mistake_tendency",
    "learning_goal",
    "time_flexibility",
    "modality_preference",
    "motivation_level",
]


class ChatTurn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class DimensionProfile(BaseModel):
    value: str = ""
    score: int = 0
    evidence: list[str] = Field(default_factory=list)


class StudentProfileExtract(BaseModel):
    student_name: str = "星轨学习者"
    major_background: DimensionProfile = Field(default_factory=DimensionProfile)
    prior_knowledge: DimensionProfile = Field(default_factory=DimensionProfile)
    cognitive_style: DimensionProfile = Field(default_factory=DimensionProfile)
    mistake_tendency: DimensionProfile = Field(default_factory=DimensionProfile)
    learning_goal: DimensionProfile = Field(default_factory=DimensionProfile)
    time_flexibility: DimensionProfile = Field(default_factory=DimensionProfile)
    modality_preference: DimensionProfile = Field(default_factory=DimensionProfile)
    motivation_level: DimensionProfile = Field(default_factory=DimensionProfile)
    missing_dimensions: list[PROFILE_DIMENSION_KEYS] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    summary: str = ""


class ProfileRequest(BaseModel):
    student_name: str = Field(default="星轨学习者", max_length=128)
    chat_history: list[ChatTurn] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    profile: StudentProfileExtract
    raw: dict = Field(default_factory=dict)
