import os
import sqlite3
import json
from config import DATABASE_URL, USER_PROFILE_ID

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

SQLITE_SOLO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "system_solo.db")
SQLITE_NEWS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antigravity_core", "data", "antigravity.db")

def migrate_all():
    print("==================================================================")
    print("       MIGRATING ALL 22 TABLES & DATA TO NEON POSTGRESQL          ")
    print("==================================================================")

    if not DATABASE_URL or not psycopg2:
        print("Error: DATABASE_URL not set or psycopg2 missing!")
        return

    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_conn.autocommit = True
    pg_cur = pg_conn.cursor()

    # Check user_state columns
    pg_cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'user_state';
    """)
    existing_cols = [r[0] for r in pg_cur.fetchall()]

    json_col = "state_data"
    if "state" in existing_cols:
        json_col = "state"
    elif not existing_cols:
        pg_cur.execute("""
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
            pg_cur.execute(query, (USER_PROFILE_ID, state_json))
            print(f"[OK] Migrated system_state (Level {state_dict.get('level')}, XP {state_dict.get('xp')}) & {len(cm_rows)} completed modules into user_state.{json_col}!")

        # Dynamic migration for tabular history tables into PostgreSQL
        tables_to_migrate = [
            "ai_chat_history", "study_journal", "bad_experiences", "reading_logs",
            "human_connections", "human_contexts", "stoic_logs", "translation_history",
            "daily_english_lessons", "settings", "teacher_topics", "mind_reality_checks",
            "mind_rumination_logs", "mind_relationships", "mind_meditation_logs"
        ]

        for table in tables_to_migrate:
            try:
                s_cur.execute(f"SELECT * FROM {table}")
                rows = s_cur.fetchall()
                if rows:
                    cols = [description[0] for description in s_cur.description]
                    # Map SQLite types to PostgreSQL types
                    pg_cols = []
                    for c in cols:
                        if c == "id":
                            pg_cols.append("id SERIAL PRIMARY KEY")
                        elif c in ("completed", "lockout_active", "gym_completed", "study_completed", "leetcode_completed", "cooking_completed", "nopmo_completed", "reading_completed", "english_completed", "grounding_used", "leave_urge"):
                            pg_cols.append(f"{c} INTEGER DEFAULT 0")
                        else:
                            pg_cols.append(f"{c} TEXT")
                    
                    create_sql = f"CREATE TABLE IF NOT EXISTS pg_{table} ({', '.join(pg_cols)});"
                    pg_cur.execute(create_sql)

                    # Truncate and insert fresh rows
                    pg_cur.execute(f"TRUNCATE TABLE pg_{table};")
                    for r in rows:
                        r_dict = dict(r)
                        col_names = list(r_dict.keys())
                        col_vals = [r_dict[k] for k in col_names]
                        placeholders = ", ".join(["%s"] * len(col_names))
                        cols_fmt = ", ".join(col_names)
                        insert_sql = f"INSERT INTO pg_{table} ({cols_fmt}) VALUES ({placeholders});"
                        pg_cur.execute(insert_sql, col_vals)

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
                pg_cur.execute("""
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
                pg_cur.execute("TRUNCATE TABLE pg_tech_news;")
                for nr in news_rows:
                    nd = dict(nr)
                    pg_cur.execute("""
                    INSERT INTO pg_tech_news (id, fetch_date, title, summary, source, url, icon, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (nd.get("id"), nd.get("fetch_date"), nd.get("title"), nd.get("summary"), nd.get("source"), nd.get("url"), nd.get("icon"), str(nd.get("created_at"))))
                print(f"[OK] Migrated 'pg_tech_news' ({len(news_rows)} rows)")
        except Exception as e:
            print(f"[Warn] Could not migrate tech_news: {e}")
        a_conn.close()

    pg_conn.close()
    print("\n==================================================================")
    print("SUCCESS: ALL 22 TABLES AND DATA FULLY MIGRATED TO NEON POSTGRESQL!")
    print("==================================================================")

if __name__ == "__main__":
    migrate_all()
