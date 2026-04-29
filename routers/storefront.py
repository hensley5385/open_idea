from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from database import get_db
from models import Lead, Message, User
from auth_utils import hash_password, verify_password, create_user_session, SESSION_COOKIE_NAME
from routers.deps_auth import require_user

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("storefront/index.html", {"request": request})

@router.get("/explore", response_class=HTMLResponse)
async def explore_services(request: Request):
    return templates.TemplateResponse("storefront/explore.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def client_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user("client")),
):
    # Dashboard expects `messages` for the "Recent Messages" section.
    messages = db.query(Message).order_by(Message.id.desc()).all()
    leads = db.query(Lead).filter(Lead.client_contact == user.email).order_by(Lead.id.desc()).all()
    return templates.TemplateResponse(
        "storefront/dashboard.html",
        {"request": request, "messages": messages, "user": user, "leads": leads},
    )


@router.get("/dashboard/projects/{lead_id}", response_class=HTMLResponse)
async def client_project_detail(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user("client")),
):
    from models import Task, Conversation

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.client_contact == user.email).first()
    if not lead:
        return RedirectResponse(url="/dashboard", status_code=303)

    task = db.query(Task).filter(Task.lead_id == lead.id).order_by(Task.id.desc()).first()
    conversation = None
    freelancer = None
    if task and task.assigned_freelancer_id:
        freelancer = db.query(User).filter(User.id == task.assigned_freelancer_id, User.role == "freelancer").first()
        conversation = db.query(Conversation).filter(Conversation.task_id == task.id).first()
        if freelancer and not conversation:
            conversation = Conversation(task_id=task.id, client_user_id=user.id, freelancer_user_id=freelancer.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

    return templates.TemplateResponse(
        "storefront/project_detail.html",
        {"request": request, "user": user, "lead": lead, "task": task, "freelancer": freelancer, "conversation": conversation},
    )

@router.post("/send-message")
async def send_message(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    new_msg = Message(
        sender_email=email,
        subject=f"Contact Form: {name}",
        content=message
    )
    db.add(new_msg)
    db.commit()
    return RedirectResponse(url="/dashboard?sent=true", status_code=303)

@router.get("/request-service", response_class=HTMLResponse)
async def request_service_page(request: Request):
    return templates.TemplateResponse("storefront/request_service.html", {"request": request})

@router.post("/request-service")
async def handle_request_service(
    service: str = Form(...),
    client_name: str = Form(...),
    email: str = Form(...),
    location: str = Form(None),
    category: str = Form(...),
    details: str = Form(...),
    db: Session = Depends(get_db)
):
    # Combine details into a single content block for the Message model
    full_content = f"Client Name: {client_name}\nCategory: {category}\nLocation: {location or 'N/A'}\n\nProject Details:\n{details}"
    
    new_msg = Message(
        sender_email=email,
        subject=f"New Service Request: {service}",
        content=full_content
    )
    db.add(new_msg)
    db.commit()
    
    # Redirect to dashboard with a success flag
    return RedirectResponse(url="/dashboard?request_sent=true", status_code=303)

@router.get("/invite", response_class=HTMLResponse)
async def invitation_page(request: Request):
    return templates.TemplateResponse("invitation.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("storefront/login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email, User.role == "client").first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "storefront/login.html",
            {"request": request, "error": "Invalid email or password."},
        )

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=create_user_session(user.id, user.role), httponly=True)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("storefront/register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            "storefront/register.html",
            {"request": request, "error": "An account with this email already exists."},
        )

    user = User(
        name=name,
        email=email,
        role="client",
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=create_user_session(user.id, user.role), httponly=True)
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

@router.get("/status-check", response_class=HTMLResponse)
async def status_check_page(request: Request):
    return templates.TemplateResponse("storefront/status_check.html", {"request": request})

@router.post("/status-check", response_class=HTMLResponse)
async def check_status(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    # Look up leads by client_contact (which stores email in this mock)
    leads = db.query(Lead).filter(Lead.client_contact == email).all()
    return templates.TemplateResponse("storefront/status_check.html", {
        "request": request, 
        "leads": leads, 
        "email": email
    })
