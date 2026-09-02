import os
import re
import json
import httpx
from typing import Dict, Any, List, Optional
from fastapi.responses import JSONResponse

from engine.database import save_chat_message, get_chat_history, update_stat
from engine.english_daily import _get_api_key_from_db
from services.finance_service import finance_service

ACTIVE_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "deepseek-r1-distill-llama-70b",
    "qwen-2.5-coder-32b",
    "llama-3.1-8b-instant",
    "gemma2-9b-it"
]

DECOMMISSIONED_GROQ_MODELS = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "mixtral-8x7b-32768": "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b": "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b": "llama-3.1-8b-instant",
    "qwen/qwen3.8-27b": "qwen-2.5-coder-32b",
    "groq/compound": "llama-3.3-70b-versatile",
    "groq/compound-mini": "llama-3.1-8b-instant"
}

def sanitize_groq_model(m: Optional[str]) -> str:
    if not m or not isinstance(m, str):
        return "llama-3.3-70b-versatile"
    m_clean = m.strip()
    return DECOMMISSIONED_GROQ_MODELS.get(m_clean, m_clean if m_clean in ACTIVE_GROQ_MODELS else "llama-3.3-70b-versatile")

async def execute_groq_chat_with_fallback(groq_key: str, requested_model: str, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> dict:
    primary = sanitize_groq_model(requested_model)
    candidates = [primary] + [m for m in ACTIVE_GROQ_MODELS if m != primary]
    
    last_error = ""
    async with httpx.AsyncClient(timeout=25.0) as client:
        for m in candidates:
            try:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": m,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return {"status": "success", "model_used": m, "content": content}
                
                err_msg = res.json().get("error", {}).get("message", res.text[:120])
                print(f"[Groq Engine Warning] Model {m} failed HTTP {res.status_code}: {err_msg}. Retrying next active model...", flush=True)
                last_error = f"Model {m} ({res.status_code}): {err_msg}"
            except Exception as ex:
                print(f"[Groq Engine Error] Exception with model {m}: {ex}. Retrying next active model...", flush=True)
                last_error = str(ex)

    return {"status": "error", "detail": f"All Groq models failed. Last error: {last_error}"}

class AIService:
    """
    OOP Service for Antigravity AI Engines.
    Manages Groq API calls, prompt building, and governance stat rewards.
    """

    @staticmethod
    def _get_groq_key(provided_key: Optional[str] = None) -> str:
        key = provided_key.strip() if provided_key else os.environ.get("GROQ_API_KEY", "")
        if not key:
            key = _get_api_key_from_db()
        return key or ""

    @staticmethod
    def _process_governance_tags(text: str):
        gov_pattern = re.compile(r'\[GOVERNANCE:\s*(\w+):\s*([+-]?\d+):\s*(.+?)\]')
        for match in gov_pattern.finditer(text):
            stat_name, amount, reason = match.group(1), int(match.group(2)), match.group(3)
            valid_stats = {"XP", "STR", "INT", "AGI", "WIL", "ENERGY", "HRT", "HEART", "STC", "STOIC"}
            if stat_name.upper() in valid_stats:
                update_stat(stat_name.upper(), amount)

    async def chat_finance_advisor(self, user_message: str, api_key: Optional[str] = None, model: Optional[str] = None, month_str: Optional[str] = None) -> Dict[str, Any]:
        """
        AI Financial Advisor Chat Engine.
        Injects real monthly budget vs actual telemetry into Groq system prompt.
        Uses Multi-Model Fallback Execution Engine.
        """
        groq_key = self._get_groq_key(api_key)
        if not groq_key:
            return {"status": "error", "detail": "No Groq API Key found. Please set GROQ_API_KEY or configure in settings."}

        fin_summary = finance_service.get_monthly_summary(month_str)

        cat_lines = []
        for m in fin_summary.get("category_matrix", []):
            cat_lines.append(f"  - {m['category']}: Budgeted ₹{m['budget']:,.0f} | Actual ₹{m['actual']:,.0f} | Diff: ₹{m['difference']:,.0f} ({m['status']})")

        fin_prompt = f"""You are ANTIGRAVITY AI FINANCIAL ADVISOR & GOVERNANCE COACH for Boopathi.
You provide data-driven, practical, disciplined financial advice based on his spending telemetry.

MONTHLY SUMMARY ({fin_summary['month_str']}):
- Income: ₹{fin_summary['income']:,.2f}
- Total Expenses: ₹{fin_summary['total_expenses']:,.2f} (Fixed: ₹{fin_summary['fixed_total']:,.2f}, Variable: ₹{fin_summary['variable_total']:,.2f})
- Actual Savings: ₹{fin_summary['actual_savings']:,.2f} (Savings Rate: {fin_summary['savings_rate_pct']}%)
- Remaining Budget: ₹{fin_summary['remaining_budget']:,.2f}

CATEGORY BREAKDOWN:
{chr(10).join(cat_lines)}

INSTRUCTIONS:
1. Be direct, clear, and actionable. Avoid generic fluff.
2. If any category status is EXCEEDED or WARNING, highlight the exact amount overspent and suggest behavioral fixes.
3. Keep response concise (under 300 words).
4. You may award governance XP for financial discipline: [GOVERNANCE: XP: +25: Logged expenses and reviewed monthly budget]"""

        save_chat_message("user", user_message, "finance")

        raw_history = get_chat_history(limit=6, bot_type="finance")
        messages = [{"role": "system", "content": fin_prompt}]
        for msg in raw_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})
        messages.append({"role": "user", "content": user_message})

        result = await execute_groq_chat_with_fallback(groq_key, model or "llama-3.3-70b-versatile", messages, temperature=0.7, max_tokens=1024)

        if result.get("status") == "error":
            return result

        ai_text = result.get("content", "No response generated.")
        self._process_governance_tags(ai_text)
        save_chat_message("ai", ai_text, "finance")

        return {"status": "success", "reply": ai_text, "model_used": result.get("model_used")}

# Global Singleton Instance
ai_service = AIService()
