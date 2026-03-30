from datetime import datetime
import logging
from typing import List, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.modules.models import Lesson, Module, ModuleAssignment, QuizAttempt, QuizOption, QuizQuestion, User, UserLessonProgress
from app.modules.training.training_schema import LessonCreateRequest
from app.modules.training.training_schema import (
    LessonOut,
    LessonUpdateRequest,
    ModuleAssignmentOut,
    ModuleAssignmentRequest,
    ModuleCreateRequest,
    ModuleOut,
    ModuleProgressOut,
    ModuleUpdateRequest,
    ModuleWithLessons,
    QuizOut,
    QuizResult,
    UserProgressOut,
    UserSummary,
)
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class TrainingService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageService()

    # -------------------------
    # Public API
    # -------------------------
    def list_modules(self, current_user: User) -> List[ModuleOut]:
        modules = self._modules_for_user(current_user)
        return [self._build_module_out(module, current_user.id) for module in modules]

    def module_lessons(self, module_id: int, current_user: User) -> ModuleWithLessons:
        module = self._get_module(module_id)
        self._ensure_module_access(module_id, current_user)

        lessons = (
            self.db.query(Lesson)
            .filter(Lesson.module_id == module_id)
            .order_by(Lesson.display_order, Lesson.id)
            .all()
        )

        completed_lesson_ids = {
            lp.lesson_id
            for lp in self.db.query(UserLessonProgress).filter(
                UserLessonProgress.user_id == current_user.id,
                UserLessonProgress.completed.is_(True),
            )
        }

        module_info = self._build_module_out(module, current_user.id, lessons_override=len(lessons))

        lesson_list = [
            self._build_lesson_out(lesson, lesson.id in completed_lesson_ids)
            for lesson in lessons
        ]

        return ModuleWithLessons(module=module_info, lessons=lesson_list)

    def create_lesson(self, module_id: int, payload: LessonCreateRequest, current_user: User) -> LessonOut:
        module = self._get_module(module_id)
        self._ensure_can_manage_module(module, current_user)

        lesson = Lesson(
            module_id=module.id,
            title=payload.title,
            duration=payload.duration,
            type=payload.type,
            description=payload.description,
            display_order=payload.display_order,
            content_mode=payload.content_mode,
            external_url=payload.external_url,
        )
        self.db.add(lesson)
        self.db.commit()
        self.db.refresh(lesson)
        return self._build_lesson_out(lesson, False)

    def update_lesson(self, lesson_id: int, payload: LessonUpdateRequest, current_user: User) -> LessonOut:
        lesson = self._get_lesson(lesson_id)
        self._ensure_can_manage_module(lesson.module, current_user)

        lesson.title = payload.title
        lesson.duration = payload.duration
        lesson.type = payload.type
        lesson.description = payload.description
        lesson.display_order = payload.display_order
        lesson.content_mode = payload.content_mode
        lesson.external_url = payload.external_url
        if payload.content_mode == "external_url":
            self.storage.delete_object(lesson.content_path)
            lesson.content_url = None
            lesson.content_path = None
            lesson.content_mime_type = None
            lesson.content_size_bytes = None
        self.db.commit()
        self.db.refresh(lesson)
        return self._build_lesson_out(lesson, self._is_lesson_completed(lesson.id, current_user.id))

    def delete_lesson(self, lesson_id: int, current_user: User) -> None:
        lesson = self._get_lesson(lesson_id)
        self._ensure_can_manage_module(lesson.module, current_user)
        self.storage.delete_object(lesson.thumbnail_path)
        self.storage.delete_object(lesson.content_path)
        self.db.delete(lesson)
        self.db.commit()

    def upload_lesson_cover(self, lesson_id: int, upload_file, current_user: User) -> LessonOut:
        lesson = self._get_lesson(lesson_id)
        self._ensure_can_manage_module(lesson.module, current_user)
        self._validate_upload(
            upload_file,
            {"image/jpeg", "image/png", "image/webp"},
            {"jpg", "jpeg", "png", "webp"},
            settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024,
        )

        asset = self.storage.upload_lesson_asset(
            module_id=lesson.module_id,
            lesson_id=lesson.id,
            asset_kind="cover",
            upload_file=upload_file,
        )
        self.storage.delete_object(lesson.thumbnail_path)
        lesson.thumbnail_url = asset["url"]
        lesson.thumbnail_path = asset["key"]
        lesson.image = asset["url"]
        self.db.commit()
        self.db.refresh(lesson)
        return self._build_lesson_out(lesson, self._is_lesson_completed(lesson.id, current_user.id))

    def upload_lesson_content(self, lesson_id: int, upload_file, current_user: User) -> LessonOut:
        lesson = self._get_lesson(lesson_id)
        self._ensure_can_manage_module(lesson.module, current_user)
        allowed = self._allowed_mime_types_for_lesson(lesson.type)
        self._validate_upload(
            upload_file,
            allowed,
            self._allowed_extensions_for_lesson(lesson.type),
            self._max_size_for_lesson(lesson.type),
        )

        asset = self.storage.upload_lesson_asset(
            module_id=lesson.module_id,
            lesson_id=lesson.id,
            asset_kind="content",
            upload_file=upload_file,
        )
        self.storage.delete_object(lesson.content_path)
        lesson.content_mode = "upload"
        lesson.content_url = asset["url"]
        lesson.content_path = asset["key"]
        lesson.content_mime_type = asset["mime_type"]
        lesson.content_size_bytes = asset["size_bytes"]
        lesson.external_url = None
        self.db.commit()
        self.db.refresh(lesson)
        return self._build_lesson_out(lesson, self._is_lesson_completed(lesson.id, current_user.id))

    def complete_lesson(self, lesson_id: int, current_user: User, completed: bool) -> Tuple[UserLessonProgress, Module]:
        lesson = self.db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leccion no encontrada")

        self._ensure_module_access(lesson.module_id, current_user)

        progress = (
            self.db.query(UserLessonProgress)
            .filter(UserLessonProgress.user_id == current_user.id, UserLessonProgress.lesson_id == lesson_id)
            .first()
        )

        if not progress:
            progress = UserLessonProgress(
                user_id=current_user.id,
                lesson_id=lesson_id,
            )
            self.db.add(progress)

        progress.completed = completed
        progress.completed_at = datetime.utcnow() if completed else None
        self.db.commit()
        self.db.refresh(progress)
        self.db.refresh(lesson)
        return progress, lesson.module

    def get_quiz(self, module_id: int, current_user: User) -> QuizOut:
        module = self._get_module(module_id)
        self._ensure_module_access(module_id, current_user)

        questions = (
            self.db.query(QuizQuestion)
            .filter(QuizQuestion.module_id == module_id)
            .order_by(QuizQuestion.display_order, QuizQuestion.id)
            .all()
        )
        if not questions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz no configurado")

        serialized_questions = []
        for q in questions:
            serialized_questions.append(
                {
                    "id": q.id,
                    "prompt": q.prompt,
                    "options": [{"id": o.id, "text": o.text} for o in q.options],
                }
            )

        return QuizOut(module_id=module.id, module_title=module.title, questions=serialized_questions)  # type: ignore

    def submit_quiz(self, module_id: int, current_user: User, answers: List[dict]) -> QuizResult:
        self._ensure_module_access(module_id, current_user)

        questions = (
            self.db.query(QuizQuestion)
            .filter(QuizQuestion.module_id == module_id)
            .order_by(QuizQuestion.display_order, QuizQuestion.id)
            .all()
        )
        if not questions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz no configurado")

        option_map = {
            option.id: option for option in self.db.query(QuizOption).filter(QuizOption.question_id.in_([q.id for q in questions]))
        }
        answers_map = {a["question_id"]: a["option_id"] for a in answers}

        correct = 0
        for q in questions:
            option_id = answers_map.get(q.id)
            if option_id and option_id in option_map and option_map[option_id].is_correct:
                correct += 1

        total = len(questions)
        score = int((correct / total) * 100) if total else 0
        passed = score >= 80

        attempt = QuizAttempt(
            user_id=current_user.id,
            module_id=module_id,
            score=score,
            correct_answers=correct,
            total_questions=total,
            passed=passed,
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        return QuizResult(
            module_id=module_id,
            correct_answers=correct,
            total_questions=total,
            score=score,
            passed=passed,
        )

    def create_module(self, payload: ModuleCreateRequest, current_user: User) -> ModuleOut:
        module = Module(
            title=payload.title,
            description=payload.description,
            icon=payload.icon,
            color=payload.color,
            due_to_checklist=payload.due_to_checklist,
            checklist_section_id=payload.checklist_section_id,
            quiz_required=payload.quiz_required,
            owner_id=current_user.id,
        )
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return self._build_module_out(module, current_user.id)

    def update_module(self, module_id: int, payload: ModuleUpdateRequest, current_user: User) -> ModuleOut:
        module = self._get_module(module_id)
        self._ensure_can_manage_module(module, current_user)

        module.title = payload.title
        module.description = payload.description
        module.icon = payload.icon
        module.color = payload.color
        module.due_to_checklist = payload.due_to_checklist
        module.checklist_section_id = payload.checklist_section_id
        module.quiz_required = payload.quiz_required
        self.db.commit()
        self.db.refresh(module)
        return self._build_module_out(module, current_user.id)

    def delete_module(self, module_id: int, current_user: User) -> None:
        module = self._get_module(module_id)
        self._ensure_can_manage_module(module, current_user)
        self.db.delete(module)
        self.db.commit()

    def assign_module(self, module_id: int, payload: ModuleAssignmentRequest, current_user: User) -> ModuleAssignmentOut:
        self._get_module(module_id)
        user_ids = set(payload.user_ids)
        if not user_ids:
            self.db.query(ModuleAssignment).filter(ModuleAssignment.module_id == module_id).delete()
            self.db.commit()
            return ModuleAssignmentOut(module_id=module_id, user_ids=[])

        users = self.db.query(User).filter(User.id.in_(list(user_ids))).all()
        found_ids = {u.id for u in users}
        missing = user_ids - found_ids
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Usuarios no encontrados: {sorted(list(missing))}")

        existing = {
            ma.user_id
            for ma in self.db.query(ModuleAssignment).filter(ModuleAssignment.module_id == module_id)
        }
        to_remove = existing - user_ids
        to_add = user_ids - existing

        if to_remove:
            self.db.query(ModuleAssignment).filter(
                ModuleAssignment.module_id == module_id,
                ModuleAssignment.user_id.in_(list(to_remove)),
            ).delete(synchronize_session=False)

        for uid in to_add:
            self.db.add(ModuleAssignment(module_id=module_id, user_id=uid, assigned_by=current_user.id))

        self.db.commit()
        return ModuleAssignmentOut(module_id=module_id, user_ids=sorted(list(user_ids)))

    def list_assignable_users(self) -> List[UserSummary]:
        users = self.db.query(User).all()
        return [
            UserSummary(
                id=user.id,
                name=user.name,
                email=user.email,
                roles=[r.code for r in user.roles],
            )
            for user in users
        ]

    def module_progress_report(self, module_id: int, current_user: User) -> ModuleProgressOut:
        module = self._get_module(module_id)
        assignments_query = self.db.query(ModuleAssignment).filter(ModuleAssignment.module_id == module_id)
        if not self._is_superadmin(current_user):
            assignments_query = assignments_query.filter(ModuleAssignment.assigned_by == current_user.id)
        assignments = assignments_query.all()

        progress_rows: List[UserProgressOut] = []
        for assignment in assignments:
            lessons_total, lessons_completed, quiz_completed = self._module_progress(module_id, assignment.user_id)
            latest_attempt = (
                self.db.query(QuizAttempt)
                .filter(QuizAttempt.module_id == module_id, QuizAttempt.user_id == assignment.user_id)
                .order_by(QuizAttempt.created_at.desc())
                .first()
            )
            progress_rows.append(
                UserProgressOut(
                    user=UserSummary(
                        id=assignment.user.id,
                        name=assignment.user.name,
                        email=assignment.user.email,
                        roles=[r.code for r in assignment.user.roles],
                    ),
                    completed_lessons=lessons_completed,
                    total_lessons=lessons_total,
                    quiz_completed=quiz_completed,
                    last_score=latest_attempt.score if latest_attempt else None,
                    last_attempt_at=latest_attempt.created_at if latest_attempt else None,
                )
            )

        return ModuleProgressOut(module_id=module.id, module_title=module.title, users=progress_rows)

    # -------------------------
    # Helpers
    # -------------------------
    def _module_progress(self, module_id: int, user_id: int) -> Tuple[int, int, bool]:
        lessons_total = (
            self.db.query(Lesson).filter(Lesson.module_id == module_id).count()
        )
        lessons_completed = (
            self.db.query(UserLessonProgress)
            .join(Lesson, Lesson.id == UserLessonProgress.lesson_id)
            .filter(
                Lesson.module_id == module_id,
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.completed.is_(True),
            )
            .count()
        )
        quiz_completed = self._quiz_completed(module_id, user_id)
        return lessons_total, lessons_completed, quiz_completed

    def _quiz_completed(self, module_id: int, user_id: int) -> bool:
        return (
            self.db.query(QuizAttempt)
            .filter(
                QuizAttempt.module_id == module_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.passed.is_(True),
            )
            .count()
            > 0
        )

    def _modules_for_user(self, current_user: User) -> List[Module]:
        if self._has_full_access(current_user):
            return self.db.query(Module).all()
        assigned_ids = [
            ma.module_id
            for ma in self.db.query(ModuleAssignment).filter(ModuleAssignment.user_id == current_user.id)
        ]
        if not assigned_ids:
            return []
        return self.db.query(Module).filter(Module.id.in_(assigned_ids)).all()

    def _build_module_out(self, module: Module, viewer_id: int, lessons_override: int | None = None) -> ModuleOut:
        lessons_total, lessons_completed, quiz_completed = self._module_progress(module.id, viewer_id)
        if lessons_override is not None:
            lessons_total = lessons_override
        due_to_checklist = module.due_to_checklist
        if module.section and module.section.status == "deficiente":
            due_to_checklist = True
        return ModuleOut(
            id=module.id,
            title=module.title,
            description=module.description,
            icon=module.icon,
            color=module.color,
            lessons=lessons_total,
            completed_lessons=lessons_completed,
            due_to_checklist=due_to_checklist,
            quiz_completed=quiz_completed,
            quiz_required=module.quiz_required,
            checklist_section_id=module.checklist_section_id,
            owner_id=module.owner_id,
        )

    def _build_lesson_out(self, lesson: Lesson, completed: bool) -> LessonOut:
        return LessonOut(
            id=lesson.id,
            title=lesson.title,
            duration=lesson.duration,
            type=lesson.type,
            description=lesson.description,
            image=lesson.image,
            thumbnail_url=lesson.thumbnail_url,
            content_mode=lesson.content_mode or "upload",
            content_url=lesson.content_url,
            content_mime_type=lesson.content_mime_type,
            content_size_bytes=lesson.content_size_bytes,
            external_url=lesson.external_url,
            display_order=lesson.display_order or 1,
            completed=completed,
        )

    def _has_full_access(self, user: User) -> bool:
        role_codes = {r.code for r in user.roles}
        return "superadmin" in role_codes or "leader" in role_codes or "admin" in role_codes

    def _is_superadmin(self, user: User) -> bool:
        return any(r.code == "superadmin" for r in user.roles)

    def _ensure_module_access(self, module_id: int, user: User) -> None:
        if self._has_full_access(user):
            return
        assignment = (
            self.db.query(ModuleAssignment)
            .filter(ModuleAssignment.module_id == module_id, ModuleAssignment.user_id == user.id)
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Modulo no asignado para el usuario")

    def _ensure_can_manage_module(self, module: Module, user: User) -> None:
        if self._is_superadmin(user):
            return
        if module.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el dueno puede modificar el modulo")

    def _get_module(self, module_id: int) -> Module:
        module = self.db.query(Module).filter(Module.id == module_id).first()
        if not module:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modulo no encontrado")
        return module

    def _get_lesson(self, lesson_id: int) -> Lesson:
        lesson = self.db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leccion no encontrada")
        return lesson

    def _is_lesson_completed(self, lesson_id: int, user_id: int) -> bool:
        return (
            self.db.query(UserLessonProgress)
            .filter(
                UserLessonProgress.lesson_id == lesson_id,
                UserLessonProgress.user_id == user_id,
                UserLessonProgress.completed.is_(True),
            )
            .count()
            > 0
        )

    def _allowed_mime_types_for_lesson(self, lesson_type: str) -> set[str]:
        if lesson_type == "video":
            return {"video/mp4", "video/webm", "video/quicktime"}
        if lesson_type == "document":
            return {
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        return {
            "application/pdf",
            "text/plain",
            "application/json",
        }

    def _allowed_extensions_for_lesson(self, lesson_type: str) -> set[str]:
        if lesson_type == "video":
            return {"mp4", "webm", "mov"}
        if lesson_type == "document":
            return {"pdf", "docx", "pptx", "xlsx"}
        return {"pdf", "txt", "json"}

    def _max_size_for_lesson(self, lesson_type: str) -> int:
        if lesson_type == "video":
            return settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024
        if lesson_type == "document":
            return settings.MAX_DOCUMENT_UPLOAD_MB * 1024 * 1024
        return settings.MAX_DOCUMENT_UPLOAD_MB * 1024 * 1024

    def _validate_upload(self, upload_file, allowed_mimes: set[str], allowed_extensions: set[str], max_bytes: int) -> None:
        content_type = upload_file.content_type
        filename = upload_file.filename or ""
        if content_type not in allowed_mimes:
            logger.warning("Upload rechazado por MIME: %s (%s)", filename, content_type)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no permitido: {content_type or filename or 'desconocido'}",
            )
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in allowed_extensions:
            logger.warning("Upload rechazado por extension: %s", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension no permitida: .{extension or 'desconocida'}",
            )
        upload_file.file.seek(0, 2)
        size = upload_file.file.tell()
        upload_file.file.seek(0)
        if size > max_bytes:
            logger.warning("Upload rechazado por tamano: %s (%s bytes)", filename, size)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archivo demasiado grande. Maximo permitido: {max_bytes // (1024 * 1024)} MB",
            )
