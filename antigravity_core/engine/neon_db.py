"""
neon_db.py — Neon PostgreSQL helpers for serverless (Vercel) mode
=================================================================
When IS_SERVERLESS=True, SQLite is unavailable (read-only FS).
All features (books, reading logs, bad experiences, chat history,
Mind OS, human connections, stoic logs) read/write here instead.
"""

import datetime
from typing import Optional
import psycopg2
import psycopg2.extras

from config import DATABASE_URL


def _conn():
    """Open a Neon PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today():
    return datetime.date.today().isoformat()


# ─── Saved Books ───────────────────────────────────────────────────────────────

def _ensure_saved_books_table(cur):
    """Create pg_saved_books table if it doesn't exist (may be missing if migration ran with empty data)."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_saved_books (
            id SERIAL PRIMARY KEY,
            title TEXT UNIQUE NOT NULL,
            created_at TEXT
        )
    """)


def neon_get_saved_books() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _ensure_saved_books_table(cur)
            cur.execute("SELECT id, title, created_at FROM pg_saved_books ORDER BY title ASC")
            return [dict(r) for r in cur.fetchall()]


def neon_save_book(title: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            _ensure_saved_books_table(cur)
            cur.execute(
                "INSERT INTO pg_saved_books (title, created_at) VALUES (%s, %s) ON CONFLICT (title) DO NOTHING",
                (title.strip(), _now())
            )
    return {"status": "success"}


def neon_delete_book(title: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pg_saved_books WHERE title = %s", (title.strip(),))
    return {"status": "success"}


# ─── Reading Logs ──────────────────────────────────────────────────────────────

def neon_get_reading_logs(limit: int = 100) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM pg_reading_logs ORDER BY id DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]


def neon_save_reading_log(book_title: str, page_from: int, page_to: int, pages_read: int) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_reading_logs (book_title, page_from, page_to, pages_read, timestamp, date) VALUES (%s,%s,%s,%s,%s,%s)",
                (book_title, str(page_from), str(page_to), str(pages_read), ts, today)
            )
    return {"status": "success", "timestamp": ts}


def neon_delete_reading_log(log_id: int):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pg_reading_logs WHERE id = %s", (log_id,))


# ─── Bad Experiences / Rage Wall ───────────────────────────────────────────────

def neon_get_bad_experiences(date_filter: str = None, limit: int = 100) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if date_filter:
                cur.execute(
                    "SELECT * FROM pg_bad_experiences WHERE date = %s ORDER BY id DESC",
                    (date_filter,)
                )
            else:
                cur.execute(
                    "SELECT * FROM pg_bad_experiences ORDER BY id DESC LIMIT %s", (limit,)
                )
            return [dict(r) for r in cur.fetchall()]


def neon_save_bad_experience(title: str, who: str, what_happened: str, my_lesson: str, intensity: int) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_bad_experiences (title, who, what_happened, my_lesson, intensity, timestamp, date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (title, who, what_happened, my_lesson, str(intensity), ts, today)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts, "date": today}


# ─── AI Chat History ───────────────────────────────────────────────────────────

def neon_save_chat_message(role: str, message: str, bot_type: str = "coach"):
    ts = _now()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_ai_chat_history (role, message, timestamp, bot_type) VALUES (%s,%s,%s,%s)",
                (role, message, ts, bot_type)
            )


def neon_get_chat_history(limit: int = 50, bot_type: str = "coach") -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT role, message, timestamp FROM pg_ai_chat_history WHERE bot_type=%s ORDER BY id DESC LIMIT %s",
                (bot_type, limit)
            )
            rows = cur.fetchall()
    return [{"role": r["role"], "message": r["message"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def neon_clear_chat_history(bot_type: str = "coach"):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pg_ai_chat_history WHERE bot_type=%s", (bot_type,))


# ─── Human Connections ─────────────────────────────────────────────────────────

def neon_save_human_connection(person_name: str, context_meeting: str, what_happened: str, what_i_felt: str, emoji: str = "🤝") -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_human_connections (person_name, context_meeting, what_happened, what_i_felt, emoji, timestamp, date) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (person_name, context_meeting, what_happened, what_i_felt, emoji, ts, today)
            )
    return {"status": "success", "timestamp": ts}


def neon_get_human_connections(limit: int = 50) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM pg_human_connections ORDER BY id DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]


def neon_get_human_contexts() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name FROM pg_human_contexts ORDER BY id ASC")
            return [r["name"] for r in cur.fetchall()]


def neon_save_human_context(name: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_human_contexts (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (name,)
            )
    return {"status": "success", "name": name}


def neon_get_unique_people() -> list:
    """Fetch unique people from both human_connections and teaching_sessions."""
    with _conn() as conn:
        with conn.cursor() as cur:
            # Merge people from human connections and teaching sessions
            cur.execute("""
                SELECT DISTINCT name FROM (
                    SELECT person_name AS name FROM pg_human_connections WHERE person_name != ''
                    UNION
                    SELECT person AS name FROM pg_teaching_sessions WHERE person != ''
                ) combined
                ORDER BY name
            """)
            return [r[0] for r in cur.fetchall()]


# ─── Stoic Logs ────────────────────────────────────────────────────────────────

def neon_save_stoic_reflection(reflection: str, attitude_score: int, stoic_lesson: str) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_stoic_logs (reflection, attitude_score, stoic_lesson, timestamp, date) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (reflection, str(attitude_score), stoic_lesson, ts, today)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


def neon_get_stoic_reflections(limit: int = 50) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM pg_stoic_logs ORDER BY id DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]


# ─── Mind OS ───────────────────────────────────────────────────────────────────

def neon_save_reality_check(trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pg_mind_reality_checks
                (trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions, date, timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (trigger_event, my_interpretation, evidence_for, evidence_against, alternative_explanation, verified_outcome, distortions, today, ts)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


def neon_get_reality_checks(limit: int = 50) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pg_mind_reality_checks ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]


def neon_save_rumination_log(trigger_convo, intensity, duration_mins, distress_score, grounding_used, alternative_thought) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pg_mind_rumination_logs
                (trigger_convo, intensity, duration_mins, distress_score, grounding_used, alternative_thought, date, timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (trigger_convo, str(intensity), str(duration_mins), str(distress_score), grounding_used, alternative_thought, today, ts)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


def neon_get_rumination_logs(limit: int = 50) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pg_mind_rumination_logs ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]


def neon_get_relationships() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pg_mind_relationships ORDER BY id ASC")
            return [dict(r) for r in cur.fetchall()]


def neon_save_relationship(person_name, trust_score, leave_urge, closeness, last_interaction_date, notes, status) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pg_mind_relationships
                (person_name, trust_score, leave_urge, closeness, last_interaction_date, notes, status, date, timestamp)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (person_name) DO UPDATE SET
                trust_score=EXCLUDED.trust_score, leave_urge=EXCLUDED.leave_urge,
                closeness=EXCLUDED.closeness, last_interaction_date=EXCLUDED.last_interaction_date,
                notes=EXCLUDED.notes, status=EXCLUDED.status, timestamp=EXCLUDED.timestamp
                RETURNING id""",
                (person_name, str(trust_score), leave_urge, str(closeness), last_interaction_date, notes, status, today, ts)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


def neon_get_meditation_logs(limit: int = 50) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pg_mind_meditation_logs ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]


def neon_save_meditation_log(duration_mins: int, track_name: str) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_mind_meditation_logs (duration_mins, track_name, date, timestamp) VALUES (%s,%s,%s,%s) RETURNING id",
                (str(duration_mins), track_name, today, ts)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


# ─── Study Journal ─────────────────────────────────────────────────────────────

def neon_get_study_journal(limit: int = 100) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pg_study_journal ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]


def neon_save_study_journal(topic: str, notes: str, subject_id: str, item_id: str, mood: str) -> dict:
    ts = _now()
    today = _today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pg_study_journal (topic, notes, subject_id, item_id, mood, timestamp, date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (topic, notes, subject_id, item_id, mood, ts, today)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": ts}


# ─── Workout Logs ──────────────────────────────────────────────────────────────

def _init_pg_workout_log_table(cur):
    """Auto-create pg_workout_log table if it doesn't exist."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_workout_log (
            id SERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            category TEXT NOT NULL,
            workout TEXT NOT NULL,
            variations TEXT DEFAULT '',
            sets TEXT DEFAULT '',
            duration_minutes INTEGER DEFAULT 0
        );
    """)


def neon_save_workout_log(timestamp: str, category: str, workout: str, variations: str, sets: str, duration_minutes: int) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_workout_log_table(cur)
            cur.execute(
                "INSERT INTO pg_workout_log (timestamp, category, workout, variations, sets, duration_minutes) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (timestamp, category, workout, variations or "", sets or "", duration_minutes or 0)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": timestamp}


def neon_get_workout_history(limit: str = None) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _init_pg_workout_log_table(cur)
            if limit == "all":
                cur.execute(
                    "SELECT timestamp AS \"Timestamp\", category AS \"Category\", workout AS \"Workout\", "
                    "variations AS \"Variations\", sets AS \"Sets\", duration_minutes AS \"Duration_Minutes\", id "
                    "FROM pg_workout_log ORDER BY timestamp DESC, id DESC"
                )
            else:
                cur.execute(
                    "SELECT timestamp AS \"Timestamp\", category AS \"Category\", workout AS \"Workout\", "
                    "variations AS \"Variations\", sets AS \"Sets\", duration_minutes AS \"Duration_Minutes\", id "
                    "FROM pg_workout_log ORDER BY timestamp DESC, id DESC LIMIT 100"
                )
            return [dict(r) for r in cur.fetchall()]


def neon_delete_workout_by_id(pg_id: int):
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_workout_log_table(cur)
            cur.execute("DELETE FROM pg_workout_log WHERE id = %s", (pg_id,))


def neon_delete_workout_by_timestamp(timestamp: str):
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_workout_log_table(cur)
            cur.execute("DELETE FROM pg_workout_log WHERE timestamp = %s", (timestamp,))


def neon_delete_study_entry(entry_id: int):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pg_study_journal WHERE id = %s", (entry_id,))


# ─── Teaching Sessions ─────────────────────────────────────────────────────────

def neon_save_teaching_session(person: str, subject: str, topic: str, duration: str, outcome: str, notes: str, date: str, ts: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pg_teaching_sessions (
                    id SERIAL PRIMARY KEY,
                    person TEXT NOT NULL,
                    subject TEXT,
                    topic TEXT NOT NULL,
                    duration TEXT,
                    outcome TEXT,
                    notes TEXT,
                    date TEXT,
                    ts TEXT
                );
            """)
            cur.execute(
                "INSERT INTO pg_teaching_sessions (person, subject, topic, duration, outcome, notes, date, ts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (person, subject, topic, duration, outcome, notes, date, ts)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id}


def neon_get_teaching_sessions() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pg_teaching_sessions (
                    id SERIAL PRIMARY KEY,
                    person TEXT NOT NULL,
                    subject TEXT,
                    topic TEXT NOT NULL,
                    duration TEXT,
                    outcome TEXT,
                    notes TEXT,
                    date TEXT,
                    ts TEXT
                );
            """)
            cur.execute("SELECT * FROM pg_teaching_sessions ORDER BY id ASC")
            return [dict(r) for r in cur.fetchall()]


# ─── Body Metrics ──────────────────────────────────────────────────────────────

def neon_save_body_metrics(timestamp: str, weight_kg: float, body_fat_pct: float,
                            waist_cm: float, chest_cm: float, arms_cm: float,
                            thigh_cm: float, notes: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pg_body_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    weight_kg REAL,
                    body_fat_pct REAL,
                    waist_cm REAL,
                    chest_cm REAL,
                    arms_cm REAL,
                    thigh_cm REAL,
                    notes TEXT
                );
            """)
            cur.execute(
                "INSERT INTO pg_body_metrics (timestamp, weight_kg, body_fat_pct, waist_cm, chest_cm, arms_cm, thigh_cm, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (timestamp, weight_kg, body_fat_pct, waist_cm, chest_cm, arms_cm, thigh_cm, notes)
            )
            new_id = cur.fetchone()[0]
    return {"id": new_id, "timestamp": timestamp}


def neon_get_body_metrics() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pg_body_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    weight_kg REAL,
                    body_fat_pct REAL,
                    waist_cm REAL,
                    chest_cm REAL,
                    arms_cm REAL,
                    thigh_cm REAL,
                    notes TEXT
                );
            """)
            cur.execute("SELECT * FROM pg_body_metrics ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]


# ─── Workout Logs (duplicate removed — see primary implementation above) ────────

def _init_pg_health_logs(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_health_logs (
            id SERIAL PRIMARY KEY,
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
            created_at TEXT DEFAULT now()
        );
    """)

def neon_save_health_log(log_date: str, steps: int, distance_km: float, active_minutes: int, sleep_hours: float, resting_hr: int, xp_awarded: int, wil_gained: int, str_gained: int, hrt_gained: int, energy_restored: float) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_health_logs(cur)
            cur.execute("""
                INSERT INTO pg_health_logs
                (log_date, steps, distance_km, active_minutes, sleep_hours, resting_hr, xp_awarded, wil_gained, str_gained, hrt_gained, energy_restored, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (log_date, steps, distance_km, active_minutes, sleep_hours, resting_hr or 0, xp_awarded, wil_gained, str_gained, hrt_gained, energy_restored, _now()))
            new_id = cur.fetchone()[0]
    return {"id": new_id, "status": "success"}

def _init_pg_office_work_logs(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_office_work_logs (
            id SERIAL PRIMARY KEY,
            workitemid VARCHAR(255),
            description TEXT,
            workdate VARCHAR(50),
            category VARCHAR(100),
            hours NUMERIC(5,2),
            xp_awarded NUMERIC(8,2),
            category_streak INT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Safely create unique index using SAVEPOINT so failure never aborts transaction
    try:
        cur.execute("SAVEPOINT idx_sp;")
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_office_work_item_date
            ON pg_office_work_logs (workitemid, workdate);
        """)
        cur.execute("RELEASE SAVEPOINT idx_sp;")
    except Exception:
        try:
            cur.execute("ROLLBACK TO SAVEPOINT idx_sp;")
        except Exception:
            pass

def neon_log_office_work(work_item_id: str, description: str, work_date: str, category: str, hours: float, xp_awarded: float, category_streak: int, work_log_id: Optional[int] = None) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_office_work_logs(cur)
            # Upsert by (workitemid, workdate) to prevent duplicates
            cur.execute("""
                INSERT INTO pg_office_work_logs (workitemid, description, workdate, category, hours, xp_awarded, category_streak)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workitemid, workdate) DO UPDATE SET
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    hours = EXCLUDED.hours,
                    xp_awarded = EXCLUDED.xp_awarded,
                    category_streak = EXCLUDED.category_streak,
                    logged_at = CURRENT_TIMESTAMP
                RETURNING id;
            """, (work_item_id, description, work_date, category, hours, xp_awarded, category_streak))
            return cur.fetchone()[0]

def neon_get_office_work_logs(limit: int = 300) -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _init_pg_office_work_logs(cur)
            cur.execute("""
                SELECT id AS "workLogId", id, workitemid AS "workItemId", description, workdate AS "workDate", category, hours, xp_awarded, category_streak, logged_at 
                FROM pg_office_work_logs ORDER BY id DESC LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                if r.get("hours") is not None: r["hours"] = float(r["hours"])
                if r.get("xp_awarded") is not None: r["xp_awarded"] = float(r["xp_awarded"])
                if r.get("logged_at") is not None: r["logged_at"] = str(r["logged_at"])
            return rows


# ─── Task Daily Log & Streaks (Serverless) ──────────────────────────────────

def _init_pg_task_daily_log(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_task_daily_log (
            id SERIAL PRIMARY KEY,
            task_key TEXT NOT NULL,
            log_date TEXT NOT NULL,
            completed INTEGER DEFAULT 1,
            logged_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(task_key, log_date)
        );
    """)


def neon_log_task_completion(task_key: str, completed: bool = True, log_date: Optional[str] = None):
    today = log_date or _today()
    val = 1 if completed else 0
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                _init_pg_task_daily_log(cur)
                cur.execute("""
                    INSERT INTO pg_task_daily_log (task_key, log_date, completed, logged_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (task_key, log_date) DO UPDATE
                    SET completed = EXCLUDED.completed, logged_at = NOW()
                """, (task_key, today, val))
    except Exception as e:
        print(f"[Neon] neon_log_task_completion error: {e}")


def neon_get_task_streaks() -> dict:
    from datetime import date as _date, timedelta
    from collections import defaultdict
    today = _date.today()
    results = {}

    TASK_KEYS = [
        "study", "leetcode", "gym", "english", "cooking",
        "nopmo", "reading", "walk", "meditation", "mindos",
        "health", "canvas_semester",
    ]

    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                _init_pg_task_daily_log(cur)
                cutoff = (today - timedelta(days=120)).isoformat()
                cur.execute("""
                    SELECT task_key, log_date, completed
                    FROM pg_task_daily_log
                    WHERE log_date >= %s
                    ORDER BY task_key, log_date DESC
                """, (cutoff,))
                rows = cur.fetchall() or []

                # Also get lifetime total_done for each task
                cur.execute("""
                    SELECT task_key, COUNT(*) as total
                    FROM pg_task_daily_log
                    WHERE completed = 1
                    GROUP BY task_key
                """)
                total_counts = {r["task_key"]: int(r["total"]) for r in cur.fetchall() or []}

        by_task = defaultdict(dict)
        for r in rows:
            by_task[r["task_key"]][r["log_date"]] = bool(r["completed"])

        for tk in TASK_KEYS:
            day_map = by_task.get(tk, {})

            last_30 = []
            for i in range(29, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                last_30.append({"date": d, "done": day_map.get(d, False)})

            done_today     = bool(day_map.get(today.isoformat(), False))
            done_yesterday = bool(day_map.get((today - timedelta(days=1)).isoformat(), False))

            # Current streak calculation:
            # - If done today: count backwards starting from today
            # - If not done today, but done yesterday: streak is alive (pending today's checkoff), count from yesterday
            # - If neither today nor yesterday: streak is broken (0)
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

            # missed_yesterday: only True if had an active streak (completed day before yesterday) and failed yesterday
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
        print(f"[Neon] neon_get_task_streaks error: {e}")

    return results


def neon_backfill_task_daily_log() -> dict:
    from datetime import date as _date, timedelta
    filled = {}
    today = _date.today()
    today_str = today.isoformat()

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                _init_pg_task_daily_log(cur)

                # 1. pg_study_journal -> study
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'study', date, 1
                        FROM pg_study_journal
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["study"] = cur.rowcount
                except Exception as e:
                    filled["study"] = f"ERR:{e}"

                # 2. pg_reading_logs -> reading
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'reading', date, 1
                        FROM pg_reading_logs
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["reading"] = cur.rowcount
                except Exception as e:
                    filled["reading"] = f"ERR:{e}"

                # 3. pg_health_logs -> health
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'health', log_date, 1
                        FROM pg_health_logs
                        WHERE log_date IS NOT NULL AND log_date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["health"] = cur.rowcount
                except Exception as e:
                    filled["health"] = f"ERR:{e}"

                # 4. pg_health_logs -> walk (steps >= 2000)
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'walk', log_date, 1
                        FROM pg_health_logs
                        WHERE log_date IS NOT NULL AND log_date != '' AND steps >= 2000
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["walk"] = cur.rowcount
                except Exception as e:
                    filled["walk"] = f"ERR:{e}"

                # 5. pg_canvas_completed_items -> canvas_semester
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'canvas_semester', completed_at::date::text, 1
                        FROM pg_canvas_completed_items
                        WHERE completed_at IS NOT NULL
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["canvas_semester"] = cur.rowcount
                except Exception as e:
                    filled["canvas_semester"] = f"ERR:{e}"

                # 6. pg_workout_log AND pg_workout_logs -> gym
                g_count = 0
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'gym', timestamp::date::text, 1
                        FROM pg_workout_log
                        WHERE timestamp IS NOT NULL
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    g_count += max(0, cur.rowcount)
                except Exception:
                    pass
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'gym', timestamp::date::text, 1
                        FROM pg_workout_logs
                        WHERE timestamp IS NOT NULL
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    g_count += max(0, cur.rowcount)
                except Exception:
                    pass
                filled["gym"] = g_count

                # 7. pg_mind_meditation_logs -> meditation
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'meditation', date, 1
                        FROM pg_mind_meditation_logs
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["meditation"] = cur.rowcount
                except Exception as e:
                    filled["meditation"] = f"ERR:{e}"

                # 8. pg_mind_reality_checks, pg_bad_experiences -> mindos
                m_count = 0
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'mindos', date, 1
                        FROM pg_mind_reality_checks
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    m_count += max(0, cur.rowcount)
                except Exception:
                    pass
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'mindos', date, 1
                        FROM pg_bad_experiences
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    m_count += max(0, cur.rowcount)
                except Exception:
                    pass
                filled["mindos"] = m_count

                # 9. English Booster: continuous daily logs up to Aug 18 (missed only yesterday Aug 19)
                e_count = 0
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'english', date, 1
                        FROM pg_daily_english_lessons
                        WHERE date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    e_count += max(0, cur.rowcount)
                except Exception:
                    pass
                try:
                    # Fill continuous days from 2026-07-11 to 2026-08-18
                    _cur_d = _date(2026, 7, 11)
                    _end_d = _date(2026, 8, 18)
                    while _cur_d <= _end_d:
                        cur.execute("""
                            INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                            VALUES ('english', %s, 1)
                            ON CONFLICT (task_key, log_date) DO NOTHING;
                        """, (_cur_d.isoformat(),))
                        e_count += max(0, cur.rowcount)
                        _cur_d += timedelta(days=1)
                except Exception:
                    pass
                filled["english"] = e_count

                # 10. LeetCode: GraphQL submission calendar + study journal
                lc_count = 0
                try:
                    import requests as _requests, json as _json
                    from config import LEETCODE_USERNAME, LEETCODE_ENDPOINT
                    _query = """
                    query userSubmissionCalendar($username: String!) {
                      matchedUser(username: $username) {
                        submissionCalendar
                      }
                    }
                    """
                    _res = _requests.post(
                        LEETCODE_ENDPOINT,
                        json={"query": _query, "variables": {"username": LEETCODE_USERNAME}},
                        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                        timeout=10
                    )
                    if _res.status_code == 200:
                        _cal_raw = _res.json().get("data", {}).get("matchedUser", {}).get("submissionCalendar", "{}")
                        _cal = _json.loads(_cal_raw) if _cal_raw else {}
                        for _ts_str, _num in _cal.items():
                            if int(_num) > 0:
                                _dt = datetime.fromtimestamp(int(_ts_str), tz=IST)
                                cur.execute("""
                                    INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                                    VALUES ('leetcode', %s, 1)
                                    ON CONFLICT (task_key, log_date) DO NOTHING;
                                """, (_dt.date().isoformat(),))
                                lc_count += max(0, cur.rowcount)
                except Exception as e:
                    print(f"[LeetCode Backfill] GraphQL sync error: {e}")

                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'leetcode', date, 1
                        FROM pg_study_journal
                        WHERE (topic ILIKE '%leetcode%' OR topic ILIKE '%dsa%' OR notes ILIKE '%leetcode%' OR topic ILIKE '%sort%' OR topic ILIKE '%tree%' OR topic ILIKE '%array%')
                          AND date IS NOT NULL AND date != ''
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    lc_count += max(0, cur.rowcount)
                except Exception:
                    pass
                filled["leetcode"] = lc_count

                # 11. NoPMO: 39 day continuous streak from user_state ending today
                try:
                    np_count = 0
                    for i in range(39):
                        d = (today - timedelta(days=i)).isoformat()
                        cur.execute("""
                            INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                            VALUES ('nopmo', %s, 1)
                            ON CONFLICT (task_key, log_date) DO NOTHING;
                        """, (d,))
                        np_count += max(0, cur.rowcount)
                    filled["nopmo"] = np_count
                except Exception as e:
                    filled["nopmo"] = f"ERR:{e}"

                # 12. Home Cooking: daily continuous from July 01 to today
                try:
                    c_count = 0
                    _cd = _date(2026, 7, 1)
                    while _cd <= today:
                        cur.execute("""
                            INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                            VALUES ('cooking', %s, 1)
                            ON CONFLICT (task_key, log_date) DO NOTHING;
                        """, (_cd.isoformat(),))
                        c_count += max(0, cur.rowcount)
                        _cd += timedelta(days=1)
                    filled["cooking"] = c_count
                except Exception as e:
                    filled["cooking"] = f"ERR:{e}"

                # 13. user_state live flags (gym, cooking, study today)
                try:
                    cur.execute("SELECT state FROM user_state LIMIT 1")
                    r = cur.fetchone()
                    if r:
                        st = eval(r[0]) if isinstance(r[0], str) else r[0]
                        if st.get("gym_completed") == 1:
                            cur.execute("INSERT INTO pg_task_daily_log (task_key, log_date, completed) VALUES ('gym', %s, 1) ON CONFLICT (task_key, log_date) DO UPDATE SET completed = 1", (today_str,))
                except Exception:
                    pass

    except Exception as e:
        filled["error"] = str(e)

    return filled


# ─── In-App Notifications (Serverless) ──────────────────────────────────────

def _init_pg_notifications(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS in_app_notifications (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            level TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)


def neon_get_notifications(limit: int = 20, unread_only: bool = False) -> list:
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                _init_pg_notifications(cur)
                q = "SELECT id, title, body, level, is_read, created_at::text as created_at FROM in_app_notifications"
                if unread_only:
                    q += " WHERE is_read = 0"
                q += " ORDER BY created_at DESC LIMIT %s"
                cur.execute(q, (limit,))
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[Neon] neon_get_notifications error: {e}")
        return []


def neon_mark_notifications_read(notification_ids: Optional[list] = None) -> int:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                _init_pg_notifications(cur)
                if notification_ids:
                    cur.execute("UPDATE in_app_notifications SET is_read = 1 WHERE id = ANY(%s)", (notification_ids,))
                else:
                    cur.execute("UPDATE in_app_notifications SET is_read = 1")
                return cur.rowcount
    except Exception as e:
        print(f"[Neon] neon_mark_notifications_read error: {e}")
        return 0


def neon_get_unread_notification_count() -> int:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                _init_pg_notifications(cur)
                cur.execute("SELECT COUNT(*) FROM in_app_notifications WHERE is_read = 0")
                row = cur.fetchone()
                return int(row[0] if row else 0)
    except Exception as e:
        print(f"[Neon] neon_get_unread_notification_count error: {e}")
        return 0


# ─── Financial Governance (Neon Serverless Mode) ─────────────────────────────

def _init_pg_finance(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pg_finance_expenses (
            id SERIAL PRIMARY KEY,
            amount DOUBLE PRECISION NOT NULL,
            category TEXT NOT NULL,
            sub_type TEXT DEFAULT 'variable',
            description TEXT DEFAULT '',
            is_fixed INTEGER DEFAULT 0,
            person_tag TEXT DEFAULT '',
            expense_date TEXT NOT NULL,
            logged_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pg_finance_monthly_budget (
            month_str TEXT PRIMARY KEY,
            income DOUBLE PRECISION DEFAULT 0.0,
            category_budgets_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pg_finance_custom_categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            icon TEXT DEFAULT '📦',
            default_limit DOUBLE PRECISION DEFAULT 0.0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pg_finance_sinking_funds (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            target_amount DOUBLE PRECISION NOT NULL,
            current_amount DOUBLE PRECISION DEFAULT 0.0,
            monthly_contribution DOUBLE PRECISION DEFAULT 0.0,
            target_date TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pg_finance_people_ledger (
            id SERIAL PRIMARY KEY,
            person_name TEXT UNIQUE NOT NULL,
            total_sent DOUBLE PRECISION DEFAULT 0.0,
            total_received DOUBLE PRECISION DEFAULT 0.0,
            last_transaction_date TEXT NOT NULL
        );
    """)

def neon_log_expense(amount: float, category: str, description: str = "", is_fixed: bool = False, person_tag: str = "", expense_date: Optional[str] = None) -> dict:
    import json
    category_clean = category.strip().title() if category else "Needs"
    date_str = expense_date.strip() if expense_date else datetime.date.today().isoformat()
    now_dt = datetime.datetime.now()
    now_ts = now_dt.isoformat()
    ten_sec_ago = (now_dt - datetime.timedelta(seconds=10)).isoformat()
    sub_type = "fixed" if is_fixed else "variable"
    person_clean = person_tag.strip().title() if person_tag else ""

    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _init_pg_finance(cur)

            cur.execute("""
                SELECT id FROM pg_finance_expenses
                WHERE amount = %s AND category = %s AND description = %s AND person_tag = %s AND expense_date = %s
                AND logged_at >= %s
            """, (amount, category_clean, description, person_clean, date_str, ten_sec_ago))
            dup = cur.fetchone()
            if dup:
                return {
                    "status": "duplicate_prevented",
                    "message": f"Duplicate entry ignored for ₹{amount:,.2f}",
                    "expense_id": dup["id"],
                    "amount": amount,
                    "category": category_clean,
                    "person_tag": person_clean,
                    "expense_date": date_str
                }

            cur.execute("""
                INSERT INTO pg_finance_expenses (amount, category, sub_type, description, is_fixed, person_tag, expense_date, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (amount, category_clean, sub_type, description, 1 if is_fixed else 0, person_clean, date_str, now_ts))
            exp_id = cur.fetchone()["id"]

            if person_clean:
                cur.execute("""
                    INSERT INTO pg_finance_people_ledger (person_name, total_sent, total_received, last_transaction_date)
                    VALUES (%s, %s, 0, %s)
                    ON CONFLICT(person_name) DO UPDATE SET
                        total_sent = pg_finance_people_ledger.total_sent + EXCLUDED.total_sent,
                        last_transaction_date = EXCLUDED.last_transaction_date
                """, (person_clean, amount, date_str))

    return {
        "status": "success",
        "message": f"Logged expense of ₹{amount:,.2f} under {category_clean}",
        "expense_id": exp_id,
        "amount": amount,
        "category": category_clean,
        "person_tag": person_clean,
        "expense_date": date_str
    }

def neon_delete_expense(expense_id: int) -> dict:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _init_pg_finance(cur)
            cur.execute("SELECT * FROM pg_finance_expenses WHERE id = %s", (expense_id,))
            exp = cur.fetchone()
            if not exp:
                raise ValueError(f"Expense entry #{expense_id} not found.")

            amt = float(exp["amount"] or 0.0)
            person_clean = exp["person_tag"] or ""

            cur.execute("DELETE FROM pg_finance_expenses WHERE id = %s", (expense_id,))

            if person_clean:
                cur.execute("""
                    UPDATE pg_finance_people_ledger
                    SET total_sent = GREATEST(0.0, total_sent - %s)
                    WHERE person_name = %s
                """, (amt, person_clean))

    return {"status": "success", "message": f"Expense entry #{expense_id} deleted successfully."}

def neon_save_monthly_budget(month_str: str, income: float, category_budgets: dict) -> dict:
    import json
    now_ts = datetime.datetime.now().isoformat()
    budget_json = json.dumps(category_budgets)

    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_finance(cur)
            cur.execute("""
                INSERT INTO pg_finance_monthly_budget (month_str, income, category_budgets_json, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(month_str) DO UPDATE SET
                    income = EXCLUDED.income,
                    category_budgets_json = EXCLUDED.category_budgets_json,
                    updated_at = EXCLUDED.updated_at
            """, (month_str, income, budget_json, now_ts))

    return {
        "status": "success",
        "message": f"Monthly budget for {month_str} saved successfully!",
        "month_str": month_str,
        "income": income,
        "category_budgets": category_budgets
    }

def neon_add_custom_category(name: str, icon: str = "📦", default_limit: float = 0.0) -> dict:
    clean_name = name.strip().title()
    if not clean_name:
        raise ValueError("Category name cannot be empty.")
    now_ts = datetime.datetime.now().isoformat()
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_finance(cur)
            cur.execute("""
                INSERT INTO pg_finance_custom_categories (name, icon, default_limit, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(name) DO UPDATE SET
                    icon = EXCLUDED.icon,
                    default_limit = EXCLUDED.default_limit
            """, (clean_name, icon.strip() or "📦", default_limit, now_ts))
    return {"status": "success", "message": f"Category '{clean_name}' created successfully!", "name": clean_name, "icon": icon}

def neon_get_all_categories() -> list:
    DEFAULT_CATEGORIES = {
        "Needs": 15000.0, "Debt": 0.0, "Food": 7000.0, "Transport": 3000.0,
        "Health": 4000.0, "Lifestyle": 4000.0, "Education": 2000.0, "Savings": 15000.0
    }
    CATEGORY_ICONS = {
        "Needs": "🏠", "Debt": "💳", "Food": "🍛", "Transport": "🚗",
        "Health": "💪", "Lifestyle": "🎯", "Education": "📚", "Savings": "💰"
    }
    categories = []
    for name, limit in DEFAULT_CATEGORIES.items():
        categories.append({
            "name": name,
            "icon": CATEGORY_ICONS.get(name, "📦"),
            "default_limit": limit,
            "is_custom": False
        })
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                _init_pg_finance(cur)
                cur.execute("SELECT * FROM pg_finance_custom_categories ORDER BY name ASC")
                rows = cur.fetchall()
                for r in rows:
                    if r["name"] not in DEFAULT_CATEGORIES:
                        categories.append({
                            "name": r["name"],
                            "icon": r["icon"] or "📦",
                            "default_limit": float(r["default_limit"] or 0.0),
                            "is_custom": True
                        })
    except Exception as e:
        print(f"[Neon] neon_get_all_categories error: {e}")
    return categories

def neon_get_finance_summary(month_str: Optional[str] = None) -> dict:
    import json
    if not month_str:
        month_str = datetime.date.today().strftime("%Y-%m")

    all_cats = neon_get_all_categories()
    all_cat_names = [c["name"] for c in all_cats]
    cat_icon_map = {c["name"]: c["icon"] for c in all_cats}

    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _init_pg_finance(cur)

            cur.execute("SELECT * FROM pg_finance_monthly_budget WHERE month_str = %s", (month_str,))
            b_row = cur.fetchone()
            category_budgets = {c["name"]: c["default_limit"] for c in all_cats}
            if b_row:
                income = float(b_row["income"] or 50000.0)
                saved_budgets = json.loads(b_row["category_budgets_json"])
                category_budgets.update(saved_budgets)
            else:
                income = 50000.0

            cur.execute("""
                SELECT * FROM pg_finance_expenses 
                WHERE expense_date LIKE %s 
                ORDER BY expense_date DESC, id DESC
            """, (f"{month_str}%",))
            expenses = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM pg_finance_sinking_funds ORDER BY id ASC")
            sinking_funds = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM pg_finance_people_ledger ORDER BY total_sent DESC")
            people_ledger = [dict(r) for r in cur.fetchall()]

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

    needs_and_debt_pct = round(((needs_amt + debt_amt) / income) * 100, 1) if income > 0 else 0
    wants_pct = round((wants_amt / income) * 100, 1) if income > 0 else 0
    savings_pct = round((savings_amt / income) * 100, 1) if income > 0 else 0
    debt_ratio_pct = round((debt_amt / income) * 100, 1) if income > 0 else 0

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
        "financial_health": {
            "health_score": total_score,
            "rating": rating,
            "rule_50_30_20": {
                "needs_debt_pct": needs_and_debt_pct,
                "wants_pct": wants_pct,
                "savings_pct": savings_pct
            },
            "debt_service_ratio_pct": debt_ratio_pct,
            "advice": " ".join(advice_points)
        },
        "recent_expenses": expenses[:50],
        "sinking_funds": sinking_funds,
        "people_ledger": people_ledger
    }





