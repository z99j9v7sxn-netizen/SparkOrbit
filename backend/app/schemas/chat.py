from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    user_id: str
    title: str = Field(default="新会话", max_length=128)


class ChatSessionOut(BaseModel):
    id: str
    user_id: str
    title: str
    status: str = "active"


class ChatMessageCreate(BaseModel):
    session_id: str
    user_id: str
    role: str = "user"
    content: str


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
