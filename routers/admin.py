from fastapi import APIRouter, Request, Depends, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import json
from pathlib import Path
import os
from database import get_db
from models import Lead, User, ScrapedFreelancer, Task, Template, Message
from auth_utils import (
    SESSION_COOKIE_NAME,
    create_signed_token,
    create_user_session,
    read_signed_token,
    verify_password,
)
from scraper import scrape_wwr_jobs, scrape_freelancers

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

ADMIN_GATE_COOKIE = "admin_gate"

def _admin_prefix() -> str:
    # Router is mounted with this prefix in main.py
    return os.getenv("ADMIN_PREFIX", "").strip() or "/_controlpanel"

def _admin_url(path: str) -> str:
    p = _admin_prefix().rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{p}{suffix}"

def _is_gate_valid(token: Optional[str]) -> bool:
    if not token:
        return False
    data = read_signed_token(token)
    return bool(data and data.get("gate") == "admin")

async def require_admin_gate(admin_gate: Optional[str] = Cookie(None, alias=ADMIN_GATE_COOKIE)) -> str:
    # Return 404 to avoid exposing the admin surface.
    if not _is_gate_valid(admin_gate):
        raise HTTPException(status_code=404, detail="Not found")
    return admin_gate

async def require_admin_session(
    db: Session = Depends(get_db),
    bridge_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> User:
    from auth_utils import read_user_session

    session = read_user_session(bridge_session or "")
    if not session or session.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not found")
    user = db.query(User).filter(User.id == session["user_id"], User.role == "admin").first()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user

@router.get("/enter", response_class=HTMLResponse)
async def admin_enter_page(request: Request):
    return templates.TemplateResponse("admin/enter.html", {"request": request, "admin_prefix": _admin_prefix()})

@router.post("/enter")
async def admin_enter_post(request: Request, access_key: str = Form(...)):
    # Default to 'bridge_access' if not set or empty in environment
    env_key = os.getenv("ADMIN_ACCESS_KEY", "").strip()
    expected = env_key if env_key else "bridge_access"
    if not expected or access_key != expected:
        return templates.TemplateResponse(
            "admin/enter.html",
            {"request": request, "admin_prefix": _admin_prefix(), "error": "Invalid access key."},
        )
    response = RedirectResponse(url=_admin_url("/login"), status_code=303)
    response.set_cookie(
        key=ADMIN_GATE_COOKIE,
        value=create_signed_token({"gate": "admin"}, ttl_seconds=60 * 10),
        httponly=True,
        samesite="lax",
    )
    return response

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, gate: str = Depends(require_admin_gate)):
    return templates.TemplateResponse("admin/login.html", {"request": request, "admin_prefix": _admin_prefix()})

@router.post("/login")
async def admin_login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    gate: str = Depends(require_admin_gate),
):
    user = db.query(User).filter(User.email == email, User.role == "admin").first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "admin_prefix": _admin_prefix(),
            "error": "Invalid admin credentials."
        })
    
    response = RedirectResponse(url=_admin_url("/"), status_code=303)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=create_user_session(user.id, user.role), httponly=True, samesite="lax")
    return response

@router.get("/logout")
async def admin_logout():
    response = RedirectResponse(url=_admin_url("/enter"), status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(ADMIN_GATE_COOKIE)
    return response

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, 
    db: Session = Depends(get_db), 
    admin: User = Depends(require_admin_session),
):
    # Fetch live leads from database
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    # Fetch registered freelancers for assignment
    freelancers = db.query(User).filter(User.role == "freelancer").all()
    # Fetch scraped freelancers for assignment
    scraped = db.query(ScrapedFreelancer).all()
    # Fetch outreach templates
    outreach_templates = db.query(Template).all()
    # Fetch client messages
    client_messages = db.query(Message).order_by(Message.id.desc()).all()
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, 
        "leads": leads,
        "freelancers": freelancers,
        "scraped": scraped,
        "outreach_templates": outreach_templates,
        "client_messages": client_messages,
        "admin_prefix": _admin_prefix(),
    })


@router.post("/scrape")
async def trigger_scrape(db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    jobs = scrape_wwr_jobs()
    new_leads_count = 0
    
    for job in jobs:
        # Deduplication: check if link already exists
        existing = db.query(Lead).filter(Lead.link == job["link"]).first()
        if not existing:
            new_lead = Lead(
                title=job.get("title", "No Title"),
                link=job.get("link", "#"),
                description=(job.get("description") or "")[:500], # Truncate safely
                source_price=100.0, # Default Estimated Budget
                client_contact="RSS Feed",
                status="new"
            )
            db.add(new_lead)
            new_leads_count += 1
    
    db.commit()
    return {"message": f"Successfully scraped. Added {new_leads_count} new leads."}

@router.get("/talent-scout", response_class=HTMLResponse)
async def talent_scout(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    scraped_freelancers = db.query(ScrapedFreelancer).order_by(ScrapedFreelancer.id.desc()).all()
    return templates.TemplateResponse("admin/talent_scout.html", {"request": request, "freelancers": scraped_freelancers, "admin_prefix": _admin_prefix()})

@router.post("/scout")
async def trigger_scout(keyword: str = Form(...), db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    freelancers = scrape_freelancers(keyword)
    new_count = 0
    for f in freelancers:
        existing = db.query(ScrapedFreelancer).filter(ScrapedFreelancer.profile_link == f["link"]).first()
        if not existing:
            new_f = ScrapedFreelancer(
                name=f["name"],
                profile_link=f["link"],
                skills=f["skills"],
                source=f["source"]
            )
            db.add(new_f)
            new_count += 1
    db.commit()
    return RedirectResponse(url="/admin/talent-scout", status_code=303)

@router.post("/assign-lead")
async def assign_lead(
    lead_id: int = Form(...),
    freelancer_id: int = Form(None),
    scraped_id: int = Form(None),
    payout: float = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_session),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Create Task
    new_task = Task(
        lead_id=lead_id,
        assigned_freelancer_id=freelancer_id,
        assigned_scraped_id=scraped_id,
        payout_price=payout,
        status="assigned"
    )
    
    lead.status = "assigned"
    db.add(new_task)
    db.commit()

    # Create a conversation when work is active between a specific client and registered freelancer.
    try:
        from models import Conversation
        if freelancer_id:
            # client_contact stores email for real client leads
            client_user = db.query(User).filter(User.email == lead.client_contact, User.role == "client").first()
            if client_user:
                existing_conv = db.query(Conversation).filter(Conversation.task_id == new_task.id).first()
                if not existing_conv:
                    db.add(Conversation(
                        task_id=new_task.id,
                        client_user_id=client_user.id,
                        freelancer_user_id=freelancer_id,
                    ))
                    db.commit()
    except Exception:
        # Conversation creation is best-effort; chat UI can create it later if needed.
        pass
    
    return RedirectResponse(url=_admin_url("/"), status_code=303)

@router.get("/finance-vault", response_class=HTMLResponse)
async def finance_vault(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    # Total Revenue: Sum of source_price for 'PAID' leads
    revenue_leads = db.query(Lead).filter(Lead.status == "PAID").all()
    total_revenue = sum(l.source_price for l in revenue_leads)
    
    # Total Liabilities: Sum of payout_price for tasks where status is 'assigned' (not yet settled)
    liabilities_tasks = db.query(Task).filter(Task.status == "assigned").all()
    total_liabilities = sum(t.payout_price for t in liabilities_tasks)
    
    # Net Profit
    net_profit = total_revenue - total_liabilities
    
    # Fetch all tasks for the payout table
    tasks = db.query(Task).order_by(Task.id.desc()).all()

    # --- New Features for Finance Vault ---
    # 1. Project Distribution (by status)
    from sqlalchemy import func
    status_distribution = db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    status_labels = [s[0] for s in status_distribution]
    status_values = [s[1] for s in status_distribution]

    # 2. Monthly Revenue (Real query by month)
    revenue_by_month = db.query(
        func.strftime('%Y-%m', Lead.created_at), 
        func.sum(Lead.source_price)
    ).filter(Lead.status == "PAID").group_by(func.strftime('%Y-%m', Lead.created_at)).all()
    
    if revenue_by_month:
        month_labels = [r[0] for r in revenue_by_month]
        monthly_revenue = [r[1] for r in revenue_by_month]
    else:
        # Fallback to empty but consistent structure
        month_labels = ["No Data"]
        monthly_revenue = [0]

    # 3. Recent Transactions (Top 5 leads)
    recent_transactions = db.query(Lead).order_by(Lead.id.desc()).limit(5).all()
    
    return templates.TemplateResponse("admin/finance_vault.html", {
        "request": request,
        "total_revenue": total_revenue,
        "total_liabilities": total_liabilities,
        "net_profit": net_profit,
        "tasks": tasks,
        "status_labels": json.dumps(status_labels),
        "status_values": json.dumps(status_values),
        "monthly_revenue": json.dumps(monthly_revenue),
        "month_labels": json.dumps(month_labels),
        "recent_transactions": recent_transactions,
        "admin_prefix": _admin_prefix(),
    })

@router.post("/settle-payout")
async def settle_payout(task_id: int = Form(...), db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = "settled"
    db.commit()
    
    return RedirectResponse(url="/admin/finance-vault", status_code=303)

@router.post("/generate-flutterwave-link/{lead_id}")
async def generate_payment_link(lead_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    from payments import generate_flutterwave_link
    result = generate_flutterwave_link(lead.id, lead.source_price)
    
    return result

# Outreach Template Management
@router.get("/outreach-templates", response_class=HTMLResponse)
async def outreach_templates(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    all_templates = db.query(Template).all()
    return templates.TemplateResponse("admin/outreach_templates.html", {"request": request, "templates": all_templates, "admin_prefix": _admin_prefix()})


@router.get("/chats", response_class=HTMLResponse)
async def admin_chats(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    from models import Conversation
    conversations = db.query(Conversation).order_by(Conversation.id.desc()).limit(200).all()
    return templates.TemplateResponse(
        "admin/chats.html",
        {"request": request, "admin_prefix": _admin_prefix(), "conversations": conversations},
    )


@router.get("/chats/{conversation_id}", response_class=HTMLResponse)
async def admin_chat_detail(conversation_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    from models import Conversation, ChatMessage
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.id.asc())
        .limit(500)
        .all()
    )
    return templates.TemplateResponse(
        "admin/chat_detail.html",
        {"request": request, "admin_prefix": _admin_prefix(), "conversation": conv, "messages": messages},
    )

@router.post("/templates/add")
async def add_template(
    name: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_session),
):
    new_template = Template(name=name, subject=subject, body=body)
    db.add(new_template)
    db.commit()
    return RedirectResponse(url="/admin/outreach-templates", status_code=303)

@router.post("/templates/edit/{template_id}")
async def edit_template(
    template_id: int,
    name: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_session),
):
    target_template = db.query(Template).filter(Template.id == template_id).first()
    if not target_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    target_template.name = name
    target_template.subject = subject
    target_template.body = body
    db.commit()
    return RedirectResponse(url="/admin/outreach-templates", status_code=303)

@router.post("/templates/delete/{template_id}")
async def delete_template(template_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_session)):
    target_template = db.query(Template).filter(Template.id == template_id).first()
    if not target_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(target_template)
    db.commit()
    return RedirectResponse(url="/admin/outreach-templates", status_code=303)
