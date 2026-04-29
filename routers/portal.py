from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import shutil
from pathlib import Path
from database import get_db
from models import User, Message
from auth_utils import hash_password, verify_password, create_user_session, SESSION_COOKIE_NAME
from routers.deps_auth import require_user

router = APIRouter(prefix="/portal")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

UPLOAD_DIR = PROJECT_ROOT / "static" / "uploads" / "certs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/", response_class=HTMLResponse)
async def portal_root(request: Request):
    return RedirectResponse(url="/portal/landing")

@router.get("/landing", response_class=HTMLResponse)
async def freelancer_landing(request: Request):
    return templates.TemplateResponse("portal/landing.html", {"request": request})

@router.get("/signup", response_class=HTMLResponse)
async def talent_signup(request: Request):
    return templates.TemplateResponse("portal/signup.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def talent_login(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def talent_login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Look up user by email
    user = db.query(User).filter(User.email == email, User.role == "freelancer").first()
    
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "error": "Invalid email or password."
        })
    
    response = RedirectResponse(url="/portal/dashboard", status_code=303)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=create_user_session(user.id, user.role), httponly=True)
    return response

@router.get("/logout")
async def talent_logout():
    response = RedirectResponse(url="/portal/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def freelancer_dashboard(
    request: Request, 
    db: Session = Depends(get_db), 
    user: User = Depends(require_user("freelancer")),
):
    # Real Stats Calculation
    from sqlalchemy import func
    from models import Task, Lead
    
    # 1. Active Projects (Tasks where status is 'assigned')
    active_tasks = db.query(Task).filter(Task.assigned_freelancer_id == user.id, Task.status == "assigned").all()
    active_count = len(active_tasks)
    
    # 2. Total Earned (Sum of payout_price for 'settled' tasks)
    total_earned = db.query(func.sum(Task.payout_price)).filter(
        Task.assigned_freelancer_id == user.id, 
        Task.status == "settled"
    ).scalar() or 0.0
    
    # 3. Completed (Count of tasks with status 'settled')
    completed_count = db.query(Task).filter(
        Task.assigned_freelancer_id == user.id, 
        Task.status == "settled"
    ).count()

    # 4. Message count
    messages = db.query(Message).order_by(Message.id.desc()).all()
    unread_messages = db.query(Message).filter(Message.is_read == 0).count()

    # 5. Opportunities (New leads)
    opportunities = db.query(Lead).filter(Lead.status == "new").limit(2).all()

    return templates.TemplateResponse("portal/dashboard.html", {
        "request": request, 
        "user": user,
        "active_tasks": active_tasks,
        "active_count": active_count,
        "total_earned": f"{total_earned:,.2f}",
        "completed_count": completed_count,
        "unread_messages": unread_messages,
        "messages": messages,
        "opportunities": opportunities
    })


@router.get("/projects/{task_id}", response_class=HTMLResponse)
async def freelancer_project_detail(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user("freelancer")),
):
    from models import Task, Lead, Conversation

    task = db.query(Task).filter(Task.id == task_id, Task.assigned_freelancer_id == user.id).first()
    if not task:
        return RedirectResponse(url="/portal/dashboard", status_code=303)
    lead = db.query(Lead).filter(Lead.id == task.lead_id).first()
    conv = db.query(Conversation).filter(Conversation.task_id == task.id).first()
    return templates.TemplateResponse(
        "portal/project_detail.html",
        {"request": request, "user": user, "task": task, "lead": lead, "conversation": conv},
    )

@router.get("/profile", response_class=HTMLResponse)
async def freelancer_profile(request: Request, user: User = Depends(require_user("freelancer"))):
    return templates.TemplateResponse("portal/profile.html", {"request": request, "user": user})

@router.post("/signup")
async def register_freelancer(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    gender: str = Form(...),
    whatsapp: str = Form(...),
    primary_skill: str = Form(...),
    password: str = Form(...),
    custom_skill: str = Form(None),
    bank_details: str = Form(None),
    certifications: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    cert_path = None
    if certifications and certifications.filename:
        cert_path = str(UPLOAD_DIR / f"{email}_{certifications.filename}")
        with open(cert_path, "wb") as buffer:
            shutil.copyfileobj(certifications.file, buffer)
    
    new_user = User(
        name=name,
        email=email,
        role="freelancer",
        gender=gender,
        whatsapp=whatsapp,
        primary_skill=primary_skill,
        custom_skill=custom_skill if primary_skill == "Other / Custom" else None,
        bank_details=bank_details,
        certifications_path=cert_path,
        password_hash=hash_password(password)
    )
    
    db.add(new_user)
    db.commit()
    
    return templates.TemplateResponse("portal/signup_success.html", {"request": request, "name": name})
