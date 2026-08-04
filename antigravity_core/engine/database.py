import os
import sqlite3
import threading
from datetime import date

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


SEED_DB_PATH = os.path.join(CORE_DIR, "data", "seed_system_solo.db")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        if os.path.exists(SEED_DB_PATH):
            import shutil
            shutil.copyfile(SEED_DB_PATH, DB_PATH)
            print(f"[DB] Initialized system_solo.db from seed: {SEED_DB_PATH}")

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
        ("english_completed", "INTEGER DEFAULT 0")
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

    conn.commit()
    conn.close()


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

def get_state() -> dict:
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
            return db_state
    except Exception as e:
        print(f"Error loading state via Neon sync engine: {e}")

    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass
    return {}

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
                english_completed = ?
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
                1 if state.get("english_completed") else 0
            ))
            conn.commit()
            conn.close()
    except Exception:
        pass

def add_xp(amount: int) -> dict:
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        state = dict(row)
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
        cursor.execute("""
        UPDATE system_state
        SET level = ?, xp = ?, str = ?, int = ?, agi = ?, wil = ?,
            energy = ?, lockout_active = ?, last_update = ?,
            streak_days = ?, continuous_study_days = ?, active_subject = ?,
            gym_completed = ?, study_completed = ?, leetcode_completed = ?,
            cooking_completed = ?, nopmo_completed = ?,
            english_completed = ?, reading_completed = ?, reading_book = ?, heart = ?, stoic = ?
        WHERE id = (SELECT id FROM system_state ORDER BY id DESC LIMIT 1)
        """, (
            state["level"], state["xp"],
            state.get("str", 10), state.get("int", 10),
            state.get("agi", 10), state.get("wil", 10),
            state.get("energy", 100.0),
            1 if state.get("lockout_active") else 0,
            state.get("last_update", date.today().isoformat()),
            state.get("streak_days", 0), state.get("continuous_study_days", 0),
            state.get("active_subject", "Python_Data_Science"),
            state.get("gym_completed", 0), state.get("study_completed", 0),
            state.get("leetcode_completed", 0), state.get("cooking_completed", 0),
            state.get("nopmo_completed", 0),
            state.get("english_completed", 0), state.get("reading_completed", 0),
            state.get("reading_book", "None"), state.get("heart", 10), state.get("stoic", 10)
        ))
        conn.commit()
        conn.close()
        return state

def update_stat(stat_name: str, amount: float) -> dict:
    """Dynamically update any core stat (XP, STR, INT, AGI, WIL, ENERGY, HEART)"""
    stat_name = stat_name.lower()
    
    # Map friendly names to DB column names
    col_map = {
        "xp": "xp", "str": "str", "int": "int", "agi": "agi", "wil": "wil", 
        "energy": "energy", "hrt": "heart", "heart": "heart", "humanity": "heart",
        "stc": "stoic", "stoic": "stoic"
    }
    
    db_col = col_map.get(stat_name)
    if not db_col:
        return {}
        
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
            
        state = dict(row)
        
        # Apply the stat change
        state[db_col] += amount
        
        # Handle specific edge cases
        if db_col == "xp":
            state["xp"] = int(state["xp"])
            
            # Handle level down
            while state["xp"] < 0 and state["level"] > 1:
                state["level"] -= 1
                state["xp"] += calculate_xp_required(state["level"])
                
            if state["xp"] < 0:
                state["xp"] = 0  # Floor at absolute 0 (Level 1, 0 XP)
                
            # Handle level up
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
            
        cursor.execute(f"""
        UPDATE system_state
        SET {db_col} = ?, level = ?
        WHERE id = (SELECT id FROM system_state ORDER BY id DESC LIMIT 1)
        """, (state[db_col], state["level"]))
        
        conn.commit()
        conn.close()
        return state

def save_chat_message(role: str, message: str, bot_type: str = "coach"):
    """Persist a chat message (role='user' or 'ai') to the database with bot_type."""
    import datetime
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

    # Automatically award +1 HRT (Heart/Humanity)
    new_state = update_stat("hrt", 1.0)
    log_activity_file("Human Connection Logged", f"Met {person_name} ({emoji}) - {context_meeting}. +1 HRT awarded!")
    return {
        "status": "success",
        "hrt_awarded": 1,
        "person_name": person_name,
        "current_hrt": new_state.get("heart", 10)
    }

def get_human_connections(limit: int = 50) -> list:
    """Fetch human connection entries for reflection and future emotional analysis."""
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
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO human_contexts (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
    return {"status": "success", "name": name}

def get_human_contexts() -> list:
    """Fetch all saved human encounter contexts/locations."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM human_contexts ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r["name"] for r in rows]

def get_unique_people() -> list:
    """Fetch distinct person names previously met for easy select dropdown."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT person_name FROM human_connections WHERE person_name != '' ORDER BY person_name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r["person_name"] for r in rows]

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
    
    # Award +2 STC (Stoic) stat point for daily self-reflection!
    update_stat("STOIC", 2)
    log_activity_file("Logged Stoic Reflection", f"Mindset score: {attitude_score}/10. Earned +2 STC.")
    
    return {"status": "success", "message": "Stoic reflection logged successfully! Gained +2 STC.", "state": get_state()}

def get_stoic_reflections(limit: int = 50) -> list:
    """Fetch recent daily stoic reflections."""
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
    from datetime import date
    today_str = date.today().isoformat()
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
            from datetime import datetime, timedelta
            if last_active:
                last_dt = datetime.strptime(last_active, "%Y-%m-%d").date()
                today_dt = date.today()
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
    
    # Award +15 XP for self-reflection & thought reframing
    update_stat("xp", 15)
    log_activity_file("CBT Reality Check Completed", f"Reframed thought: '{my_interpretation}' -> '{alternative_explanation}'. Awarded +15 XP.")
    return {"status": "success", "id": new_id, "earned_xp": 15}

def get_reality_checks(limit: int = 50) -> list:
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
        
    # Reward +2 STC (Stoic) for stopping/managing rumination, plus some XP
    update_stat("stoic", 2)
    update_stat("xp", 10)
    log_activity_file("Rumination Grounded", f"Managed mental replay from conversation: '{trigger_convo}'. Gained +2 STC, +10 XP.")
    return {"status": "success", "id": new_id, "earned_stc": 2, "earned_xp": 10}

def get_rumination_logs(limit: int = 50) -> list:
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_rumination_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_relationship(person_name: str, trust_score: int, leave_urge: int, closeness: int, last_interaction_date: str, notes: str, status: str) -> dict:
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
        
    # Log connection maintenance in activity logs
    log_activity_file("Relationship Profile Updated", f"Updated alignment for {person_name}. Trust: {trust_score}/10, Leave Urge: {leave_urge}/10, Closeness: {closeness}/10.")
    return {"status": "success", "person_name": person_name}

def get_relationships() -> list:
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_relationships ORDER BY trust_score DESC, closeness DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_mind_summary() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total and Pending Reality Checks
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN verified_outcome = 'Pending' THEN 1 ELSE 0 END) FROM mind_reality_checks")
    rc_row = cursor.fetchone()
    total_rc = rc_row[0] if rc_row else 0
    pending_rc = rc_row[1] if rc_row and rc_row[1] is not None else 0
        
    # 2. Avg Rumination distress & duration
    cursor.execute("SELECT AVG(distress_score), AVG(duration_mins), SUM(grounding_used) FROM mind_rumination_logs")
    rl_row = cursor.fetchone()
    avg_distress = round(rl_row[0], 1) if rl_row and rl_row[0] is not None else 0.0
    avg_duration = round(rl_row[1], 1) if rl_row and rl_row[1] is not None else 0.0
    total_groundings = rl_row[2] if rl_row and rl_row[2] is not None else 0
    
    # 3. Active relationships & warning count (leave_urge > trust_score)
    cursor.execute("""
    SELECT COUNT(*), SUM(CASE WHEN leave_urge >= trust_score AND status = 'Active' THEN 1 ELSE 0 END)
    FROM mind_relationships
    """)
    rel_row = cursor.fetchone()
    total_rels = rel_row[0] if rel_row else 0
    warning_rels = rel_row[1] if rel_row and rel_row[1] is not None else 0
    
    # 4. Meditation Stats
    cursor.execute("SELECT COUNT(*), SUM(duration_mins) FROM mind_meditation_logs")
    med_row = cursor.fetchone()
    total_med = med_row[0] if med_row else 0
    total_med_mins = med_row[1] if med_row and med_row[1] is not None else 0

    conn.close()
    
    return {
        "total_reality_checks": total_rc,
        "pending_reality_checks": pending_rc,
        "avg_rumination_distress": avg_distress,
        "avg_rumination_duration": avg_duration,
        "total_groundings": total_groundings,
        "total_relationships": total_rels,
        "warning_relationships": warning_rels,
        "total_meditations": total_med,
        "total_meditation_minutes": total_med_mins
    }

def save_meditation_log(duration_mins: int, track_name: str) -> dict:
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
        
    # Award stats: +2 STC (Stoic), +1 WIL (Willpower), and +20 XP
    update_stat("stoic", 2)
    update_stat("wil", 1)
    new_state = update_stat("xp", 20)
    
    log_activity_file(
        doing="Meditation Session Completed",
        accomplished=f"Completed {duration_mins} minutes of focused meditation listening to '{track_name}'. Awarded +20 XP, +2 STC, +1 WIL."
    )
    return {
        "status": "success", 
        "id": new_id, 
        "earned_xp": 20, 
        "earned_stc": 2, 
        "earned_wil": 1,
        "level": new_state.get("level", 1),
        "xp": new_state.get("xp", 0)
    }

def get_meditation_logs(limit: int = 50) -> list:
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mind_meditation_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]



