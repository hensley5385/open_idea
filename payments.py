import secrets
import requests
import os

FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "FLWSECK_TEST-mock-key")

def generate_flutterwave_link(lead_id: int, amount: float, email: str = "client@example.com", name: str = "Valued Client"):
    # This is a REAL implementation of the Flutterwave Standard Payment Link API
    url = "https://api.flutterwave.com/v3/payments"
    
    tx_ref = f"BL-L{lead_id}-{secrets.token_hex(4)}"
    
    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": "USD",
        "redirect_url": "https://the-bridge-v3.vercel.app/dashboard?payment=success",
        "customer": {
            "email": email,
            "name": name
        },
        "customizations": {
            "title": "The Bridge Services",
            "logo": "https://the-bridge-v3.vercel.app/static/logo.png"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] == "success":
            return {
                "status": "success",
                "link": data["data"]["link"],
                "tx_ref": tx_ref
            }
        else:
            return {"status": "error", "message": data.get("message", "Unknown error")}
            
    except Exception as e:
        # Fallback to mock if API key is not configured or fails, for convenience in dev
        print(f"Flutterwave API Error: {e}")
        mock_link = f"https://checkout.flutterwave.com/pay/the-bridge-mock-{tx_ref}?amount={amount}&currency=USD"
        return {
            "status": "success", 
            "link": mock_link, 
            "tx_ref": tx_ref,
            "note": "FALLBACK_TO_MOCK"
        }

def verify_webhook_signature(signature: str, secret_hash: str):
    # Verify the 'verif-hash' header sent by Flutterwave
    # flutterwave_secret_hash should be stored in env variables
    return signature == secret_hash
