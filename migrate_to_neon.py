import json
import os
import sqlite3
from config import STATE_FILE, DATABASE_URL, USER_PROFILE_ID
from state import save_state_to_db, init_db

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "system_solo.db")

def migrate():
    print("Starting migration to Neon PostgreSQL...")
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable is not set in .env!")
        return

    init_db()

    state_data = {
        "level": 7,
        "xp": 1662,
        "str": 213,
        "int": 171,
        "agi": 203,
        "wil": 70,
        "heart": 44,
        "stoic": 37,
        "energy": 100.0,
        "lockout_active": False,
        "streak_days": 28,
        "continuous_study_days": 0,
        "last_update": "2026-08-04",
        "active_subject": "Calculus_Optimization",
        "gym_completed": False,
        "study_completed": False,
        "leetcode_completed": True,
        "cooking_completed": True,
        "nopmo_completed": True,
        "english_completed": False,
        "reading_completed": False,
        "reading_book": "None",
        "completed_syllabus_items": {},
        "completed_quests_today": [],
        "daily_telemetry": {
            "study_hours": 0.0,
            "gym_hours": 0.0,
            "dopamine_rewards": 0
        }
    }

    # 1. Read SQLite system_solo.db if available
    if os.path.exists(SQLITE_DB_PATH):
        print(f"Reading Workstation SQLite state from: {SQLITE_DB_PATH}")
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                d = dict(row)
                for k, v in d.items():
                    if k != "id":
                        state_data[k] = v
            
            # Read completed modules
            cursor.execute("SELECT * FROM completed_modules")
            mod_rows = cursor.fetchall()
            completed_dict = {}
            for mr in mod_rows:
                m_dict = dict(mr)
                course = m_dict.get("course", "Calculus_Optimization")
                m_name = m_dict.get("module_name", "")
                completed_dict.setdefault(course, []).append(m_name)
            
            if completed_dict:
                state_data["completed_syllabus_items"] = completed_dict

            conn.close()
            print("Successfully extracted SQLite state & completed modules!")
        except Exception as e:
            print(f"Warning reading SQLite DB: {e}")

    print(f"Uploading state to Neon PostgreSQL for user: '{USER_PROFILE_ID}'")
    print(f"Migrating Level {state_data.get('level')} | XP {state_data.get('xp')} | STR {state_data.get('str')} | INT {state_data.get('int')} | AGI {state_data.get('agi')} | WIL {state_data.get('wil')} | HRT {state_data.get('heart')} | STC {state_data.get('stoic')}")
    
    save_state_to_db(state_data)
    print("SUCCESS! Local Workstation data is now migrated live to Neon PostgreSQL!")

if __name__ == "__main__":
    migrate()
