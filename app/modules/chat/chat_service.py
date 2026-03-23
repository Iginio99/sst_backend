from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException, status, WebSocket
from jose import JWTError
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.security import decode_token
from app.modules.auth.auth_service import AuthService
from app.modules.chat.chat_schema import ChatContactOut, ChatMessageCreate, ChatMessageOut
from app.modules.models import ChatMessage, Role, User


ROLE_CHAT_MAP = {
    "superadmin": {"admin"},
    "admin": {"superadmin", "leader"},
    "leader": {"admin", "collaborator"},
    "collaborator": {"leader"},
}


def _unique_roles(roles: Iterable[str]) -> set[str]:
    return {r for r in roles if r}


def get_current_user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_token(token, expected_type="access")
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    service = AuthService(db)
    user = service._get_user_with_relations(user_id=int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        print(f"[chat/ws] accepted user_id={user_id}")
        self._connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        user_sockets = self._connections.get(user_id)
        if not user_sockets:
            return
        user_sockets.discard(websocket)
        if not user_sockets:
            self._connections.pop(user_id, None)
        print(f"[chat/ws] removed socket user_id={user_id} remaining={len(user_sockets)}")

    async def send_to_users(self, user_ids: Iterable[int], payload: dict) -> None:
        for user_id in set(user_ids):
            sockets = set(self._connections.get(user_id, set()))
            stale: set[WebSocket] = set()
            for socket in sockets:
                try:
                    await socket.send_json(payload)
                except Exception:
                    stale.add(socket)
            if stale:
                for socket in stale:
                    self.disconnect(user_id, socket)


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def list_contacts(self, current_user: User) -> list[ChatContactOut]:
        allowed_roles = self._allowed_role_codes(current_user)
        if not allowed_roles:
            return []

        users = (
            self.db.query(User)
            .join(User.roles)
            .options(joinedload(User.roles))
            .filter(Role.code.in_(list(allowed_roles)), User.id != current_user.id)
            .distinct()
            .all()
        )
        return [
            ChatContactOut(
                id=user.id,
                email=user.email,
                name=user.name,
                roles=[role.code for role in user.roles],
            )
            for user in users
        ]

    def list_messages(self, current_user: User, other_user_id: int) -> list[ChatMessageOut]:
        other_user = self.db.query(User).options(joinedload(User.roles)).filter(User.id == other_user_id).first()
        if not other_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if not self._can_chat(current_user, other_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversacion no permitida")

        messages = (
            self.db.query(ChatMessage)
            .options(joinedload(ChatMessage.sender))
            .filter(
                or_(
                    and_(
                        ChatMessage.sender_id == current_user.id,
                        ChatMessage.recipient_id == other_user.id,
                    ),
                    and_(
                        ChatMessage.sender_id == other_user.id,
                        ChatMessage.recipient_id == current_user.id,
                    ),
                )
            )
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [self._serialize_message(message) for message in messages]

    def send_message(self, current_user: User, payload: ChatMessageCreate) -> ChatMessageOut:
        recipient = (
            self.db.query(User)
            .options(joinedload(User.roles))
            .filter(User.id == payload.recipient_id)
            .first()
        )
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if recipient.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes enviarte mensajes")
        if not self._can_chat(current_user, recipient):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversacion no permitida")

        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mensaje vacio")

        message = ChatMessage(sender_id=current_user.id, recipient_id=recipient.id, content=content)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        message.sender = current_user
        return self._serialize_message(message, client_message_id=payload.client_message_id)

    def _allowed_role_codes(self, user: User) -> set[str]:
        role_codes = _unique_roles([role.code for role in user.roles])
        allowed: set[str] = set()
        for code in role_codes:
            allowed |= ROLE_CHAT_MAP.get(code, set())
        return allowed

    def _can_chat(self, user: User, other_user: User) -> bool:
        allowed = self._allowed_role_codes(user)
        if not allowed:
            return False
        other_roles = _unique_roles([role.code for role in other_user.roles])
        return bool(allowed.intersection(other_roles))

    def _serialize_message(
        self,
        message: ChatMessage,
        client_message_id: Optional[str] = None,
    ) -> ChatMessageOut:
        return ChatMessageOut(
            id=message.id,
            sender_id=message.sender_id,
            recipient_id=message.recipient_id,
            content=message.content,
            created_at=message.created_at,
            sender_name=message.sender.name if message.sender else None,
            client_message_id=client_message_id,
        )
