from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import os
import json
import mimetypes

# Ensure .apk files are served with the correct Android package mime type
mimetypes.add_type('application/vnd.android.package-archive', '.apk')

from state import load_state, save_state, add_xp, update_daily_energy, check_date_transition, check_circuit_breaker
from leetcode import has_solved_today, get_user_solved_stats
from sync import is_online, get_unsynced_rows, push_pending_to_neon

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SYLLABUS_PATH = os.path.join(BASE_DIR, "syllabus.json")

app = FastAPI(title="Antigravity Core API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TelemetryPayload(BaseModel):
    study_hours: float
    gym_hours: float
    dopamine_rewards: int

class CleansePayload(BaseModel):
    payload_type: str  # "physical" or "mathematical"
    solution: str

class ChecklistTogglePayload(BaseModel):
    item: str  # "gym", "cooking", "nopmo"
    value: bool

class ShopClaimPayload(BaseModel):
    item_id: str

class ActiveSubjectPayload(BaseModel):
    subject_id: str

class SyllabusTogglePayload(BaseModel):
    subject_id: str
    item_id: str
    completed: bool

# Mathematical challenges list
MATH_CHALLENGES = [
    {
        "id": 1,
        "question": "Derive the closed-form solution for Ordinary Least Squares (OLS): beta = ?",
        "expected_answer": "(X^T X)^{-1} X^T y"
    },
    {
        "id": 2,
        "question": "Write the gradient of the standard Binary Cross-Entropy loss L(y, p) with respect to prediction p.",
        "expected_answer": "(p - y) / (p * (1 - p))"
    },
    {
        "id": 3,
        "question": "What is the formula for Scaled Dot-Product Attention? Attention(Q, K, V) = ?",
        "expected_answer": "softmax(Q K^T / sqrt(d_k)) V"
    },
    {
        "id": 4,
        "question": "Write the update rule for parameters theta in Gradient Descent with learning rate eta.",
        "expected_answer": "theta - eta * grad(L)"
    }
]

# Dopamine shop inventory catalog
DOPAMINE_OFFERS = {
    "ammu_chat": {"name": "Chat session with Ammu ❤️", "cost_xp": 0, "min_energy": 30.0},
    "park_walk": {"name": "Walk in Bengaluru park 🌳", "cost_xp": 0, "min_energy": 20.0},
    "music_session": {"name": "Hear favorite music tracks 🎵", "cost_xp": 0, "min_energy": 0.0},
    "chess_match": {"name": "Competitive chess match ♟️", "cost_xp": 20, "min_energy": 40.0},
    "movie_session": {"name": "Watch one movie guilt-free 🎬", "cost_xp": 60, "min_energy": 50.0},
    "buy_dress": {"name": "Dress shopping spree 🛍️", "cost_xp": 100, "min_energy": 60.0},
    "travel_trip": {"name": "Excursion (Mountain/Sea) ⛰️🌊", "cost_xp": 250, "min_energy": 70.0}
}

# Mount static folder if it exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def get_dashboard():
    # Serves the main index.html file from static
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Antigravity Core Online. Static interface index.html not found yet."}

@app.get("/manifest.json")
def get_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))

@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"))

@app.get("/icon.svg")
def get_icon():
    return FileResponse(os.path.join(STATIC_DIR, "icon.svg"))

@app.get("/api/status")
def get_status():
    state = load_state()
    state = check_date_transition(state)
    save_state(state)
    return state

@app.get("/api/syllabus")
def get_syllabus():
    if not os.path.exists(SYLLABUS_PATH):
        raise HTTPException(status_code=404, detail="Syllabus file missing.")
    try:
        with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/syllabus/active")
def set_active_subject(payload: ActiveSubjectPayload):
    state = load_state()
    state = check_date_transition(state)
    
    # Validate course exists in syllabus.json
    if os.path.exists(SYLLABUS_PATH):
        with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
            syllabus = json.load(f)
        if payload.subject_id not in syllabus.get("courses", {}):
            raise HTTPException(status_code=400, detail="Invalid subject ID.")
            
    state["active_subject"] = payload.subject_id
    from state import update_syllabus_quest
    state = update_syllabus_quest(state)
    save_state(state)
    return state

@app.post("/api/syllabus/toggle")
def toggle_syllabus_item(payload: SyllabusTogglePayload):
    state = load_state()
    state = check_date_transition(state)
    
    sub_id = payload.subject_id
    item_id = payload.item_id
    
    if not os.path.exists(SYLLABUS_PATH):
        raise HTTPException(status_code=500, detail="Syllabus file missing.")
        
    with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
        syllabus = json.load(f)

        
    course = syllabus.get("courses", {}).get(sub_id)
    if not course:
        raise HTTPException(status_code=400, detail="Subject not found.")
        
    # Find item
    target_item = None
    target_week = None
    for week in course.get("weeks", []):
        for item in week.get("items", []):
            if item["id"] == item_id:
                target_item = item
                target_week = week
                break
        if target_item:
            break
            
    if not target_item:
        raise HTTPException(status_code=400, detail="Syllabus item not found.")
        
    completed_list = state.setdefault("completed_syllabus_items", {}).setdefault(sub_id, [])
    
    already_completed = item_id in completed_list
    
    if payload.completed:
        if not already_completed:
            completed_list.append(item_id)
            # Award item XP
            xp_award = target_item.get("xp", 5)
            state = add_xp(state, xp_award)
            
            # Check if week is now complete
            week_item_ids = [it["id"] for it in target_week["items"]]
            week_completed = all(w_id in completed_list for w_id in week_item_ids)
            
            week_key = f"{sub_id}_w{target_week['week']}_bonus"
            if week_completed and not state.setdefault("syllabus_bonuses", {}).get(week_key, False):
                state["syllabus_bonuses"][week_key] = True
                state = add_xp(state, 100) # Dungeon Cleared bonus!
    else:
        if already_completed:
            completed_list.remove(item_id)
            # Deduct XP (reversing completion)
            xp_deduct = target_item.get("xp", 5)
            from state import add_xp
            state = add_xp(state, -xp_deduct)

    from state import update_syllabus_quest
    state = update_syllabus_quest(state)
    save_state(state)
    return state

@app.post("/api/telemetry/submit")
def submit_telemetry(payload: TelemetryPayload):
    state = load_state()
    state = check_date_transition(state)
    
    # Update energy using formula
    state = update_daily_energy(
        state, 
        study_hours=payload.study_hours, 
        gym_hours=payload.gym_hours, 
        dopamine_rewards=payload.dopamine_rewards
    )
    
    # Check if gym hours is set, check gym off
    if payload.gym_hours > 0.0 and not state.get("gym_completed", False):
        state["gym_completed"] = True
        state = add_xp(state, 10)
        
    save_state(state)
    return {"message": "Telemetry processed successfully", "new_energy": state["energy"]}

@app.post("/api/checklist/toggle")
def toggle_checklist(payload: ChecklistTogglePayload):
    state = load_state()
    state = check_date_transition(state)
    
    item_key = f"{payload.item}_completed"
    if item_key not in state:
        raise HTTPException(status_code=400, detail="Invalid checklist item selection.")
        
    prev_val = state[item_key]
    state[item_key] = payload.value
    
    # Reward transition
    if payload.value and not prev_val:
        if payload.item == "gym":
            state = add_xp(state, 10)
        elif payload.item == "cooking":
            state = add_xp(state, 10)
        elif payload.item == "nopmo":
            state = add_xp(state, 15)
            state["willpower"] = state.get("willpower", 10) + 1
            
    save_state(state)
    return state

@app.post("/api/dopamine/claim")
def claim_dopamine(payload: ShopClaimPayload):
    state = load_state()
    state = check_date_transition(state)
    
    offer_id = payload.item_id
    if offer_id not in DOPAMINE_OFFERS:
        raise HTTPException(status_code=400, detail="Offer not found in catalog.")
        
    offer = DOPAMINE_OFFERS[offer_id]
    
    # Validate energy
    if state["energy"] < offer["min_energy"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Energy capacity too low. Requires {offer['min_energy']}% to unlock this offer."
        )
        
    # Calculate dynamic XP cost
    # Micro-dopamine offers are free for the first claim today, then cost 10 XP
    claimed_list = state.get("claimed_rewards_today", [])
    claimed_count = claimed_list.count(offer_id)
    cost = offer["cost_xp"]
    if cost == 0 and claimed_count >= 1:
        cost = 10
        
    # Validate XP
    if state["xp"] < cost:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient XP. First claim today is free, but subsequent claims cost 10 XP. Requires {cost} XP."
        )
        
    state["xp"] -= cost
    state["energy"] = min(100.0, state["energy"] + 5.0) # Claiming dopamine slightly replenishes energy
    
    # Store claim log
    if "claimed_rewards_today" not in state:
        state["claimed_rewards_today"] = []
    state["claimed_rewards_today"].append(offer_id)
    
    save_state(state)
    return {
        "message": f"Successfully unlocked and claimed '{offer['name']}'!",
        "new_xp": state["xp"],
        "new_energy": state["energy"]
    }

@app.post("/api/quest/complete")
def complete_quest(quest_type: str = Query(..., regex="^(core_skill|agility_code)$")):
    state = load_state()
    state = check_date_transition(state)
    
    if quest_type in state["completed_quests_today"]:
        raise HTTPException(status_code=400, detail="Quest already completed today.")
        
    if quest_type == "core_skill":
        # Verification: Check LeetCode active telemetry
        if not has_solved_today():
            raise HTTPException(
                status_code=400, 
                detail="LeetCode GraphQL API does not register a solved problem in the last 24 hours. Submit solution first!"
            )
        xp_gain = 30
        description = state["active_quests"]["core_skill"]
    else:  # agility_code
        xp_gain = 20
        description = state["active_quests"]["agility_code"]
        
    state["completed_quests_today"].append(quest_type)
    state = add_xp(state, xp_gain)
    
    # Reset/Assign new random quests
    if quest_type == "core_skill":
        state["active_quests"]["core_skill"] = "Solve another Medium/Hard LeetCode problem (dynamic sequence)"
    else:
        state["active_quests"]["agility_code"] = "Optimize clean code pipeline (dynamic python trigger)"
        
    save_state(state)
    return {
        "message": f"Quest '{description}' verified and completed!",
        "xp_gained": xp_gain,
        "new_level": state["level"],
        "new_xp": state["xp"]
    }

@app.get("/api/dungeon/challenge")
def get_dungeon_challenge():
    """Returns a random mathematical challenge for the cleanse payload."""
    challenge = random.choice(MATH_CHALLENGES)
    return {"id": challenge["id"], "question": challenge["question"]}

@app.post("/api/dungeon/cleanse")
def execute_cleanse(payload: CleansePayload):
    state = load_state()
    if not state["lockout_active"]:
        return {"message": "Dungeon is not active. No lockouts present."}
        
    if payload.payload_type == "physical":
        if payload.solution.strip() == "100":
            state["lockout_active"] = False
            state["energy"] = 30.0  # Reset to safe threshold level
            save_state(state)
            return {"message": "Dungeon Cleanse successful. 100 Reps validated. Lockout lifted."}
        else:
            raise HTTPException(status_code=400, detail="Incomplete physical strain repetition counts.")
            
    elif payload.payload_type == "mathematical":
        ans = payload.solution.strip().replace(" ", "")
        correct = False
        for c in MATH_CHALLENGES:
            clean_expected = c["expected_answer"].replace(" ", "")
            if ans == clean_expected:
                correct = True
                break
        if correct:
            state["lockout_active"] = False
            state["energy"] = 30.0  # Reset to safe threshold level
            save_state(state)
            return {"message": "Mathematical derivation verified. Access granted."}
        else:
            raise HTTPException(status_code=400, detail="Mathematical proof derivation failed validation.")
            
    elif payload.payload_type == "emergency":
        state["lockout_active"] = False
        state["energy"] = 30.0  # Reset to safe threshold level
        state["willpower"] = max(0, state.get("willpower", 10) - 5)
        state["xp"] = max(0, state.get("xp", 0) - 100)
        save_state(state)
        return {
            "message": "Emergency override triggered. Lockout lifted with penalty: -5 Willpower, -100 XP."
        }
            
    raise HTTPException(status_code=400, detail="Invalid payload classification.")


@app.get("/api/sync/status")
def get_sync_status():
    """Returns the current online/offline sync status and count of pending changes."""
    online = is_online()
    pending = get_unsynced_rows()
    return {
        "online": online,
        "pending_changes": len(pending),
        "storage": "neon_db" if online else "local_only",
        "message": (
            f"Online — synced to Neon DB. {len(pending)} changes pending push."
            if online
            else f"Offline — {len(pending)} changes saved locally, will sync when online."
        )
    }


@app.post("/api/sync/push")
def trigger_sync_push():
    """Manually trigger a push of all unsynced local changes to Neon DB."""
    pending_before = len(get_unsynced_rows())
    if pending_before == 0:
        return {"message": "Nothing to sync — all changes are already up to date.", "pushed": 0}
    success = push_pending_to_neon()
    if success:
        return {
            "message": f"Successfully pushed {pending_before} pending change(s) to Neon DB.",
            "pushed": pending_before
        }
    raise HTTPException(status_code=503, detail="Could not reach Neon DB. Try again when online.")

