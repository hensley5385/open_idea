from database import SessionLocal, engine, Base, migrate_sqlite_schema
from models import User, Lead, Message, Task, ScrapedFreelancer
from auth_utils import hash_password

def seed():
    migrate_sqlite_schema()
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if admin already exists
    admin = db.query(User).filter(User.email == "admin@thebridge.com").first()
    if not admin:
        new_admin = User(
            name="Super Admin",
            email="admin@thebridge.com",
            role="admin",
            password_hash=hash_password("admin123")
        )
        db.add(new_admin)
        print("Admin user created: admin@thebridge.com / admin123")
    
    # Check if a freelancer exists
    freelancer = db.query(User).filter(User.email == "freelancer@thebridge.com").first()
    if not freelancer:
        new_f = User(
            name="Expert Developer",
            email="freelancer@thebridge.com",
            role="freelancer",
            primary_skill="Web Developer",
            password_hash=hash_password("free123"),
            bank_details="Chase Bank, 12345678"
        )
        db.add(new_f)
        print("Freelancer user created: freelancer@thebridge.com / free123")
        
        # Add some sample data for this freelancer
        db.commit() # Commit to get IDs
        
        lead = Lead(
            title="Next.js Portfolio",
            link="https://example.com/job1",
            description="Build a premium portfolio using Next.js and Tailwind.",
            source_price=500.0,
            client_contact="client1@example.com",
            status="assigned"
        )
        db.add(lead)
        db.commit()
        
        task = Task(
            lead_id=lead.id,
            assigned_freelancer_id=new_f.id,
            payout_price=400.0,
            status="assigned"
        )
        db.add(task)
        
        msg = Message(
            sender_email="client1@example.com",
            subject="Question about timeline",
            content="When can we expect the first draft?",
            is_read=0
        )
        db.add(msg)
        print("Sample lead, task, and message created.")

    # Check if a client exists (for client auth/chat demos)
    client = db.query(User).filter(User.email == "client@thebridge.com").first()
    if not client:
        new_client = User(
            name="Client User",
            email="client@thebridge.com",
            role="client",
            password_hash=hash_password("client123"),
        )
        db.add(new_client)
        print("Client user created: client@thebridge.com / client123")
    
    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
