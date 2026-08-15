from pydantic import BaseModel, Field


class ProfileHistoryItem(BaseModel):
    id: str
    student_name: str
    summary: str
    major_background: str = ""
    prior_knowledge: str = ""
    cognitive_style: str = ""
    mistake_tendency: str = ""
    learning_goal: str = ""
    time_flexibility: str = ""
    modality_preference: str = ""
    motivation_level: str = ""
    major_background_score: int | None = None
    prior_knowledge_score: int | None = None
    cognitive_style_score: int | None = None
    mistake_tendency_score: int | None = None
    learning_goal_score: int | None = None
    time_flexibility_score: int | None = None
    modality_preference_score: int | None = None
    motivation_level_score: int | None = None
    created_at: str | None = None
