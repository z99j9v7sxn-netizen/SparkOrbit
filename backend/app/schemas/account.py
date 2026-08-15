from pydantic import BaseModel

from app.schemas.auth import UserInfo


class TeacherBrief(BaseModel):
    id: str
    username: str
    display_name: str


class ClassBrief(BaseModel):
    id: str
    name: str
    teacher_id: str
    teacher_name: str = ""
    invite_code: str = ""


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
