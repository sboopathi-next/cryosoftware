import json
import os
from datetime import datetime, date
from config import STATE_FILE, ALPHA, BETA, GAMMA, CIRCUIT_BREAKER_LIMIT, MAX_STREAK_LIMIT, DATABASE_URL, USER_PROFILE_ID, IS_SERVERLESS

try:
    import psycopg2
except ImportError:
    psycopg2 = None

DEFAULT_STATE = {
    "level": 1,
    "xp": 0,
    "str": 10,
    "int": 10,
    "agi": 10,
    "wil": 10,
    "heart": 10,
    "stoic": 10,
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
    "completed_syllabus_items": {},
    "reading_book": "None",
    "reading_completed": False,
    "english_completed": False,
    "leetcode_completed": False,
    "study_completed": False,
    "walk_completed": 0,
    "meditation_completed": 0,
    "mindos_completed": 0,
    "health_completed": 0,
    "holiday_month": "",
    "holidays_used_this_month": 0,
    "active_holiday_date": "",
    "holiday_history": []
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
    """Load state from local state.json only (no DB). Returns None if file missing or serverless."""
    if IS_SERVERLESS:
        return None  # Serverless: no local filesystem — use Neon directly
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
    """Save state to local state.json only. Skipped in serverless mode."""
    if IS_SERVERLESS:
        return  # Serverless: filesystem is read-only, skip file write
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def load_state() -> dict:
    """Load state using the sync engine (offline+online merge)."""
    if IS_SERVERLESS:
        # Serverless mode: go directly to Neon DB (no local file fallback)
        try:
            state = load_state_from_db()
            state = update_syllabus_quest(state)
            state = check_date_transition(state)
            return state
        except Exception as e:
            print(f"[State] Serverless Neon load failed, using defaults: {e}")
            return DEFAULT_STATE.copy()

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
    state = check_date_transition(state)
    return state

_last_state_snapshot: dict = {}

def save_state(state: dict):
    """Save state via sync engine (local + CSV changelog + Neon when online)."""
    global _last_state_snapshot
    if IS_SERVERLESS:
        # Serverless mode: write directly to Neon DB only
        try:
            save_state_to_db(state)
        except Exception as e:
            print(f"[State] Serverless Neon save failed: {e}")
        _last_state_snapshot = dict(state)
        return

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
        elif state["xp"] < 0 and state["level"] > 1:
            state["level"] -= 1
            state["xp"] += calculate_xp_required(state["level"])
        else:
            if state["xp"] < 0:
                state["xp"] = 0
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

def get_today_ist_str() -> str:
    """Returns today's date ISO string in India Standard Time (IST, UTC+5:30)."""
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).date().isoformat()

def check_date_transition(state: dict) -> dict:
    """
    Checks if a new day has started in IST timezone.
    Calculates the streak, updates energy, resets daily metrics, and writes to activity log.
    """
    if not state:
        return state
    today_str = get_today_ist_str()
    current_month = today_str[:7] if today_str else ""
    
    # Auto-refresh 2 Universal Sanctuary Passes on 1st of every new month
    if state.get("holiday_month") != current_month:
        state["holiday_month"] = current_month
        state["holidays_used_this_month"] = 0
    
    last_update_str = state.get("last_update", "")
    
    if last_update_str and last_update_str != today_str:
        # Check if last_update was an active Sanctuary Holiday
        was_sanctuary_holiday = (state.get("active_holiday_date") == last_update_str)

        # Pre-check LeetCode sync to prevent losing streak
        try:
            from antigravity_core.engine.leetcode_sync import sync_leetcode
            sync_leetcode()
            # Reload state after sync
            try:
                from state import load_state_file
                file_state = load_state_file()
                if file_state:
                    state.update(file_state)
            except Exception:
                pass
        except Exception as e:
            print(f"[Day Transition] Pre-check LeetCode sync failed: {e}")

        # Calculate elapsed days
        try:
            import datetime
            last_dt = datetime.date.fromisoformat(last_update_str)
            today_dt = datetime.date.fromisoformat(today_str)
            elapsed_days = max(1, (today_dt - last_dt).days)
        except Exception:
            elapsed_days = 1

        # Require ALL core discipline targets (Study, LeetCode, Gym, English) to be completed OR Sanctuary Holiday active
        mandatory_targets = [
            bool(state.get("study_completed", False)),
            bool(state.get("leetcode_completed", False)),
            bool(state.get("gym_completed", False)),
            bool(state.get("english_completed", False))
        ]
        all_completed = all(mandatory_targets) or was_sanctuary_holiday
        
        if was_sanctuary_holiday:
            current_streak = max(33, state.get("streak_days", 33))
            state["streak_days"] = current_streak + elapsed_days
            state["energy"] = 100.0  # Full recovery
            doing = f"Day Transition: Universal Sanctuary Pass Activated for {last_update_str}"
            accomplished = f"🛡️ Universal Sanctuary Day Immunity active! All 12 streaks protected & Cognitive Energy refilled to 100%."
        elif all_completed:
            current_streak = max(33, state.get("streak_days", 33))
            state["streak_days"] = current_streak + elapsed_days
            state["energy"] = min(100.0, state.get("energy", 100.0) + 25.0)
            doing = f"Day Transition: ALL Core Discipline Targets Passed for {last_update_str}"
            accomplished = f"Completed ALL core targets! Streak incremented by +{elapsed_days}d to {state['streak_days']} days."
        else:
            current_streak = max(33, state.get("streak_days", 33))
            state["streak_days"] = current_streak
            doing = f"Day Transition: Partial Completion for {last_update_str}"
            failures = []
            if not state.get("study_completed", False): failures.append("Study")
            if not state.get("leetcode_completed", False): failures.append("LeetCode")
            if not state.get("gym_completed", False): failures.append("Gym")
            if not state.get("english_completed", False): failures.append("English")
            accomplished = f"Streak maintained at {state['streak_days']} days. Missing: {', '.join(failures)}."

        # Write check-in to activity log file
        try:
            import datetime
            timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"\n## {timestamp_str} check-in\n- **Current Activity**: {doing}\n- **Accomplished**: {accomplished}\n"
            import os
            core_dir = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(core_dir, "antigravity_core", "data", "activity_log.md")
            if not os.path.exists(os.path.dirname(log_path)):
                log_path = os.path.join(core_dir, "data", "activity_log.md")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[State] Day transition log error: {e}")

        # Reset daily checklist items for the new day
        state["completed_quests_today"] = []
        state["gym_completed"] = 0
        state["study_completed"] = 0
        state["leetcode_completed"] = 0
        state["cooking_completed"] = 0
        state["nopmo_completed"] = 0
        state["reading_completed"] = 0
        state["english_completed"] = 0
        state["walk_completed"] = 0
        state["meditation_completed"] = 0
        state["mindos_completed"] = 0
        state["health_completed"] = 0
        state["daily_telemetry"] = {
            "study_hours": 0.0,
            "gym_hours": 0.0,
            "dopamine_rewards": 0
        }
        
        # Check circuit breaker
        check_circuit_breaker(state)
        
        state["last_update"] = today_str
        save_state(state)
        
    elif not last_update_str:
        state["last_update"] = today_str
        save_state(state)
        
    return state
