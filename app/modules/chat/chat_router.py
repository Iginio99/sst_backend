from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.config.database import SessionLocal
from app.infrastructure.respository import get_db
from app.modules.auth.auth_service import get_current_user
from app.modules.chat.chat_schema import ChatContactOut, ChatMessageCreate, ChatMessageOut
from app.modules.chat.chat_service import ChatService, ConnectionManager, get_current_user_from_token

router = APIRouter(prefix="/chat", tags=["Chat"])
manager = ConnectionManager()


@router.get("/contacts", response_model=list[ChatContactOut])
def list_contacts(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return ChatService(db).list_contacts(current_user)


@router.get("/messages/{user_id}", response_model=list[ChatMessageOut])
def list_messages(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return ChatService(db).list_messages(current_user, user_id)


@router.post("/messages", response_model=ChatMessageOut)
def send_message(payload: ChatMessageCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return ChatService(db).send_message(current_user, payload)


@router.websocket("/ws")
async def chat_socket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    user_id: int | None = None
    try:
        current_user = get_current_user_from_token(token, db)
        user_id = current_user.id
        print(f"[chat/ws] connect user_id={user_id} roles={[r.code for r in current_user.roles]}")
        await manager.connect(user_id, websocket)
        service = ChatService(db)

        while True:
            data = await websocket.receive_json()
            print(f"[chat/ws] recv from user_id={user_id} payload={data}")
            try:
                payload = ChatMessageCreate(**data)
                message = service.send_message(current_user, payload)
                print(
                    "[chat/ws] send message "
                    f"id={message.id} from={message.sender_id} to={message.recipient_id}"
                )
                await manager.send_to_users(
                    [message.recipient_id],
                    {"type": "message", "message": message.model_dump()},
                )
            except (HTTPException, ValidationError) as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else "Mensaje invalido"
                await websocket.send_json({"type": "error", "detail": detail})
    except WebSocketDisconnect:
        print(f"[chat/ws] disconnect user_id={user_id}")
        if user_id is not None:
            manager.disconnect(user_id, websocket)
    except Exception:
        print(f"[chat/ws] error user_id={user_id}")
        if user_id is not None:
            manager.disconnect(user_id, websocket)
    finally:
        db.close()
