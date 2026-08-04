import json
import os
from datetime import datetime, date
from config import STATE_FILE, ALPHA, BETA, GAMMA, CIRCUIT_BREAKER_LIMIT, MAX_STREAK_LIMIT, DATABASE_URL, USER_PROFILE_ID

try:
    import psycopg2
except ImportError:
    psycopg2 = None

DEFAULT_STATE = {
    "level": 1,
    "xp": 0,
    "willpower": 10,
    "energy": 100.0,
    "streak_days": 0,
    "continuous_study_days": 0,
    "last_update": "",
    "lockout_active": False,
    "active_quests": {
        "core_skill": "Study Python_Data_Science W1: L01: NumPy N-Dimensional Array Memory Architecture: Strides, Contiguity, and C vs Fortran Memory Formats",
        "agility_code": "Verify the flattened code layout and launch the Uvicorn server"
    },
    "completed_quests_today": [],
    "daily_telemetry": {
        "study_hours": 0.0,
        "gym_hours": 0.0,
        "dopamine_rewards": 0
    },
    "gym_completed": False,
    "cooking_completed": False,
    "nopmo_completed": False,
    "active_subject": "Python_Data_Science",
    "completed_syllabus_items": {}
}

def get_db_connection():
    if not DATABASE_URL or not psycopg2:
        return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL or not psycopg2:
        return
    try:
        conn = get_db_connection()
        if conn:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_state (
                            user_id VARCHAR(255) PRIMARY KEY,
                            state JSONB NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
            conn.close()
    except Exception as e:
        print(f"Database init warning: {e}")

def load_state_from_db() -> dict:
    init_db()
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("Could not connect to Neon PostgreSQL database")
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM user_state WHERE user_id = %s;", (USER_PROFILE_ID,))
                row = cur.fetchone()
                if row and row[0]:
                    state = row[0]
                    if isinstance(state, str):
                        state = json.loads(state)
                    for k, v in DEFAULT_STATE.items():
                        if k not in state:
                            state[k] = v
                    return state
                else:
                    save_state_to_db(DEFAULT_STATE)
                    return DEFAULT_STATE.copy()
    finally:
        conn.close()

def save_state_to_db(state: dict):
    init_db()
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("Could not connect to Neon PostgreSQL database")
    try:
        state_json = json.dumps(state)
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_state (user_id, state, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET state = EXCLUDED.state, updated_at = CURRENT_TIMESTAMP;
                """, (USER_PROFILE_ID, state_json))
    finally:
        conn.close()

def calculate_xp_required(level: int) -> int:
    """Calculates XP required to level up from the given level."""
    return int(100 * (level ** 1.5))

def update_syllabus_quest(state: dict) -> dict:
    """Finds the first incomplete topic in the active syllabus and maps it as the active INT quest."""
    syllabus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syllabus.json")
    if not os.path.exists(syllabus_path):
        return state
        
    try:
        with open(syllabus_path, "r", encoding="utf-8") as f:
            syllabus = json.load(f)
            
        active_sub = state.get("active_subject", "Python_Data_Science")
        course = syllabus.get("courses", {}).get(active_sub)
        if not course:
            return state
            
        completed = state.setdefault("completed_syllabus_items", {}).setdefault(active_sub, [])
        
        found_quest = None
        for week in course.get("weeks", []):
            for item in week.get("items", []):
                if item["id"] not in completed:
                    found_quest = f"Study {active_sub} W{week['week']}: {item['name']}"
                    break
            if found_quest:
                break
                
        if found_quest:
            state["active_quests"]["core_skill"] = found_quest
        else:
            state["active_quests"]["core_skill"] = f"Course Complete: {course['name']} Mastered!"
    except Exception as e:
        print(f"Error updating syllabus quest: {e}")
    return state

def load_state_file() -> dict:
    """Load state from local state.json only (no DB). Returns None if file missing."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            for k, v in DEFAULT_STATE.items():
                if k not in state:
                    state[k] = v
            return state
    except Exception:
        return None

def save_state_file(state: dict):
    """Save state to local state.json only."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def load_state() -> dict:
    """Load state using the sync engine (offline+online merge)."""
    try:
        from sync import sync_load_state
        state = sync_load_state()
    except Exception as e:
        print(f"[State] Sync load failed, using local file: {e}")
        state = load_state_file()
        if state is None:
            save_state_file(DEFAULT_STATE)
            state = DEFAULT_STATE.copy()

    state = update_syllabus_quest(state)
    return state

_last_state_snapshot: dict = {}

def save_state(state: dict):
    """Save state via sync engine (local + CSV changelog + Neon when online)."""
    global _last_state_snapshot
    try:
        from sync import sync_save_state
        sync_save_state(state, old_state=_last_state_snapshot or None)
    except Exception as e:
        print(f"[State] Sync save failed, writing local only: {e}")
        save_state_file(state)
    _last_state_snapshot = dict(state)


def add_xp(state: dict, amount: int) -> dict:
    state["xp"] += amount
    while True:
        req = calculate_xp_required(state["level"])
        if state["xp"] >= req:
            state["xp"] -= req
            state["level"] += 1
        else:
            break
    return state

def update_daily_energy(state: dict, study_hours: float, gym_hours: float, dopamine_rewards: int) -> dict:
    """
    Applies the energy update formula:
    E_{t+1} = E_t - (alpha * study_hours) + (beta * gym_hours) + (gamma * dopamine_rewards)
    """
    current_energy = state["energy"]
    drawdown = ALPHA * study_hours
    gain_gym = BETA * gym_hours
    gain_dopamine = GAMMA * dopamine_rewards
    
    new_energy = current_energy - drawdown + gain_gym + gain_dopamine
    state["energy"] = max(0.0, min(100.0, round(new_energy, 2)))
    
    # Store today's telemetry input
    state["daily_telemetry"] = {
        "study_hours": study_hours,
        "gym_hours": gym_hours,
        "dopamine_rewards": dopamine_rewards
    }
    
    # Auto-complete gym check if gym hours > 0
    if gym_hours > 0.0:
        state["gym_completed"] = True
        
    # Check circuit breaker triggers
    check_circuit_breaker(state)
    return state

def check_circuit_breaker(state: dict):
    """
    Triggers lockout if energy <= 20% or if continuous study streak >= 21 days.
    """
    energy_depleted = state["energy"] <= CIRCUIT_BREAKER_LIMIT
    streak_overload = state.get("continuous_study_days", 0) >= MAX_STREAK_LIMIT
    
    if energy_depleted or streak_overload:
        state["lockout_active"] = True
    else:
        state["lockout_active"] = False

def check_date_transition(state: dict) -> dict:
    """
    Checks if a new day has started. Updates energy and resets daily metrics.
    """
    today_str = date.today().isoformat()
    last_update_str = state.get("last_update", "")
    
    if last_update_str != today_str:
        # Reset checklist items
        state["completed_quests_today"] = []
        state["gym_completed"] = False
        state["cooking_completed"] = False
        state["nopmo_completed"] = False
        state["daily_telemetry"] = {
            "study_hours": 0.0,
            "gym_hours": 0.0,
            "dopamine_rewards": 0
        }
        state["last_update"] = today_str
    return state
