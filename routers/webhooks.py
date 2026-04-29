from fastapi import APIRouter, Request, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Lead
import os
from payments import verify_webhook_signature

router = APIRouter(prefix="/webhooks")

# You should set this in your environment variables
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH", "the-bridge-secret-hash")

@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    verif_hash: str = Header(None, alias="verif-hash"),
    db: Session = Depends(get_db)
):
    # Verify the authenticity of the webhook
    if not verif_hash or not verify_webhook_signature(verif_hash, FLW_SECRET_HASH):
        # We return a 200 even for failed verification sometimes to stop retries if it's just a probe,
        # but for security, a 401 is more appropriate. 
        # However, Flutterwave expects a 200 for successful receipt.
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    
    # Process the event
    event = payload.get("event")
    data = payload.get("data", {})
    
    if event == "charge.completed":
        status = data.get("status")
        tx_ref = data.get("tx_ref")
        amount = data.get("amount")
        
        if status == "successful":
            # Extract lead_id from tx_ref (Format: BL-L{lead_id}-hex)
            try:
                # Split by dash and take the second part, then strip the 'L'
                lead_id_str = tx_ref.split("-")[1][1:]
                lead_id = int(lead_id_str)
                
                lead = db.query(Lead).filter(Lead.id == lead_id).first()
                if lead:
                    lead.status = "PAID"
                    db.commit()
                    print(f"Payment successful for Lead {lead_id}. Status updated to PAID.")
            except (IndexError, ValueError) as e:
                print(f"Error parsing tx_ref {tx_ref}: {e}")
                
    return {"status": "received"}
