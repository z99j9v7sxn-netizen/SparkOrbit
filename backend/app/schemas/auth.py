from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = Field(..., description="所选角色：student / teacher / admin")


class PreflightRequest(BaseModel):
    username: str
    role: str = Field(..., description="所选角色：student / teacher / admin")


class PreflightResponse(BaseModel):
    ok: bool
    message: str = ""


class CheckUsernameRequest(BaseModel):
    username: str


class CheckUsernameResponse(BaseModel):
    available: bool
    message: str = ""


class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    display_name: str
    avatar: str = ""
    avatar_cartoon_url: str = ""
    class_id: str = ""
    teacher_id: str = ""
    pet_slug: str = ""
    pet_affinity: int = 0
    equipped_title: str = ""
    study_theme: str = ""


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    equipped_title: str | None = None
    study_theme: str | None = None
