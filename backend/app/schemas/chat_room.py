from pydantic import BaseModel, Field


class ChatRoomOut(BaseModel):
    id: str
    room_type: str
    title: str
    class_id: str = ""
    created_by: str = ""
    last_message: str = ""
    unread_count: int = 0


class ChatRoomMessageOut(BaseModel):
    id: str
    room_id: str
    sender_id: str
    sender_name: str = ""
    content: str
    created_at: str


class ChatSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class PrivateChatCreateRequest(BaseModel):
    target_user_id: str = Field(min_length=1)


class TopicRoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)


class GroupChatCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    member_ids: list[str] = Field(default_factory=list)


class GroupInviteIn(BaseModel):
    target_user_id: str = Field(min_length=1)


class ChatReactionIn(BaseModel):
    emoji: str = Field(default="👍", max_length=8)


class ChatReactionOut(BaseModel):
    message_id: str
    emoji: str
    count: int
    reacted_by_me: bool


class ChatSummaryOut(BaseModel):
    summary: str
    message_count: int
