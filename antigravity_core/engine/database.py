import sys
import os
import sqlite3
import threading
from datetime import date
from typing import Optional, List, Dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from config import IS_SERVERLESS
except ImportError:
    IS_SERVERLESS = False

CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("VERCEL") or not os.access(CORE_DIR, os.W_OK):
    DB_DIR = "/tmp/antigravity_data"
else:
    DB_DIR = os.path.join(CORE_DIR, "data")

os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "system_solo.db")
ACTIVITY_LOG_PATH = os.path.join(DB_DIR, "activity_log.md")
EXAM_SCRATCHPAD_PATH = os.path.join(DB_DIR, "exam_scratchpad.md")

# Global write lock — SQLite in WAL mode supports concurrent reads,
# but writes must be serialized in a multi-threaded process.
_DB_WRITE_LOCK = threading.Lock()


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)

    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # 1. State Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        str INTEGER DEFAULT 10,
        int INTEGER DEFAULT 10,
        agi INTEGER DEFAULT 10,
        wil INTEGER DEFAULT 10,
        energy REAL DEFAULT 100.0,
        lockout_active INTEGER DEFAULT 0,
        last_update TEXT,
        streak_days INTEGER DEFAULT 0,
        continuous_study_days INTEGER DEFAULT 0,
        active_subject TEXT DEFAULT 'Python_Data_Science'
    )
    """)
    
    # Check if we need to alter table (in case system_state exists without active_subject)
    try:
        cursor.execute("ALTER TABLE system_state ADD COLUMN active_subject TEXT DEFAULT 'Python_Data_Science'")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Check and add checklist columns to system_state
    columns_to_add = [
        ("gym_completed", "INTEGER DEFAULT 0"),
        ("study_completed", "INTEGER DEFAULT 0"),
        ("leetcode_completed", "INTEGER DEFAULT 0"),
        ("cooking_completed", "INTEGER DEFAULT 0"),
        ("nopmo_completed", "INTEGER DEFAULT 0"),
        ("heart", "INTEGER DEFAULT 10"),
        ("stoic", "INTEGER DEFAULT 10"),
        ("reading_completed", "INTEGER DEFAULT 0"),
        ("reading_book", "TEXT DEFAULT 'None'"),
        ("english_completed", "INTEGER DEFAULT 0"),
        ("walk_completed", "INTEGER DEFAULT 0"),
        ("meditation_completed", "INTEGER DEFAULT 0"),
        ("mindos_completed", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE system_state ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists
    
    # 2. Leetcode Solved Stats Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leetcode_stats (
        difficulty TEXT PRIMARY KEY,
        solved_count INTEGER DEFAULT 0
    )
    """)
    
    # 3. Completed Syllabus Modules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_modules (
        module_name TEXT PRIMARY KEY,
        course TEXT,
        xp_earned INTEGER,
        completed_at TEXT
    )
    """)
    
    # Dynamic System Energy State Register
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS energy_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_energy REAL DEFAULT 80.0,
        cumulative_fatigue REAL DEFAULT 0.0,
        tier_status TEXT DEFAULT 'NORMAL',
        deep_work_blocks_today INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Immutable Ledger of Energy Drains and Restorations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS energy_ledger (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_type TEXT CHECK(transaction_type IN ('DRAIN', 'RECOVERY', 'RESET')),
        category TEXT,
        magnitude REAL,
        energy_before REAL,
        energy_after REAL,
        associated_quest_id TEXT,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed Singleton Register
    cursor.execute("""
    INSERT OR IGNORE INTO energy_state (id, current_energy, cumulative_fatigue, tier_status)
    VALUES (1, 80.0, 0.0, 'NORMAL');
    """)

    # Initialize default state if empty
    cursor.execute("SELECT COUNT(*) FROM system_state")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO system_state (level, xp, str, int, agi, wil, energy, lockout_active, last_update, streak_days, continuous_study_days, active_subject, gym_completed, study_completed, leetcode_completed, cooking_completed, nopmo_completed, heart, stoic, english_completed, reading_completed, reading_book)
        VALUES (1, 0, 10, 10, 10, 10, 100.0, 0, ?, 0, 0, 'Python_Data_Science', 0, 0, 0, 0, 0, 10, 10, 0, 0, 'None')
        """, (date.today().isoformat(),))
        
    # 4. AI Chat History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)
    try:
        cursor.execute("ALTER TABLE ai_chat_history ADD COLUMN bot_type TEXT DEFAULT 'coach'")
    except sqlite3.OperationalError:
        pass # Column already exists

    # 6. English Translation History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS translation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        definition TEXT DEFAULT '',
        translation TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 7. Daily English Lessons Cache Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_english_lessons (
        log_date TEXT PRIMARY KEY,
        lesson_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # 8. Financial Governance Tables
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
    CREATE TABLE IF NOT EXISTS daily_english_lessons (
        date TEXT PRIMARY KEY,
        word TEXT NOT NULL,
        word_tamil TEXT NOT NULL,
        word_definition TEXT NOT NULL,
        word_example TEXT NOT NULL,
        spoken_phrase TEXT NOT NULL,
        spoken_tamil TEXT NOT NULL,
        spoken_explanation TEXT NOT NULL,
        spoken_example TEXT NOT NULL,
        grammar_rule TEXT NOT NULL,
        grammar_explanation TEXT NOT NULL,
        grammar_quiz TEXT NOT NULL,
        grammar_quiz_explanation TEXT NOT NULL
    )
    """)

    # 8. Offline English-Tamil Dictionary Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS offline_dictionary (
        word TEXT PRIMARY KEY,
        part_of_speech TEXT DEFAULT 'noun',
        tamil_translation TEXT NOT NULL,
        definition TEXT DEFAULT '',
        synonyms TEXT DEFAULT '',
        example_en TEXT DEFAULT '',
        example_ta TEXT DEFAULT ''
    )
    """)

    # 9. English User Progress & Streak Tracker
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS english_user_progress (
        id INTEGER PRIMARY KEY DEFAULT 1,
        streak_days INTEGER DEFAULT 1,
        last_active_date TEXT DEFAULT '',
        total_speaking_seconds INTEGER DEFAULT 0,
        words_mastered INTEGER DEFAULT 0,
        xp_points INTEGER DEFAULT 0,
        unlocked_badges TEXT DEFAULT '[]'
    )
    """)

    # 10. English Public Speaking & Voice Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS english_speech_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        transcript TEXT NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        wpm INTEGER DEFAULT 0,
        filler_count INTEGER DEFAULT 0,
        fluency_score INTEGER DEFAULT 0,
        feedback TEXT DEFAULT '',
        timestamp TEXT NOT NULL
    )
    """)

    # Clean dummy translation history entries on startup
    cursor.execute("DELETE FROM translation_history WHERE translation LIKE '%(மொழிபெயர்ப்பு%' OR translation LIKE '%(Tamil meaning%'")



    # 5. Study Journal Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS study_journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        notes TEXT DEFAULT '',
        subject_id TEXT DEFAULT '',
        item_id TEXT DEFAULT '',
        mood TEXT DEFAULT 'focused',
        timestamp TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    # 6. Bad Experiences / Scold Log Table (rage-fuel motivation wall)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bad_experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        who TEXT DEFAULT '',
        what_happened TEXT NOT NULL,
        my_lesson TEXT DEFAULT '',
        intensity INTEGER DEFAULT 3,
        timestamp TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    # 7. Saved Books Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS saved_books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Reading Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reading_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_title TEXT NOT NULL,
        page_from INTEGER NOT NULL,
        page_to INTEGER NOT NULL,
        pages_read INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    # 9. Human Connection & Stranger Meeting Tracker Table (+1 HRT)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS human_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_name TEXT NOT NULL,
        context_meeting TEXT DEFAULT '',
        what_happened TEXT NOT NULL,
        what_i_felt TEXT NOT NULL,
        emoji TEXT DEFAULT '🤝',
        timestamp TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    # 10. Saved Human Encounter Locations/Contexts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS human_contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # 11. Stoic Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stoic_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reflection TEXT NOT NULL,
        attitude_score INTEGER DEFAULT 5,
        stoic_lesson TEXT DEFAULT '',
        timestamp TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    default_contexts = [
        "☕ Coffee Shop / Cafe",
        "🏋️ Gym / Fitness Center",
        "🏢 Office / Workplace",
        "🚌 Public Transport / Commute",
        "🎓 University / Campus",
        "🚶 Park / Outdoor Walk",
        "🏠 Neighborhood",
        "🛒 Store / Supermarket",
        "🌐 Online / Tech Community"
    ]
    for ctx in default_contexts:
        cursor.execute("INSERT OR IGNORE INTO human_contexts (name) VALUES (?)", (ctx,))

    # Initialize default leetcode stats if empty
    for diff in ["Easy", "Medium", "Hard", "All"]:
        cursor.execute("INSERT OR IGNORE INTO leetcode_stats (difficulty, solved_count) VALUES (?, 0)", (diff,))
        
    # 12. Global Settings Table (key-value store for API keys, preferences)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 13. AI Teacher Topics Checklist Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teacher_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        completed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 14. Mind OS - Reality Checks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mind_reality_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_event TEXT NOT NULL,
        my_interpretation TEXT NOT NULL,
        evidence_for TEXT,
        evidence_against TEXT,
        alternative_explanation TEXT,
        verified_outcome TEXT DEFAULT 'Pending',
        distortions TEXT,
        date TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 15. Mind OS - Rumination Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mind_rumination_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_convo TEXT NOT NULL,
        intensity INTEGER DEFAULT 5,
        duration_mins INTEGER DEFAULT 10,
        distress_score INTEGER DEFAULT 5,
        grounding_used INTEGER DEFAULT 0,
        alternative_thought TEXT,
        date TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 16. Mind OS - Relationships Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mind_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_name TEXT UNIQUE NOT NULL,
        trust_score INTEGER DEFAULT 5,
        leave_urge INTEGER DEFAULT 0,
        closeness INTEGER DEFAULT 5,
        last_interaction_date TEXT,
        notes TEXT,
        status TEXT DEFAULT 'Active',
        date TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 17. Mind OS - Meditation Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mind_meditation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        duration_mins INTEGER,
        track_name TEXT,
        date TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 18. Teaching Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teaching_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person TEXT NOT NULL,
        subject TEXT,
        topic TEXT NOT NULL,
        duration TEXT,
        outcome TEXT,
        notes TEXT,
        date TEXT,
        ts TEXT
    )
    """)

    # 19. Office Work Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS office_work_logs (
        workLogId INTEGER PRIMARY KEY AUTOINCREMENT,
        workItemId TEXT,
        description TEXT,
        workDate TEXT,
        category TEXT,
        hours REAL,
        xp_awarded REAL,
        category_streak INTEGER,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    try:
        cursor.execute("PRAGMA table_info(office_work_logs)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and "workLogId" not in cols:
            cursor.execute("ALTER TABLE office_work_logs RENAME TO _office_work_logs_old")
            cursor.execute("""
                CREATE TABLE office_work_logs (
                    workLogId INTEGER PRIMARY KEY AUTOINCREMENT,
                    workItemId TEXT,
                    description TEXT,
                    workDate TEXT,
                    category TEXT,
                    hours REAL,
                    xp_awarded REAL,
                    category_streak INTEGER,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO office_work_logs (workItemId, description, workDate, category, hours, xp_awarded, category_streak, logged_at)
                SELECT workItemId, description, workDate, category, hours, xp_awarded, category_streak, logged_at FROM _office_work_logs_old
            """)
            cursor.execute("DROP TABLE _office_work_logs_old")
    except Exception as e:
        print(f"[DB] Migration note for office_work_logs: {e}")

    # 20. Gym Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gym_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        duration_minutes REAL,
        workout_type TEXT,
        is_manual INTEGER,
        notes TEXT,
        xp_awarded INTEGER,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 21. Per-Task Daily Completion Log (source of truth for individual task streaks)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_daily_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        task_key    TEXT NOT NULL,
        log_date    TEXT NOT NULL,
        completed   INTEGER DEFAULT 1,
        logged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(task_key, log_date)
    )
    """)

    # 22. In-App Notification Bell (Canvas reminders + system alerts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS in_app_notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        body        TEXT NOT NULL,
        level       TEXT DEFAULT 'info',
        is_read     INTEGER DEFAULT 0,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()




def log_task_completion(task_key: str, completed: bool = True, log_date: str = None):
    """
    Record today's completion/unset for a task in task_daily_log / pg_task_daily_log.
    Called from toggle_checklist in server.py on every state change.
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_log_task_completion
        return neon_log_task_completion(task_key, completed, log_date)

    from datetime import date as _date
    today = log_date or _date.today().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.execute("PRAGMA journal_mode=WAL;")
        if completed:
            conn.execute(
                "INSERT OR REPLACE INTO task_daily_log (task_key, log_date, completed) VALUES (?, ?, 1)",
                (task_key, today)
            )
        else:
            # Mark as uncompleted (keep row so we know it was toggled off)
            conn.execute(
                "INSERT OR REPLACE INTO task_daily_log (task_key, log_date, completed) VALUES (?, ?, 0)",
                (task_key, today)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_task_completion error for {task_key}: {e}")


def get_task_streaks() -> dict:
    """
    Compute per-task streak stats from task_daily_log / pg_task_daily_log.
    Returns a dict keyed by task_key with:
      current_streak, best_streak, total_done, missed_yesterday,
      done_today, last_30 (list of {date, done})
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_task_streaks
        return neon_get_task_streaks()

    from datetime import date as _date, timedelta
    today = _date.today()
    results = {}

    TASK_KEYS = [
        "study", "leetcode", "gym", "english", "cooking",
        "nopmo", "reading", "walk", "meditation", "mindos",
        "health", "canvas_semester",
    ]

    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.row_factory = sqlite3.Row
        # Fetch last 120 days of logs for all tasks in one query
        cutoff = (today - timedelta(days=120)).isoformat()
        rows = conn.execute(
            "SELECT task_key, log_date, completed FROM task_daily_log WHERE log_date >= ? ORDER BY task_key, log_date DESC",
            (cutoff,)
        ).fetchall()

        # Lifetime total counts
        total_rows = conn.execute(
            "SELECT task_key, COUNT(*) as total FROM task_daily_log WHERE completed = 1 GROUP BY task_key"
        ).fetchall()
        total_counts = {r[0]: int(r[1]) for r in total_rows}
        conn.close()

        # Group by task_key
        from collections import defaultdict
        by_task = defaultdict(dict)
        for r in rows:
            by_task[r["task_key"]][r["log_date"]] = bool(r["completed"])

        for tk in TASK_KEYS:
            day_map = by_task.get(tk, {})

            # Last 30 days calendar
            last_30 = []
            for i in range(29, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                last_30.append({"date": d, "done": day_map.get(d, False)})

            done_today     = bool(day_map.get(today.isoformat(), False))
            done_yesterday = bool(day_map.get((today - timedelta(days=1)).isoformat(), False))

            current_streak = 0
            if done_today:
                check_day = today
                while True:
                    if day_map.get(check_day.isoformat(), False):
                        current_streak += 1
                        check_day = check_day - timedelta(days=1)
                    else:
                        break
            elif done_yesterday:
                check_day = today - timedelta(days=1)
                while True:
                    if day_map.get(check_day.isoformat(), False):
                        current_streak += 1
                        check_day = check_day - timedelta(days=1)
                    else:
                        break

            # Best streak (sliding window over 120 days)
            best_streak = 0
            run = 0
            for i in range(120):
                ds = (today - timedelta(days=i)).isoformat()
                if day_map.get(ds, False):
                    run += 1
                    best_streak = max(best_streak, run)
                else:
                    run = 0

            total_done = total_counts.get(tk, sum(1 for v in day_map.values() if v))
            has_history = total_done > 0

            day_before_yesterday = (today - timedelta(days=2)).isoformat()
            had_recent_streak = bool(day_map.get(day_before_yesterday, False))
            missed_yesterday = (
                had_recent_streak
                and not done_yesterday
                and not done_today
            )

            results[tk] = {
                "task_key":         tk,
                "current_streak":   current_streak,
                "best_streak":      max(best_streak, current_streak),
                "total_done":       total_done,
                "missed_yesterday": missed_yesterday,
                "done_today":       done_today,
                "has_history":      has_history,
                "last_30":          last_30,
            }

    except Exception as e:
        print(f"[DB] get_task_streaks error: {e}")

    return results


def backfill_task_daily_log() -> dict:
    """
    One-time backfill: reads all existing activity tables and populates
    task_daily_log / pg_task_daily_log with historical completion data.
    Safe to call multiple times — uses INSERT OR IGNORE / ON CONFLICT DO NOTHING.
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_backfill_task_daily_log
        return neon_backfill_task_daily_log()

    from datetime import date as _date
    filled = {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.execute("PRAGMA journal_mode=WAL;")

        def _insert(task_key, date_str):
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO task_daily_log (task_key, log_date, completed) VALUES (?, ?, 1)",
                    (task_key, date_str)
                )
            except Exception:
                pass

        # study_journal → study
        try:
            rows = conn.execute("SELECT DISTINCT date FROM study_journal WHERE date IS NOT NULL").fetchall()
            for r in rows:
                _insert("study", r[0])
            filled["study"] = len(rows)
        except Exception as e:
            filled["study"] = f"ERR:{e}"

        # reading_logs → reading
        try:
            rows = conn.execute("SELECT DISTINCT date FROM reading_logs WHERE date IS NOT NULL").fetchall()
            for r in rows:
                _insert("reading", r[0])
            filled["reading"] = len(rows)
        except Exception as e:
            filled["reading"] = f"ERR:{e}"

        # health_sync_logs → health + walk (steps >= 2000)
        try:
            rows = conn.execute("SELECT DISTINCT log_date, steps FROM health_sync_logs WHERE log_date IS NOT NULL").fetchall()
            h, w = 0, 0
            for r in rows:
                _insert("health", r[0])
                h += 1
                if (r[1] or 0) >= 2000:
                    _insert("walk", r[0])
                    w += 1
            filled["health"] = h
            filled["walk"]   = w
        except Exception as e:
            filled["health"] = f"ERR:{e}"

        # canvas_completed_items → canvas_semester
        try:
            rows = conn.execute(
                "SELECT DISTINCT date(completed_at) as d FROM canvas_completed_items WHERE completed_at IS NOT NULL"
            ).fetchall()
            for r in rows:
                if r[0]:
                    _insert("canvas_semester", r[0])
            filled["canvas_semester"] = len(rows)
        except Exception as e:
            filled["canvas_semester"] = f"ERR:{e}"

        # gym_logs → gym (use logged_at timestamp)
        try:
            rows = conn.execute(
                "SELECT DISTINCT date(logged_at) as d FROM gym_logs WHERE logged_at IS NOT NULL"
            ).fetchall()
            for r in rows:
                if r[0]:
                    _insert("gym", r[0])
            filled["gym"] = len(rows)
        except Exception as e:
            filled["gym"] = f"ERR:{e}"

        conn.commit()
        conn.close()
        print(f"[DB] backfill_task_daily_log complete: {filled}")
    except Exception as e:
        print(f"[DB] backfill_task_daily_log error: {e}")
        filled["error"] = str(e)

    return filled


def get_notifications(limit: int = 20, unread_only: bool = False) -> list:
    """
    Fetch in-app notifications (Canvas reminders + system alerts).
    Returns list of dicts with id, title, body, level, is_read, created_at.
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_notifications
        return neon_get_notifications(limit=limit, unread_only=unread_only)

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS in_app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, body TEXT NOT NULL,
                level TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        query = "SELECT * FROM in_app_notifications"
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        rows = conn.execute(query, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] get_notifications error: {e}")
        return []


def mark_notifications_read(notification_ids: list = None) -> int:
    """
    Mark notifications as read. If notification_ids is None or empty, marks ALL as read.
    Returns count of rows updated.
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_mark_notifications_read
        return neon_mark_notifications_read(notification_ids)

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        if notification_ids:
            placeholders = ",".join("?" * len(notification_ids))
            cur = conn.execute(
                f"UPDATE in_app_notifications SET is_read=1 WHERE id IN ({placeholders})",
                notification_ids
            )
        else:
            cur = conn.execute("UPDATE in_app_notifications SET is_read=1")
        conn.commit()
        count = cur.rowcount
        conn.close()
        return count
    except Exception as e:
        print(f"[DB] mark_notifications_read error: {e}")
        return 0


def get_unread_notification_count() -> int:
    """Quick count of unread notifications for the bell badge."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_unread_notification_count
        return neon_get_unread_notification_count()

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        row = conn.execute(
            "SELECT COUNT(*) FROM in_app_notifications WHERE is_read=0"
        ).fetchone()
        conn.close()
        return int(row[0] or 0)
    except Exception:
        return 0



def get_db_connection():

    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        init_db()
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def calculate_xp_required(level: int) -> int:
    """XP required to level up: XP_req = 100 * level^1.5"""
    return int(100 * (level ** 1.5))

def check_date_transition_db(state: dict) -> dict:
    return state

def get_state() -> dict:
    state = {}
    try:
        from state import load_state
        db_state = load_state()
        if db_state:
            # Merge with any local SQLite specific columns
            try:
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
                r = cur.fetchone()
                if r:
                    for k, v in dict(r).items():
                        if k not in db_state:
                            db_state[k] = v
                conn.close()
            except Exception:
                pass
            state = db_state
    except Exception as e:
        print(f"Error loading state via Neon sync engine: {e}")

    if not state:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                state = dict(row)
        except Exception:
            pass

    if state:
        state = check_date_transition_db(state)
    return state or {}

def save_state(state: dict):
    # 1. Save via root state.py sync engine (Neon PostgreSQL DB + local file sync)
    try:
        from state import save_state as root_save_state
        root_save_state(state)
    except Exception as e:
        print(f"Error saving state via Neon sync engine: {e}")

    # 2. Update local SQLite DB if available
    try:
        with _DB_WRITE_LOCK:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE system_state
            SET level = ?,
                xp = ?,
                str = ?,
                int = ?,
                agi = ?,
                wil = ?,
                energy = ?,
                lockout_active = ?,
                last_update = ?,
                streak_days = ?,
                continuous_study_days = ?,
                active_subject = ?,
                gym_completed = ?,
                study_completed = ?,
                leetcode_completed = ?,
                cooking_completed = ?,
                nopmo_completed = ?,
                heart = ?,
                stoic = ?,
                reading_completed = ?,
                reading_book = ?,
                english_completed = ?,
                walk_completed = ?,
                meditation_completed = ?,
                mindos_completed = ?
            WHERE id = (SELECT id FROM system_state ORDER BY id DESC LIMIT 1)
            """, (
                state.get("level", 1),
                state.get("xp", 0),
                state.get("str", 10),
                state.get("int", 10),
                state.get("agi", 10),
                state.get("wil", 10),
                state.get("energy", 100.0),
                1 if state.get("lockout_active") else 0,
                state.get("last_update", date.today().isoformat()),
                state.get("streak_days", 0),
                state.get("continuous_study_days", 0),
                state.get("active_subject", "Python_Data_Science"),
                1 if state.get("gym_completed") else 0,
                1 if state.get("study_completed") else 0,
                1 if state.get("leetcode_completed") else 0,
                1 if state.get("cooking_completed") else 0,
                1 if state.get("nopmo_completed") else 0,
                state.get("heart", 10),
                state.get("stoic", 10),
                1 if state.get("reading_completed") else 0,
                state.get("reading_book", "None"),
                1 if state.get("english_completed") else 0,
                1 if state.get("walk_completed") else 0,
                1 if state.get("meditation_completed") else 0,
                1 if state.get("mindos_completed") else 0
            ))
            conn.commit()
            conn.close()
    except Exception:
        pass

def add_xp(amount: int) -> dict:
    state = get_state()
    if not state:
        return {}
    state["xp"] += amount
    
    # Handle level down
    while state["xp"] < 0 and state["level"] > 1:
        state["level"] -= 1
        state["xp"] += calculate_xp_required(state["level"])
        
    if state["xp"] < 0:
        state["xp"] = 0
        
    # Handle level up
    while True:
        req = calculate_xp_required(state["level"])
        if state["xp"] >= req:
            state["xp"] -= req
            state["level"] += 1
        else:
            break
            
    save_state(state)
    return state

def update_stat(stat_name: str, amount: float) -> dict:
    """Dynamically update any core stat (XP, STR, INT, AGI, WIL, ENERGY, HEART)"""
    stat_name = stat_name.lower()
    col_map = {
        "xp": "xp", "str": "str", "int": "int", "agi": "agi", "wil": "wil", 
        "energy": "energy", "hrt": "heart", "heart": "heart", "humanity": "heart",
        "stc": "stoic", "stoic": "stoic"
    }
    
    db_col = col_map.get(stat_name)
    if not db_col:
        return {}
        
    state = get_state()
    if not state:
        return {}
        
    state[db_col] += amount
    
    if db_col == "xp":
        state["xp"] = int(state["xp"])
        while state["xp"] < 0 and state["level"] > 1:
            state["level"] -= 1
            state["xp"] += calculate_xp_required(state["level"])
        if state["xp"] < 0:
            state["xp"] = 0
        while True:
            req = calculate_xp_required(state["level"])
            if state["xp"] >= req:
                state["xp"] -= req
                state["level"] += 1
            else:
                break
    elif db_col == "energy":
        state["energy"] = max(0.0, min(100.0, float(state["energy"])))
    else:
        state[db_col] = int(state[db_col])
        
    save_state(state)
    return state

def save_chat_message(role: str, message: str, bot_type: str = "coach"):
    """Persist a chat message (role='user' or 'ai') to the database with bot_type."""
    import datetime
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_chat_message
        neon_save_chat_message(role, message, bot_type)
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ai_chat_history (role, message, timestamp, bot_type) VALUES (?, ?, ?, ?)",
            (role, message, timestamp, bot_type)
        )
        conn.commit()
        conn.close()


def get_chat_history(limit: int = 50, bot_type: str = "coach") -> list:
    """Fetch the last `limit` messages from ai_chat_history in chronological order filtered by bot_type."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_chat_history
        return neon_get_chat_history(limit=limit, bot_type=bot_type)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, message, timestamp FROM ai_chat_history WHERE bot_type = ? ORDER BY id DESC LIMIT ?",
        (bot_type, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    # Reverse so oldest is first
    return [{"role": r["role"], "message": r["message"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def clear_chat_history(bot_type: str = "coach"):
    """Delete all chat history messages for a specific bot_type from the database."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_clear_chat_history
        neon_clear_chat_history(bot_type)
        return
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_chat_history WHERE bot_type = ?", (bot_type,))
        conn.commit()
        conn.close()


def log_activity_file(doing: str, accomplished: str):
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp} Log\n- **Current Activity**: {doing}\n- **Accomplished**: {accomplished}\n"
    os.makedirs(os.path.dirname(ACTIVITY_LOG_PATH), exist_ok=True)
    try:
        with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[Activity Log] Error appending to log: {e}")


# init_db is called explicitly by main.py and tests, not at import time.


def save_bad_experience(title: str, who: str, what_happened: str, my_lesson: str, intensity: int) -> dict:
    """Persist a bad experience / scold log entry and return the saved record."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_bad_experience
        return neon_save_bad_experience(title, who, what_happened, my_lesson, intensity)
    import datetime
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bad_experiences (title, who, what_happened, my_lesson, intensity, timestamp, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title.strip(), who.strip(), what_happened.strip(), my_lesson.strip(), intensity, timestamp, date_str)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
    return {"id": new_id, "timestamp": timestamp, "date": date_str}


def get_bad_experiences(date: str = None, limit: int = 100) -> list:
    """Fetch bad experience entries, optionally filtered by date."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_bad_experiences
        return neon_get_bad_experiences(date_filter=date, limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if date:
        cursor.execute(
            "SELECT * FROM bad_experiences WHERE date = ? ORDER BY id DESC", (date,)
        )
    else:
        cursor.execute(
            "SELECT * FROM bad_experiences ORDER BY id DESC LIMIT ?", (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_human_connection(person_name: str, context_meeting: str, what_happened: str, what_i_felt: str, emoji: str = "🤝") -> dict:
    """Save a human encounter/connection entry and award +1 HRT (Heart/Humanity)."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_human_connection
        neon_save_human_connection(person_name, context_meeting, what_happened, what_i_felt, emoji)
        new_state = update_stat("hrt", 1.0)
        log_activity_file("Human Connection Logged", f"Met {person_name} ({emoji}) - {context_meeting}. +1 HRT awarded!")
        return {"status": "success", "hrt_awarded": 1, "person_name": person_name, "current_hrt": new_state.get("heart", 10)}
    import datetime
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().isoformat()
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO human_connections (person_name, context_meeting, what_happened, what_i_felt, emoji, timestamp, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (person_name, context_meeting, what_happened, what_i_felt, emoji, timestamp, today))
        conn.commit()
        conn.close()
    new_state = update_stat("hrt", 1.0)
    log_activity_file("Human Connection Logged", f"Met {person_name} ({emoji}) - {context_meeting}. +1 HRT awarded!")
    return {"status": "success", "hrt_awarded": 1, "person_name": person_name, "current_hrt": new_state.get("heart", 10)}

def get_human_connections(limit: int = 50) -> list:
    """Fetch human connection entries for reflection and future emotional analysis."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_human_connections
        return neon_get_human_connections(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM human_connections ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_human_context(name: str) -> dict:
    """Save a custom encounter context/location to database."""
    name = name.strip()
    if not name:
        return {"status": "error", "message": "Context name cannot be empty"}
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_human_context
        return neon_save_human_context(name)
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO human_contexts (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
    return {"status": "success", "name": name}

def get_human_contexts() -> list:
    """Fetch all saved human encounter contexts/locations."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_human_contexts
        return neon_get_human_contexts()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM human_contexts ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r["name"] for r in rows]

def get_unique_people() -> list:
    """Fetch distinct person names from both human_connections and teaching_sessions."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_unique_people
        return neon_get_unique_people()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Merge people from human connections and teaching sessions
    cursor.execute("""
        SELECT DISTINCT name FROM (
            SELECT person_name AS name FROM human_connections WHERE person_name != ''
            UNION
            SELECT person AS name FROM teaching_sessions WHERE person != ''
        ) combined
        ORDER BY name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [r["name"] for r in rows]

def get_recent_offline_logs(limit: int = 3) -> str:
    """Fetch the latest manual offline logs to feed into AI context."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    logs = []
    
    # 1. Study Journal
    try:
        cursor.execute("SELECT * FROM study_journal ORDER BY id DESC LIMIT ?", (limit,))
        for r in cursor.fetchall():
            logs.append(f"STUDY JOURNAL (Date: {r['date']}): Topic - {r['topic']}, Notes - {r['notes']}, Mood - {r['mood']}")
    except Exception:
        pass
        
    # 2. Bad Experiences
    try:
        cursor.execute("SELECT * FROM bad_experiences ORDER BY id DESC LIMIT ?", (limit,))
        for r in cursor.fetchall():
            logs.append(f"RAGE FUEL (Date: {r['date']}): Title - {r['title']}, What Happened - {r['what_happened']}, Lesson - {r['my_lesson']}, Intensity - {r['intensity']}/5")
    except Exception:
        pass
        
    # 3. Human Connections & Stranger Encounters (+1 HRT)
    try:
        cursor.execute("SELECT * FROM human_connections ORDER BY id DESC LIMIT ?", (limit,))
        for r in cursor.fetchall():
            logs.append(f"HUMAN CONNECTION / HRT LOG (Date: {r['date']}): Met {r['person_name']} ({r['emoji']}) at {r['context_meeting']} - What Happened: {r['what_happened']}, Feelings: {r['what_i_felt']}")
    except Exception:
        pass

    # Stoic Reflections & Mindset Daily Log
    try:
        cursor.execute("SELECT * FROM stoic_logs ORDER BY id DESC LIMIT ?", (limit,))
        for r in cursor.fetchall():
            logs.append(f"DAILY STOIC & MINDSET REFLECTION (Date: {r['date']}): Reflection: {r['reflection']} | Attitude Score: {r['attitude_score']}/10 | Stoic Lesson: {r['stoic_lesson']}")
    except Exception:
        pass

    conn.close()
    
    # 4. Activity Log
    try:
        if os.path.exists(ACTIVITY_LOG_PATH):
            with open(ACTIVITY_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    logs.append("RECENT ACTIVITY LOGS:\n" + "".join(lines[-15:]))
    except Exception:
        pass
        
    # 5. Exam Scratchpad
    try:
        if os.path.exists(EXAM_SCRATCHPAD_PATH):
            with open(EXAM_SCRATCHPAD_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logs.append("EXAM SCRATCHPAD (Current Work):\n" + content)
    except Exception:
        pass

        
    return "\n\n".join(logs)


def save_stoic_reflection(reflection: str, attitude_score: int, stoic_lesson: str) -> dict:
    """Save a daily stoic/mindset log and award +2 STC (Stoicism/Stoic) stat point."""
    from datetime import datetime
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_stoic_reflection
        neon_save_stoic_reflection(reflection, attitude_score, stoic_lesson)
        update_stat("STOIC", 2)
        log_activity_file("Logged Stoic Reflection", f"Mindset score: {attitude_score}/10. Earned +2 STC.")
        return {"status": "success", "message": "Stoic reflection logged successfully! Gained +2 STC.", "state": get_state()}
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    today_str = datetime.now().date().isoformat()
    with _DB_WRITE_LOCK:
        cursor.execute("""
        INSERT INTO stoic_logs (reflection, attitude_score, stoic_lesson, timestamp, date)
        VALUES (?, ?, ?, ?, ?)
        """, (reflection, attitude_score, stoic_lesson, now_str, today_str))
        conn.commit()
    conn.close()
    update_stat("STOIC", 2)
    log_activity_file("Logged Stoic Reflection", f"Mindset score: {attitude_score}/10. Earned +2 STC.")
    return {"status": "success", "message": "Stoic reflection logged successfully! Gained +2 STC.", "state": get_state()}

def get_stoic_reflections(limit: int = 50) -> list:
    """Fetch recent daily stoic reflections."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_stoic_reflections
        return neon_get_stoic_reflections(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stoic_logs ORDER BY date DESC, id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── English translation & lessons helpers ────────────────────────────────────

def save_translation(query: str, definition: str, translation: str):
    """Save an English-Tamil translation query to the database."""
    from datetime import datetime
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    with _DB_WRITE_LOCK:
        cursor.execute("""
        INSERT INTO translation_history (query, definition, translation, timestamp)
        VALUES (?, ?, ?, ?)
        """, (query, definition, translation, now_str))
        conn.commit()
    conn.close()

def get_translation_history(limit: int = 50) -> list:
    """Get the recent translation queries."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM translation_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cached_daily_lesson(date_str: str) -> dict:
    """Retrieve the cached daily lesson for a given date if it exists."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_english_lessons WHERE date = ?", (date_str,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

def save_cached_daily_lesson(date_str: str, lesson: dict):
    """Cache the daily generated lesson in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("""
        INSERT OR REPLACE INTO daily_english_lessons (
            date, word, word_tamil, word_definition, word_example,
            spoken_phrase, spoken_tamil, spoken_explanation, spoken_example,
            grammar_rule, grammar_explanation, grammar_quiz, grammar_quiz_explanation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date_str,
            lesson.get("word"),
            lesson.get("word_tamil"),
            lesson.get("word_definition"),
            lesson.get("word_example"),
            lesson.get("spoken_phrase"),
            lesson.get("spoken_tamil"),
            lesson.get("spoken_explanation"),
            lesson.get("spoken_example"),
            lesson.get("grammar_rule"),
            lesson.get("grammar_explanation"),
            lesson.get("grammar_quiz"),
            lesson.get("grammar_quiz_explanation")
        ))
        conn.commit()
    conn.close()

# ─── AI Teacher Topics Checklist helpers ──────────────────────────────────────

def save_teacher_topics(topics: list[str]):
    """Clear existing topics and save the new list of extracted topics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("DELETE FROM teacher_topics")
        for t in topics:
            if t.strip():
                cursor.execute(
                    "INSERT OR IGNORE INTO teacher_topics (name, completed) VALUES (?, 0)",
                    (t.strip(),)
                )
        conn.commit()
    conn.close()

def get_teacher_topics() -> list:
    """Retrieve the current topics checklist."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, completed FROM teacher_topics ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{"name": r["name"], "completed": bool(r["completed"])} for r in rows]

def toggle_teacher_topic(topic_name: str, completed: bool):
    """Toggle completion status of a topic in the checklist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute(
            "UPDATE teacher_topics SET completed = ? WHERE name = ?",
            (1 if completed else 0, topic_name.strip())
        )
        conn.commit()
    conn.close()

def clear_teacher_topics():
    """Clear all topics from the checklist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("DELETE FROM teacher_topics")
        conn.commit()
    conn.close()

def save_teaching_session(person: str, subject: str, topic: str, duration: str, outcome: str, notes: str, date: str, ts: str):
    """Log a teaching session."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_teaching_session
        return neon_save_teaching_session(person, subject, topic, duration, outcome, notes, date, ts)
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute(
            "INSERT INTO teaching_sessions (person, subject, topic, duration, outcome, notes, date, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (person, subject, topic, duration, outcome, notes, date, ts)
        )
        conn.commit()
    conn.close()

def get_teaching_sessions() -> list:
    """Retrieve all logged teaching sessions."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_teaching_sessions
        return neon_get_teaching_sessions()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teaching_sessions ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_translation_history_item(item_id: int):
    """Delete a single translation history entry by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("DELETE FROM translation_history WHERE id = ?", (item_id,))
        conn.commit()
    conn.close()

def clear_translation_history():
    """Clear all translation history entries."""
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("DELETE FROM translation_history")
        conn.commit()
    conn.close()

def get_english_user_progress() -> dict:
    """Get or initialize user progress stats for English Learning & Public Speaking."""
    from datetime import datetime, date, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    today_dt = datetime.now(ist).date()
    today_str = today_dt.isoformat()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM english_user_progress WHERE id = 1")
    row = cursor.fetchone()
    if not row:
        with _DB_WRITE_LOCK:
            cursor.execute("""
            INSERT INTO english_user_progress (id, streak_days, last_active_date, total_speaking_seconds, words_mastered, xp_points, unlocked_badges)
            VALUES (1, 1, ?, 0, 0, 50, '["First Step"]')
            """, (today_str,))
            conn.commit()
        cursor.execute("SELECT * FROM english_user_progress WHERE id = 1")
        row = cursor.fetchone()
    
    prog = dict(row)
    # Check streak update
    last_active = prog.get("last_active_date", "")
    if last_active != today_str:
        try:
            if last_active:
                last_dt = datetime.strptime(last_active, "%Y-%m-%d").date()
                if today_dt - last_dt == timedelta(days=1):
                    prog["streak_days"] += 1
                elif today_dt - last_dt > timedelta(days=1):
                    prog["streak_days"] = 1
            else:
                prog["streak_days"] = 1
            prog["last_active_date"] = today_str
            with _DB_WRITE_LOCK:
                cursor.execute("""
                UPDATE english_user_progress SET streak_days = ?, last_active_date = ? WHERE id = 1
                """, (prog["streak_days"], today_str))
                conn.commit()
        except Exception:
            pass
    conn.close()
    return prog

def save_english_speech_log(topic: str, transcript: str, duration_seconds: int, wpm: int, filler_count: int, fluency_score: int, feedback: str) -> dict:
    """Log a public speaking session and update XP / streak / badge progress."""
    from datetime import datetime, date
    now_str = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    with _DB_WRITE_LOCK:
        cursor.execute("""
        INSERT INTO english_speech_logs (topic, transcript, duration_seconds, wpm, filler_count, fluency_score, feedback, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (topic, transcript, duration_seconds, wpm, filler_count, fluency_score, feedback, now_str))
        
        # Update progress stats
        cursor.execute("SELECT total_speaking_seconds, xp_points, unlocked_badges FROM english_user_progress WHERE id = 1")
        row = cursor.fetchone()
        current_secs = row[0] if row else 0
        current_xp = row[1] if row else 0
        badges_json = row[2] if row else "[]"
        try:
            import json
            badges = json.loads(badges_json)
        except Exception:
            badges = []

        new_secs = current_secs + duration_seconds
        new_xp = current_xp + 30 + (fluency_score // 2)

        if "Stage Ready" not in badges and new_secs >= 300:
            badges.append("Stage Ready")
        if "Public Speaker" not in badges and new_secs >= 1800:
            badges.append("Public Speaker")
        if "High Fluency" not in badges and fluency_score >= 85:
            badges.append("High Fluency")

        cursor.execute("""
        UPDATE english_user_progress
        SET total_speaking_seconds = ?, xp_points = ?, unlocked_badges = ?, last_active_date = ?
        WHERE id = 1
        """, (new_secs, new_xp, json.dumps(badges), date.today().isoformat()))

        conn.commit()
    conn.close()
    return {"status": "ok", "earned_xp": 30 + (fluency_score // 2), "total_speaking_seconds": new_secs}

# ─── Mind OS Helpers ─────────────────────────────────────────────────────────

def save_reality_check(trigger_event: str, my_interpretation: str, evidence_for: str, evidence_against: str, alternative_explanation: str, verified_outcome: str, distortions: str) -> dict:
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_reality_check
        result = neon_save_reality_check(trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions)
        update_stat("xp", 15)
        state = get_state()
        if state:
            state["mindos_completed"] = 1
            save_state(state)
        log_activity_file("CBT Reality Check Completed", f"Reframed thought: '{my_interpretation}' -> '{alternative_explanation}'. Awarded +15 XP.")
        return {"status": "success", "id": result["id"], "earned_xp": 15}
    from datetime import datetime
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().isoformat()
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO mind_reality_checks (trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions, date, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions, today, timestamp))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
    update_stat("xp", 15)
    state = get_state()
    if state:
        state["mindos_completed"] = 1
        save_state(state)
    log_activity_file("CBT Reality Check Completed", f"Reframed thought: '{my_interpretation}' -> '{alternative_explanation}'. Awarded +15 XP.")
    return {"status": "success", "id": new_id, "earned_xp": 15}

def get_reality_checks(limit: int = 50) -> list:
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_reality_checks
        return neon_get_reality_checks(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_reality_checks ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def verify_reality_check(check_id: int, verified_outcome: str) -> dict:
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE mind_reality_checks SET verified_outcome = ? WHERE id = ?", (verified_outcome, check_id))
        conn.commit()
        conn.close()
    return {"status": "success", "id": check_id}

def save_rumination_log(trigger_convo: str, intensity: int, duration_mins: int, distress_score: int, grounding_used: int, alternative_thought: str) -> dict:
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_rumination_log
        result = neon_save_rumination_log(trigger_convo, intensity, duration_mins, distress_score, grounding_used, alternative_thought)
        update_stat("stoic", 2)
        update_stat("xp", 10)
        state = get_state()
        if state:
            state["mindos_completed"] = 1
            save_state(state)
        log_activity_file("Rumination Grounded", f"Managed mental replay. Gained +2 STC, +10 XP.")
        return {"status": "success", "id": result["id"], "earned_stc": 2, "earned_xp": 10}
    from datetime import datetime
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().isoformat()
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO mind_rumination_logs (trigger_convo, intensity, duration_mins, distress_score, grounding_used, alternative_thought, date, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (trigger_convo, intensity, duration_mins, distress_score, grounding_used, alternative_thought, today, timestamp))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
    update_stat("stoic", 2)
    update_stat("xp", 10)
    state = get_state()
    if state:
        state["mindos_completed"] = 1
        save_state(state)
    log_activity_file("Rumination Grounded", f"Managed mental replay from conversation: '{trigger_convo}'. Gained +2 STC, +10 XP.")
    return {"status": "success", "id": new_id, "earned_stc": 2, "earned_xp": 10}

def get_rumination_logs(limit: int = 50) -> list:
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_rumination_logs
        return neon_get_rumination_logs(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_rumination_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_relationship(person_name: str, trust_score: int, leave_urge: int, closeness: int, last_interaction_date: str, notes: str, status: str) -> dict:
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_relationship
        result = neon_save_relationship(person_name, trust_score, leave_urge, closeness, last_interaction_date, notes, status)
        state = get_state()
        if state:
            state["mindos_completed"] = 1
            save_state(state)
        log_activity_file("Relationship Profile Updated", f"Updated alignment for {person_name}. Trust: {trust_score}/10.")
        return {"status": "success", "person_name": person_name}
    from datetime import datetime
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().isoformat()
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO mind_relationships (person_name, trust_score, leave_urge, closeness, last_interaction_date, notes, status, date, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (person_name.strip(), trust_score, leave_urge, closeness, last_interaction_date, notes, status, today, timestamp))
        conn.commit()
        conn.close()
    state = get_state()
    if state:
        state["mindos_completed"] = 1
        save_state(state)
    log_activity_file("Relationship Profile Updated", f"Updated alignment for {person_name}. Trust: {trust_score}/10, Leave Urge: {leave_urge}/10, Closeness: {closeness}/10.")
    return {"status": "success", "person_name": person_name}

def get_relationships() -> list:
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_relationships
        return neon_get_relationships()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_relationships ORDER BY trust_score DESC, closeness DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_mind_summary() -> dict:
    if IS_SERVERLESS:
        # Query Neon pg_mind_* tables
        try:
            import psycopg2
            from config import DATABASE_URL
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*), SUM(CASE WHEN verified_outcome='Pending' THEN 1 ELSE 0 END) FROM pg_mind_reality_checks")
                    rc = cur.fetchone(); total_rc = rc[0] or 0; pending_rc = rc[1] or 0
                    cur.execute("SELECT AVG(CAST(distress_score AS FLOAT)), AVG(CAST(duration_mins AS FLOAT)), SUM(grounding_used) FROM pg_mind_rumination_logs")
                    rl = cur.fetchone(); avg_distress = round(rl[0], 1) if rl[0] else 0.0; avg_duration = round(rl[1], 1) if rl[1] else 0.0; total_groundings = rl[2] or 0
                    cur.execute("SELECT COUNT(*), SUM(CASE WHEN CAST(leave_urge AS INT) >= CAST(trust_score AS INT) AND status='Active' THEN 1 ELSE 0 END) FROM pg_mind_relationships")
                    rel = cur.fetchone(); total_rels = rel[0] or 0; warning_rels = rel[1] or 0
                    cur.execute("SELECT COUNT(*), SUM(CAST(duration_mins AS INT)) FROM pg_mind_meditation_logs")
                    med = cur.fetchone(); total_med = med[0] or 0; total_med_mins = med[1] or 0
            return {"total_reality_checks": total_rc, "pending_reality_checks": pending_rc, "avg_rumination_distress": avg_distress, "avg_rumination_duration": avg_duration, "total_groundings": total_groundings, "total_relationships": total_rels, "warning_relationships": warning_rels, "total_meditations": total_med, "total_meditation_minutes": total_med_mins}
        except Exception as e:
            print(f"[Mind OS] Neon summary failed: {e}")
            return {"total_reality_checks": 0, "pending_reality_checks": 0, "avg_rumination_distress": 0.0, "avg_rumination_duration": 0.0, "total_groundings": 0, "total_relationships": 0, "warning_relationships": 0, "total_meditations": 0, "total_meditation_minutes": 0}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN verified_outcome = 'Pending' THEN 1 ELSE 0 END) FROM mind_reality_checks")
    rc_row = cursor.fetchone(); total_rc = rc_row[0] if rc_row else 0; pending_rc = rc_row[1] if rc_row and rc_row[1] is not None else 0
    cursor.execute("SELECT AVG(distress_score), AVG(duration_mins), SUM(grounding_used) FROM mind_rumination_logs")
    rl_row = cursor.fetchone(); avg_distress = round(rl_row[0], 1) if rl_row and rl_row[0] is not None else 0.0; avg_duration = round(rl_row[1], 1) if rl_row and rl_row[1] is not None else 0.0; total_groundings = rl_row[2] if rl_row and rl_row[2] is not None else 0
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN leave_urge >= trust_score AND status = 'Active' THEN 1 ELSE 0 END) FROM mind_relationships")
    rel_row = cursor.fetchone(); total_rels = rel_row[0] if rel_row else 0; warning_rels = rel_row[1] if rel_row and rel_row[1] is not None else 0
    cursor.execute("SELECT COUNT(*), SUM(duration_mins) FROM mind_meditation_logs")
    med_row = cursor.fetchone(); total_med = med_row[0] if med_row else 0; total_med_mins = med_row[1] if med_row and med_row[1] is not None else 0
    conn.close()
    return {"total_reality_checks": total_rc, "pending_reality_checks": pending_rc, "avg_rumination_distress": avg_distress, "avg_rumination_duration": avg_duration, "total_groundings": total_groundings, "total_relationships": total_rels, "warning_relationships": warning_rels, "total_meditations": total_med, "total_meditation_minutes": total_med_mins}

def save_meditation_log(duration_mins: int, track_name: str) -> dict:
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_meditation_log
        result = neon_save_meditation_log(duration_mins, track_name)
        update_stat("stoic", 2)
        update_stat("wil", 1)
        state = get_state()
        if state:
            state["meditation_completed"] = 1
            state["mindos_completed"] = 1
            save_state(state)
        new_state = update_stat("xp", 20)
        log_activity_file("Meditation Session Completed", f"Completed {duration_mins} mins. +20 XP, +2 STC, +1 WIL.")
        return {"status": "success", "id": result["id"], "earned_xp": 20, "earned_stc": 2, "earned_wil": 1, "level": new_state.get("level", 1), "xp": new_state.get("xp", 0)}
    from datetime import datetime, date
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().isoformat()
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO mind_meditation_logs (duration_mins, track_name, date, timestamp)
        VALUES (?, ?, ?, ?)
        """, (duration_mins, track_name, today, timestamp))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
    update_stat("stoic", 2)
    update_stat("wil", 1)
    state = get_state()
    if state:
        state["meditation_completed"] = 1
        state["mindos_completed"] = 1
        save_state(state)
    new_state = update_stat("xp", 20)
    log_activity_file("Meditation Session Completed", f"Completed {duration_mins} minutes of focused meditation listening to '{track_name}'. Awarded +20 XP, +2 STC, +1 WIL.")
    return {"status": "success", "id": new_id, "earned_xp": 20, "earned_stc": 2, "earned_wil": 1, "level": new_state.get("level", 1), "xp": new_state.get("xp", 0)}


def get_meditation_logs(limit: int = 50) -> list:
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_meditation_logs
        return neon_get_meditation_logs(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_meditation_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def process_health_sync(steps: int = 0, distance_km: float = 0.0, active_minutes: int = 0, sleep_hours: float = 0.0, resting_hr: Optional[int] = None, log_date: Optional[str] = None) -> dict:
    """
    Processes health metrics from Google Health Connect / MacroDroid / Termux / Manual Logger.
    Calculates:
    - Step Count: +10 XP & +1 WIL per 1,000 steps.
    - Active Workout Minutes: +2 STR & +15 XP per 10 active mins (+2 XP / min).
    - Sleep Recovery: +35% Cognitive Energy if sleep >= 7.0 hrs (+15% if >= 5.5 hrs).
    - Resting HR: +1 HRT if resting HR in optimal range (50-70 bpm).
    """
    from datetime import date
    log_date = log_date or date.today().isoformat()

    step_xp    = (steps // 1000) * 10
    wil_gained = steps // 1000
    str_gained = (active_minutes // 10) * 2
    active_xp  = active_minutes * 2
    total_xp   = step_xp + active_xp

    energy_restored = 0.0
    if sleep_hours >= 7.0:
        energy_restored = 35.0
    elif sleep_hours >= 5.5:
        energy_restored = 15.0

    hrt_gained = 1 if (resting_hr and 50 <= resting_hr <= 70) else 0

    state = get_state() or {}
    if state:
        state["xp"] = state.get("xp", 0) + total_xp
        state["wil"] = state.get("wil", 10) + wil_gained
        state["str"] = state.get("str", 10) + str_gained
        state["heart"] = state.get("heart", 10) + hrt_gained
        state["health_completed"] = 1
        if steps >= 1000 or distance_km >= 0.5 or active_minutes >= 10:
            state["walk_completed"] = 1
        if energy_restored > 0:
            state["energy"] = min(100.0, state.get("energy", 100.0) + energy_restored)
        save_state(state)

    if IS_SERVERLESS:
        from engine.neon_db import neon_save_health_log
        neon_save_health_log(log_date, steps, distance_km, active_minutes, sleep_hours, resting_hr or 0, total_xp, wil_gained, str_gained, hrt_gained, energy_restored)
    else:
        with _DB_WRITE_LOCK:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_sync_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_date TEXT NOT NULL,
                    steps INTEGER DEFAULT 0,
                    distance_km REAL DEFAULT 0.0,
                    active_minutes INTEGER DEFAULT 0,
                    sleep_hours REAL DEFAULT 0.0,
                    resting_hr INTEGER DEFAULT 0,
                    xp_awarded INTEGER DEFAULT 0,
                    wil_gained INTEGER DEFAULT 0,
                    str_gained INTEGER DEFAULT 0,
                    hrt_gained INTEGER DEFAULT 0,
                    energy_restored REAL DEFAULT 0.0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO health_sync_logs
                (log_date, steps, distance_km, active_minutes, sleep_hours, resting_hr, xp_awarded, wil_gained, str_gained, hrt_gained, energy_restored)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_date, steps, distance_km, active_minutes, sleep_hours, resting_hr or 0, total_xp, wil_gained, str_gained, hrt_gained, energy_restored))
            conn.commit()
            conn.close()

    log_activity_file("Health & Fitness Sync", f"Synced {steps:,} steps ({distance_km} km), {sleep_hours}h sleep, {active_minutes}m active. +{total_xp} XP, +{wil_gained} WIL, +{str_gained} STR, +{energy_restored}% Energy.")

    return {
        "status": "SUCCESS",
        "log_date": log_date,
        "steps": steps,
        "distance_km": distance_km,
        "active_minutes": active_minutes,
        "sleep_hours": sleep_hours,
        "xp_awarded": total_xp,
        "wil_gained": wil_gained,
        "str_gained": str_gained,
        "hrt_gained": hrt_gained,
        "energy_restored": energy_restored
    }

def get_health_sync_history(limit: int = 50) -> list:
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_health_logs
        return neon_get_health_logs(limit=limit)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            steps INTEGER DEFAULT 0,
            distance_km REAL DEFAULT 0.0,
            active_minutes INTEGER DEFAULT 0,
            sleep_hours REAL DEFAULT 0.0,
            resting_hr INTEGER DEFAULT 0,
            xp_awarded INTEGER DEFAULT 0,
            wil_gained INTEGER DEFAULT 0,
            str_gained INTEGER DEFAULT 0,
            hrt_gained INTEGER DEFAULT 0,
            energy_restored REAL DEFAULT 0.0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT * FROM health_sync_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]




