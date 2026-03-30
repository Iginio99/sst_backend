from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ModuleOut(BaseModel):
    id: int
    title: str
    description: str
    icon: str
    color: str
    lessons: int
    completed_lessons: int
    due_to_checklist: bool
    quiz_completed: bool
    quiz_required: bool = True
    checklist_section_id: Optional[int] = None
    owner_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class LessonOut(BaseModel):
    id: int
    title: str
    duration: str
    type: str
    description: Optional[str] = None
    image: Optional[str] = None
    thumbnail_url: Optional[str] = None
    content_mode: str = "upload"
    content_url: Optional[str] = None
    content_mime_type: Optional[str] = None
    content_size_bytes: Optional[int] = None
    external_url: Optional[str] = None
    display_order: int = 1
    completed: bool

    model_config = ConfigDict(from_attributes=True)


class ModuleWithLessons(BaseModel):
    module: ModuleOut
    lessons: List[LessonOut]


class LessonCompletionRequest(BaseModel):
    completed: bool = True


class LessonCompletionResponse(BaseModel):
    lesson_id: int
    module_id: int
    completed: bool
    completed_lessons: int
    total_lessons: int
    quiz_completed: bool
    progress: float


class QuizOptionOut(BaseModel):
    id: int
    text: str

    model_config = ConfigDict(from_attributes=True)


class QuizQuestionOut(BaseModel):
    id: int
    prompt: str
    options: List[QuizOptionOut]

    model_config = ConfigDict(from_attributes=True)


class QuizOut(BaseModel):
    module_id: int
    module_title: str
    questions: List[QuizQuestionOut]


class QuizAnswer(BaseModel):
    question_id: int
    option_id: int


class QuizSubmission(BaseModel):
    answers: List[QuizAnswer]


class QuizResult(BaseModel):
    module_id: int
    correct_answers: int
    total_questions: int
    score: int
    passed: bool


class ModuleCreateRequest(BaseModel):
    title: str
    description: str
    icon: str
    color: str
    due_to_checklist: bool = False
    checklist_section_id: Optional[int] = None
    quiz_required: bool = True


class ModuleUpdateRequest(ModuleCreateRequest):
    pass


class LessonBaseRequest(BaseModel):
    title: str
    duration: str
    type: str
    description: Optional[str] = None
    display_order: int = 1
    content_mode: str = "upload"
    external_url: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed = {"video", "document", "interactive"}
        if value not in allowed:
            raise ValueError("type debe ser video, document o interactive")
        return value

    @field_validator("content_mode")
    @classmethod
    def validate_content_mode(cls, value: str) -> str:
        allowed = {"upload", "external_url"}
        if value not in allowed:
            raise ValueError("content_mode debe ser upload o external_url")
        return value

    @field_validator("external_url")
    @classmethod
    def validate_external_url_format(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError("external_url debe iniciar con http:// o https://")
        return cleaned

    @model_validator(mode="after")
    def validate_external_url_requirement(self):
        if self.content_mode == "external_url" and not self.external_url:
            raise ValueError("external_url es obligatoria cuando content_mode=external_url")
        return self


class LessonCreateRequest(LessonBaseRequest):
    pass


class LessonUpdateRequest(LessonBaseRequest):
    pass


class ModuleAssignmentRequest(BaseModel):
    user_ids: List[int]


class UserSummary(BaseModel):
    id: int
    name: str
    email: str
    roles: List[str]


class ModuleAssignmentOut(BaseModel):
    module_id: int
    user_ids: List[int]


class UserProgressOut(BaseModel):
    user: UserSummary
    completed_lessons: int
    total_lessons: int
    quiz_completed: bool
    last_score: Optional[int] = None
    last_attempt_at: Optional[datetime] = None


class ModuleProgressOut(BaseModel):
    module_id: int
    module_title: str
    users: List[UserProgressOut]
