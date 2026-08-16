"""
reauth_google_fit.py — One-click / CLI Google Fit OAuth Re-Authenticator
========================================================================
Generates a fresh GOOGLE_FIT_REFRESH_TOKEN when Google invalidates older tokens.
"""

import os
import sys
import json
import re

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR   = os.path.dirname(_ENGINE_DIR)
_ROOT_DIR   = os.path.dirname(_CORE_DIR)

for _p in [_ROOT_DIR, _CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT_DIR, ".env"))
except Exception:
    pass

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.sleep.read'
]

def perform_reauth():
    client_id = os.getenv("GOOGLE_FIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_FIT_CLIENT_SECRET", "").strip()
    
    cred_dict = {
        "installed": {
            "client_id": client_id,
            "project_id": "cryosoftware",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"]
        }
    }
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_config(cred_dict, SCOPES)
        
        print("\n" + "="*70)
        print("🌐 OPENING BROWSER FOR GOOGLE HEALTH FIT OAUTH AUTHORIZATION...")
        print("="*70 + "\n")
        
        creds = flow.run_local_server(port=0)
        
        # Save to token.json
        token_path = os.path.join(_CORE_DIR, "data", "token.json")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"✅ Saved token.json to {token_path}")
        
        # Update .env file with new refresh token
        if creds.refresh_token:
            env_path = os.path.join(_ROOT_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    env_content = f.read()
                if "GOOGLE_FIT_REFRESH_TOKEN" in env_content:
                    env_content = re.sub(
                        r'GOOGLE_FIT_REFRESH_TOKEN\s*=\s*".*?"',
                        f'GOOGLE_FIT_REFRESH_TOKEN="{creds.refresh_token}"',
                        env_content
                    )
                    with open(env_path, "w", encoding="utf-8") as f:
                        f.write(env_content)
                    print(f"🚀 SUCCESS! Updated GOOGLE_FIT_REFRESH_TOKEN in .env: {creds.refresh_token[:15]}...")
                    
        return True
    except Exception as e:
        print(f"❌ Re-authentication error: {e}")
        return False

if __name__ == "__main__":
    perform_reauth()
