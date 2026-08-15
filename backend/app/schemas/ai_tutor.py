from pydantic import BaseModel, Field


class SimilarQuestionItem(BaseModel):
    question: str
    answer: str
    explanation: str
    difficulty: str = "medium"


class SimilarQuestionsRequest(BaseModel):
    source_question: str = Field(min_length=3)
    count: int = Field(default=3, ge=1, le=8)
    subject: str = ""


class SimilarQuestionsResponse(BaseModel):
    source_question: str
    items: list[SimilarQuestionItem]
    fallback: bool = False


class GradeItemRequest(BaseModel):
    question: str
    reference_answer: str
    student_answer: str


class GradeRequest(BaseModel):
    items: list[GradeItemRequest] = Field(min_length=1)


class GradeItemResult(BaseModel):
    question: str
    student_answer: str
    score: int
    is_correct: bool
    feedback: str
    suggestion: str = ""


class GradeResponse(BaseModel):
    total_score: int
    max_score: int
    items: list[GradeItemResult]
    summary: str
    fallback: bool = False
