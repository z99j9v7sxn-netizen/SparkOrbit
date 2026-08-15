from __future__ import annotations

from pydantic import BaseModel, Field


class OralPracticeIn(BaseModel):
    cabin: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="speaking", max_length=20)


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    vcn: str = Field(default="", max_length=64)


class OralPracticeOut(BaseModel):
    reply: str
    feedback: str = ""
    score: int | None = None
    next_prompt: str = ""
    audio_url: str = ""
    transcript: str = ""
    pronunciation: dict | None = None


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    link: str = ""
    is_read: bool = False
    created_at: str = ""


class MoodDiaryIn(BaseModel):
    mood: str = "calm"
    content: str = Field(min_length=1, max_length=2000)
    image_url: str = ""


class MoodDiaryOut(BaseModel):
    id: str
    mood: str
    content: str
    image_url: str = ""
    created_at: str = ""


class TreeHolePostIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    image_url: str = ""


class TreeHolePostOut(BaseModel):
    id: str
    content: str
    image_url: str = ""
    like_count: int = 0
    liked_by_me: bool = False
    reaction_summary: dict[str, int] = {}
    my_reactions: list[str] = []
    comment_count: int = 0
    is_mine: bool = False
    created_at: str = ""


class TreeHoleCommentIn(BaseModel):
    content: str = Field(default="", max_length=500)
    emoji: str = ""


class TreeHoleCommentOut(BaseModel):
    id: str
    post_id: str
    content: str = ""
    emoji: str = ""
    created_at: str = ""


class TreeHoleReactIn(BaseModel):
    emoji: str = Field(min_length=1, max_length=8)


class KnowledgeExplainOut(BaseModel):
    slug: str
    name: str = ""
    galaxy: str = ""
    summary: str = ""
    tips: list[str] = []


class KnowledgeAskIn(BaseModel):
    slug: str
    question: str = Field(min_length=1, max_length=500)


class KnowledgeAskOut(BaseModel):
    answer: str


class AiQuizOut(BaseModel):
    slug: str
    name: str = ""
    questions: list[dict] = []


class AiQuizSubmitRequest(BaseModel):
    slug: str
    question_index: int = 0
    answer: str = ""
    self_ok: bool | None = None


class AiQuizSubmitOut(BaseModel):
    ok: bool = True
    correct: bool = False
    feedback: str = ""
    message: str = ""


class FocusYearlyOut(BaseModel):
    cells: list[dict] = []
    total_minutes: int = 0
