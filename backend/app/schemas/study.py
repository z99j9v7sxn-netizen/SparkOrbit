from pydantic import BaseModel


class StudyConstellationOut(BaseModel):
    slug: str
    name: str
    symbol: str
    room_count: int = 0
    total_occupancy: int = 0


class StudyRoomOut(BaseModel):
    id: str
    constellation: str
    name: str
    size: str
    capacity: int
    occupancy: int = 0
    is_full: bool = False


class OccupantOut(BaseModel):
    user_id: str
    display_name: str
    avatar: str = ""
    joined_at: str
    focus_minutes: int = 0
    status: str = "focus"


class StudyJoinResponse(BaseModel):
    room: StudyRoomOut
    occupants: list[OccupantOut]
