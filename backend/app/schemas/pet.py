from pydantic import BaseModel, Field


class PetActionOut(BaseModel):
    key: str
    label: str
    icon: str = "✨"
    animation_row: int = 0
    frame_count: int = 6
    fps: int = 8
    loop: bool = False
    route: str = ""


class PetManifestOut(BaseModel):
    slug: str
    name: str
    description: str = ""
    preview_url: str = ""
    manifest_url: str = ""
    sprite_url: str = ""
    format: str = "spritesheet"
    columns: int = 1
    rows: int = 1
    cell_width: int = 0
    cell_height: int = 0
    sheet_width: int = 0
    sheet_height: int = 0
    animation_row: int = 0
    frame_count: int = 0
    fps: int = 12
    actions: list[PetActionOut] = []


class PetSelectRequest(BaseModel):
    pet_slug: str


class PetAffinityIn(BaseModel):
    delta: int = Field(default=1, ge=1, le=20)
    reason: str = ""


class PetAffinityOut(BaseModel):
    pet_affinity: int
    level: int
    level_name: str
