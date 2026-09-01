import os
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, JSONResponse

from services.finance_service import finance_service
from services.ai_service import ai_service
from engine.auth import verify_token

router = APIRouter(tags=["Financial Governance"])

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

class ExpensePayload(BaseModel):
    amount: float
    category: str
    description: Optional[str] = ""
    is_fixed: Optional[bool] = False
    person_tag: Optional[str] = ""
    expense_date: Optional[str] = None

class ExpenseBatchPayload(BaseModel):
    entries: List[ExpensePayload]

class BulkParsePayload(BaseModel):
    text: str

class CategoryPayload(BaseModel):
    name: str
    icon: Optional[str] = "📦"
    default_limit: Optional[float] = 0.0

class BudgetPayload(BaseModel):
    month_str: str
    income: float
    category_budgets: Dict[str, float]

class SinkingFundPayload(BaseModel):
    name: str
    target_amount: float
    current_amount: float
    monthly_contribution: float
    target_date: Optional[str] = ""

class FinanceAIChatPayload(BaseModel):
    message: str
    api_key: Optional[str] = ""
    groq_model: Optional[str] = "openai/gpt-oss-120b"
    month_str: Optional[str] = None

@router.get("/finance")
def get_finance_page():
    return FileResponse(os.path.join(STATIC_DIR, "finance.html"))

@router.get("/api/finance/summary")
def get_finance_summary(month: Optional[str] = Query(None), authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.get_monthly_summary(month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/finance/categories")
def get_categories(authenticated: bool = Depends(verify_token)):
    try:
        return {"categories": finance_service.get_all_categories()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/category")
def add_custom_category(payload: CategoryPayload, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.add_custom_category(
            name=payload.name,
            icon=payload.icon or "📦",
            default_limit=payload.default_limit or 0.0
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/finance/category/{name}")
def delete_custom_category(name: str, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.delete_custom_category(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/expense")
def add_expense(payload: ExpensePayload, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.log_expense(
            amount=payload.amount,
            category=payload.category,
            description=payload.description or "",
            is_fixed=bool(payload.is_fixed),
            person_tag=payload.person_tag or "",
            expense_date=payload.expense_date
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/expense_batch")
def add_expense_batch(payload: ExpenseBatchPayload, authenticated: bool = Depends(verify_token)):
    try:
        entries_dicts = [e.dict() for e in payload.entries]
        return finance_service.log_batch_expenses(entries_dicts)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/bulk_parse")
def parse_bulk_text(payload: BulkParsePayload, authenticated: bool = Depends(verify_token)):
    try:
        rows = finance_service.parse_bulk_ai_text(payload.text)
        return {"status": "success", "parsed_rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/finance/expense/{expense_id}")
def delete_expense(expense_id: int, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.delete_expense(expense_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/budget")
def save_budget(payload: BudgetPayload, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.save_monthly_budget(
            month_str=payload.month_str,
            income=payload.income,
            category_budgets=payload.category_budgets
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/finance/sinking_fund")
def save_sinking_fund(payload: SinkingFundPayload, authenticated: bool = Depends(verify_token)):
    try:
        return finance_service.update_sinking_fund(
            name=payload.name,
            target_amount=payload.target_amount,
            current_amount=payload.current_amount,
            monthly_contribution=payload.monthly_contribution,
            target_date=payload.target_date or ""
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/ai/finance_advisor")
async def chat_finance_advisor(payload: FinanceAIChatPayload, authenticated: bool = Depends(verify_token)):
    try:
        res = await ai_service.chat_finance_advisor(
            user_message=payload.message,
            api_key=payload.api_key,
            model=payload.groq_model,
            month_str=payload.month_str
        )
        if res.get("status") == "error":
            return JSONResponse(status_code=400, content={"detail": res.get("detail")})
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Financial AI Exception: {str(e)}"})
