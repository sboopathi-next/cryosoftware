import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional
import os

from engine.database import get_db_connection, save_state, get_state, add_xp

DEFAULT_CATEGORIES = {
    "Needs": 15000.0,
    "Food": 7000.0,
    "Transport": 3000.0,
    "Health": 4000.0,
    "Lifestyle": 4000.0,
    "Education": 2000.0,
    "Savings": 15000.0
}

class FinanceService:
    """
    OOP Service for Antigravity Financial Governance.
    Handles daily expense tracking, monthly budget planning, sinking funds,
    and variance analysis.
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FinanceService Init Warning] {e}")

    def log_expense(self, amount: float, category: str, description: str = "", is_fixed: bool = False, expense_date: Optional[str] = None) -> Dict[str, Any]:
        """Logs a daily expense and updates user financial telemetry."""
        if amount <= 0:
            raise ValueError("Expense amount must be greater than 0.")
            
        category_clean = category.strip().capitalize() if category else "Needs"
        date_str = expense_date.strip() if expense_date else datetime.date.today().isoformat()
        now_ts = datetime.datetime.now().isoformat()
        sub_type = "fixed" if is_fixed else "variable"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO finance_expenses (amount, category, sub_type, description, is_fixed, expense_date, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (amount, category_clean, sub_type, description, 1 if is_fixed else 0, date_str, now_ts))
        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Award +5 XP for financial discipline tracking
        add_xp(5)

        return {
            "status": "success",
            "message": f"Logged expense of ₹{amount:,.2f} under {category_clean}",
            "expense_id": expense_id,
            "amount": amount,
            "category": category_clean,
            "expense_date": date_str
        }

    def delete_expense(self, expense_id: int) -> Dict[str, Any]:
        """Deletes an expense log entry by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM finance_expenses WHERE id = ?", (expense_id,))
        rows = cursor.rowcount
        conn.commit()
        conn.close()
        if rows == 0:
            raise ValueError(f"Expense with ID {expense_id} not found.")
        return {"status": "success", "message": f"Deleted expense ID {expense_id}"}

    def save_monthly_budget(self, month_str: str, income: float, category_budgets: Dict[str, float]) -> Dict[str, Any]:
        """Saves or updates planned income and category budget limits for a given month (YYYY-MM)."""
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
        """Creates or updates a sinking fund (e.g. Phone, Insurance, Bike service)."""
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

    def get_monthly_summary(self, month_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates complete financial summary for a month:
        - Planned Income vs. Actual Expenses
        - Budget vs. Actuals per category
        - Fixed vs. Variable breakdown
        - Savings Rate %
        - Overspend warnings & category health
        """
        if not month_str:
            month_str = datetime.date.today().strftime("%Y-%m")

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Load monthly budget
        cursor.execute("SELECT * FROM finance_monthly_budget WHERE month_str = ?", (month_str,))
        b_row = cursor.fetchone()
        if b_row:
            income = float(b_row["income"] or 50000.0)
            category_budgets = json.loads(b_row["category_budgets_json"])
        else:
            income = 50000.0
            category_budgets = DEFAULT_CATEGORIES.copy()

        # Load expenses for month_str (starts with YYYY-MM)
        cursor.execute("""
            SELECT * FROM finance_expenses 
            WHERE expense_date LIKE ? 
            ORDER BY expense_date DESC, id DESC
        """, (f"{month_str}%",))
        expenses = [dict(r) for r in cursor.fetchall()]

        # Load sinking funds
        cursor.execute("SELECT * FROM finance_sinking_funds ORDER BY id ASC")
        sinking_funds = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Default sinking funds if none exist
        if not sinking_funds:
            sinking_funds = [
                {"name": "New Phone Fund", "target_amount": 30000.0, "current_amount": 7500.0, "monthly_contribution": 2500.0, "target_date": "2026-12-31"},
                {"name": "Vehicle Insurance", "target_amount": 12000.0, "current_amount": 4000.0, "monthly_contribution": 1000.0, "target_date": "2026-11-30"},
                {"name": "Bike Maintenance", "target_amount": 6000.0, "current_amount": 2000.0, "monthly_contribution": 500.0, "target_date": "2026-10-31"}
            ]

        # Calculate actuals per category and fixed/variable totals
        category_actuals = {cat: 0.0 for cat in DEFAULT_CATEGORIES.keys()}
        fixed_total = 0.0
        variable_total = 0.0

        for exp in expenses:
            amt = float(exp.get("amount", 0.0))
            cat = exp.get("category", "Needs").capitalize()
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

        # Build category variance & health matrix
        matrix = []
        for cat, budget_amt in category_budgets.items():
            actual_amt = category_actuals.get(cat, 0.0)
            diff = budget_amt - actual_amt
            pct = round((actual_amt / budget_amt * 100.0), 1) if budget_amt > 0 else 0.0
            status = "EXCEEDED" if actual_amt > budget_amt else ("WARNING" if pct >= 85.0 else "HEALTHY")
            matrix.append({
                "category": cat,
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
            "category_matrix": matrix,
            "recent_expenses": expenses[:50],
            "sinking_funds": sinking_funds
        }

# Global Singleton Instance
finance_service = FinanceService()
