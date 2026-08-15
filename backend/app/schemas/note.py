from typing import Any, Optional

from pydantic import BaseModel, Field


class NoteIn(BaseModel):
    title: str = Field(default="", max_length=256)
    content: str = Field(min_length=1, max_length=20000)
    planet_slug: str = ""
    galaxy_slug: str = ""
    attachment_url: str = ""
    blocks_json: list[Any] = Field(default_factory=list)
    source: str = "manual"
    session_id: str = ""


class NoteUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=256)
    content: Optional[str] = Field(default=None, max_length=20000)
    blocks_json: Optional[list[Any]] = None
    attachment_url: Optional[str] = None


class NoteOut(BaseModel):
    id: str
    planet_slug: str = ""
    galaxy_slug: str = ""
    title: str = ""
    content: str = ""
    attachment_url: str = ""
    blocks_json: list[Any] = Field(default_factory=list)
    source: str = "manual"
    session_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class NoteClipIn(BaseModel):
    planet_slug: str
    block: dict[str, Any] = Field(default_factory=dict)
    title: str = ""


class NoteAiSummaryIn(BaseModel):
    planet_slug: str


class LessonResourceOut(BaseModel):
    id: str
    title: str = ""
    galaxy_slug: str = ""
    file_url: str = ""
    class_id: str = ""
    resource_kind: str = "other"
    promoted_asset_id: str = ""
    created_at: str = ""


class LessonResourceTextIn(BaseModel):
    title: str = Field(default="", max_length=256)
    content: str = Field(min_length=1, max_length=200000)
    galaxy_slug: str = ""
    class_id: str = ""
    resource_kind: str = "plan"


class PromoteResourceIn(BaseModel):
    class_id: str = ""
    galaxy_slug: str = ""
    planet_slug: str = ""
    asset_type: str = "note_pack"
