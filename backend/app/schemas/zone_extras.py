from pydantic import BaseModel, Field


class FocusSessionIn(BaseModel):
    minutes: int = Field(default=25, ge=1, le=180)
    source: str = "pomodoro"
    room_id: str = ""


class FocusSummaryOut(BaseModel):
    today_minutes: int = 0
    week_minutes: int = 0
    sessions: int = 0


class FocusHeatmapCell(BaseModel):
    day: int
    slot: str
    minutes: int


class FocusHeatmapOut(BaseModel):
    week_start: str = ""
    week_end: str = ""
    total_minutes: int = 0
    cells: list[FocusHeatmapCell] = []


class FocusLeaderboardItem(BaseModel):
    user_id: str
    display_name: str
    minutes: int


class MistakeIn(BaseModel):
    question: str
    student_answer: str = ""
    correct_answer: str = ""
    subject: str = ""
    note: str = ""


class MistakeOut(BaseModel):
    id: str
    question: str
    student_answer: str = ""
    correct_answer: str = ""
    subject: str = ""
    note: str = ""
    created_at: str = ""


class WishIn(BaseModel):
    content: str = Field(min_length=1, max_length=280)


class WishOut(BaseModel):
    id: str
    user_id: str
    display_name: str
    content: str
    likes: int
    liked_by_me: bool = False
    created_at: str = ""


class ForumPostIn(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1)
    kind: str = "note"
    file_url: str = ""
    source_type: str = ""
    source_id: str = ""


class ForumPostOut(BaseModel):
    id: str
    author_id: str
    author_name: str = ""
    class_id: str = ""
    title: str
    body: str
    kind: str = "note"
    file_url: str = ""
    source_type: str = ""
    source_id: str = ""
    like_count: int = 0
    promoted_asset_id: str = ""
    created_at: str = ""


class ForumAttachableItem(BaseModel):
    id: str
    source_type: str  # vault | workshop | video
    title: str
    subtitle: str = ""
    kind_label: str = ""
    file_url: str = ""
    content_preview: str = ""
    suggested_kind: str = "file"  # note | file


class ForumPromoteIn(BaseModel):
    galaxy_slug: str = ""
    planet_slug: str = ""


class ForumPromoteOut(ForumPostOut):
    star_asset: dict | None = None


class ShopItemOut(BaseModel):
    id: str
    name: str
    description: str
    cost: int
    kind: str  # pet | title | audio


class RedeemIn(BaseModel):
    item_id: str


class AchievementOut(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    unlocked: bool
    progress: int = 0
    target: int = 1


class LeisureSessionOut(BaseModel):
    points_awarded: int = 0
    total_points: int = 0
    message: str = ""
    pet_affinity_delta: int = 0


class DailyTaskOut(BaseModel):
    id: str
    title: str
    task_type: str
    done: bool
    points: int


class DailyTaskToggleIn(BaseModel):
    task_id: str


class SignInOut(BaseModel):
    signed_today: bool
    streak: int
    points_awarded: int
    calendar: list[dict] = []


class StudyStreakOut(BaseModel):
    streak_days: int
    calendar: list[dict] = []


class KnowledgeGraphNode(BaseModel):
    id: str
    name: str
    slug: str
    galaxy: str
    status: str
    mastery: float


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str


class KnowledgeGraphOut(BaseModel):
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]


class ProgressBoardItem(BaseModel):
    user_id: str
    display_name: str
    lit_count: int
    total_planets: int
    mastery_rate: int
    recent_activity: str = ""
    is_me: bool = False


class ProgressBoardOut(BaseModel):
    scope: str = "class"  # class | site
    scope_label: str = ""
    total_planets: int = 0
    students: list[ProgressBoardItem] = Field(default_factory=list)


class BuddyMatchOut(BaseModel):
    user_id: str
    display_name: str
    reason: str
    complement_score: int


class GameChallengeIn(BaseModel):
    target_user_id: str
    game: str
    score: int = 0


class GameChallengeOut(BaseModel):
    id: str
    challenger_name: str
    target_name: str
    game: str
    challenger_score: int
    target_score: int
    status: str


class MilestoneOut(BaseModel):
    id: str
    achievement_id: str
    achievement_name: str
    unlocked_at: str


class EquippedTitleIn(BaseModel):
    title_id: str


class StudyThemeIn(BaseModel):
    theme_id: str


class OwnedShopItemOut(BaseModel):
    item_id: str
    item_name: str
    cost: int
    redeemed_at: str = ""


class LeisureSessionIn(BaseModel):
    game: str
    score: int = 0
    won: bool = False
