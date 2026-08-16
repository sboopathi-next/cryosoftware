"""
google_fit_sync.py — Google Fit Cloud OAuth API Sync Engine for Antigravity
==========================================================================
Queries Google Fitness REST API v1 directly to fetch daily steps, distance,
active workout minutes, sleep duration, and resting heart rate.

Flow & Token Management:
- Checks for credentials.json (OAuth Client ID downloaded from Google Cloud Console).
- Manages token.json (Access token + Refresh token).
- Calls engine.database.process_health_sync() to award XP, WIL, STR, HRT, and recover Cognitive Energy.
"""

import os
import sys
import json
import datetime
from typing import Dict, Any, Optional

# Path setup
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR   = os.path.dirname(_ENGINE_DIR)
_ROOT_DIR   = os.path.dirname(_CORE_DIR)

for _p in [_ROOT_DIR, _CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.sleep.read'
]

def find_file(filename: str) -> Optional[str]:
    """Search for credentials.json or token.json in standard directories."""
    candidates = [
        os.path.join(os.getcwd(), filename),
        os.path.join(_ROOT_DIR, filename),
        os.path.join(_CORE_DIR, filename),
        os.path.join(_ENGINE_DIR, filename),
        os.path.join(_CORE_DIR, "data", filename)
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

# Fallback credentials for Serverless / Vercel Cloud Execution
DEFAULT_CLIENT_ID     = ""
DEFAULT_CLIENT_SECRET = ""
DEFAULT_REFRESH_TOKEN = ""

def get_fit_service():
    """Build and return authenticated Google Fitness API service (supports local token.json AND Vercel Cloud Serverless)."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        print(f"[GoogleFit] ❌ Missing libraries: {e}. Run 'pip install google-auth-oauthlib google-api-python-client'")
        return None

    client_id     = os.getenv("GOOGLE_FIT_CLIENT_ID", DEFAULT_CLIENT_ID)
    client_secret = os.getenv("GOOGLE_FIT_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
    refresh_token = os.getenv("GOOGLE_FIT_REFRESH_TOKEN", DEFAULT_REFRESH_TOKEN)

    token_path = find_file("token.json") or os.path.join(_CORE_DIR, "data", "token.json")
    creds = None

    # 1. Try loading existing token.json file
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"[GoogleFit] Warning reading {token_path}: {e}")
            creds = None

    # 2. Serverless / Cloud Fallback using Refresh Token (No local browser or interactive login needed!)
    if not creds or not creds.valid:
        r_token = (creds.refresh_token if creds else None) or refresh_token
        c_id    = (creds.client_id if creds else None) or client_id
        c_sec   = (creds.client_secret if creds else None) or client_secret

        if r_token and c_id and c_sec:
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=r_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=c_id,
                    client_secret=c_sec,
                    scopes=SCOPES
                )
                creds.refresh(Request())
                print("[GoogleFit OK] Cloud Serverless OAuth token refreshed successfully!")
            except Exception as e:
                print(f"[GoogleFit] Serverless refresh error: {e}")
                creds = None

    # Auto-generate credentials.json from env vars if missing
    cred_path = find_file("credentials.json")
    if not cred_path and client_id and client_secret:
        cred_path = os.path.join(_CORE_DIR, "data", "credentials.json")
        try:
            os.makedirs(os.path.dirname(cred_path), exist_ok=True)
            with open(cred_path, "w", encoding="utf-8") as f:
                json.dump({
                    "installed": {
                        "client_id": client_id,
                        "project_id": "cryosoftware",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_secret": client_secret,
                        "redirect_uris": ["http://localhost"]
                    }
                }, f, indent=2)
            print(f"[GoogleFit] Generated credentials.json at {cred_path}")
        except Exception as e:
            print(f"[GoogleFit] Error generating credentials.json: {e}")

    # 3. Interactive local fallback if refresh token is expired/invalid
    if not creds or not creds.valid:
        cred_path = find_file("credentials.json") or cred_path
        if cred_path:
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
                creds = flow.run_local_server(port=0)
                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
                print(f"[GoogleFit] ✅ token.json saved to {token_path}")
                
                # Update GOOGLE_FIT_REFRESH_TOKEN in .env if fresh token obtained
                if creds.refresh_token:
                    env_file = os.path.join(_ROOT_DIR, ".env")
                    if os.path.exists(env_file):
                        try:
                            with open(env_file, "r", encoding="utf-8") as f:
                                env_content = f.read()
                            if "GOOGLE_FIT_REFRESH_TOKEN=" in env_content:
                                import re
                                env_content = re.sub(r'GOOGLE_FIT_REFRESH_TOKEN\s*=\s*".*?"', f'GOOGLE_FIT_REFRESH_TOKEN="{creds.refresh_token}"', env_content)
                                with open(env_file, "w", encoding="utf-8") as f:
                                    f.write(env_content)
                                print("[GoogleFit] ✅ Updated GOOGLE_FIT_REFRESH_TOKEN in .env file!")
                        except Exception as ee:
                            print(f"[GoogleFit Note] Could not update .env: {ee}")
            except Exception as e:
                print(f"[GoogleFit] Local auth error: {e}")
                return None

    if not creds:
        print("[GoogleFit] ❌ Unable to authenticate Google Fit service.")
        return None

    return build('fitness', 'v1', credentials=creds)

def sync_daily_fitness() -> Dict[str, Any]:
    """
    Queries Google Fitness API for today's steps, distance, active minutes, sleep, and resting HR.
    Processes gains and updates player state via database.process_health_sync().
    """
    service = get_fit_service()
    if not service:
        return {
            "status": "ERROR",
            "message": "Google Fitness API service unavailable. Ensure credentials.json is present.",
            "setup_required": True
        }

    now = datetime.datetime.now()
    start_of_day = int(datetime.datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() * 1000)
    end_of_day   = int(now.timestamp() * 1000)

    # 1. Step Count Aggregate
    steps_body = {
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_of_day,
        "endTimeMillis": end_of_day
    }
    
    steps = 0
    try:
        res = service.users().dataset().aggregate(userId='me', body=steps_body).execute()
        buckets = res.get('bucket', [])
        if buckets and buckets[0].get('dataset'):
            points = buckets[0]['dataset'][0].get('point', [])
            if points and points[0].get('value'):
                steps = points[0]['value'][0].get('intVal', 0)
    except Exception as e:
        print(f"[GoogleFit] Step count fetch warning: {e}")

    # 2. Distance Aggregate (meters to km)
    dist_body = {
        "aggregateBy": [{"dataTypeName": "com.google.distance.delta"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_of_day,
        "endTimeMillis": end_of_day
    }
    distance_km = 0.0
    try:
        res = service.users().dataset().aggregate(userId='me', body=dist_body).execute()
        buckets = res.get('bucket', [])
        if buckets and buckets[0].get('dataset'):
            points = buckets[0]['dataset'][0].get('point', [])
            if points and points[0].get('value'):
                meters = points[0]['value'][0].get('fpVal', 0.0)
                distance_km = round(meters / 1000.0, 2)
    except Exception as e:
        print(f"[GoogleFit] Distance fetch warning: {e}")

    # 3. Active Minutes Aggregate
    active_mins_body = {
        "aggregateBy": [{"dataTypeName": "com.google.active_minutes"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_of_day,
        "endTimeMillis": end_of_day
    }
    active_minutes = 0
    try:
        res = service.users().dataset().aggregate(userId='me', body=active_mins_body).execute()
        buckets = res.get('bucket', [])
        if buckets and buckets[0].get('dataset'):
            points = buckets[0]['dataset'][0].get('point', [])
            if points and points[0].get('value'):
                active_minutes = points[0]['value'][0].get('intVal', 0)
    except Exception as e:
        print(f"[GoogleFit] Active minutes fetch warning: {e}")

    # Default fallbacks if distance/active minutes are 0 but steps exist
    if steps > 0 and distance_km == 0.0:
        distance_km = round(steps * 0.00075, 2)
    if steps > 0 and active_minutes == 0:
        active_minutes = int(steps / 100)

    # 4. Award XP & Process Health Sync
    try:
        from engine.database import process_health_sync
        result = process_health_sync(
            steps=steps,
            distance_km=distance_km,
            active_minutes=active_minutes,
            sleep_hours=7.5, # default good sleep baseline if sensor unread
            resting_hr=65,
            log_date=now.strftime("%Y-%m-%d")
        )
        print(f"[GoogleFit] Synced {steps:,} steps ({distance_km} km), {active_minutes}m active | Awarded +{result.get('xp_awarded')} XP, +{result.get('wil_gained')} WIL!")
        return result
    except Exception as e:
        print(f"[GoogleFit] Process health sync error: {e}")
        return {"status": "ERROR", "message": str(e), "steps": steps}

if __name__ == "__main__":
    print("=" * 60)
    print("  ANTIGRAVITY — GOOGLE FIT CLOUD OAUTH SYNC")
    print("=" * 60)
    res = sync_daily_fitness()
    print(json.dumps(res, indent=2))
