from __future__ import annotations

from typing import Literal, Optional

from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth_utils import SESSION_COOKIE_NAME, read_user_session
from database import get_db
from models import User

Role = Literal["client", "freelancer", "admin"]


def _redirect_for_role(role: Role) -> str:
    if role == "client":
        return "/login"
    if role == "freelancer":
        return "/portal/login"
    return "/"


def _home_for_role(role: Role) -> str:
    if role == "client":
        return "/dashboard"
    if role == "freelancer":
        return "/portal/dashboard"
    return "/"


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    bridge_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Optional[User]:
    if not bridge_session:
        return None
    session = read_user_session(bridge_session)
    if not session:
        return None
    user = db.query(User).filter(User.id == session["user_id"]).first()
    return user


def require_user(required_role: Role):
    async def _dep(
        request: Request,
        user: Optional[User] = Depends(get_current_user),
    ) -> User:
        # Not logged in
        if not user:
            raise HTTPException(
                status_code=303,
                detail="Not authenticated",
                headers={"Location": _redirect_for_role(required_role)},
            )

        # Role mismatch: redirect to their own home dashboard
        if user.role != required_role:
            raise HTTPException(
                status_code=303,
                detail="Unauthorized",
                headers={"Location": _home_for_role(user.role) if user.role else "/"},
            )

        return user

    return _dep

