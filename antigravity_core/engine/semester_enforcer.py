"""
semester_enforcer.py — 12-Week Semester Daily Cadence Enforcer
===============================================================
Enforces a 5-day rotating subject schedule across 12 weeks.
Runs nightly at 23:30 IST to audit completion and apply
rewards (+150 XP) or penalties (-150 XP, -3 WIL, Energy cap).

Academic Rotation (Mon–Fri):
  Mon → Machine Learning       (OLMDS603)
  Tue → Multivariate Analysis  (OLMDS602)
  Wed → Financial Analytics    (OLMDS607)
  Thu → Big Data Analytics     (OLMDS601)
  Fri → Programming in Java    (OLMDS604)
  Sat → DSA & LeetCode Sprint  (Core Engine)
  Sun → System Audit & Buffer  (Mind OS)
"""

import os
import sys
import sqlite3
import datetime
import threading
import time

# ── Path Setup ──────────────────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR   = os.path.dirname(_ENGINE_DIR)
_ROOT_DIR   = os.path.dirname(_CORE_DIR)
for _p in [_ROOT_DIR, _CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from engine.database import get_state, save_state, add_xp, DB_PATH
except ImportError:
    DB_PATH = os.path.join(_CORE_DIR, "data", "system_solo.db")
    def get_state(): return {}
    def save_state(s): pass
    def add_xp(x): pass

# ── 12-Week Semester Configuration ─────────────────────────────────────────────
SEMESTER_START_DATE = datetime.date(2026, 8, 18)   # Monday — Week 1 Day 1
SEMESTER_WEEKS      = 12

# 5-Day Rotating Course Schedule (weekday 0=Mon ... 4=Fri)
CADENCE_SCHEDULE = {
    0: {"code": "OLMDS603", "name": "Machine Learning",          "emoji": "🤖", "color": "#7c3aed", "stat": "int"},
    1: {"code": "OLMDS602", "name": "Multivariate Data Analysis","emoji": "📊", "color": "#0891b2", "stat": "int"},
    2: {"code": "OLMDS607", "name": "Financial Data Analytics",  "emoji": "💹", "color": "#059669", "stat": "int"},
    3: {"code": "OLMDS601", "name": "Big Data Analytics",        "emoji": "🗄️", "color": "#d97706", "stat": "agi"},
    4: {"code": "OLMDS604", "name": "Programming in Java",       "emoji": "☕", "color": "#dc2626", "stat": "agi"},
    5: {"code": "DSA_LEETCODE", "name": "DSA & LeetCode Sprint", "emoji": "⚡", "color": "#f59e0b", "stat": "agi"},
    6: {"code": "MIND_OS",  "name": "System Audit & Buffer",     "emoji": "🧘", "color": "#8b5cf6", "stat": "wil"},
}

ALL_COURSES = [
    {"code": "OLMDS603", "name": "Machine Learning",           "emoji": "🤖", "color": "#7c3aed", "total_weeks": 12},
    {"code": "OLMDS602", "name": "Multivariate Data Analysis", "emoji": "📊", "color": "#0891b2", "total_weeks": 12},
    {"code": "OLMDS607", "name": "Financial Data Analytics",   "emoji": "💹", "color": "#059669", "total_weeks": 12},
    {"code": "OLMDS601", "name": "Big Data Analytics",         "emoji": "🗄️", "color": "#d97706", "total_weeks": 12},
    {"code": "OLMDS604", "name": "Programming in Java",        "emoji": "☕", "color": "#dc2626", "total_weeks": 12},
]

XP_ON_TIME_BONUS  = 150
XP_MISSED_PENALTY = 150
WIL_PENALTY       = 3
WIL_BONUS         = 2
ENERGY_CAP_ON_MISS = 50
STAT_BONUS_ON_CLEAR = 5


# ── Database Helpers ─────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_semester_tables():
    """Create all semester tracking tables if they don't exist."""
    conn   = _get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_academic_cadence (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date             TEXT UNIQUE,
            week_number          INTEGER,
            weekday_index        INTEGER,
            required_course_code TEXT,
            required_course_name TEXT,
            items_completed      INTEGER DEFAULT 0,
            quiz_submitted       INTEGER DEFAULT 0,
            assignment_submitted INTEGER DEFAULT 0,
            status               TEXT CHECK(status IN ('PENDING','CLEARED','PENALIZED','WEEKEND')) DEFAULT 'PENDING',
            xp_awarded           INTEGER DEFAULT 0,
            notes                TEXT,
            audited_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semester_weekly_progress (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code      TEXT NOT NULL,
            course_name      TEXT NOT NULL,
            week_number      INTEGER NOT NULL,
            videos_watched   INTEGER DEFAULT 0,
            quiz_done        INTEGER DEFAULT 0,
            assignment_done  INTEGER DEFAULT 0,
            concepts_notes   TEXT,
            status           TEXT CHECK(status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED')) DEFAULT 'NOT_STARTED',
            completed_at     TEXT,
            UNIQUE(course_code, week_number)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semester_course_stats (
            course_code         TEXT PRIMARY KEY,
            course_name         TEXT,
            total_xp_earned     INTEGER DEFAULT 0,
            weeks_cleared       INTEGER DEFAULT 0,
            current_week        INTEGER DEFAULT 1,
            streak_weeks        INTEGER DEFAULT 0,
            last_activity_date  TEXT,
            canvas_course_id    INTEGER
        )
    """)

    for c in ALL_COURSES:
        cursor.execute("""
            INSERT OR IGNORE INTO semester_course_stats
            (course_code, course_name, total_xp_earned, weeks_cleared, current_week, streak_weeks)
            VALUES (?, ?, 0, 0, 1, 0)
        """, (c["code"], c["name"]))

    for c in ALL_COURSES:
        for wk in range(1, SEMESTER_WEEKS + 1):
            cursor.execute("""
                INSERT OR IGNORE INTO semester_weekly_progress
                (course_code, course_name, week_number, status)
                VALUES (?, ?, ?, 'NOT_STARTED')
            """, (c["code"], c["name"], wk))

    conn.commit()
    conn.close()
    print("[Semester] All semester tables initialized.")


# ── Week Calculator ──────────────────────────────────────────────────────────────

def get_current_week_number(ref_date: datetime.date = None) -> int:
    today = ref_date or datetime.date.today()
    delta = (today - SEMESTER_START_DATE).days
    if delta < 0:
        return 1
    week = (delta // 7) + 1
    return min(week, SEMESTER_WEEKS)


def get_today_target() -> dict:
    today   = datetime.date.today()
    weekday = today.weekday()
    week_number = get_current_week_number(today)
    target  = CADENCE_SCHEDULE.get(weekday, CADENCE_SCHEDULE[6])

    deadline = datetime.datetime.combine(today, datetime.time(23, 59, 0))
    now      = datetime.datetime.now()
    seconds_remaining = max(0, int((deadline - now).total_seconds()))

    return {
        "date":             today.isoformat(),
        "weekday":          weekday,
        "weekday_name":     today.strftime("%A"),
        "week_number":      week_number,
        "course_code":      target["code"],
        "course_name":      target["name"],
        "course_emoji":     target["emoji"],
        "course_color":     target["color"],
        "is_weekend":       weekday >= 5,
        "deadline_str":     deadline.strftime("%Y-%m-%d 23:59:00"),
        "hours_remaining":  seconds_remaining // 3600,
        "mins_remaining":   (seconds_remaining % 3600) // 60,
        "seconds_remaining": seconds_remaining,
        "semester_pct":     round((week_number - 1) / SEMESTER_WEEKS * 100, 1),
        "weeks_left":       SEMESTER_WEEKS - week_number + 1,
    }


# ── Daily Audit Engine ───────────────────────────────────────────────────────────

def run_daily_audit(force: bool = False) -> dict:
    """
    Core nightly audit. Checks canvas_completed_items for today's course,
    awards +150 XP on success, or penalizes -150 XP / -3 WIL / energy cap on miss.
    """
    today       = datetime.date.today()
    today_str   = today.isoformat()
    weekday     = today.weekday()
    week_number = get_current_week_number(today)
    now_ts      = datetime.datetime.now().isoformat()

    conn   = _get_conn()
    cursor = conn.cursor()
    init_semester_tables()

    if not force:
        cursor.execute(
            "SELECT status FROM daily_academic_cadence WHERE log_date = ?",
            (today_str,)
        )
        row = cursor.fetchone()
        if row and row[0] in ("CLEARED", "PENALIZED", "WEEKEND"):
            conn.close()
            return {"already_audited": True, "status": row[0], "date": today_str}

    if weekday >= 5:
        cursor.execute("""
            INSERT OR REPLACE INTO daily_academic_cadence
            (log_date, week_number, weekday_index, required_course_code,
             required_course_name, status, xp_awarded, notes, audited_at)
            VALUES (?, ?, ?, ?, ?, 'WEEKEND', 120, 'Weekend: DSA + Mind OS mode', ?)
        """, (today_str, week_number, weekday,
              CADENCE_SCHEDULE[weekday]["code"],
              CADENCE_SCHEDULE[weekday]["name"], now_ts))
        conn.commit()
        conn.close()
        return {"status": "WEEKEND", "date": today_str, "message": "Weekend mode"}

    target = CADENCE_SCHEDULE[weekday]
    print(f"[Semester Audit] {today_str} | Week {week_number} | Target: {target['name']}")

    # Check canvas_completed_items for today's completions
    cursor.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN item_type IN ('Quiz') OR item_title LIKE '%Quiz%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN item_type IN ('Assignment') OR item_title LIKE '%Assignment%' THEN 1 ELSE 0 END)
        FROM canvas_completed_items
        WHERE date(completed_at) = ?
          AND (course_name LIKE ? OR course_name LIKE ?)
    """, (today_str, f"%{target['name']}%", f"%{target['code']}%"))

    row              = cursor.fetchone()
    items_completed  = int(row[0] or 0)
    quizzes_done     = int(row[1] or 0)
    assignments_done = int(row[2] or 0)

    if items_completed > 0:
        status     = "CLEARED"
        xp_awarded = XP_ON_TIME_BONUS
        try:
            add_xp(xp_awarded)
            state = get_state()
            if state:
                state["wil"]             = state.get("wil", 10) + WIL_BONUS
                state[target["stat"]]    = state.get(target["stat"], 10) + STAT_BONUS_ON_CLEAR
                state["streak_days"]     = state.get("streak_days", 0) + 1
                save_state(state)
        except Exception as e:
            cursor.execute("""
                UPDATE system_state SET xp = xp + ?, wil = MIN(100, wil + 2), streak_days = streak_days + 1 WHERE id = 1
            """, (xp_awarded,))

        cursor.execute("""
            UPDATE semester_course_stats
            SET total_xp_earned = total_xp_earned + ?, weeks_cleared = weeks_cleared + 1,
                current_week = ?, last_activity_date = ?
            WHERE course_code = ?
        """, (xp_awarded, week_number, today_str, target["code"]))

        cursor.execute("""
            INSERT OR REPLACE INTO semester_weekly_progress
            (course_code, course_name, week_number, videos_watched, quiz_done, assignment_done, status, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', ?)
        """, (target["code"], target["name"], week_number,
              max(items_completed - quizzes_done - assignments_done, 0),
              quizzes_done, assignments_done, today_str))

    else:
        status     = "PENALIZED"
        xp_awarded = -XP_MISSED_PENALTY
        try:
            state = get_state()
            if state:
                state["xp"]     = max(0, state.get("xp", 0) - XP_MISSED_PENALTY)
                state["wil"]    = max(0, state.get("wil", 10) - WIL_PENALTY)
                state["energy"] = min(state.get("energy", 100), ENERGY_CAP_ON_MISS)
                save_state(state)
        except Exception:
            cursor.execute("""
                UPDATE system_state SET xp = MAX(0, xp - ?), wil = MAX(0, wil - ?), energy = MIN(energy, ?) WHERE id = 1
            """, (XP_MISSED_PENALTY, WIL_PENALTY, ENERGY_CAP_ON_MISS))

    cursor.execute("""
        INSERT OR REPLACE INTO daily_academic_cadence
        (log_date, week_number, weekday_index, required_course_code, required_course_name,
         items_completed, quiz_submitted, assignment_submitted, status, xp_awarded, audited_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (today_str, week_number, weekday, target["code"], target["name"],
          items_completed, quizzes_done, assignments_done, status, abs(xp_awarded), now_ts))

    conn.commit()
    conn.close()

    return {
        "status":           status,
        "date":             today_str,
        "week_number":      week_number,
        "course":           target["name"],
        "course_code":      target["code"],
        "items_completed":  items_completed,
        "quizzes_done":     quizzes_done,
        "assignments_done": assignments_done,
        "xp_delta":         xp_awarded,
    }


# ── Manual Override ──────────────────────────────────────────────────────────────

def mark_day_cleared(date_str: str = None, notes: str = "") -> dict:
    """Manually mark a date as CLEARED (admin override)."""
    target_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    weekday     = target_date.weekday()
    week_number = get_current_week_number(target_date)
    target      = CADENCE_SCHEDULE.get(weekday, CADENCE_SCHEDULE[0])

    conn   = _get_conn()
    cursor = conn.cursor()
    init_semester_tables()
    cursor.execute("""
        INSERT OR REPLACE INTO daily_academic_cadence
        (log_date, week_number, weekday_index, required_course_code, required_course_name,
         items_completed, status, xp_awarded, notes, audited_at)
        VALUES (?, ?, ?, ?, ?, 1, 'CLEARED', ?, ?, ?)
    """, (target_date.isoformat(), week_number, weekday, target["code"], target["name"],
          XP_ON_TIME_BONUS, f"Manual override: {notes}", datetime.datetime.now().isoformat()))
    try:
        add_xp(XP_ON_TIME_BONUS)
    except Exception:
        cursor.execute("UPDATE system_state SET xp = xp + ? WHERE id = 1", (XP_ON_TIME_BONUS,))
    conn.commit()
    conn.close()
    return {"status": "CLEARED", "date": target_date.isoformat(), "course": target["name"], "xp_awarded": XP_ON_TIME_BONUS}


# ── Dashboard Data Provider ──────────────────────────────────────────────────────

def get_semester_dashboard_data() -> dict:
    today        = datetime.date.today()
    week_number  = get_current_week_number(today)
    today_target = get_today_target()

    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    init_semester_tables()

    cursor.execute("""
        SELECT course_code, course_name, week_number, videos_watched,
               quiz_done, assignment_done, status, completed_at
        FROM semester_weekly_progress
        ORDER BY course_code, week_number
    """)
    weekly_rows = [dict(r) for r in cursor.fetchall()]

    progress_grid = {}
    for row in weekly_rows:
        cc = row["course_code"]
        wk = row["week_number"]
        if cc not in progress_grid:
            progress_grid[cc] = {}
        progress_grid[cc][wk] = row

    cursor.execute("""
        SELECT log_date, week_number, required_course_code, required_course_name,
               items_completed, quiz_submitted, assignment_submitted, status, xp_awarded, notes
        FROM daily_academic_cadence
        ORDER BY log_date DESC
        LIMIT 14
    """)
    audit_log = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT status, items_completed, xp_awarded FROM daily_academic_cadence WHERE log_date = ?", (today.isoformat(),))
    today_audit = dict(cursor.fetchone() or {"status": "PENDING", "items_completed": 0, "xp_awarded": 0})

    cursor.execute("SELECT xp, wil, int, agi, str, energy, streak_days, level FROM system_state WHERE id = 1")
    state_row    = cursor.fetchone()
    player_state = dict(state_row) if state_row else {}

    cursor.execute("SELECT course_name, COUNT(*) as items, SUM(xp_awarded) as total_xp FROM canvas_completed_items GROUP BY course_name")
    canvas_xp_rows = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT log_date, status, required_course_code FROM daily_academic_cadence WHERE log_date >= date('now', '-30 days') ORDER BY log_date ASC")
    calendar_data = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT course_code, course_name, total_xp_earned, weeks_cleared, current_week, streak_weeks, last_activity_date FROM semester_course_stats")
    course_stats = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT
          COUNT(CASE WHEN status = 'CLEARED'   THEN 1 END) as days_cleared,
          COUNT(CASE WHEN status = 'PENALIZED' THEN 1 END) as days_missed,
          SUM(CASE WHEN status = 'CLEARED'   THEN xp_awarded ELSE 0 END) as total_bonus_xp,
          SUM(CASE WHEN status = 'PENALIZED' THEN xp_awarded ELSE 0 END) as total_penalty_xp
        FROM daily_academic_cadence
    """)
    summary_row = cursor.fetchone()
    summary     = dict(summary_row) if summary_row else {}
    conn.close()

    weekly_schedule = []
    for i in range(7):
        d  = today + datetime.timedelta(days=i)
        wd = d.weekday()
        t  = CADENCE_SCHEDULE.get(wd, CADENCE_SCHEDULE[6])
        weekly_schedule.append({
            "date": d.isoformat(), "day_name": d.strftime("%a"),
            "is_today": d == today, "course_code": t["code"],
            "course_name": t["name"], "emoji": t["emoji"],
            "color": t["color"], "is_weekend": wd >= 5,
        })

    return {
        "today":           today.isoformat(),
        "week_number":     week_number,
        "semester_weeks":  SEMESTER_WEEKS,
        "semester_pct":    round((week_number - 1) / SEMESTER_WEEKS * 100, 1),
        "weeks_left":      SEMESTER_WEEKS - week_number + 1,
        "today_target":    today_target,
        "today_audit":     today_audit,
        "player_state":    player_state,
        "weekly_schedule": weekly_schedule,
        "progress_grid":   progress_grid,
        "audit_log":       audit_log,
        "canvas_xp":       canvas_xp_rows,
        "course_stats":    course_stats,
        "calendar_data":   calendar_data,
        "summary":         summary,
        "all_courses":     ALL_COURSES,
    }


# ── Background Daemon Loop ───────────────────────────────────────────────────────

def run_semester_enforcer_loop(stop_event: threading.Event):
    """Nightly 23:30 IST audit loop. Add to main.py as a daemon thread."""
    print("[Semester Enforcer] 12-Week Academic Cadence Daemon started.")
    init_semester_tables()
    while not stop_event.is_set():
        now = datetime.datetime.now()
        if now.hour == 23 and now.minute == 30:
            print(f"[Semester Enforcer] 23:30 nightly audit firing...")
            try:
                result = run_daily_audit()
                print(f"[Semester Enforcer] Result: {result.get('status')} | {result.get('course','—')} | {result.get('xp_delta', 0):+d} XP")
            except Exception as e:
                print(f"[Semester Enforcer] Audit error: {e}")
            stop_event.wait(65)
        else:
            stop_event.wait(30)
    print("[Semester Enforcer] Daemon stopped.")


if __name__ == "__main__":
    import json
    print("=" * 60)
    print("  ANTIGRAVITY — 12-Week Semester Enforcer")
    print("=" * 60)
    init_semester_tables()
    target = get_today_target()
    print(f"\nToday: {target['weekday_name']} Week {target['week_number']}/12")
    print(f"Target: {target['course_emoji']} {target['course_name']}")
    print(f"Time left: {target['hours_remaining']}h {target['mins_remaining']}m")
    print("\nRunning audit (force=True)...")
    result = run_daily_audit(force=True)
    print(json.dumps(result, indent=2))
