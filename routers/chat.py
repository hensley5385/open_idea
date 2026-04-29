from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from auth_utils import SESSION_COOKIE_NAME, read_user_session
from database import get_db
from models import ChatMessage, Conversation, User
from routers.deps_auth import get_current_user


router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = {}

    async def connect(self, conversation_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._conns.setdefault(conversation_id, set()).add(websocket)

    def disconnect(self, conversation_id: int, websocket: WebSocket) -> None:
        conns = self._conns.get(conversation_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._conns.pop(conversation_id, None)

    async def broadcast(self, conversation_id: int, payload: dict) -> None:
        conns = list(self._conns.get(conversation_id, set()))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, ws)


manager = ConnectionManager()


def _require_chat_user(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(status_code=303, detail="Not authenticated", headers={"Location": "/login"})
    if user.role not in ("client", "freelancer", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@router.get("/chat", response_class=HTMLResponse)
async def chat_home(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    user = _require_chat_user(user)
    if user.role == "client":
        conversations = db.query(Conversation).filter(Conversation.client_user_id == user.id).order_by(Conversation.id.desc()).all()
    elif user.role == "freelancer":
        conversations = db.query(Conversation).filter(Conversation.freelancer_user_id == user.id).order_by(Conversation.id.desc()).all()
    else:
        conversations = db.query(Conversation).order_by(Conversation.id.desc()).limit(100).all()

    return templates.TemplateResponse(
        "chat/chat.html",
        {"request": request, "user": user, "conversations": conversations, "selected_conversation_id": None},
    )


@router.get("/chat/{conversation_id}", response_class=HTMLResponse)
async def chat_open(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    user = _require_chat_user(user)
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if user.role != "admin" and user.id not in (conv.client_user_id, conv.freelancer_user_id):
        raise HTTPException(status_code=303, detail="Unauthorized", headers={"Location": "/chat"})

    if user.role == "client":
        conversations = db.query(Conversation).filter(Conversation.client_user_id == user.id).order_by(Conversation.id.desc()).all()
    elif user.role == "freelancer":
        conversations = db.query(Conversation).filter(Conversation.freelancer_user_id == user.id).order_by(Conversation.id.desc()).all()
    else:
        conversations = db.query(Conversation).order_by(Conversation.id.desc()).limit(100).all()

    return templates.TemplateResponse(
        "chat/chat.html",
        {"request": request, "user": user, "conversations": conversations, "selected_conversation_id": conversation_id},
    )


def _ws_get_user_id_role(websocket: WebSocket) -> Optional[dict]:
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return read_user_session(token)


@router.websocket("/ws/chat/{conversation_id}")
async def chat_ws(conversation_id: int, websocket: WebSocket):
    # We open a DB session manually for the WS lifecycle.
    db: Session = next(get_db())
    try:
        session = _ws_get_user_id_role(websocket)
        if not session:
            await websocket.close(code=1008)
            return

        user = db.query(User).filter(User.id == session["user_id"]).first()
        if not user:
            await websocket.close(code=1008)
            return

        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            await websocket.close(code=1008)
            return

        if user.role != "admin" and user.id not in (conv.client_user_id, conv.freelancer_user_id):
            await websocket.close(code=1008)
            return

        await manager.connect(conversation_id, websocket)

        # Initial history
        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.asc())
            .limit(200)
            .all()
        )
        await websocket.send_json(
            {
                "type": "history",
                "messages": [
                    {
                        "id": m.id,
                        "sender_user_id": m.sender_user_id,
                        "sender_role": m.sender_role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in history
                ],
            }
        )

        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue
            if data.get("type") != "message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue
            if len(content) > 2000:
                content = content[:2000]

            msg = ChatMessage(
                conversation_id=conversation_id,
                sender_user_id=user.id,
                sender_role=user.role,
                content=content,
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)

            await manager.broadcast(
                conversation_id,
                {
                    "type": "message",
                    "message": {
                        "id": msg.id,
                        "sender_user_id": msg.sender_user_id,
                        "sender_role": msg.sender_role,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                    },
                },
            )
    except WebSocketDisconnect:
        manager.disconnect(conversation_id, websocket)
    finally:
        try:
            db.close()
        except Exception:
            pass

