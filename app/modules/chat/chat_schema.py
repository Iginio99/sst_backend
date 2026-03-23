from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatContactOut(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]


class ChatMessageCreate(BaseModel):
    recipient_id: int
    content: str = Field(min_length=1, max_length=2000)
    client_message_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    created_at: datetime
    sender_name: Optional[str] = None
    client_message_id: Optional[str] = None
