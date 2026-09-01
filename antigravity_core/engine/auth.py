import os
from typing import Optional
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer_scheme = HTTPBearer(auto_error=False)

def verify_token(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
):
    """
    FastAPI dependency injected on protected routes.
    Rules:
      - If APP_SECRET is empty or AUTH_DISABLED=true -> pass (offline / local dev mode).
      - Otherwise validate the Bearer token against APP_SECRET.
      - If invalid -> 401 Unauthorized (triggers shared.js redirect to /login).
    """
    _APP_SECRET = os.getenv("APP_SECRET", "")
    _AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")

    if _AUTH_DISABLED or not _APP_SECRET:
        return True  # Local/offline mode — no password set

    if creds and creds.credentials == _APP_SECRET:
        return True

    raise HTTPException(status_code=401, detail="Unauthorized. Please authenticate at /login.")
