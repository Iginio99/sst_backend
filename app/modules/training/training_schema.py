from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


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
    image: Optional[str] = None
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
