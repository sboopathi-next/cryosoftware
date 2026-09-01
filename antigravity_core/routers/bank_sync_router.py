from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import JSONResponse

from services.bank_sync_service import bank_sync_service
from engine.database import get_db_connection
from engine.auth import verify_token

router = APIRouter(tags=["Bank Sync & Account Aggregator"])

class AAConsentPayload(BaseModel):
    bank_name: Optional[str] = "HDFC Bank"
    provider: Optional[str] = "OneMoney"

@router.post("/api/finance/bank_import")
async def import_bank_statement(
    file: UploadFile = File(...),
    bank_name: str = Form("HDFC Bank"),
    authenticated: bool = Depends(verify_token)
):
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        
        res = bank_sync_service.parse_and_import_statement(
            file_content=content,
            filename=file.filename or "bank_statement.csv",
            bank_name=bank_name
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bank statement import error: {str(e)}")

@router.post("/api/finance/aa_sandbox/connect")
def connect_aa_sandbox(payload: AAConsentPayload, authenticated: bool = Depends(verify_token)):
    try:
        return bank_sync_service.simulate_aa_consent(
            bank_name=payload.bank_name or "HDFC Bank",
            provider=payload.provider or "OneMoney"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/finance/bank_sync/status")
def get_bank_sync_status(authenticated: bool = Depends(verify_token)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT filename, bank_name, records_imported, imported_at FROM finance_bank_imports ORDER BY id DESC LIMIT 10")
        imports = [dict(zip(["filename", "bank_name", "records_imported", "imported_at"], r)) for r in cursor.fetchall()]

        cursor.execute("SELECT provider, consent_id, status, bank_name, created_at FROM finance_aa_sessions ORDER BY id DESC LIMIT 5")
        sessions = [dict(zip(["provider", "consent_id", "status", "bank_name", "created_at"], r)) for r in cursor.fetchall()]
        conn.close()

        return {
            "status": "success",
            "security_policy": "Zero Credential Storage • Local AES Encryption • SHA-256 Hash Deduplication",
            "recent_imports": imports,
            "aa_sessions": sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
