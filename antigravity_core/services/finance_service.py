import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional
import os

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
    Handles daily expense tracking, monthly budget planning, sinking funds,
    custom category management, and Financial Laws scoring (50/30/20 rule & Debt Ratio).
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
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_custom_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT '📦',
                default_limit REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FinanceService Init Warning] {e}")

    def add_custom_category(self, name: str, icon: str = "📦", default_limit: float = 0.0) -> Dict[str, Any]:
        """Creates a new custom expense category."""
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

    def log_expense(self, amount: float, category: str, description: str = "", is_fixed: bool = False, expense_date: Optional[str] = None) -> Dict[str, Any]:
        """Logs a daily expense and updates user financial telemetry."""
        if amount <= 0:
            raise ValueError("Expense amount must be greater than 0.")
            
        category_clean = category.strip().title() if category else "Needs"
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

    def _calculate_financial_laws(self, income: float, total_expenses: float, needs_amt: float, debt_amt: float, wants_amt: float, savings_amt: float) -> Dict[str, Any]:
        """
        Calculates Financial Health Score (0-100) using established financial principles:
        1. 50/30/20 Rule: 50% Needs & Debt, 30% Wants, 20% Savings.
        2. Debt Service Ratio: Debt / Income <= 20%.
        3. Savings Rate: Actual Savings / Income >= 20%.
        """
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

        # Score components (Total 100)
        # Needs & Debt score (Max 30): Target <= 50%
        needs_score = 30 if needs_and_debt_pct <= 50 else max(0, 30 - int((needs_and_debt_pct - 50) * 1.2))
        
        # Wants score (Max 30): Target <= 30%
        wants_score = 30 if wants_pct <= 30 else max(0, 30 - int((wants_pct - 30) * 1.5))
        
        # Savings score (Max 30): Target >= 20%
        savings_score = min(30, int((savings_pct / 20.0) * 30))
        
        # Debt ratio score (Max 10): Target <= 20%
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
        """
        Calculates complete financial summary for a month including custom categories
        and Financial Laws scoring.
        """
        if not month_str:
            month_str = datetime.date.today().strftime("%Y-%m")

        all_cats = self.get_all_categories()
        all_cat_names = [c["name"] for c in all_cats]
        cat_icon_map = {c["name"]: c["icon"] for c in all_cats}

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Load monthly budget
        cursor.execute("SELECT * FROM finance_monthly_budget WHERE month_str = ?", (month_str,))
        b_row = cursor.fetchone()
        
        category_budgets = {c["name"]: c["default_limit"] for c in all_cats}
        if b_row:
            income = float(b_row["income"] or 50000.0)
            saved_budgets = json.loads(b_row["category_budgets_json"])
            category_budgets.update(saved_budgets)
        else:
            income = 50000.0

        # Load expenses for month_str
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

        if not sinking_funds:
            sinking_funds = [
                {"name": "New Phone Fund", "target_amount": 30000.0, "current_amount": 7500.0, "monthly_contribution": 2500.0, "target_date": "2026-12-31"},
                {"name": "Vehicle Insurance", "target_amount": 12000.0, "current_amount": 4000.0, "monthly_contribution": 1000.0, "target_date": "2026-11-30"},
                {"name": "Emergency Fund (3 Months)", "target_amount": 100000.0, "current_amount": 45000.0, "monthly_contribution": 5000.0, "target_date": "2027-03-31"}
            ]

        # Calculate actuals per category
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

        # Sub-groupings for Financial Laws (50/30/20)
        needs_amt = category_actuals.get("Needs", 0.0) + category_actuals.get("Transport", 0.0) + category_actuals.get("Health", 0.0)
        debt_amt = category_actuals.get("Debt", 0.0)
        wants_amt = category_actuals.get("Food", 0.0) + category_actuals.get("Lifestyle", 0.0)
        savings_amt = actual_savings

        fin_laws = self._calculate_financial_laws(income, total_expenses, needs_amt, debt_amt, wants_amt, savings_amt)

        # Build category variance matrix
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
            "sinking_funds": sinking_funds
        }

# Global Singleton Instance
finance_service = FinanceService()
