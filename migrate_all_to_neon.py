import os
import sqlite3
import json
import csv
from config import DATABASE_URL, USER_PROFILE_ID

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, execute_values
except ImportError:
    psycopg2 = None

SQLITE_SOLO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "system_solo.db")
SQLITE_NEWS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "antigravity.db")

def connect_pg():
    if not DATABASE_URL or not psycopg2:
        return None
    conn = psycopg2.connect(DATABASE_URL, keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    conn.autocommit = True
    return conn

def migrate_all():
    print("==================================================================")
    print("       MIGRATING ALL TABLES & CSV DATASETS TO NEON POSTGRESQL     ")
    print("==================================================================")

    if not DATABASE_URL or not psycopg2:
        print("Error: DATABASE_URL not set or psycopg2 missing!")
        return

    conn = connect_pg()
    cur = conn.cursor()

    # 1. Check user_state columns
    cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'user_state';
    """)
    existing_cols = [r[0] for r in cur.fetchall()]

    json_col = "state_data"
    if "state" in existing_cols:
        json_col = "state"
    elif not existing_cols:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_state (
            user_id VARCHAR(255) PRIMARY KEY,
            state_data JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    # 2. Migrate system_solo.db tables to JSON state & Neon PG
    if os.path.exists(SQLITE_SOLO_PATH):
        s_conn = sqlite3.connect(SQLITE_SOLO_PATH)
        s_conn.row_factory = sqlite3.Row
        s_cur = s_conn.cursor()

        # system_state
        s_cur.execute("SELECT * FROM system_state ORDER BY id DESC LIMIT 1")
        row = s_cur.fetchone()
        if row:
            state_dict = dict(row)
            if "id" in state_dict:
                del state_dict["id"]
            
            # completed_modules
            s_cur.execute("SELECT * FROM completed_modules")
            cm_rows = s_cur.fetchall()
            cm_dict = {}
            for cm in cm_rows:
                cm_d = dict(cm)
                course = cm_d.get("course", "Calculus_Optimization")
                m_name = cm_d.get("module_name", "")
                cm_dict.setdefault(course, []).append(m_name)
            state_dict["completed_syllabus_items"] = cm_dict

            # Upload JSON state
            state_json = json.dumps(state_dict)
            query = f"""
            INSERT INTO user_state (user_id, {json_col}, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE
            SET {json_col} = EXCLUDED.{json_col},
                updated_at = CURRENT_TIMESTAMP;
            """
            cur.execute(query, (USER_PROFILE_ID, state_json))
            print(f"[OK] Migrated system_state (Level {state_dict.get('level')}, XP {state_dict.get('xp')}) & {len(cm_rows)} completed modules into user_state.{json_col}!")

        # Dynamic migration for tabular history tables into PostgreSQL using bulk execute_values
        tables_to_migrate = [
            "ai_chat_history", "study_journal", "bad_experiences", "reading_logs",
            "human_connections", "human_contexts", "stoic_logs", "translation_history",
            "daily_english_lessons", "settings", "teacher_topics", "mind_reality_checks",
            "mind_rumination_logs", "mind_relationships", "mind_meditation_logs",
            "leetcode_stats", "saved_books", "english_user_progress", "english_speech_logs",
            "offline_dictionary"
        ]

        for table in tables_to_migrate:
            try:
                s_cur.execute(f"SELECT * FROM {table}")
                rows = s_cur.fetchall()
                if rows:
                    cols = [description[0] for description in s_cur.description]
                    pg_cols = []
                    for c in cols:
                        if c == "id":
                            pg_cols.append("id SERIAL PRIMARY KEY")
                        elif c in ("completed", "lockout_active", "gym_completed", "study_completed", "leetcode_completed", "cooking_completed", "nopmo_completed", "reading_completed", "english_completed", "grounding_used", "leave_urge"):
                            pg_cols.append(f"{c} INTEGER DEFAULT 0")
                        else:
                            pg_cols.append(f"{c} TEXT")
                    
                    create_sql = f"CREATE TABLE IF NOT EXISTS pg_{table} ({', '.join(pg_cols)});"
                    cur.execute(create_sql)

                    cur.execute(f"TRUNCATE TABLE pg_{table};")
                    col_names = [c for c in cols]
                    cols_fmt = ", ".join(col_names)
                    val_tuples = [tuple(r[k] for k in col_names) for r in rows]
                    
                    execute_values(cur, f"INSERT INTO pg_{table} ({cols_fmt}) VALUES %s;", val_tuples)
                    print(f"[OK] Migrated table 'pg_{table}' ({len(rows)} rows)")
            except Exception as e:
                print(f"[Warn] Could not migrate table '{table}': {e}")

        s_conn.close()

    # 3. Migrate antigravity.db (tech_news)
    if os.path.exists(SQLITE_NEWS_PATH):
        a_conn = sqlite3.connect(SQLITE_NEWS_PATH)
        a_conn.row_factory = sqlite3.Row
        a_cur = a_conn.cursor()
        try:
            a_cur.execute("SELECT * FROM tech_news")
            news_rows = a_cur.fetchall()
            if news_rows:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS pg_tech_news (
                    id SERIAL PRIMARY KEY,
                    fetch_date TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    url TEXT,
                    icon TEXT,
                    created_at TEXT
                );
                """)
                cur.execute("TRUNCATE TABLE pg_tech_news;")
                val_tuples = [
                    (nd.get("id"), nd.get("fetch_date"), nd.get("title"), nd.get("summary"), nd.get("source"), nd.get("url"), nd.get("icon"), str(nd.get("created_at")))
                    for nd in [dict(nr) for nr in news_rows]
                ]
                execute_values(cur, """
                INSERT INTO pg_tech_news (id, fetch_date, title, summary, source, url, icon, created_at)
                VALUES %s;
                """, val_tuples)
                print(f"[OK] Migrated 'pg_tech_news' ({len(news_rows)} rows)")
        except Exception as e:
            print(f"[Warn] Could not migrate tech_news: {e}")
        a_conn.close()

    # 4. Migrate workout_log.csv
    workout_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "workout_log.csv")
    if os.path.exists(workout_csv_path):
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pg_workout_logs (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT,
                workout TEXT,
                variations TEXT,
                sets TEXT,
                duration_minutes INTEGER DEFAULT 0
            );
            """)
            cur.execute("TRUNCATE TABLE pg_workout_logs;")
            vals = []
            with open(workout_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dur = 0
                    try:
                        dur = int(row.get("Duration_Minutes", 0) or 0)
                    except Exception:
                        pass
                    vals.append((row.get("Timestamp"), row.get("Category"), row.get("Workout"), row.get("Variations"), row.get("Sets"), dur))
            if vals:
                execute_values(cur, """
                INSERT INTO pg_workout_logs (timestamp, category, workout, variations, sets, duration_minutes)
                VALUES %s;
                """, vals)
            print(f"[OK] Migrated 'pg_workout_logs' ({len(vals)} rows from CSV)")
        except Exception as e:
            print(f"[Warn] Could not migrate workout_log.csv: {e}")

    # 5. Migrate syllabuls.csv
    syllabus_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syllabuls.csv")
    if os.path.exists(syllabus_csv_path):
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pg_syllabus (
                id SERIAL PRIMARY KEY,
                course_module TEXT,
                level_required TEXT,
                xp_points_earned INTEGER DEFAULT 0,
                course TEXT
            );
            """)
            cur.execute("TRUNCATE TABLE pg_syllabus;")
            vals = []
            with open(syllabus_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    xp = 0
                    try:
                        xp = int(row.get("XP_Points_Earned", 0) or 0)
                    except Exception:
                        pass
                    vals.append((row.get("Course_Module"), row.get("Level_Required"), xp, row.get("Course")))
            if vals:
                execute_values(cur, """
                INSERT INTO pg_syllabus (course_module, level_required, xp_points_earned, course)
                VALUES %s;
                """, vals)
            print(f"[OK] Migrated 'pg_syllabus' ({len(vals)} rows from syllabuls.csv)")
        except Exception as e:
            print(f"[Warn] Could not migrate syllabuls.csv: {e}")

    # 6. Migrate gym_workouts_by_category.csv
    gym_cat_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "gym_workouts_by_category.csv")
    if os.path.exists(gym_cat_csv_path):
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pg_gym_workouts_by_category (
                id SERIAL PRIMARY KEY,
                category TEXT,
                workout TEXT
            );
            """)
            cur.execute("TRUNCATE TABLE pg_gym_workouts_by_category;")
            vals = []
            with open(gym_cat_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vals.append((row.get("Category"), row.get("Workout")))
            if vals:
                execute_values(cur, """
                INSERT INTO pg_gym_workouts_by_category (category, workout)
                VALUES %s;
                """, vals)
            print(f"[OK] Migrated 'pg_gym_workouts_by_category' ({len(vals)} rows from CSV)")
        except Exception as e:
            print(f"[Warn] Could not migrate gym_workouts_by_category.csv: {e}")

    # 7. Migrate dictionary.csv
    dict_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "dictionary.csv")
    if os.path.exists(dict_csv_path):
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pg_dictionary (
                id SERIAL PRIMARY KEY,
                english TEXT,
                tamil TEXT
            );
            """)
            cur.execute("TRUNCATE TABLE pg_dictionary;")
            vals = []
            with open(dict_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vals.append((row.get("English"), row.get("Tamil")))
            if vals:
                execute_values(cur, """
                INSERT INTO pg_dictionary (english, tamil)
                VALUES %s;
                """, vals)
            print(f"[OK] Migrated 'pg_dictionary' ({len(vals)} rows from dictionary.csv)")
        except Exception as e:
            print(f"[Warn] Could not migrate dictionary.csv: {e}")

    conn.close()
    print("\n==================================================================")
    print("SUCCESS: ALL TABLES AND CSV DATASETS FULLY MIGRATED TO NEON PG!")
    print("==================================================================")

if __name__ == "__main__":
    migrate_all()
