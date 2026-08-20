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

def neon_get_saved_books() -> list:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, title, created_at FROM pg_saved_books ORDER BY title ASC")
            return [dict(r) for r in cur.fetchall()]


def neon_save_book(title: str) -> dict:
    with _conn() as conn:
        with conn.cursor() as cur:
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
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT person_name FROM pg_human_connections ORDER BY person_name")
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
                    "FROM pg_workout_log ORDER BY id DESC"
                )
            else:
                cur.execute(
                    "SELECT timestamp AS \"Timestamp\", category AS \"Category\", workout AS \"Workout\", "
                    "variations AS \"Variations\", sets AS \"Sets\", duration_minutes AS \"Duration_Minutes\", id "
                    "FROM pg_workout_log ORDER BY id DESC LIMIT 50"
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

def neon_log_office_work(work_item_id: str, description: str, work_date: str, category: str, hours: float, xp_awarded: float, category_streak: int, work_log_id: Optional[int] = None) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            _init_pg_office_work_logs(cur)
            existing = None
            if work_log_id is not None:
                cur.execute("SELECT id FROM pg_office_work_logs WHERE id = %s", (work_log_id,))
                existing = cur.fetchone()
            
            if existing:
                cur.execute("""
                    UPDATE pg_office_work_logs
                    SET workitemid = %s, description = %s, workdate = %s, category = %s, hours = %s, xp_awarded = %s, category_streak = %s
                    WHERE id = %s
                    RETURNING id;
                """, (work_item_id, description, work_date, category, hours, xp_awarded, category_streak, existing[0]))
                return existing[0]
            else:
                cur.execute("""
                    INSERT INTO pg_office_work_logs (workitemid, description, workdate, category, hours, xp_awarded, category_streak)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (work_item_id, description, work_date, category, hours, xp_awarded, category_streak))
                new_id = cur.fetchone()[0]
                return new_id

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
    filled = {}
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

                # 6. pg_workout_logs / pg_workout_log -> gym
                try:
                    cur.execute("""
                        INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                        SELECT DISTINCT 'gym', timestamp::date::text, 1
                        FROM pg_workout_logs
                        WHERE timestamp IS NOT NULL
                        ON CONFLICT (task_key, log_date) DO NOTHING;
                    """)
                    filled["gym"] = cur.rowcount
                except Exception:
                    try:
                        cur.execute("""
                            INSERT INTO pg_task_daily_log (task_key, log_date, completed)
                            SELECT DISTINCT 'gym', timestamp::date::text, 1
                            FROM pg_workout_log
                            WHERE timestamp IS NOT NULL
                            ON CONFLICT (task_key, log_date) DO NOTHING;
                        """)
                        filled["gym"] = cur.rowcount
                    except Exception as e:
                        filled["gym"] = f"ERR:{e}"
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



