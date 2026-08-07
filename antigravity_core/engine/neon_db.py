"""
neon_db.py — Neon PostgreSQL helpers for serverless (Vercel) mode
=================================================================
When IS_SERVERLESS=True, SQLite is unavailable (read-only FS).
All features (books, reading logs, bad experiences, chat history,
Mind OS, human connections, stoic logs) read/write here instead.
"""

import datetime
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
