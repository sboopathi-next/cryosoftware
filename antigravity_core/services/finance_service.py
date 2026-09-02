import json
import sqlite3
import datetime
import re
from typing import Dict, Any, List, Optional
import os

from config import IS_SERVERLESS, DATABASE_URL
from engine.database import get_db_connection, save_state, get_state, add_xp

DEFAULT_CATEGORIES = {
    "Needs": 15000.0,
    "Debt": 0.0,
    "Food": 7000.0,
    "Transport": 3000.0,
    "Health": 4000.0,
    "Lifestyle": 4000.0,
    "Education": 2000.0,
    "Savings": 15000.0
}

CATEGORY_ICONS = {
    "Needs": "🏠",
    "Debt": "💳",
    "Food": "🍛",
    "Transport": "🚗",
    "Health": "💪",
    "Lifestyle": "🎯",
    "Education": "📚",
    "Savings": "💰"
}

class FinanceService:
    """
    OOP Service for Antigravity Financial Governance.
    Handles:
    - Daily expense tracking & Gym-Pro style batch 'Log Set' logging
    - Monthly budget planning & Category matrix
    - AI Bulk Text parsing & People Debt Ledger tracking
    - Sinking funds & 50/30/20 Financial Law evaluation
    """

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                sub_type TEXT DEFAULT 'variable',
                description TEXT DEFAULT '',
                is_fixed INTEGER DEFAULT 0,
                person_tag TEXT DEFAULT '',
                expense_date TEXT NOT NULL,
                logged_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_monthly_budget (
                month_str TEXT PRIMARY KEY,
                income REAL DEFAULT 0.0,
                category_budgets_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_sinking_funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                target_amount REAL NOT NULL,
                current_amount REAL DEFAULT 0.0,
                monthly_contribution REAL DEFAULT 0.0,
                target_date TEXT DEFAULT ''
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_custom_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT '📦',
                default_limit REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_people_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT NOT NULL UNIQUE,
                total_sent REAL DEFAULT 0.0,
                total_received REAL DEFAULT 0.0,
                last_transaction_date TEXT NOT NULL
            )
            """)
            try:
                cursor.execute("ALTER TABLE finance_expenses ADD COLUMN person_tag TEXT DEFAULT ''")
            except Exception:
                pass # Column already exists
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FinanceService Init Warning] {e}")

    def add_custom_category(self, name: str, icon: str = "📦", default_limit: float = 0.0) -> Dict[str, Any]:
        """Creates a new custom expense category."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_add_custom_category
                return neon_add_custom_category(name, icon, default_limit)
            except Exception as e:
                print(f"[FinanceService] Neon add_custom_category failed ({e}), falling back to SQLite", flush=True)

        clean_name = name.strip().title()
        if not clean_name:
            raise ValueError("Category name cannot be empty.")
            
        now_ts = datetime.datetime.now().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO finance_custom_categories (name, icon, default_limit, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                icon = EXCLUDED.icon,
                default_limit = EXCLUDED.default_limit
        """, (clean_name, icon.strip() or "📦", default_limit, now_ts))
        conn.commit()
        conn.close()

        return {"status": "success", "message": f"Category '{clean_name}' created successfully!", "name": clean_name, "icon": icon}

    def delete_custom_category(self, name: str) -> Dict[str, Any]:
        """Deletes a custom category."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM finance_custom_categories WHERE name = ?", (name.strip().title(),))
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Category '{name}' deleted"}

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Fetches all categories (default + custom)."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_get_all_categories
                return neon_get_all_categories()
            except Exception as e:
                print(f"[FinanceService] Neon get_all_categories failed ({e}), falling back to SQLite", flush=True)

        categories = []
        for name, limit in DEFAULT_CATEGORIES.items():
            categories.append({
                "name": name,
                "icon": CATEGORY_ICONS.get(name, "📦"),
                "default_limit": limit,
                "is_custom": False
            })

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM finance_custom_categories ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            if r["name"] not in DEFAULT_CATEGORIES:
                categories.append({
                    "name": r["name"],
                    "icon": r["icon"] or "📦",
                    "default_limit": float(r["default_limit"] or 0.0),
                    "is_custom": True
                })

        return categories

    def log_expense(self, amount: float, category: str, description: str = "", is_fixed: bool = False, person_tag: str = "", expense_date: Optional[str] = None) -> Dict[str, Any]:
        """Logs a single daily expense and updates people ledger telemetry if tagged."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_log_expense
                return neon_log_expense(amount, category, description, is_fixed, person_tag, expense_date)
            except Exception as e:
                print(f"[FinanceService] Neon log_expense failed ({e}), falling back to SQLite", flush=True)

        if amount <= 0:
            raise ValueError("Expense amount must be greater than 0.")
            
        category_clean = category.strip().title() if category else "Needs"
        date_str = expense_date.strip() if expense_date else datetime.date.today().isoformat()
        now_dt = datetime.datetime.now()
        now_ts = now_dt.isoformat()
        ten_sec_ago = (now_dt - datetime.timedelta(seconds=10)).isoformat()
        sub_type = "fixed" if is_fixed else "variable"
        person_clean = person_tag.strip().title() if person_tag else ""

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Prevent duplicate submissions triggered within 10 seconds
        cursor.execute("""
            SELECT id FROM finance_expenses
            WHERE amount = ? AND category = ? AND description = ? AND person_tag = ? AND expense_date = ?
            AND logged_at >= ?
        """, (amount, category_clean, description, person_clean, date_str, ten_sec_ago))
        existing_dup = cursor.fetchone()
        if existing_dup:
            dup_id = existing_dup["id"]
            conn.close()
            return {
                "status": "duplicate_prevented",
                "message": f"Duplicate entry ignored for ₹{amount:,.2f}",
                "expense_id": dup_id,
                "amount": amount,
                "category": category_clean,
                "person_tag": person_clean,
                "expense_date": date_str
            }

        cursor.execute("""
            INSERT INTO finance_expenses (amount, category, sub_type, description, is_fixed, person_tag, expense_date, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (amount, category_clean, sub_type, description, 1 if is_fixed else 0, person_clean, date_str, now_ts))
        expense_id = cursor.lastrowid

        # Update people ledger if tagged
        if person_clean:
            cursor.execute("""
                INSERT INTO finance_people_ledger (person_name, total_sent, total_received, last_transaction_date)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(person_name) DO UPDATE SET
                    total_sent = total_sent + EXCLUDED.total_sent,
                    last_transaction_date = EXCLUDED.last_transaction_date
            """, (person_clean, amount, date_str))

        conn.commit()
        conn.close()

        add_xp(5)

        return {
            "status": "success",
            "message": f"Logged expense of ₹{amount:,.2f} under {category_clean}",
            "expense_id": expense_id,
            "amount": amount,
            "category": category_clean,
            "person_tag": person_clean,
            "expense_date": date_str
        }

    def delete_expense(self, expense_id: int) -> Dict[str, Any]:
        """Deletes an expense log entry by ID."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_delete_expense
                return neon_delete_expense(expense_id)
            except Exception as e:
                print(f"[FinanceService] Neon delete_expense failed ({e}), falling back to SQLite", flush=True)

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM finance_expenses WHERE id = ?", (expense_id,))
        exp = cursor.fetchone()
        if not exp:
            conn.close()
            raise ValueError(f"Expense entry #{expense_id} not found.")

        amt = float(exp["amount"] or 0.0)
        person_clean = exp["person_tag"] or ""

        cursor.execute("DELETE FROM finance_expenses WHERE id = ?", (expense_id,))

        if person_clean:
            cursor.execute("""
                UPDATE finance_people_ledger
                SET total_sent = MAX(0.0, total_sent - ?)
                WHERE person_name = ?
            """, (amt, person_clean))

        conn.commit()
        conn.close()

        return {"status": "success", "message": f"Expense entry #{expense_id} deleted successfully."}

    def log_batch_expenses(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Logs a Gym-Pro style batch 'Log Set' of transactions in one atomic operation.
        """
        if not entries:
            raise ValueError("No transaction rows provided.")

        logged_count = 0
        total_amount = 0.0
        date_str = datetime.date.today().isoformat()

        for item in entries:
            amt = float(item.get("amount", 0.0))
            if amt <= 0:
                continue
            cat = item.get("category", "Needs")
            desc = item.get("description", "")
            is_fixed = bool(item.get("is_fixed", False))
            person = item.get("person_tag", "")
            exp_date = item.get("expense_date") or date_str

            self.log_expense(
                amount=amt,
                category=cat,
                description=desc,
                is_fixed=is_fixed,
                person_tag=person,
                expense_date=exp_date
            )
            logged_count += 1
            total_amount += amt

        add_xp(logged_count * 5 + 10)

        return {
            "status": "success",
            "message": f"Logged {logged_count} entries totaling ₹{total_amount:,.2f}! +{logged_count * 5 + 10} XP",
            "logged_count": logged_count,
            "total_amount": total_amount
        }

    def parse_bulk_ai_text(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        Parses freeform text or bulleted list into structured transaction rows for the Log Set UI.
        """
        if not raw_text or not raw_text.strip():
            return []

        lines = raw_text.strip().splitlines()
        parsed_rows = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Extract amount
            amt_match = re.search(r'(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{1,2})?)', line_str, re.IGNORECASE)
            if not amt_match:
                continue

            amt = float(amt_match.group(1))

            # Extract Person Tag (e.g. "to Ramesh", "for Suresh", "to Mom")
            person_match = re.search(r'(?:to|for|given to|sent to)\s+([A-Z][a-z]+|\bMom\b|\bDad\b)', line_str, re.IGNORECASE)
            person_tag = person_match.group(1).title() if person_match else ""

            # Detect Category & Fixed/Variable
            d = line_str.upper()
            if any(w in d for w in ["SWIGGY", "ZOMATO", "FOOD", "DINNER", "LUNCH", "COFFEE", "TEA"]):
                cat, is_fixed = "Food", False
            elif any(w in d for w in ["EMI", "LOAN", "DEBT", "CREDIT CARD", "SENT", "GAVE", "MUTHOOT"]):
                cat, is_fixed = "Debt", True if "EMI" in d else False
            elif any(w in d for w in ["PETROL", "CAB", "UBER", "OLA", "RAPIDO", "BUS", "METRO", "FUEL"]):
                cat, is_fixed = "Transport", False
            elif any(w in d for w in ["RENT", "GROCERY", "ELECTRICITY", "BILL", "JIO", "AIRTEL"]):
                cat, is_fixed = "Needs", True
            elif any(w in d for w in ["DOCTOR", "MEDICINE", "GYM", "PHARMACY"]):
                cat, is_fixed = "Health", True if "GYM" in d else False
            elif any(w in d for w in ["SHOPPING", "MOVIE", "NETFLIX", "AMAZON"]):
                cat, is_fixed = "Lifestyle", False
            elif any(w in d for w in ["SIP", "INVEST", "FD", "SAVINGS"]):
                cat, is_fixed = "Savings", True
            else:
                cat, is_fixed = "Needs", False

            parsed_rows.append({
                "amount": amt,
                "category": cat,
                "description": line_str[:60],
                "is_fixed": is_fixed,
                "person_tag": person_tag,
                "expense_date": datetime.date.today().isoformat()
            })

        return parsed_rows

    def save_monthly_budget(self, month_str: str, income: float, category_budgets: Dict[str, float]) -> Dict[str, Any]:
        """Saves or updates planned income and category budget limits for a given month (YYYY-MM)."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_save_monthly_budget
                return neon_save_monthly_budget(month_str, income, category_budgets)
            except Exception as e:
                print(f"[FinanceService] Neon save_monthly_budget failed ({e}), falling back to SQLite", flush=True)

        now_ts = datetime.datetime.now().isoformat()
        budget_json = json.dumps(category_budgets)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO finance_monthly_budget (month_str, income, category_budgets_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(month_str) DO UPDATE SET
                income = EXCLUDED.income,
                category_budgets_json = EXCLUDED.category_budgets_json,
                updated_at = EXCLUDED.updated_at
        """, (month_str, income, budget_json, now_ts))
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": f"Monthly budget for {month_str} saved successfully!",
            "month_str": month_str,
            "income": income,
            "category_budgets": category_budgets
        }

    def update_sinking_fund(self, name: str, target_amount: float, current_amount: float, monthly_contribution: float, target_date: str = "") -> Dict[str, Any]:
        """Creates or updates a sinking fund."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO finance_sinking_funds (name, target_amount, current_amount, monthly_contribution, target_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                target_amount = EXCLUDED.target_amount,
                current_amount = EXCLUDED.current_amount,
                monthly_contribution = EXCLUDED.monthly_contribution,
                target_date = EXCLUDED.target_date
        """, (name, target_amount, current_amount, monthly_contribution, target_date))
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Sinking fund '{name}' updated successfully!"}

    def _calculate_financial_laws(self, income: float, total_expenses: float, needs_amt: float, debt_amt: float, wants_amt: float, savings_amt: float) -> Dict[str, Any]:
        """Calculates Financial Health Score (0-100) using 50/30/20 & Debt Ratio."""
        if income <= 0:
            return {
                "health_score": 50,
                "rating": "NEUTRAL",
                "rule_50_30_20": {"needs_pct": 0, "wants_pct": 0, "savings_pct": 0},
                "debt_service_ratio_pct": 0,
                "advice": "Set up your monthly income to get exact financial health analysis."
            }

        needs_and_debt_pct = round(((needs_amt + debt_amt) / income) * 100, 1)
        wants_pct = round((wants_amt / income) * 100, 1)
        savings_pct = round((savings_amt / income) * 100, 1)
        debt_ratio_pct = round((debt_amt / income) * 100, 1)

        needs_score = 30 if needs_and_debt_pct <= 50 else max(0, 30 - int((needs_and_debt_pct - 50) * 1.2))
        wants_score = 30 if wants_pct <= 30 else max(0, 30 - int((wants_pct - 30) * 1.5))
        savings_score = min(30, int((savings_pct / 20.0) * 30))
        debt_score = 10 if debt_ratio_pct <= 20 else max(0, 10 - int((debt_ratio_pct - 20) * 0.8))

        total_score = min(100, needs_score + wants_score + savings_score + debt_score)
        rating = "EXCELLENT" if total_score >= 85 else ("GOOD" if total_score >= 70 else ("NEEDS ATTENTION" if total_score >= 50 else "CRITICAL"))

        advice_points = []
        if debt_ratio_pct > 20:
            advice_points.append(f"⚠️ High Debt Ratio ({debt_ratio_pct}% of income goes to Debt/EMIs). Target < 20% using Debt Snowball method.")
        if wants_pct > 30:
            advice_points.append(f"🍛 Food & Lifestyle spending is {wants_pct}% (Ideal: ≤ 30%). Cap dining out next month.")
        if savings_pct < 20:
            advice_points.append(f"💰 Savings rate is {savings_pct}% (Ideal: ≥ 20%). Automate savings on the 1st of every month.")
        if not advice_points:
            advice_points.append("✅ Outstanding financial discipline! Maintain your 50/30/20 balance.")

        return {
            "health_score": total_score,
            "rating": rating,
            "rule_50_30_20": {
                "needs_debt_pct": needs_and_debt_pct,
                "wants_pct": wants_pct,
                "savings_pct": savings_pct
            },
            "debt_service_ratio_pct": debt_ratio_pct,
            "advice": " ".join(advice_points)
        }

    def get_monthly_summary(self, month_str: Optional[str] = None) -> Dict[str, Any]:
        """Calculates complete financial summary for a month including people ledger telemetry."""
        if IS_SERVERLESS and DATABASE_URL:
            try:
                from engine.neon_db import neon_get_finance_summary
                return neon_get_finance_summary(month_str)
            except Exception as e:
                print(f"[FinanceService] Neon get_monthly_summary failed ({e}), falling back to SQLite", flush=True)

        if not month_str:
            month_str = datetime.date.today().strftime("%Y-%m")

        all_cats = self.get_all_categories()
        all_cat_names = [c["name"] for c in all_cats]
        cat_icon_map = {c["name"]: c["icon"] for c in all_cats}

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM finance_monthly_budget WHERE month_str = ?", (month_str,))
        b_row = cursor.fetchone()
        if not b_row:
            cursor.execute("SELECT * FROM finance_monthly_budget ORDER BY updated_at DESC LIMIT 1")
            b_row = cursor.fetchone()
        
        category_budgets = {c["name"]: c["default_limit"] for c in all_cats}
        if b_row:
            income = float(b_row["income"] or 68000.0)
            saved_budgets = json.loads(b_row["category_budgets_json"])
            category_budgets.update(saved_budgets)
        else:
            income = 68000.0

        cursor.execute("""
            SELECT * FROM finance_expenses 
            WHERE expense_date LIKE ? 
            ORDER BY expense_date DESC, id DESC
        """, (f"{month_str}%",))
        expenses = [dict(r) for r in cursor.fetchall()]

        if not expenses:
            cursor.execute("SELECT * FROM finance_expenses ORDER BY expense_date DESC, id DESC LIMIT 100")
            expenses = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM finance_sinking_funds ORDER BY id ASC")
        sinking_funds = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM finance_people_ledger ORDER BY total_sent DESC")
        people_ledger = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not people_ledger and expenses:
            p_map = {}
            p_dates = {}
            for e in expenses:
                ptag = e.get("person_tag")
                if ptag:
                    p_map[ptag] = p_map.get(ptag, 0.0) + float(e.get("amount", 0.0))
                    p_dates[ptag] = e.get("expense_date") or datetime.date.today().isoformat()
            people_ledger = [
                {"person_name": name, "total_sent": amt, "last_transaction_date": p_dates.get(name, "")}
                for name, amt in p_map.items()
            ]

        if not sinking_funds:
            sinking_funds = [
                {"name": "New Phone Fund", "target_amount": 30000.0, "current_amount": 7500.0, "monthly_contribution": 2500.0, "target_date": "2026-12-31"},
                {"name": "Vehicle Insurance", "target_amount": 12000.0, "current_amount": 4000.0, "monthly_contribution": 1000.0, "target_date": "2026-11-30"},
                {"name": "Emergency Fund (3 Months)", "target_amount": 100000.0, "current_amount": 45000.0, "monthly_contribution": 5000.0, "target_date": "2027-03-31"}
            ]

        category_actuals = {cat: 0.0 for cat in all_cat_names}
        fixed_total = 0.0
        variable_total = 0.0

        for exp in expenses:
            amt = float(exp.get("amount", 0.0))
            cat = exp.get("category", "Needs").title()
            if cat not in category_actuals:
                category_actuals[cat] = 0.0
            category_actuals[cat] += amt

            if exp.get("is_fixed") or exp.get("sub_type") == "fixed":
                fixed_total += amt
            else:
                variable_total += amt

        total_expenses = fixed_total + variable_total
        planned_savings = float(category_budgets.get("Savings", 15000.0))
        actual_savings = max(0.0, income - total_expenses)
        savings_rate_pct = round((actual_savings / income * 100.0), 1) if income > 0 else 0.0

        needs_amt = category_actuals.get("Needs", 0.0) + category_actuals.get("Transport", 0.0) + category_actuals.get("Health", 0.0)
        debt_amt = category_actuals.get("Debt", 0.0)
        wants_amt = category_actuals.get("Food", 0.0) + category_actuals.get("Lifestyle", 0.0)
        savings_amt = actual_savings

        fin_laws = self._calculate_financial_laws(income, total_expenses, needs_amt, debt_amt, wants_amt, savings_amt)

        matrix = []
        for cat in all_cat_names:
            budget_amt = category_budgets.get(cat, 0.0)
            actual_amt = category_actuals.get(cat, 0.0)
            diff = budget_amt - actual_amt
            pct = round((actual_amt / budget_amt * 100.0), 1) if budget_amt > 0 else 0.0
            status = "EXCEEDED" if (budget_amt > 0 and actual_amt > budget_amt) else ("WARNING" if pct >= 85.0 else "HEALTHY")
            matrix.append({
                "category": cat,
                "icon": cat_icon_map.get(cat, "📦"),
                "budget": budget_amt,
                "actual": actual_amt,
                "difference": diff,
                "usage_pct": pct,
                "status": status
            })

        return {
            "month_str": month_str,
            "income": income,
            "total_expenses": total_expenses,
            "fixed_total": fixed_total,
            "variable_total": variable_total,
            "planned_savings": planned_savings,
            "actual_savings": actual_savings,
            "savings_rate_pct": savings_rate_pct,
            "remaining_budget": max(0.0, income - total_expenses),
            "debt_total": debt_amt,
            "category_matrix": matrix,
            "all_categories": all_cats,
            "financial_health": fin_laws,
            "recent_expenses": expenses[:50],
            "sinking_funds": sinking_funds,
            "people_ledger": people_ledger
        }

# Global Singleton Instance
finance_service = FinanceService()
