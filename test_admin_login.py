import requests

BASE_URL = "http://127.0.0.1:8000"
ADMIN_PREFIX = "/_controlpanel"

session = requests.Session()

# Step 1: Enter access key
resp = session.post(f"{BASE_URL}{ADMIN_PREFIX}/enter", data={"access_key": "bridge_access"}, allow_redirects=True)
print(f"Step 1 (Enter) Status: {resp.status_code}")
print(f"Step 1 URL: {resp.url}")

# Step 2: Login
resp = session.post(f"{BASE_URL}{ADMIN_PREFIX}/login", data={"email": "admin@thebridge.com", "password": "admin123"}, allow_redirects=True)
print(f"Step 2 (Login) Status: {resp.status_code}")
print(f"Step 2 URL: {resp.url}")

if "/_controlpanel/" in resp.url or resp.url.endswith("/_controlpanel"):
    print("Admin login successful!")
else:
    print("Admin login failed.")
