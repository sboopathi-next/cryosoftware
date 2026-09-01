import os
import re
import json
import httpx
from typing import Dict, Any, List, Optional
from fastapi.responses import JSONResponse

from engine.database import save_chat_message, get_chat_history, update_stat
from engine.english_daily import _get_api_key_from_db
from services.finance_service import finance_service

GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"

def sanitize_groq_model(m: Optional[str]) -> str:
    if not m or not isinstance(m, str):
        return GROQ_DEFAULT_MODEL
    m_clean = m.strip().lower()
    deprecated = ["llama3-70b-8192", "llama3-8b-8192", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
    if m_clean in deprecated or "llama" in m_clean or "mixtral" in m_clean:
        return GROQ_DEFAULT_MODEL
    return m.strip()

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
        """
        groq_key = self._get_groq_key(api_key)
        if not groq_key:
            return {"status": "error", "detail": "No Groq API Key found. Please set GROQ_API_KEY or configure in settings."}

        groq_model = sanitize_groq_model(model)
        fin_summary = finance_service.get_monthly_summary(month_str)

        # Build clean financial context for prompt
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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_key}"
        }

        request_body = {
            "model": groq_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", json=request_body, headers=headers)

        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", "Groq API Error")
            return {"status": "error", "detail": f"Groq API Error: {error_detail}"}

        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return {"status": "error", "detail": "Groq returned no candidates."}

        ai_text = choices[0].get("message", {}).get("content", "No response generated.")
        self._process_governance_tags(ai_text)
        save_chat_message("ai", ai_text, "finance")

        return {"status": "success", "reply": ai_text}

# Global Singleton Instance
ai_service = AIService()
