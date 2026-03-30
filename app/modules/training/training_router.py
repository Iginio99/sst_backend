from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.infrastructure.respository import get_db
from app.modules.auth.auth_service import require_permissions
from app.modules.training.training_schema import (
    LessonCompletionRequest,
    LessonCompletionResponse,
    LessonCreateRequest,
    LessonUpdateRequest,
    LessonOut,
    ModuleAssignmentOut,
    ModuleAssignmentRequest,
    ModuleCreateRequest,
    ModuleOut,
    ModuleProgressOut,
    ModuleUpdateRequest,
    ModuleWithLessons,
    QuizOut,
    QuizResult,
    QuizSubmission,
    UserSummary,
)
from app.modules.training.training_service import TrainingService

router = APIRouter(prefix="/training", tags=["Training"])


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.view"])),
):
    service = TrainingService(db)
    return service.list_modules(current_user)


@router.get("/modules/{module_id}/lessons", response_model=ModuleWithLessons)
def get_module_lessons(
    module_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.view"])),
):
    service = TrainingService(db)
    return service.module_lessons(module_id, current_user)


@router.post("/lessons/{lesson_id}/complete", response_model=LessonCompletionResponse)
def complete_lesson(
    lesson_id: int,
    payload: LessonCompletionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.complete"])),
):
    service = TrainingService(db)
    progress, module = service.complete_lesson(lesson_id, current_user, payload.completed)
    lessons_total, lessons_completed, quiz_completed = service._module_progress(module.id, current_user.id)
    progress_value = lessons_completed / lessons_total if lessons_total else 0
    return LessonCompletionResponse(
        lesson_id=lesson_id,
        module_id=module.id,
        completed=progress.completed,
        completed_lessons=lessons_completed,
        total_lessons=lessons_total,
        quiz_completed=quiz_completed,
        progress=progress_value,
    )


@router.post(
    "/modules/{module_id}/lessons",
    response_model=LessonOut,
)
def create_lesson(
    module_id: int,
    payload: LessonCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.create_lesson(module_id, payload, current_user)


@router.put(
    "/lessons/{lesson_id}",
    response_model=LessonOut,
)
def update_lesson(
    lesson_id: int,
    payload: LessonUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.update_lesson(lesson_id, payload, current_user)


@router.delete(
    "/lessons/{lesson_id}",
    status_code=204,
)
def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    service.delete_lesson(lesson_id, current_user)


@router.post(
    "/lessons/{lesson_id}/cover",
    response_model=LessonOut,
)
def upload_lesson_cover(
    lesson_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.upload_lesson_cover(lesson_id, file, current_user)


@router.post(
    "/lessons/{lesson_id}/content",
    response_model=LessonOut,
)
def upload_lesson_content(
    lesson_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.upload_lesson_content(lesson_id, file, current_user)


@router.get("/modules/{module_id}/quiz", response_model=QuizOut)
def get_quiz(module_id: int, db: Session = Depends(get_db), current_user=Depends(require_permissions(["training.view"]))):
    service = TrainingService(db)
    return service.get_quiz(module_id, current_user)


@router.post("/modules/{module_id}/quiz/submit", response_model=QuizResult)
def submit_quiz(
    module_id: int,
    payload: QuizSubmission,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.quiz"])),
):
    service = TrainingService(db)
    return service.submit_quiz(module_id, current_user, [answer.dict() for answer in payload.answers])


@router.post(
    "/modules",
    response_model=ModuleOut,
)
def create_module(
    payload: ModuleCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.create_module(payload, current_user)


@router.put(
    "/modules/{module_id}",
    response_model=ModuleOut,
)
def update_module(
    module_id: int,
    payload: ModuleUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    return service.update_module(module_id, payload, current_user)


@router.delete(
    "/modules/{module_id}",
    status_code=204,
)
def delete_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.manage"])),
):
    service = TrainingService(db)
    service.delete_module(module_id, current_user)


@router.post(
    "/modules/{module_id}/assign",
    response_model=ModuleAssignmentOut,
)
def assign_module(
    module_id: int,
    payload: ModuleAssignmentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.assign"])),
):
    service = TrainingService(db)
    return service.assign_module(module_id, payload, current_user)


@router.get(
    "/modules/{module_id}/progress",
    response_model=ModuleProgressOut,
)
def module_progress(
    module_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permissions(["training.monitor"])),
):
    service = TrainingService(db)
    return service.module_progress_report(module_id, current_user)


@router.get(
    "/assignable-users",
    response_model=list[UserSummary],
    dependencies=[Depends(require_permissions(["training.assign"]))],
)
def list_assignable_users(db: Session = Depends(get_db)):
    service = TrainingService(db)
    return service.list_assignable_users()
