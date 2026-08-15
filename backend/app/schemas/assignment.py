from pydantic import BaseModel, Field


class AssignmentCreateIn(BaseModel):
    class_id: str = ""
    title: str = Field(min_length=1, max_length=256)
    description: str = ""
    galaxy_slug: str = ""
    due_at: str = ""
    questions: list[dict] = Field(default_factory=list)
    source_resource_id: str = ""


class AssignmentOut(BaseModel):
    id: str
    class_id: str = ""
    title: str
    description: str = ""
    galaxy_slug: str = ""
    due_at: str = ""
    created_at: str = ""
    submission_count: int = 0
    my_status: str = ""
    my_score: int | None = None
    submission_id: str = ""
    questions: list[dict] = Field(default_factory=list)
    source_resource_id: str = ""


class AssignmentExtractOut(BaseModel):
    title_suggestion: str = ""
    raw_text_preview: str = ""
    questions: list[dict] = Field(default_factory=list)
    provider: str = ""
    message: str = ""


class AssignmentSubmitIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    attachment_url: str = ""


class GradeSubmissionIn(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str = ""


class SubmissionOut(BaseModel):
    id: str
    student_id: str
    student_name: str = ""
    content: str = ""
    attachment_url: str = ""
    score: int | None = None
    feedback: str = ""
    status: str = ""
    submitted_at: str = ""


class GradebookRow(BaseModel):
    user_id: str
    display_name: str
    username: str
    mastery_rate: int = 0
    quiz_accuracy: int = 0
    assignment_avg: int | None = None
    lit_count: int = 0
    total_planets: int = 0


class BroadcastIn(BaseModel):
    class_id: str = Field(min_length=1)
    title: str = Field(default="教师通知", max_length=256)
    body: str = Field(min_length=1, max_length=2000)


class BroadcastOut(BaseModel):
    id: str
    class_id: str = ""
    title: str = ""
    body: str = ""
    recipient_count: int = 0
    created_at: str = ""


class AttendanceSetIn(BaseModel):
    class_id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    status: str = Field(default="present")
    record_date: str = ""


class AttendanceRow(BaseModel):
    student_id: str
    display_name: str
    status: str = "unknown"
