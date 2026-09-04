import sqlite3
import math
import os
from datetime import datetime

try:
    from config import IS_SERVERLESS, DATABASE_URL
except ImportError:
    IS_SERVERLESS = False
    DATABASE_URL = ""

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("VERCEL") or IS_SERVERLESS or not os.access(CORE_DIR, os.W_OK):
    DB_DIR = "/tmp/antigravity_data"
else:
    DB_DIR = os.path.join(CORE_DIR, "data")

try:
    os.makedirs(DB_DIR, exist_ok=True)
except Exception:
    DB_DIR = "/tmp/antigravity_data"
    os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "system_solo.db")


class EnergyEngine:
    T_MIN = 10.0      # Minimum meaningful sprint (minutes)
    T_MAX = 120.0     # Maximum focused block (minutes)
    GAMMA = 1.7       # Non-linear capacity curvature factor

    CATEGORY_FRICTION = {
        "Machine_Learning": 2.8,
        "DSA_LeetCode": 2.8,
        "Linear_Algebra": 2.5,
        "Probability_Stats": 2.5,
        "Database_Systems": 2.0,
        "Office_Work": 2.0,
        "Canvas_Lecture": 1.2,
        "Gym_Pro": 3.5,
        "Mind_OS": 0.8
    }

    def __init__(self, db_path: str = None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = DB_PATH
        self._ensure_tables_exist()

    def _get_connection(self):
        """Returns (connection, db_type) supporting both Neon PostgreSQL and SQLite."""
        if (IS_SERVERLESS or os.environ.get("VERCEL")) and DATABASE_URL and HAS_PSYCOPG2:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                return conn, "pg"
            except Exception as e:
                print("[EnergyEngine] Neon PG connection failed, falling back to SQLite:", e)

        conn = sqlite3.connect(self.db_path, timeout=10.0)
        return conn, "sqlite"

    def _exec(self, cursor, db_type: str, sql: str, params: tuple = ()):
        if db_type == "pg":
            sql = sql.replace("?", "%s")
        cursor.execute(sql, params)

    @staticmethod
    def calculate_capacity(energy: float) -> int:
        """Returns recommended task duration in minutes."""
        energy_clamped = max(0.0, min(100.0, energy))
        capacity = EnergyEngine.T_MIN + (EnergyEngine.T_MAX - EnergyEngine.T_MIN) * math.pow(energy_clamped / 100.0, EnergyEngine.GAMMA)
        return int(round(capacity))

    @staticmethod
    def get_tier(energy: float) -> tuple[str, str]:
        if energy >= 75.0:
            return "POWER", "Deep Work, Algorithm Implementation, Heavy Derivations"
        elif energy >= 50.0:
            return "NORMAL", "Standard Quizzes, Refactoring, Applied Labs"
        elif energy >= 25.0:
            return "LOW", "Concept Reviews, Micro-Sprints, Reading Notes"
        else:
            return "SURVIVAL", "Minimum Action Only: 1 Quiz / Flashcard Review. Protect Streak."

    def get_current_state(self) -> dict:
        row = None
        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()
            self._exec(cursor, db_type, "SELECT current_energy, cumulative_fatigue, tier_status, deep_work_blocks_today FROM energy_state WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
        except Exception as e:
            print("[EnergyEngine] Error fetching current state:", e)

        if not row:
            energy, fatigue, tier, deep_blocks = 80.0, 0.0, "NORMAL", 0
        else:
            energy, fatigue, tier, deep_blocks = row

        capacity = self.calculate_capacity(energy)
        return {
            "current_energy": round(energy, 1),
            "fatigue_accumulated": round(fatigue, 1),
            "tier": tier,
            "max_task_capacity_minutes": capacity,
            "deep_work_blocks_used": deep_blocks,
            "deep_work_blocks_remaining": max(0, 3 - deep_blocks)
        }

    def consume_energy(self, category: str, duration_minutes: float, difficulty: int, quest_id: str = None) -> dict:
        state = self.get_current_state()
        e_curr = state["current_energy"]
        tier = state["tier"]

        kc = self.CATEGORY_FRICTION.get(category, 2.0)
        is_deep_work = duration_minutes >= 45 and difficulty >= 7
        if is_deep_work and state["deep_work_blocks_used"] >= 3:
            return {
                "status": "REJECTED",
                "reason": "Daily deep work ceiling reached (3/3 blocks). Switch to light maintenance or recovery."
            }

        cost = kc * difficulty * math.pow(duration_minutes / 60.0, 0.85)
        e_next = max(0.0, e_curr - cost)

        base_xp = 35.0
        streak_multiplier = 1.5
        target_cap = max(10, self.calculate_capacity(e_curr))
        effort_ratio = min(1.5, duration_minutes / target_cap)
        xp_earned = int(round((base_xp * (1.0 + 0.15 * difficulty) * effort_ratio) * streak_multiplier))

        new_tier, _ = self.get_tier(e_next)

        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()

            self._exec(cursor, db_type, """
                UPDATE energy_state 
                SET current_energy = ?,
                    tier_status = ?,
                    deep_work_blocks_today = deep_work_blocks_today + ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (e_next, new_tier, 1 if is_deep_work else 0))

            try:
                self._exec(cursor, db_type, """
                    UPDATE player 
                    SET current_xp = current_xp + ?,
                        cognitive_energy = ?
                    WHERE id = 1
                """, (xp_earned, int(e_next)))
            except Exception:
                pass

            try:
                self._exec(cursor, db_type, """
                    UPDATE system_state 
                    SET xp = xp + ?,
                        energy = ?
                    WHERE id = 1
                """, (xp_earned, e_next))
            except Exception:
                pass

            self._exec(cursor, db_type, """
                INSERT INTO energy_ledger (transaction_type, category, magnitude, energy_before, energy_after, associated_quest_id)
                VALUES ('DRAIN', ?, ?, ?, ?, ?)
            """, (category, cost, e_curr, e_next, quest_id))

            conn.commit()
            conn.close()
        except Exception as e:
            print("[EnergyEngine] DB consume write error:", e)

        return {
            "status": "SUCCESS",
            "energy_cost": round(cost, 1),
            "energy_remaining": round(e_next, 1),
            "xp_minted": xp_earned,
            "tier_transition": f"{tier} -> {new_tier}"
        }

    def apply_recovery(self, recovery_type: str, units: float = 0.0) -> dict:
        recovery_values = {
            "POWER_NAP": 15.0,
            "MEDITATION": 8.0,
            "NUTRITION": 12.0,
            "NATURE_WALK": 15.0,
            "WORKOUT_RECOVERY": 20.0
        }

        gain = recovery_values.get(recovery_type, units if units > 0 else 10.0)
        state = self.get_current_state()
        e_curr = state["current_energy"]
        e_next = min(100.0, e_curr + gain)
        new_tier, _ = self.get_tier(e_next)

        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()

            self._exec(cursor, db_type, """
                UPDATE energy_state 
                SET current_energy = ?, tier_status = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (e_next, new_tier))

            try:
                self._exec(cursor, db_type, "UPDATE player SET cognitive_energy = ? WHERE id = 1", (int(e_next),))
            except Exception:
                pass

            try:
                self._exec(cursor, db_type, "UPDATE system_state SET energy = ? WHERE id = 1", (e_next,))
            except Exception:
                pass

            self._exec(cursor, db_type, """
                INSERT INTO energy_ledger (transaction_type, category, magnitude, energy_before, energy_after)
                VALUES ('RECOVERY', ?, ?, ?, ?)
            """, (recovery_type, gain, e_curr, e_next))

            conn.commit()
            conn.close()
        except Exception as e:
            print("[EnergyEngine] DB recovery write error:", e)

        return {
            "status": "RECOVERED",
            "energy_restored": round(gain, 1),
            "new_energy": round(e_next, 1),
            "tier": new_tier
        }

    def midnight_fatigue_rollover(self, sleep_hours: float) -> dict:
        drain, recovery, f_current = 0.0, 0.0, 0.0
        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()

            self._exec(cursor, db_type, """
                SELECT 
                    SUM(CASE WHEN transaction_type = 'DRAIN' THEN magnitude ELSE 0 END),
                    SUM(CASE WHEN transaction_type = 'RECOVERY' THEN magnitude ELSE 0 END)
                FROM energy_ledger 
                WHERE date(logged_at) = date('now', '-1 day')
            """)
            row = cursor.fetchone()
            if row:
                drain = row[0] if row[0] else 0.0
                recovery = row[1] if row[1] else 0.0

            self._exec(cursor, db_type, "SELECT cumulative_fatigue FROM energy_state WHERE id = 1")
            f_row = cursor.fetchone()
            if f_row and f_row[0]:
                f_current = f_row[0]
            conn.close()
        except Exception as e:
            print("[EnergyEngine] Error reading fatigue rollover:", e)

        f_next = max(0.0, 0.65 * f_current + (drain - recovery))
        sleep_rebound = min(25.0, 4.0 * (sleep_hours - 5.0)) if sleep_hours >= 5.0 else -15.0
        morning_e = max(15.0, min(100.0, 80.0 + sleep_rebound - 0.4 * f_next))
        tier, _ = self.get_tier(morning_e)

        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()

            self._exec(cursor, db_type, """
                UPDATE energy_state 
                SET current_energy = ?,
                    cumulative_fatigue = ?,
                    tier_status = ?,
                    deep_work_blocks_today = 0,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (morning_e, f_next, tier))

            try:
                self._exec(cursor, db_type, "UPDATE player SET cognitive_energy = ? WHERE id = 1", (int(morning_e),))
            except Exception:
                pass

            try:
                self._exec(cursor, db_type, "UPDATE system_state SET energy = ? WHERE id = 1", (morning_e,))
            except Exception:
                pass

            self._exec(cursor, db_type, """
                INSERT INTO energy_ledger (transaction_type, category, magnitude, energy_before, energy_after)
                VALUES ('RESET', 'SLEEP_ROLLOVER', ?, 0, ?)
            """, (sleep_hours, morning_e))

            conn.commit()
            conn.close()
        except Exception as e:
            print("[EnergyEngine] DB rollover write error:", e)

        return {
            "status": "DAY_INITIALIZED",
            "morning_energy": round(morning_e, 1),
            "fatigue_balance": round(f_next, 1),
            "tier": tier
        }

    def _ensure_tables_exist(self):
        try:
            conn, db_type = self._get_connection()
            cursor = conn.cursor()

            if db_type == "pg":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS energy_state (
                        id INT PRIMARY KEY CHECK (id = 1),
                        current_energy DOUBLE PRECISION DEFAULT 80.0,
                        cumulative_fatigue DOUBLE PRECISION DEFAULT 0.0,
                        tier_status TEXT DEFAULT 'NORMAL',
                        deep_work_blocks_today INT DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS energy_ledger (
                        transaction_id SERIAL PRIMARY KEY,
                        transaction_type TEXT CHECK(transaction_type IN ('DRAIN', 'RECOVERY', 'RESET')),
                        category TEXT,
                        magnitude DOUBLE PRECISION,
                        energy_before DOUBLE PRECISION,
                        energy_after DOUBLE PRECISION,
                        associated_quest_id TEXT,
                        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    INSERT INTO energy_state (id, current_energy, cumulative_fatigue, tier_status)
                    VALUES (1, 80.0, 0.0, 'NORMAL')
                    ON CONFLICT (id) DO NOTHING;
                """)
            else:
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
                cursor.execute("""
                    INSERT OR IGNORE INTO energy_state (id, current_energy, cumulative_fatigue, tier_status)
                    VALUES (1, 80.0, 0.0, 'NORMAL');
                """)

            conn.commit()
            conn.close()
        except Exception as e:
            print("[EnergyEngine] Table initialization note:", e)
