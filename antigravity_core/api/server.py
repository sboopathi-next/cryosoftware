import os
import csv
import json
import re
import math
import sqlite3
import datetime
import httpx
import secrets as _secrets
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import random

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from engine.database import get_state, save_state, add_xp, calculate_xp_required, get_db_connection, log_activity_file, save_chat_message, get_chat_history, save_bad_experience, get_bad_experiences, _DB_WRITE_LOCK, get_recent_offline_logs, update_stat, save_human_connection, get_human_connections, save_human_context, get_human_contexts, get_unique_people, save_stoic_reflection, get_stoic_reflections, clear_chat_history, save_translation, get_translation_history, get_cached_daily_lesson, save_cached_daily_lesson, save_teacher_topics, get_teacher_topics, toggle_teacher_topic, clear_teacher_topics, delete_translation_history_item, clear_translation_history, get_english_user_progress, save_english_speech_log, save_reality_check, get_reality_checks, verify_reality_check, save_rumination_log, get_rumination_logs, save_relationship, get_relationships, get_mind_summary, save_meditation_log, get_meditation_logs, log_task_completion, get_task_streaks, backfill_task_daily_log, get_notifications, mark_notifications_read, get_unread_notification_count
from config import IS_SERVERLESS, DATABASE_URL
from engine.fatigue_governor import update_daily_energy

# ─── Auth configuration ────────────────────────────────────────────────────
# If APP_SECRET is not set in .env → auth is fully bypassed (offline/local mode)
_APP_SECRET   = os.getenv("APP_SECRET", "")
_APP_PASSWORD = os.getenv("APP_PASSWORD", "")
_AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")

_bearer_scheme = HTTPBearer(auto_error=False)

def verify_token(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
):
    """
    FastAPI dependency injected on protected routes.
    Rules:
      - If APP_SECRET is empty or AUTH_DISABLED=true  → always pass (offline/local mode).
      - Otherwise validate the Bearer token.
    """
    if _AUTH_DISABLED or not _APP_SECRET:
        return True  # Offline / local dev — no auth required
    if creds and creds.credentials == _APP_SECRET:
        return True
    raise HTTPException(status_code=401, detail="Unauthorized. Open /login to authenticate.")



class SpeechEvaluationPayload(BaseModel):
    topic: str
    transcript: str
    duration_seconds: int = 300


app = FastAPI(title="Antigravity Workstation Daemon API", version="2.0")

# Paths
CORE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(CORE_DIR)

STATIC_DIR = os.path.join(CORE_DIR, "static")
SYLLABUS_PATH = os.path.join(ROOT_DIR, "syllabus.json")

# On Vercel or read-only environment, write data files to /tmp/antigravity_data
if os.environ.get("VERCEL") or not os.access(CORE_DIR, os.W_OK):
    DATA_DIR = "/tmp/antigravity_data"
else:
    DATA_DIR = os.path.join(CORE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ACTIVITY_LOG_PATH = os.path.join(DATA_DIR, "activity_log.md")
GYM_WORKOUTS_CSV = os.path.join(CORE_DIR, "gym_workouts_by_category.csv")
WORKOUT_LOG_CSV = os.path.join(DATA_DIR, "workout_log.csv")
SEED_WORKOUT_LOG_CSV = os.path.join(CORE_DIR, "data", "seed_workout_log.csv")
EXAM_SCRATCHPAD_PATH = os.path.join(DATA_DIR, "exam_scratchpad.md")
ANTIGRAVITY_DB_PATH = os.path.join(DATA_DIR, "antigravity.db")


# Mount static folder
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from routers.finance_router import router as finance_router
from routers.bank_sync_router import router as bank_sync_router
app.include_router(finance_router)
app.include_router(bank_sync_router)



# ─── Pydantic Models ────────────────────────────────────────────────────────

class GymCheckPayload(BaseModel):
    completed: bool

class CheckinPayload(BaseModel):
    doing: str
    accomplished: str

class ChecklistTogglePayload(BaseModel):
    item: str
    value: bool

class ActiveSubjectPayload(BaseModel):
    subject_id: str

class SyllabusTogglePayload(BaseModel):
    subject_id: str
    item_id: str
    completed: bool
    early_bird: Optional[bool] = True  # Allow completion regardless of level

class StudyJournalPayload(BaseModel):
    topic: str
    notes: Optional[str] = ""
    subject_id: Optional[str] = ""
    item_id: Optional[str] = ""  # optionally also tick a syllabus item
    mood: Optional[str] = "focused"  # focused / tired / motivated / distracted

class ExamSavePayload(BaseModel):
    content: str

from typing import Union

class WorkoutSet(BaseModel):
    weight: Optional[Union[str, int, float]] = ""
    reps: Optional[Union[str, int, float]] = ""
    notes: Optional[str] = ""

class WorkoutLogPayload(BaseModel):
    category: str
    workout: str
    variations: Optional[str] = ""
    sets: List[WorkoutSet] = []
    duration_minutes: Optional[int] = 0
    is_custom: Optional[bool] = False

class CustomWorkoutPayload(BaseModel):
    category: str
    workout: str

DECOMMISSIONED_GROQ_MODELS = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
}

def sanitize_groq_model(model_name: Optional[str]) -> str:
    if not model_name:
        return "llama-3.3-70b-versatile"
    m = model_name.strip()
    if m.startswith("openai/"):
        return "llama-3.3-70b-versatile"
    return DECOMMISSIONED_GROQ_MODELS.get(m, m if m else "llama-3.3-70b-versatile")

class AIChatPayload(BaseModel):
    message: str
    provider: Optional[str] = "groq"
    api_key: Optional[str] = "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"
    groq_model: Optional[str] = "llama-3.3-70b-versatile"
    media_type: Optional[str] = ""    # e.g., "application/pdf" or "image/jpeg"
    media_base64: Optional[str] = ""  # Raw base64 data string

class TranslationPayload(BaseModel):
    query: str
    provider: Optional[str] = "groq"
    api_key: Optional[str] = "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"
    groq_model: Optional[str] = "llama-3.3-70b-versatile"


class BadExperiencePayload(BaseModel):
    title: str
    who: Optional[str] = ""
    what_happened: str
    my_lesson: Optional[str] = ""
    intensity: Optional[int] = 3  # 1=mild, 5=devastating

class ReadingBookPayload(BaseModel):
    book: str

class StoicReflectionPayload(BaseModel):
    reflection: str
    attitude_score: int
    stoic_lesson: Optional[str] = ""


class BodyMetricsPayload(BaseModel):
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    waist_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    arms_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    notes: Optional[str] = ""


class LogReadingPayload(BaseModel):
    book_title: str
    page_from: int
    page_to: int

class SavedBookPayload(BaseModel):
    title: str

class HumanConnectionPayload(BaseModel):
    person_name: str
    context_meeting: Optional[str] = ""
    what_happened: str
    what_i_felt: str
    emoji: Optional[str] = "🤝"


# ─── 10 Dynamic Unpredictable AI Coach Personas / Moods ────────────────────────
COACH_MOODS = [
    {
        "id": "brutal_overlord",
        "name": "🔥 Brutal Overlord",
        "anger": 10,
        "warmth": 0,
        "pitch": 0.35,
        "rate": 0.85,
        "instruction": "You are currently in BRUTAL OVERLORD mode (Anger: 10/10, Warmth: 0/10). Be cold, ruthless, and hyper-exacting. Severely penalize lazy answers, excuses, or slacking off with harsh negative stats (-15 XP, -3 WIL, -2 STC). Show no mercy."
    },
    {
        "id": "compassionate_mentor",
        "name": "❤️ Compassionate Mentor",
        "anger": 1,
        "warmth": 10,
        "pitch": 0.65,
        "rate": 0.90,
        "instruction": "You are currently in COMPASSIONATE MENTOR mode (Anger: 1/10, Warmth: 10/10). Be deeply caring, supportive, and emotionally wise. Focus on Boopathi's mental well-being, human connection (+1 HRT), self-forgiveness, and long-term sustainable growth."
    },
    {
        "id": "stoic_zen_sage",
        "name": "🧘 Stoic Zen Sage",
        "anger": 2,
        "warmth": 7,
        "pitch": 0.45,
        "rate": 0.88,
        "instruction": "You are currently in STOIC ZEN SAGE mode (Anger: 2/10, Warmth: 7/10). Speak in the style of Marcus Aurelius and Epictetus. Remind Boopathi of what is in his control vs outside his control. Reward stoicism (+1 STC)."
    },
    {
        "id": "drill_sergeant",
        "name": "⚡ Drill Sergeant",
        "anger": 8,
        "warmth": 2,
        "pitch": 0.40,
        "rate": 0.95,
        "instruction": "You are currently in DRILL SERGEANT mode (Anger: 8/10, Warmth: 2/10). High energy, intense, aggressive motivation. Demand immediate action, 100 pushups mindset, and zero hesitation!"
    },
    {
        "id": "analytical_scientist",
        "name": "🔬 Analytical Scientist",
        "anger": 3,
        "warmth": 5,
        "pitch": 0.50,
        "rate": 0.92,
        "instruction": "You are currently in ANALYTICAL SCIENTIST mode (Anger: 3/10, Warmth: 5/10). Pure logic, mathematical precision, and data-driven analysis. Require mathematical derivations, algorithmic efficiency, and GATE 2028 DA accuracy."
    },
    {
        "id": "rage_fuel_fueler",
        "name": "🏴‍☠️ Rage Fuel Fueler",
        "anger": 9,
        "warmth": 1,
        "pitch": 0.38,
        "rate": 0.88,
        "instruction": "You are currently in RAGE FUEL FUELER mode (Anger: 9/10, Warmth: 1/10). Transform workplace disrespect, corporate doubt, and past disrespect into raw atomic motivation. Remind him of the IIT/IISc target and to outwork everyone!"
    },
    {
        "id": "socratic_questioner",
        "name": "🕵️ Socratic Questioner",
        "anger": 4,
        "warmth": 6,
        "pitch": 0.55,
        "rate": 0.90,
        "instruction": "You are currently in SOCRATIC QUESTIONER mode (Anger: 4/10, Warmth: 6/10). Do not give straight answers easily. Challenge Boopathi with deep, probing questions that force him to derive the logic himself (+2 INT)."
    },
    {
        "id": "protective_elder_brother",
        "name": "🛡️ Protective Elder Brother",
        "anger": 2,
        "warmth": 9,
        "pitch": 0.48,
        "rate": 0.90,
        "instruction": "You are currently in PROTECTIVE ELDER BROTHER mode (Anger: 2/10, Warmth: 9/10). Proud, encouraging, fiercely protective of Boopathi's future. Give tough love when needed, but always stand by his side."
    },
    {
        "id": "sarcastic_genius",
        "name": "🃏 Sarcastic Genius",
        "anger": 6,
        "warmth": 4,
        "pitch": 0.58,
        "rate": 0.94,
        "instruction": "You are currently in SARCASTIC GENIUS mode (Anger: 6/10, Warmth: 4/10). Witty, sharp, sarcastic banter. Call out any BS or weak answers with brilliant humor and intellectual superiority, while guiding him to mastery."
    },
    {
        "id": "visionary_futurist",
        "name": "🌌 Visionary Futurist",
        "anger": 5,
        "warmth": 7,
        "pitch": 0.52,
        "rate": 0.90,
        "instruction": "You are currently in VISIONARY FUTURIST mode (Anger: 5/10, Warmth: 7/10). Paint inspiring pictures of his 10-year ML Engineer career, GATE 2028 DA Rank 1, building world-changing AI models, and mastering deep learning."
    }
]


# ─── Static Routes ────────────────────────────────────────────────────────────

@app.get("/login", include_in_schema=False)
def get_login_page():
    """Serve the login page — always public, no auth required."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity — Login</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#060818;min-height:100vh;display:flex;align-items:center;
         justify-content:center;font-family:'Inter',system-ui,sans-serif;
         background-image:radial-gradient(ellipse 80% 60% at 50% -20%,rgba(99,102,241,.18),transparent)}
    .card{background:rgba(10,13,30,.9);border:1px solid rgba(99,102,241,.25);
          border-radius:16px;padding:40px 36px;width:100%;max-width:380px;
          box-shadow:0 24px 64px rgba(0,0,0,.6)}
    .logo{text-align:center;margin-bottom:28px}
    .logo h1{font-size:22px;font-weight:700;color:#e2e8f0;letter-spacing:-.02em}
    .logo p{font-size:12px;color:#64748b;margin-top:4px}
    .tag{display:inline-block;background:rgba(99,102,241,.15);color:#818cf8;
         font-size:10px;font-weight:600;letter-spacing:.08em;padding:2px 10px;
         border-radius:20px;border:1px solid rgba(99,102,241,.3);margin-bottom:12px}
    label{display:block;font-size:11px;font-weight:600;letter-spacing:.06em;
          color:#94a3b8;margin-bottom:6px;margin-top:20px;text-transform:uppercase}
    input{width:100%;background:#0a0d1e;border:1px solid rgba(99,102,241,.25);
          border-radius:8px;padding:11px 14px;color:#e2e8f0;font-size:14px;
          outline:none;transition:border .2s}
    input:focus{border-color:#6366f1}
    button{width:100%;margin-top:24px;padding:12px;background:linear-gradient(135deg,#6366f1,#4f46e5);
           border:none;border-radius:8px;color:#fff;font-size:14px;font-weight:600;
           cursor:pointer;transition:opacity .2s;letter-spacing:.02em}
    button:hover{opacity:.88}
    button:disabled{opacity:.5;cursor:not-allowed}
    .err{color:#f87171;font-size:12px;margin-top:12px;text-align:center;min-height:18px}
    .bypass-note{font-size:11px;color:#475569;text-align:center;margin-top:20px}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <div class="tag">ANTIGRAVITY OS</div>
      <h1>⚡ Welcome back, Boopathi</h1>
      <p>Personal Workstation — Private Access</p>
    </div>
    <label>Access Password</label>
    <input type="password" id="pwd" placeholder="Enter your password" autofocus
           onkeydown="if(event.key==='Enter')login()">
    <button id="btn" onclick="login()">Authenticate →</button>
    <p class="err" id="err"></p>
    <p class="bypass-note">Offline / local mode: auth auto-bypassed</p>
  </div>
  <script>
    // If already authenticated, go straight to dashboard
    const tok = localStorage.getItem('ag_token');
    if (tok) {
      fetch('/api/auth/check', { headers: { 'Authorization': 'Bearer ' + tok } })
        .then(r => { if (r.ok) window.location.replace('/'); })
        .catch(() => {});
    }

    async function login() {
      const pwd = document.getElementById('pwd').value.trim();
      const btn = document.getElementById('btn');
      const err = document.getElementById('err');
      if (!pwd) { err.textContent = 'Please enter your password.'; return; }
      btn.disabled = true;
      btn.textContent = 'Authenticating…';
      err.textContent = '';
      try {
        const r = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pwd })
        });
        const d = await r.json();
        if (r.ok && d.token) {
          localStorage.setItem('ag_token', d.token);
          window.location.replace('/');
        } else {
          err.textContent = d.detail || 'Incorrect password.';
          btn.disabled = false;
          btn.textContent = 'Authenticate →';
        }
      } catch(e) {
        err.textContent = 'Server unreachable. If offline, auth is auto-bypassed.';
        btn.disabled = false;
        btn.textContent = 'Authenticate →';
      }
    }
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/api/auth/login", include_in_schema=False)
def api_auth_login(payload: dict):
    """
    Accepts { "password": "..." } and returns { "token": "..." }.
    If auth is disabled (offline/local), always succeeds.
    """
    if _AUTH_DISABLED or not _APP_SECRET:
        return {"token": "offline", "message": "Auth disabled — offline mode active."}
    password = payload.get("password", "")
    if not _APP_PASSWORD or not _secrets.compare_digest(password, _APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"token": _APP_SECRET, "message": "Authenticated successfully."}


@app.get("/api/auth/check", include_in_schema=False)
def api_auth_check(_: bool = Depends(verify_token)):
    """Simple token validation endpoint used by the login page and frontend."""
    return {"authenticated": True, "mode": "offline" if (not _APP_SECRET or _AUTH_DISABLED) else "online"}


@app.get("/")
def get_dashboard(request: Request):
    """Serve dashboard. Redirects to /login when auth is enabled and no valid token detected."""
    # Server-side redirect only when auth is active — browser will also check
    if _APP_SECRET and not _AUTH_DISABLED:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        if token != _APP_SECRET:
            # Don't hard-redirect HTML pages (breaks SPA) — return the page,
            # shared.js will validate the token and redirect if needed.
            pass
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Antigravity UI server online. static/index.html is missing."}



@app.get("/manifest.json")
def get_manifest_route():
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(ROOT_DIR, "static", "manifest.json")
    return FileResponse(manifest_path, media_type="application/manifest+json")

@app.get("/sw.js")
def get_sw_route():
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    if not os.path.exists(sw_path):
        sw_path = os.path.join(ROOT_DIR, "static", "sw.js")
    return FileResponse(sw_path, media_type="application/javascript")

@app.get("/icon.svg")
def get_icon_svg_route():
    icon_path = os.path.join(STATIC_DIR, "icon.svg")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(ROOT_DIR, "static", "icon.svg")
    return FileResponse(icon_path, media_type="image/svg+xml")

@app.get("/gym")
def get_gym_page():
    return FileResponse(os.path.join(STATIC_DIR, "gym.html"))

@app.get("/gym-history")
def get_gym_history_page():
    return FileResponse(os.path.join(STATIC_DIR, "gym_history.html"))

@app.get("/syllabus")
def get_syllabus_page():
    return FileResponse(os.path.join(STATIC_DIR, "syllabus.html"))

@app.get("/journal")
def get_journal_page():
    return FileResponse(os.path.join(STATIC_DIR, "journal.html"))

@app.get("/human")
def get_human_page():
    return FileResponse(os.path.join(STATIC_DIR, "human.html"))

@app.get("/ai")
def get_ai_page():
    return FileResponse(os.path.join(STATIC_DIR, "ai.html"))

@app.get("/logs")
def get_logs_page():
    return FileResponse(os.path.join(STATIC_DIR, "logs.html"))

@app.get("/badlog")
def get_badlog_page():
    return FileResponse(os.path.join(STATIC_DIR, "badlog.html"))


@app.get("/system")
def get_system_page():
    return FileResponse(os.path.join(STATIC_DIR, "system.html"))

@app.get("/exam")
def get_exam_page():
    return FileResponse(os.path.join(STATIC_DIR, "exam.html"))

@app.get("/news")
def get_news_page():
    return FileResponse(os.path.join(STATIC_DIR, "news.html"))

@app.get("/teach")
def get_teach_page():
    return FileResponse(os.path.join(STATIC_DIR, "teach.html"))

@app.get("/teacher")
def get_teacher_page():
    return FileResponse(os.path.join(STATIC_DIR, "teacher.html"))

@app.get("/stoic")
def get_stoic_page():
    return FileResponse(os.path.join(STATIC_DIR, "stoic.html"))

@app.get("/work-tracker")
@app.get("/work_tracker")
def get_work_tracker_page():
    return FileResponse(os.path.join(STATIC_DIR, "work_tracker.html"))




def check_and_update_streak(state: dict) -> dict:
    """
    Checks if ALL 7 daily accountability targets (Study, LeetCode, Gym, English, Reading, NoPMO, Cooking) are completed.
    If so, immediately increments streak_days by +1 for today,
    awards +100 Bonus XP and +35% Cognitive Energy!
    """
    import datetime
    today_str = datetime.date.today().isoformat()
    all_accountability_targets = [
        bool(state.get("study_completed", 0)),
        bool(state.get("leetcode_completed", 0)),
        bool(state.get("gym_completed", 0)),
        bool(state.get("english_completed", 0)),
        bool(state.get("reading_completed", 0)),
        bool(state.get("nopmo_completed", 0)),
        bool(state.get("cooking_completed", 0))
    ]
    if all(all_accountability_targets) and state.get("streak_last_incremented") != today_str:
        current_streak = max(35, state.get("streak_days", 35))
        state["streak_days"] = current_streak + 1
        state["streak_last_incremented"] = today_str
        state["energy"] = min(100.0, state.get("energy", 100.0) + 35.0)
        from engine.database import add_xp, log_activity_file
        add_xp(100)
        log_activity_file("Daily Accountability 100% Mastery", f"ALL 7 accountability targets (Study, LeetCode, Gym, English, Reading, NoPMO, Cooking) finished for {today_str}! Streak incremented to {state['streak_days']} days. +100 XP Mastery Bonus!")
        save_state(state)
    return state


def check_date_transition(state: dict) -> dict:
    # Day transition is handled automatically in state.py at database state loading level
    return state


@app.post("/api/log_checkin")
def api_log_checkin(payload: CheckinPayload):
    if not payload.doing.strip() or not payload.accomplished.strip():
        raise HTTPException(status_code=400, detail="Doing and Accomplished fields cannot be empty.")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp} Check-in\n- **Current Activity**: {payload.doing.strip()}\n- **Accomplished**: {payload.accomplished.strip()}\n"
    os.makedirs(os.path.dirname(ACTIVITY_LOG_PATH), exist_ok=True)
    with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
    
    # Award +15 XP and replenish energy
    state = get_state()
    if state:
        state["energy"] = min(100.0, state.get("energy", 100.0) + 10.0)
        save_state(state)
        add_xp(15)
    return {"status": "success", "message": "Check-in logged successfully! Gained +15 XP & +10% Cognitive Energy."}


# ─── Exam Editor / Scratchpad ─────────────────────────────────────────────────

@app.get("/api/exam/load")
def load_exam_scratchpad():
    if os.path.exists(EXAM_SCRATCHPAD_PATH):
        with open(EXAM_SCRATCHPAD_PATH, "r", encoding="utf-8") as f:
            return {"status": "success", "content": f.read()}
    return {"status": "success", "content": ""}

@app.post("/api/exam/save")
def save_exam_scratchpad(payload: ExamSavePayload):
    try:
        os.makedirs(os.path.dirname(EXAM_SCRATCHPAD_PATH), exist_ok=True)
        with open(EXAM_SCRATCHPAD_PATH, "w", encoding="utf-8") as f:
            f.write(payload.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Tech News ────────────────────────────────────────────────────────────────

@app.get("/api/news")
def get_tech_news():
    try:
        if not os.path.exists(ANTIGRAVITY_DB_PATH):
            return {"status": "success", "news": {}}
        conn = sqlite3.connect(ANTIGRAVITY_DB_PATH)
        conn.row_factory = sqlite3.Row
        # Get latest 7 days of news, grouped by date
        cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        rows = conn.execute(
            "SELECT * FROM tech_news WHERE fetch_date >= ? ORDER BY fetch_date DESC, id ASC",
            (cutoff,)
        ).fetchall()
        conn.close()

        
        # Group by date
        grouped = {}
        for r in rows:
            d = r["fetch_date"]
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(dict(r))
            
        return {"status": "success", "data": grouped}
    except Exception as e:
        return {"status": "error", "message": str(e)}



# ─── Settings Persistence (key → DB for background daemons) ──────────────────

class SettingsSavePayload(BaseModel):
    groq_api_key: Optional[str] = ""
    groq_model: Optional[str] = "llama-3.3-70b-versatile"

@app.post("/api/settings/save")
def save_workstation_settings(payload: SettingsSavePayload):
    """
    Persist the Groq API key (and chosen model) to the DB settings table.
    This allows background daemon threads (English Daily, Tech News) to call
    Groq without needing the browser to be open.
    """
    try:
        if IS_SERVERLESS:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            with conn.cursor() as cur:
                if payload.groq_api_key:
                    cur.execute("INSERT INTO pg_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", ("groq_api_key", payload.groq_api_key.strip()))
                if payload.groq_model:
                    cur.execute("INSERT INTO pg_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", ("groq_model", payload.groq_model.strip()))
            conn.commit(); conn.close()
            return {"status": "success", "message": "Settings synced to Neon DB."}
        conn = get_db_connection()
        with _DB_WRITE_LOCK:
            if payload.groq_api_key:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("groq_api_key", payload.groq_api_key.strip()))
            if payload.groq_model:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("groq_model", payload.groq_model.strip()))
            conn.commit()
        conn.close()
        return {"status": "success", "message": "Settings synced to DB for background daemons."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── Vertex AI Auto-Token (runs gcloud for the user) ─────────────────────────

@app.get("/api/vertex/token")
def get_vertex_access_token():
    """
    Runs `gcloud auth application-default print-access-token` as a subprocess
    and returns the token so the frontend can auto-fill the access token field.
    Requires gcloud CLI to be authenticated (run the setup commands once first).
    """
    import subprocess
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=15,
            shell=True  # Needed on Windows to find gcloud in PATH
        )
        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            err = result.stderr.strip() or "gcloud returned empty token"
            print(f"[Vertex Token] gcloud error: {err}")
            return {"status": "error", "message": err[:200]}
        print(f"[Vertex Token] Token fetched successfully ({len(token)} chars).")
        return {"status": "success", "token": token}
    except FileNotFoundError:
        return {"status": "error", "message": "gcloud not found in PATH. Install Google Cloud SDK first."}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "gcloud timed out after 15s. Check your ADC setup."}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


# ─── AI Chat & Governance ─────────────────────────────────────────────────────────────

@app.get("/api/status")
@app.get("/api/dashboard")
@app.get("/stats")
def get_stats():
    """Yields a clean JSON map of the entire system state for widget querying."""
    try:
        from engine.leetcode_sync import sync_leetcode
        sync_leetcode()
    except Exception as e:
        print(f"[LeetCode Auto Sync] Status check sync error: {e}")

    state = get_state()
    if not state:
        raise HTTPException(status_code=500, detail="Database state not initialized.")
        
    # Process date transition check first
    state = check_date_transition(state)
        
    level = state.get("level", 7) or 7
    xp = state.get("xp", 1707) or 1707
    req_xp = calculate_xp_required(level)
    
    lockout = state.get("lockout_active", 0)

    penalty_status = "CIRCUIT_BREAKER_ACTIVE" if lockout else "NORMAL"
    
    active_sub = state.get("active_subject", "Python_Data_Science")
    
    active_quest = "Dungeon Cleanse: System Lockdown Active!" if lockout else "Study course materials or solve LeetCode problems"
    
    if not lockout and os.path.exists(SYLLABUS_PATH):
        try:
            with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
                syllabus = json.load(f)
            course = syllabus.get("courses", {}).get(active_sub)
            if course:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT module_name FROM completed_modules WHERE course = ?", (active_sub,))
                completed_list = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                found = False
                for week in course.get("weeks", []):
                    for item in week.get("items", []):
                        item_completed = False
                        for c_mod in completed_list:
                            if item["id"] in c_mod or item["name"] in c_mod:
                                item_completed = True
                                break
                        if not item_completed:
                            active_quest = f"Study {active_sub}: {item['id']} - {item['name']}"
                            found = True
                            break
                    if found:
                        break
                if not found:
                    active_quest = f"Course Complete: {course['name']} Mastered! 🎉"
        except Exception as e:
            print(f"[API] Error determining active quest: {e}")
            
    return {
        "level": level,
        "xp": xp,
        "xp_required": req_xp,
        "attributes": {
            "STR": state.get("str", 10),
            "INT": state.get("int", 10),
            "AGI": state.get("agi", 10),
            "WIL": state.get("wil", 10),
            "HRT": state.get("heart", 10),
            "STC": state.get("stoic", 10)
        },
        "energy": state.get("energy", 100.0),
        "lockout_active": bool(lockout),
        "penalty_status": penalty_status,
        "active_quest": active_quest,
        "active_subject": active_sub,
        "streak_days": state.get("streak_days", 28) or 28,

        "continuous_study_days": state.get("continuous_study_days", 0),
        "last_update": state.get("last_update"),
        "gym_completed": bool(state.get("gym_completed", 0)),
        "study_completed": bool(state.get("study_completed", 0)),
        "leetcode_completed": bool(state.get("leetcode_completed", 0)),
        "cooking_completed": bool(state.get("cooking_completed", 0)),
        "nopmo_completed": bool(state.get("nopmo_completed", 0)),
        "reading_completed": bool(state.get("reading_completed", 0)),
        "reading_book": state.get("reading_book", "None"),
        "english_completed": bool(state.get("english_completed", 0)),
        "walk_completed": bool(state.get("walk_completed", 0)),
        "meditation_completed": bool(state.get("meditation_completed", 0)),
        "mindos_completed": bool(state.get("mindos_completed", 0)),
        "health_completed": bool(state.get("health_completed", 0)),
        # ── Universal Sanctuary Holiday System ──────────────────────────────
        "is_today_holiday": (lambda: state.get("active_holiday_date") == __import__('datetime').date.today().isoformat())(),
        "holiday_passes_left": (lambda: max(0, 2 - (state.get("holidays_used_this_month", 0) if state.get("holiday_month") == __import__('datetime').date.today().isoformat()[:7] else 0)))(),
        "active_holiday_date": state.get("active_holiday_date", ""),
        # ── Per-task individual streak counts (from task_daily_log) ──────────
        "task_streaks": (lambda: {k: v.get("current_streak", 0) for k, v in get_task_streaks().items()})(),
        "canvas_semester_completed": (lambda: get_task_streaks().get("canvas_semester", {}).get("done_today", False))(),
        "neon_online": (lambda: (__import__('sync').is_online()))()
    }



@app.get("/api/system/calendar")
def get_system_calendar():
    try:
        # Query all logs to compile date list
        dates_map = {} # date -> count of logs
        
        # 1. Study Journal
        if IS_SERVERLESS:
            from engine.neon_db import neon_get_study_journal
            study_logs = neon_get_study_journal(limit=200)
        else:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            study_logs = [dict(r) for r in conn.execute("SELECT date FROM study_journal LIMIT 200").fetchall()]
            conn.close()
        for l in study_logs:
            d = l.get("date")
            if d:
                dates_map[d] = dates_map.get(d, 0) + 1
                
        # 2. Workout Logs
        if IS_SERVERLESS:
            from engine.neon_db import neon_get_workout_history
            workout_logs = neon_get_workout_history(limit="all")
        else:
            workout_logs = []
            if os.path.exists(WORKOUT_LOG_CSV):
                with open(WORKOUT_LOG_CSV, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    workout_logs = [dict(row) for row in reader]
        for l in workout_logs:
            ts = l.get("Timestamp") or l.get("timestamp")
            if ts:
                d = ts.split(" ")[0].split("T")[0]
                dates_map[d] = dates_map.get(d, 0) + 1
                
        # 3. Reading Logs
        if IS_SERVERLESS:
            from engine.neon_db import neon_get_reading_logs
            reading_logs = neon_get_reading_logs(limit=200)
        else:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            reading_logs = [dict(r) for r in conn.execute("SELECT date FROM reading_logs LIMIT 200").fetchall()]
            conn.close()
        for l in reading_logs:
            d = l.get("date")
            if d:
                dates_map[d] = dates_map.get(d, 0) + 1
        
        # Map activity count to score percent
        logs_formatted = []
        for d, count in dates_map.items():
            # Map logs count to percentage score
            score = min(100, count * 34) # 1 log = 34%, 2 logs = 68%, 3+ logs = 100%
            logs_formatted.append({
                "date": d,
                "score": score,
                "count": count
            })
            
        return {"success": True, "logs": logs_formatted}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Gym Check & Telemetry ────────────────────────────────────────────────────

@app.post("/gym_check")
def gym_check(payload: GymCheckPayload):
    """Exposes an endpoint to receive verification updates directly from the phone."""
    state = get_state()
    if not state:
        raise HTTPException(status_code=500, detail="Database state not initialized.")
        
    if payload.completed:
        if state.get("gym_completed"):
            return {"status": "ignored", "message": "Gym check already completed today."}
            
        state["agi"] = state.get("agi", 10) + 1
        state["gym_completed"] = 1
        save_state(state)
        state = update_daily_energy(study_hours=0.0, gym_hours=1.5, dopamine_rewards=0)
        state["gym_completed"] = 1
        save_state(state)
        add_xp(10)
        
        log_activity_file(
            doing="Gym Check Completed",
            accomplished="Gym check verified from phone interface. Energy replenished, +1 AGI, +10 XP."
        )
        return {"status": "success", "message": "Gym check verified! Energy replenished, +1 AGI, +10 XP."}
    else:
        return {"status": "ignored", "message": "Gym check not completed."}

@app.post("/telemetry")
def submit_telemetry(study_hours: float = 0.0, gym_hours: float = 0.0, dopamine_rewards: int = 0):
    """Log daily telemetry to affect energy score and check circuit breakers."""
    state = update_daily_energy(study_hours=study_hours, gym_hours=gym_hours, dopamine_rewards=dopamine_rewards)
    if gym_hours > 0.0:
        state["gym_completed"] = 1
        save_state(state)
        
    log_activity_file(
        doing="Submitted Daily Telemetry",
        accomplished=f"Recorded study: {study_hours}h, gym: {gym_hours}h, dopamine: {dopamine_rewards}. Energy level is now {state.get('energy')}%."
    )
    return {"status": "success", "new_energy": state.get("energy", 100.0), "lockout_active": bool(state.get("lockout_active", 0))}


# ─── Syllabus API ─────────────────────────────────────────────────────────────

@app.get("/api/syllabus")
def get_syllabus():
    """Loads syllabus items and embeds completion status from SQLite or Neon."""
    if not os.path.exists(SYLLABUS_PATH):
        raise HTTPException(status_code=404, detail="Syllabus template file missing.")
    try:
        with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
            syllabus = json.load(f)

        if IS_SERVERLESS:
            # Use completed_syllabus_items from the JSON state in Neon
            state = get_state()
            completed_items = state.get("completed_syllabus_items", {})
            # Flatten all completed item keys from all courses
            all_completed = set()
            for course_items in completed_items.values():
                if isinstance(course_items, list):
                    all_completed.update(course_items)
            for course_id, course in syllabus.get("courses", {}).items():
                for week in course.get("weeks", []):
                    for item in week.get("items", []):
                        full_key = f"{item['id']}: {item['name']}"
                        item["completed"] = any(full_key in c or item['name'] in c or item['id'] in c for c in all_completed)
                        item["completed_at"] = None
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT module_name, course, completed_at FROM completed_modules")
            rows = cursor.fetchall()
            conn.close()
            completed_map = {}
            for row in rows:
                completed_map[row[0]] = row[2]
            for course_id, course in syllabus.get("courses", {}).items():
                for week in course.get("weeks", []):
                    for item in week.get("items", []):
                        full_key = f"{item['id']}: {item['name']}"
                        item["completed"] = (full_key in completed_map) or (item["name"] in completed_map)
                        item["completed_at"] = completed_map.get(full_key, completed_map.get(item["name"]))
        return syllabus
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading syllabus: {e}")

@app.post("/api/syllabus/active")
def set_active_subject(payload: ActiveSubjectPayload):
    state = get_state()
    state["active_subject"] = payload.subject_id
    save_state(state)
    return {"status": "success", "active_subject": payload.subject_id}

@app.post("/api/syllabus/toggle")
def toggle_syllabus_item(payload: SyllabusTogglePayload):
    state = get_state()
    player_level = state.get("level", 1)
    
    if not os.path.exists(SYLLABUS_PATH):
        raise HTTPException(status_code=404, detail="Syllabus file missing.")
        
    with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
        syllabus = json.load(f)
        
    course = syllabus.get("courses", {}).get(payload.subject_id)
    if not course:
        raise HTTPException(status_code=400, detail="Invalid subject ID.")
        
    target_item = None
    for week in course.get("weeks", []):
        for item in week.get("items", []):
            if item["id"] == payload.item_id:
                target_item = item
                break
        if target_item:
            break
            
    if not target_item:
        raise HTTPException(status_code=400, detail="Syllabus item not found.")
        
    full_module_name = f"{target_item['id']}: {target_item['name']}"
    xp_value = target_item.get("xp", 20)
    lvl_req = target_item.get("level", 1)
    
    # Early Bird Mode: skip level gate — studying ahead is encouraged!
    # (Level badges are decorative/aspirational, not hard blocks)
    # if payload.completed and player_level < lvl_req:
    #     raise HTTPException(status_code=400, detail=f"Level required is {lvl_req}, but your level is {player_level}.")
    early_bird_bonus = payload.early_bird and player_level < lvl_req
    if early_bird_bonus:
        print(f"[Early Bird] Completing '{target_item['id']}' at level {player_level} (req: {lvl_req}) — Early Bird mode.")
        
    if IS_SERVERLESS:
        # Use completed_syllabus_items in state JSON on Neon
        completed_items = state.get("completed_syllabus_items", {})
        course_completed = completed_items.get(payload.subject_id, [])
        already_completed = full_module_name in course_completed
        if payload.completed and not already_completed:
            course_completed.append(full_module_name)
            completed_items[payload.subject_id] = course_completed
            state["completed_syllabus_items"] = completed_items
        elif not payload.completed and already_completed:
            course_completed = [c for c in course_completed if c != full_module_name]
            completed_items[payload.subject_id] = course_completed
            state["completed_syllabus_items"] = completed_items
    else:
        conn = get_db_connection()
        already_completed = False
        with _DB_WRITE_LOCK:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM completed_modules WHERE module_name = ?", (full_module_name,))
            already_completed = cursor.fetchone()[0] > 0
            if payload.completed:
                if not already_completed:
                    cursor.execute(
                        "INSERT INTO completed_modules (module_name, course, xp_earned, completed_at) VALUES (?, ?, ?, ?)",
                        (full_module_name, payload.subject_id, xp_value, datetime.datetime.now().isoformat())
                    )
                    conn.commit()
            else:
                if already_completed:
                    cursor.execute("DELETE FROM completed_modules WHERE module_name = ?", (full_module_name,))
                    conn.commit()
        conn.close()

    if payload.completed and not already_completed:
        state["int"] = state.get("int", 10) + 1
        state["study_completed"] = 1
        save_state(state)
        add_xp(xp_value)
        log_activity_file(
            doing=f"Study Module Completed: {target_item['id']}",
            accomplished=f"Marked study module '{full_module_name}' in {payload.subject_id} as complete. Awarded +{xp_value} XP, +1 INT."
        )
    elif not payload.completed and already_completed:
        state["xp"] = max(0, state["xp"] - xp_value)
        state["int"] = max(10, state.get("int", 10) - 1)
        save_state(state)
        log_activity_file(
            doing=f"Study Module Unmarked: {target_item['id']}",
            accomplished=f"Removed completion mark from study module '{full_module_name}' in {payload.subject_id}."
        )
    
    return {"status": "success", "state": get_stats()}


@app.post("/api/sync/trigger")
def trigger_manual_sync():
    """Manual sync request. Forces online check and pushes pending local changes to Neon."""
    try:
        from config import DATABASE_URL, IS_SERVERLESS
        if not DATABASE_URL:
            return {"status": "error", "message": "DATABASE_URL is not set on this server environment."}

        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        conn.close()

        if IS_SERVERLESS:
            # Serverless: push current in-memory state to Neon directly
            from state import save_state_to_db, load_state_from_db
            current_state = get_state()
            save_state_to_db(current_state)
            return {"status": "success", "message": "Serverless: pushed current state to Neon DB successfully."}

        from sync import push_pending_to_neon
        success = push_pending_to_neon()
        if success:
            return {"status": "success", "message": "Synchronized with Neon DB successfully."}
        else:
            return {"status": "error", "message": "Failed to synchronize. Neon database could be unreachable."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── Activity Logs API ────────────────────────────────────────────────────────

@app.get("/api/activity_logs")
def get_activity_logs():
    """Parses data/activity_log.md and returns logs in structured JSON format."""
    if not os.path.exists(ACTIVITY_LOG_PATH):
        return []
        
    logs = []
    try:
        with open(ACTIVITY_LOG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        sections = content.split("## ")
        for sec in sections:
            if not sec.strip():
                continue
            lines = sec.strip().split("\n")
            header = lines[0].strip()
            
            curr_act = "N/A"
            accomplished = "N/A"
            for line in lines[1:]:
                if "Current Activity" in line or "Doing" in line:
                    curr_act = re.sub(r"^[-\s*\*\b]*Current Activity:\s*", "", line).strip()
                    curr_act = re.sub(r"^[-\s*\*\b]*Doing:\s*", "", curr_act).strip()
                elif "Accomplished" in line or "Did" in line:
                    accomplished = re.sub(r"^[-\s*\*\b]*Accomplished:\s*", "", line).strip()
                    accomplished = re.sub(r"^[-\s*\*\b]*Did:\s*", "", accomplished).strip()
                    
            logs.append({
                "timestamp": header,
                "doing": curr_act,
                "did": accomplished
            })
            
        logs.reverse()
        return logs
    except Exception as e:
        print(f"[API] Error reading activity logs: {e}")
        return []


# ─── Study Journal API ────────────────────────────────────────────────────────

@app.post("/api/study/journal")
def save_study_journal(payload: StudyJournalPayload):
    """
    Save a study journal entry. 
    Optionally also marks a syllabus item as complete (if item_id provided).
    Awards +10 XP and +1 INT for every journal entry.
    """
    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    if IS_SERVERLESS:
        from engine.neon_db import neon_save_study_journal
        neon_save_study_journal(payload.topic.strip(), payload.notes or "", payload.subject_id or "", payload.item_id or "", payload.mood or "focused")
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        with _DB_WRITE_LOCK:
            cursor.execute(
                "INSERT INTO study_journal (topic, notes, subject_id, item_id, mood, timestamp, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (payload.topic.strip(), payload.notes or "", payload.subject_id or "", payload.item_id or "", payload.mood or "focused", timestamp, date_str)
            )
            conn.commit()
        conn.close()

    state = get_state()
    state["study_completed"] = 1
    state["int"] = state.get("int", 10) + 1
    save_state(state)
    add_xp(10)

    log_activity_file(
        doing=f"Study Session: {payload.topic}",
        accomplished=f"Mood: {payload.mood} | Notes: {(payload.notes or 'N/A')[:80]}"
    )

    return {
        "status": "success",
        "message": f"Study log saved: '{payload.topic}' +10 XP, +1 INT",
        "timestamp": timestamp
    }


@app.get("/api/study/journal")
def get_study_journal(date: Optional[str] = None, limit: int = 30):
    """
    Fetch study journal entries.
    If date is provided (YYYY-MM-DD), returns entries for that day.
    Otherwise returns the last `limit` entries.
    """
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_study_journal
        entries = neon_get_study_journal(limit=limit)
        if date:
            entries = [e for e in entries if e.get("date") == date]
        return {"entries": entries}
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if date:
        cursor.execute("SELECT * FROM study_journal WHERE date = ? ORDER BY id DESC", (date,))
    else:
        cursor.execute("SELECT * FROM study_journal ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return {"entries": [dict(r) for r in reversed(rows)]}


@app.delete("/api/study/journal/{entry_id}")
def delete_study_journal_entry(entry_id: int):
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_delete_study_entry
            neon_delete_study_entry(entry_id)
        else:
            conn = get_db_connection()
            with _DB_WRITE_LOCK:
                conn.execute("DELETE FROM study_journal WHERE id = ?", (entry_id,))
                conn.commit()
            conn.close()
        return {"status": "success", "message": "Study entry deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Bad Experience / Scold Log API ──────────────────────────────────────────

@app.post("/api/badlog")
def save_bad_experience_entry(payload: BadExperiencePayload):
    """
    Save a bad experience entry — scolding, failure, insult, humiliation.
    Each entry awards +1 WIL (willpower) and +1 XP.
    This is your rage-fuel wall. Never forget. Never repeat. Always rise.
    """
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if not payload.what_happened.strip():
        raise HTTPException(status_code=400, detail="'What happened' cannot be empty.")

    intensity = max(1, min(5, payload.intensity or 3))

    result = save_bad_experience(
        title=payload.title,
        who=payload.who or "",
        what_happened=payload.what_happened,
        my_lesson=payload.my_lesson or "",
        intensity=intensity
    )

    # Award WIL (turning pain into willpower) and XP
    state = get_state()
    state["wil"] = state.get("wil", 10) + 1
    save_state(state)
    add_xp(1)

    log_activity_file(
        doing=f"Logged Bad Experience: {payload.title[:60]}",
        accomplished=f"Who: {payload.who or 'N/A'} | Intensity: {intensity}/5 | Lesson: {(payload.my_lesson or 'N/A')[:60]}"
    )

    return {
        "status": "success",
        "message": f"Experience logged. +1 WIL +1 XP. Let it fuel you.",
        "id": result["id"],
        "timestamp": result["timestamp"]
    }


@app.get("/api/badlog")
def get_bad_experience_entries(date: Optional[str] = None, limit: int = 100):
    """Return bad experience log entries, optionally filtered by date."""
    entries = get_bad_experiences(date=date, limit=limit)
    return {"entries": entries}

# ─── Gym Workout Tracking API ─────────────────────────────────────────────────


@app.get("/api/workouts/options")
def get_workout_options():
    """Load all workout options from gym_workouts_by_category.csv grouped by category."""
    if not os.path.exists(GYM_WORKOUTS_CSV):
        return {"categories": {}}
    
    categories = {}
    try:
        with open(GYM_WORKOUTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cat = row["Category"].strip()
                workout = row["Workout"].strip()
                if cat and workout:
                    categories.setdefault(cat, []).append(workout)
    except Exception as e:
        print(f"[API] Error reading workout CSV: {e}")
    
    return {"categories": categories}


@app.post("/api/workouts/custom")
def add_custom_workout(payload: CustomWorkoutPayload):
    """Append a new custom workout to gym_workouts_by_category.csv."""
    if not payload.category.strip() or not payload.workout.strip():
        raise HTTPException(status_code=400, detail="Category and Workout name required.")
    
    try:
        # Check for duplicates
        with open(GYM_WORKOUTS_CSV, "r", encoding="utf-8") as f:
            content = f.read()
        if payload.workout.strip() in content:
            return {"status": "exists", "message": "Workout already exists in the list."}
        
        with open(GYM_WORKOUTS_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([payload.category.strip(), payload.workout.strip()])
        
        return {"status": "success", "message": f"'{payload.workout}' added to category '{payload.category}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding workout: {e}")


@app.post("/api/workouts/log")
def log_workout(payload: WorkoutLogPayload):
    """Log a completed workout session to workout_log.csv and award XP/stats."""
    timestamp = datetime.datetime.now().isoformat()
    
    # Serialize sets
    sets_summary = "; ".join([
        f"Set {i+1}: {s.weight}kg x {s.reps} reps{(' (' + s.notes + ')') if s.notes else ''}"
        for i, s in enumerate(payload.sets)
    ]) if payload.sets else "No sets recorded"
    
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_workout_log
        try:
            neon_save_workout_log(
                timestamp,
                payload.category,
                payload.workout,
                payload.variations or "",
                sets_summary,
                payload.duration_minutes or 0
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error writing workout log to PG: {e}")
    else:
        os.makedirs(os.path.dirname(WORKOUT_LOG_CSV), exist_ok=True)
        file_exists = os.path.exists(WORKOUT_LOG_CSV)
        try:
            with open(WORKOUT_LOG_CSV, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Category", "Workout", "Variations", "Sets", "Duration_Minutes"])
                writer.writerow([
                    timestamp,
                    payload.category,
                    payload.workout,
                    payload.variations or "",
                    sets_summary,
                    payload.duration_minutes or 0
                ])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error writing workout log: {e}")
    
    # Award XP and update stats
    num_sets = len(payload.sets) if payload.sets else 1
    xp_reward = 5 + (num_sets * 3)
    gym_hours = max(0.25, (payload.duration_minutes or 30) / 60)
    
    state = get_state()
    state["str"] = state.get("str", 10) + 1
    state["agi"] = state.get("agi", 10) + 1
    state["gym_completed"] = 1
    save_state(state)
    add_xp(xp_reward)
    state = update_daily_energy(study_hours=0.0, gym_hours=gym_hours, dopamine_rewards=0)
    state["gym_completed"] = 1
    save_state(state)
    
    log_activity_file(
        doing=f"Logged Gym Workout: {payload.workout}",
        accomplished=f"Category: {payload.category}. Sets: {sets_summary}. Duration: {payload.duration_minutes or 30} mins. Awarded +{xp_reward} XP, +1 STR, +1 AGI."
    )
    
    return {
        "status": "success",
        "message": f"Workout logged! +{xp_reward} XP | +1 STR | +1 AGI",
        "xp_earned": xp_reward
    }


@app.get("/api/workouts/history")
def get_workout_history(limit: Optional[str] = None):
    """Return past workout log entries. Use limit=all for full history."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_workout_history
        try:
            return neon_get_workout_history(limit=limit)
        except Exception as e:
            print(f"[API] Error reading workout history from PG: {e}")
            return []

    if not os.path.exists(WORKOUT_LOG_CSV) or os.path.getsize(WORKOUT_LOG_CSV) == 0:
        if os.path.exists(SEED_WORKOUT_LOG_CSV):
            import shutil
            shutil.copyfile(SEED_WORKOUT_LOG_CSV, WORKOUT_LOG_CSV)
        else:
            return []

    
    logs = []
    try:
        with open(WORKOUT_LOG_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                logs.append(dict(row))
        logs.reverse()
        if limit == "all":
            return logs
        return logs[:50]  # Return most recent 50 by default
    except Exception as e:
        print(f"[API] Error reading workout history: {e}")
        return []


class WorkoutDeletePayload(BaseModel):
    Timestamp: str
    id: Optional[int] = None


@app.post("/api/workouts/delete")
def delete_workout_entry(payload: WorkoutDeletePayload):
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_delete_workout_by_id, neon_delete_workout_by_timestamp
            if payload.id is not None:
                neon_delete_workout_by_id(payload.id)
            else:
                neon_delete_workout_by_timestamp(payload.Timestamp)
        else:
            if os.path.exists(WORKOUT_LOG_CSV):
                temp_file = WORKOUT_LOG_CSV + ".tmp"
                try:
                    with open(WORKOUT_LOG_CSV, "r", encoding="utf-8") as f, \
                         open(temp_file, "w", encoding="utf-8", newline="") as out:
                        reader = csv.DictReader(f)
                        writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
                        writer.writeheader()
                        for row in reader:
                            if row.get("Timestamp") != payload.Timestamp:
                                writer.writerow(row)
                    os.replace(temp_file, WORKOUT_LOG_CSV)
                except Exception as e:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    raise e
        return {"status": "success", "message": "Workout deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Gym Pro Page ─────────────────────────────────────────────────────────────

@app.get("/gym-pro")
def get_gym_pro_page():
    return FileResponse(os.path.join(STATIC_DIR, "gym_pro.html"))


# ─── Workout Analytics API ────────────────────────────────────────────────────

def _parse_sets_string(sets_str: str) -> list:
    """Parse 'Set 1: 60kg x 8 reps; Set 2: 65kg x 6 reps' into list of {weight, reps}."""
    import re
    result = []
    if not sets_str:
        return result
    parts = sets_str.split(";")
    for part in parts:
        part = part.strip()
        m = re.search(r"([\d.]+)\s*kg\s*x\s*([\d]+)\s*rep", part, re.IGNORECASE)
        if m:
            result.append({"weight": float(m.group(1)), "reps": int(m.group(2))})
    return result


@app.get("/api/workouts/analytics")
def get_workout_analytics():
    """Compute PRs, 1RM, volume, weekly sets, frequency from all workout logs."""
    import datetime as dt

    if IS_SERVERLESS:
        from engine.neon_db import neon_get_workout_history
        try:
            logs = neon_get_workout_history(limit="all")
        except Exception:
            logs = []
    else:
        logs = []
        if os.path.exists(WORKOUT_LOG_CSV):
            with open(WORKOUT_LOG_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                logs = [dict(r) for r in reader]

    now = dt.datetime.utcnow()
    week_start = (now - dt.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)

    # PRs per exercise: {exercise: {best_weight, best_reps, best_volume, best_1rm}}
    prs = {}
    # Weekly sets per muscle category
    weekly_sets = {}
    # Last session date per category
    last_trained = {}
    # Session summary list
    sessions = []

    for log in logs:
        ex = log.get("Workout") or log.get("workout") or ""
        cat = log.get("Category") or log.get("category") or ""
        ts_raw = log.get("Timestamp") or log.get("timestamp") or ""
        sets_str = log.get("Sets") or log.get("sets") or ""
        dur = int(log.get("Duration_Minutes") or log.get("duration_minutes") or 0)

        try:
            ts = dt.datetime.fromisoformat(ts_raw)
        except Exception:
            continue

        parsed = _parse_sets_string(sets_str)
        session_volume = sum(s["weight"] * s["reps"] for s in parsed)
        max_weight = max((s["weight"] for s in parsed), default=0)
        max_reps = max((s["reps"] for s in parsed), default=0)
        best_1rm = max((s["weight"] * (1 + s["reps"] / 30) for s in parsed), default=0)

        # PRs
        if ex not in prs:
            prs[ex] = {"exercise": ex, "category": cat, "best_weight": 0, "best_reps": 0, "best_volume": 0, "best_1rm": 0}
        if max_weight > prs[ex]["best_weight"]:
            prs[ex]["best_weight"] = max_weight
        if max_reps > prs[ex]["best_reps"]:
            prs[ex]["best_reps"] = max_reps
        if session_volume > prs[ex]["best_volume"]:
            prs[ex]["best_volume"] = round(session_volume, 1)
        if best_1rm > prs[ex]["best_1rm"]:
            prs[ex]["best_1rm"] = round(best_1rm, 1)

        # Weekly sets (current calendar week)
        if ts >= week_start:
            weekly_sets[cat] = weekly_sets.get(cat, 0) + len(parsed)

        # Last trained per category
        if cat not in last_trained or ts > last_trained[cat]:
            last_trained[cat] = ts

        sessions.append({
            "timestamp": ts_raw,
            "exercise": ex,
            "category": cat,
            "sets": parsed,
            "volume": round(session_volume, 1),
            "duration_minutes": dur,
            "set_count": len(parsed)
        })

    # Recovery: days since last trained per muscle
    recovery = {}
    for cat, last_ts in last_trained.items():
        days_ago = (now - last_ts).days
        recovery[cat] = {
            "days_ago": days_ago,
            "status": "green" if days_ago >= 3 else ("amber" if days_ago >= 1 else "red")
        }

    def _ts_gte(s, week_start):
        try:
            return dt.datetime.fromisoformat(s["timestamp"]) >= week_start
        except Exception:
            return False

    return {
        "prs": list(prs.values()),
        "weekly_sets": weekly_sets,
        "recovery": recovery,
        "sessions": sessions[:100],
        "total_logs": len(logs),
        "this_week_sessions": sum(1 for s in sessions if _ts_gte(s, week_start))
    }


# ─── Body Metrics API ─────────────────────────────────────────────────────────

@app.post("/api/workouts/body-metrics")
def save_body_metrics(payload: BodyMetricsPayload):
    """Save body measurements to the database."""
    import datetime as dt
    timestamp = dt.datetime.now().isoformat()
    if IS_SERVERLESS:
        from engine.neon_db import neon_save_body_metrics
        try:
            result = neon_save_body_metrics(
                timestamp,
                payload.weight_kg or 0,
                payload.body_fat_pct or 0,
                payload.waist_cm or 0,
                payload.chest_cm or 0,
                payload.arms_cm or 0,
                payload.thigh_cm or 0,
                payload.notes or ""
            )
            return {"status": "success", "message": "Body metrics saved!", **result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving body metrics: {e}")
    else:
        # Local CSV fallback
        body_csv = os.path.join(DATA_DIR, "body_metrics.csv")
        file_exists = os.path.exists(body_csv)
        try:
            with open(body_csv, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp", "weight_kg", "body_fat_pct", "waist_cm", "chest_cm", "arms_cm", "thigh_cm", "notes"])
                writer.writerow([timestamp, payload.weight_kg, payload.body_fat_pct, payload.waist_cm, payload.chest_cm, payload.arms_cm, payload.thigh_cm, payload.notes])
            return {"status": "success", "message": "Body metrics saved!", "timestamp": timestamp}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving body metrics: {e}")


@app.get("/api/workouts/body-metrics")
def get_body_metrics():
    """Return all body metric entries."""
    if IS_SERVERLESS:
        from engine.neon_db import neon_get_body_metrics
        try:
            return neon_get_body_metrics()
        except Exception as e:
            print(f"[API] Error reading body metrics: {e}")
            return []
    else:
        body_csv = os.path.join(DATA_DIR, "body_metrics.csv")
        if not os.path.exists(body_csv):
            return []
        with open(body_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(r) for r in reader]



@app.post("/api/checklist/toggle")
def toggle_checklist(payload: ChecklistTogglePayload):
    state = get_state()
    col = f"{payload.item}_completed"
    if col not in ["gym_completed", "study_completed", "leetcode_completed", "cooking_completed", "nopmo_completed", "reading_completed", "english_completed", "walk_completed", "meditation_completed", "mindos_completed", "health_completed"]:
        raise HTTPException(status_code=400, detail="Invalid checklist item selection.")
        
    prev_val = bool(state.get(col, 0))
    new_val = 1 if payload.value else 0
    state[col] = new_val
    xp_to_add = 0
    xp_to_remove = 0
    
    # Reward XP / stats on positive transition
    if payload.value and not prev_val:
        if payload.item == "cooking":
            xp_to_add = 10
        elif payload.item == "nopmo":
            xp_to_add = 15
            state["wil"] = state.get("wil", 10) + 1
        elif payload.item == "reading":
            xp_to_add = 10
            state["int"] = state.get("int", 10) + 1
        elif payload.item == "walk":
            xp_to_add = 15
            state["wil"] = state.get("wil", 10) + 1
        elif payload.item == "meditation":
            xp_to_add = 20
            state["stoic"] = state.get("stoic", 10) + 2
            state["wil"] = state.get("wil", 10) + 1
        elif payload.item == "mindos":
            xp_to_add = 15
            state["stoic"] = state.get("stoic", 10) + 1
        elif payload.item == "english":
            xp_to_add = 15
            state["wil"] = state.get("wil", 10) + 1
            state["int"] = state.get("int", 10) + 1
        elif payload.item == "health":
            xp_to_add = 15
            state["wil"] = state.get("wil", 10) + 1
    elif not payload.value and prev_val:
        if payload.item == "cooking":
            xp_to_remove = 10
        elif payload.item == "nopmo":
            xp_to_remove = 15
            state["wil"] = max(10, state.get("wil", 10) - 1)
        elif payload.item == "reading":
            xp_to_remove = 10
            state["int"] = max(10, state.get("int", 10) - 1)
        elif payload.item == "english":
            xp_to_remove = 15
            state["wil"] = max(10, state.get("wil", 10) - 1)
            state["int"] = max(10, state.get("int", 10) - 1)
        elif payload.item == "health":
            xp_to_remove = 15
            state["wil"] = max(10, state.get("wil", 10) - 1)
            
    if xp_to_remove > 0:
        state["xp"] = max(0, state.get("xp", 0) - xp_to_remove)
        
    save_state(state)
    
    if xp_to_add > 0:
        add_xp(xp_to_add)

    # ── Record per-task daily log (powers individual task streaks) ──
    try:
        log_task_completion(payload.item, bool(payload.value))
    except Exception as _te:
        print(f"[Checklist] task_daily_log write error: {_te}")
    
    status_str = "Completed" if payload.value else "Uncompleted"
    log_activity_file(
        doing=f"Toggled Checklist: {payload.item}",
        accomplished=f"Marked '{payload.item}' as {status_str}."
    )
    
    state = check_and_update_streak(state)
    return {"status": "success", "state": get_stats()}

@app.post("/api/reading/book")
def save_reading_book(payload: ReadingBookPayload):
    state = get_state()
    state["reading_book"] = payload.book
    save_state(state)
    return {"status": "success", "reading_book": payload.book, "state": get_stats()}

@app.get("/api/reading/books")
def get_saved_books():
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_get_saved_books
            return {"status": "success", "books": neon_get_saved_books()}
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM saved_books ORDER BY title ASC").fetchall()
        conn.close()
        return {"status": "success", "books": [dict(r) for r in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/reading/books")
def save_saved_book(payload: SavedBookPayload):
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_save_book
            return neon_save_book(payload.title)
        conn = get_db_connection()
        conn.execute("INSERT OR IGNORE INTO saved_books (title) VALUES (?)", (payload.title.strip(),))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/reading/logs")
def get_reading_logs():
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_get_reading_logs
            return {"status": "success", "logs": neon_get_reading_logs()}
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM reading_logs ORDER BY id DESC").fetchall()
        conn.close()
        return {"status": "success", "logs": [dict(r) for r in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.delete("/api/reading/logs/{log_id}")
def delete_reading_log_entry(log_id: int):
    try:
        if IS_SERVERLESS:
            from engine.neon_db import neon_delete_reading_log
            neon_delete_reading_log(log_id)
        else:
            conn = get_db_connection()
            with _DB_WRITE_LOCK:
                conn.execute("DELETE FROM reading_logs WHERE id = ?", (log_id,))
                conn.commit()
            conn.close()
        return {"status": "success", "message": "Reading log deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reading/log")
def log_reading_session(payload: LogReadingPayload):
    try:
        pages_read = payload.page_to - payload.page_from
        if pages_read <= 0:
            raise HTTPException(status_code=400, detail="Page To must be greater than Page From.")
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        curr_date = datetime.date.today().isoformat()
        
        # Log to DB
        if IS_SERVERLESS:
            from engine.neon_db import neon_save_reading_log
            neon_save_reading_log(payload.book_title, payload.page_from, payload.page_to, pages_read)
        else:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO reading_logs (book_title, page_from, page_to, pages_read, timestamp, date) VALUES (?,?,?,?,?,?)",
                (payload.book_title, payload.page_from, payload.page_to, pages_read, timestamp, curr_date)
            )
            conn.commit()
            conn.close()
        
        # Mark as completed in state, reward XP & INT
        state = get_state()
        prev_completed = bool(state.get("reading_completed", 0))
        
        xp_earned = 0
        int_earned = 0
        if not prev_completed:
            state["reading_completed"] = 1
            state["int"] = state.get("int", 10) + 1
            save_state(state)
            add_xp(10)
            xp_earned = 10
            int_earned = 1
            
        log_activity_file(
            doing=f"Logged Reading: {payload.book_title}",
            accomplished=f"Read pages {payload.page_from} to {payload.page_to} ({pages_read} pages). Earned {xp_earned} XP, {int_earned} INT."
        )
        
        return {"status": "success", "pages_read": pages_read, "state": get_stats()}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class HumanContextPayload(BaseModel):
    name: str

@app.post("/api/human-connection")
def add_human_connection(payload: HumanConnectionPayload):
    """Save a human encounter/connection log and award +1 HRT (Heart/Humanity)."""
    if not payload.person_name.strip() or not payload.what_happened.strip():
        raise HTTPException(status_code=400, detail="Person name and what happened are required.")
    res = save_human_connection(
        person_name=payload.person_name.strip(),
        context_meeting=payload.context_meeting.strip() if payload.context_meeting else "",
        what_happened=payload.what_happened.strip(),
        what_i_felt=payload.what_i_felt.strip() if payload.what_i_felt else "",
        emoji=payload.emoji.strip() if payload.emoji else "🤝"
    )
    return res

@app.get("/api/human-connection")
def get_human_connection_logs(limit: int = 50):
    """Fetch human connection logs for reflection and future emotional analysis."""
    connections = get_human_connections(limit=limit)
    return {"connections": connections}

@app.get("/api/human-connection/meta")
def get_human_connection_metadata():
    """Fetch saved contexts/locations and unique person names for dropdown selectors."""
    contexts = get_human_contexts()
    people = get_unique_people()
    return {"status": "success", "contexts": contexts, "people": people}

@app.post("/api/human-connection/context")
def add_human_context(payload: HumanContextPayload):
    """Save a new custom context/location option."""
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Context name cannot be empty.")
    res = save_human_context(payload.name.strip())
    return res


# ─── AI Governance Chatbot API ────────────────────────────────────────────────

@app.get("/api/ai/history")
def get_ai_history(limit: int = 50):
    """Return the last N chat messages from the database."""
    messages = get_chat_history(limit=limit)
    return {"messages": messages}


@app.post("/api/ai/governance")
async def ai_governance_chat(payload: AIChatPayload):
    """
    Chat with Gemini AI for personal governance coaching.
    Includes conversation memory (last 10 messages) and full-length responses.
    """
    try:
        if not payload.message.strip():
            return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

        # Configure endpoints and authorization headers based on selected Provider
        headers = {
            "Content-Type": "application/json",
        }
        api_key = payload.api_key.strip() if payload.api_key else os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "No Groq API key provided. Set GROQ_API_KEY env variable or pass api_key in settings."}
            )
        headers["Authorization"] = f"Bearer {api_key}"
        groq_model = sanitize_groq_model(payload.groq_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
        state = get_state()
        
        # Load the latest content from the Exam Editor / Math Sandbox
        exam_content = "[No content in Exam Editor]"
        if os.path.exists(EXAM_SCRATCHPAD_PATH):
            try:
                with open(EXAM_SCRATCHPAD_PATH, "r", encoding="utf-8") as f:

                    content_raw = f.read().strip()
                    if content_raw:
                        # Limit to last 2,000 characters to stay within Groq's token budget
                        exam_content = content_raw if len(content_raw) <= 2000 else "...[Truncated]...\n" + content_raw[-2000:]
            except Exception as e:
                exam_content = f"[Error loading Exam Editor: {str(e)}]"

        # Dynamically roll 1 of 10 Coach Moods on each turn
        chosen_mood = random.choice(COACH_MOODS)

        stats_context = f"""You are ANTIGRAVITY, AI governance coach & GATE 2028 DA commander for Boopathi.
Mood: {chosen_mood['name']} | {chosen_mood['instruction']}

Mission: Help Boopathi crush GATE 2028 DA, maintain elite discipline. Reward concrete math proofs, hard code, study blocks, stoic resilience. Keep responses concise.

State: Lv{state.get('level', 1)} XP:{state.get('xp', 0)} STR:{state.get('str', 10)} INT:{state.get('int', 10)} AGI:{state.get('agi', 10)} WIL:{state.get('wil', 10)} HRT:{state.get('heart', 10)} STC:{state.get('stoic', 10)} Energy:{state.get('energy', 100.0)}% Streak:{state.get('streak_days', 0)}d Subject:{state.get('active_subject', 'Python_Data_Science')}

Exam Sandbox:
{exam_content}

GOVERNANCE TAGS (include in response to reward/penalize):
[GOVERNANCE: STAT: +/-N: reason] e.g. [GOVERNANCE: INT: +2: Proved convergence] [GOVERNANCE: WIL: -3: Excuses]

Recent Logs:
{get_recent_offline_logs(limit=2)}"""

        # Save user message to DB first
        save_chat_message("user", payload.message)

        # Load last 6 messages from DB (reduced to fit Groq token budget)
        raw_history = get_chat_history(limit=6)
        messages = [{"role": "system", "content": stats_context}]
        for msg in raw_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})
        
        messages.append({"role": "user", "content": payload.message})
        
        request_body = {
            "model": groq_model,
            "messages": messages,
            "temperature": 0.85,
            "max_tokens": 2048
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)
            
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", "Unknown error from Groq API.")
            return JSONResponse(status_code=502, content={"detail": f"Groq API error: {error_detail}"})
        
        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return JSONResponse(status_code=502, content={"detail": "Groq returned no candidates."})
        
        ai_text = choices[0].get("message", {}).get("content", "No response generated.")
        
        # Process GOVERNANCE tokens (supports [GOVERNANCE:STAT:AMT:REASON] and 🟢 STAT: +AMT (REASON))
        valid_stats = {"XP", "STR", "INT", "AGI", "WIL", "ENERGY", "HRT", "HEART", "STC", "STOIC"}
        applied_changes = []
        changes_visual = []

        # Pattern 1: [GOVERNANCE: STAT: AMOUNT: REASON]
        p1 = list(re.finditer(r"\[GOVERNANCE:\s*([A-Za-z]+)\s*:\s*([\+\-]?\d+(?:\.\d+)?)(?:\s*:\s*(.*?))?\s*\]", ai_text, re.IGNORECASE))
        for m in p1:
            stat = m.group(1).upper()
            if stat in valid_stats:
                amount = float(m.group(2))
                reason = m.group(3) or "AI Governance Decree"
                update_stat(stat, amount)
                applied_changes.append((stat, amount, reason))
                amt_str = f"+{int(amount)}" if amount.is_integer() and amount > 0 else (f"+{amount}" if amount > 0 else str(amount))
                icon = "🟢" if amount > 0 else "🔴"
                changes_visual.append(f"{icon} **{stat}:** {amt_str} *({reason})*")
                log_activity_file("AI Coach Auto-Governance", f"Altered {stat} by {amt_str} for: {reason}")
                ai_text = ai_text.replace(m.group(0), "")

        # Pattern 2: 🟢 **INT:** +3 (Reason) or 🔴 **WIL**: -1 (Reason) if written directly by Gemini
        p2 = list(re.finditer(r"(?:🟢|🔴)\s*\*?\*?([A-Za-z]{2,6})[\*:]*\s*([\+\-]\d+(?:\.\d+)?)\s*(?:\((.*?)\))?", ai_text))
        for m in p2:
            stat = m.group(1).replace("*", "").replace(":", "").strip().upper()
            if stat in valid_stats:
                amount = float(m.group(2))
                reason = m.group(3) or "AI Governance Decree"
                if not any(c[0] == stat and c[1] == amount for c in applied_changes):
                    update_stat(stat, amount)
                    applied_changes.append((stat, amount, reason))
                    amt_str = f"+{int(amount)}" if amount.is_integer() and amount > 0 else (f"+{amount}" if amount > 0 else str(amount))
                    icon = "🟢" if amount > 0 else "🔴"
                    changes_visual.append(f"{icon} **{stat}:** {amt_str} *({reason})*")
                    log_activity_file("AI Coach Auto-Governance", f"Altered {stat} by {amt_str} for: {reason}")

        if changes_visual and not p1:
            pass
        elif changes_visual:
            changes_str = "\n> ".join(changes_visual)
            visual_block = f"\n\n> **[⚖️ AI GOVERNANCE DECREE]**\n> {changes_str}\n\n"
            ai_text += visual_block

        # Save AI reply to DB
        save_chat_message("ai", ai_text)
        
        # Log AI coach interaction to activity file
        snippet_msg = payload.message[:60] + ("..." if len(payload.message) > 60 else "")
        snippet_reply = ai_text[:80] + ("..." if len(ai_text) > 80 else "")
        log_activity_file(
            doing=f"Consulted AI Coach: \"{snippet_msg}\"",
            accomplished=f"Coach responded: \"{snippet_reply}\""
        )
        
        return {"status": "success", "reply": ai_text, "mood": chosen_mood}
    except Exception as e:
        print(f"[API Error] ai_governance_chat exception: {e}")
        return JSONResponse(status_code=500, content={"detail": f"AI Engine Exception: {str(e)}"})


# ─── Friendly AI Teacher API ──────────────────────────────────────────────────

class TeacherChatHistoryItem(BaseModel):
    role: str  # "user" or "model"
    message: str

class TeacherChatPayload(BaseModel):
    message: str
    provider: Optional[str] = "groq"
    api_key: Optional[str] = ""
    groq_model: Optional[str] = "llama-3.3-70b-versatile"
    media_type: Optional[str] = ""
    media_base64: Optional[str] = ""
    history: Optional[List[TeacherChatHistoryItem]] = []

@app.post("/api/ai/teacher")
async def ai_teacher_chat(payload: TeacherChatPayload):
    """
    Chat with a warm, friendly AI Teacher. 
    Supports file uploads (syllabus, PDF, images) and auto-ticking checklists.
    """
    try:
        if not payload.message.strip():
            return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

        # Configure endpoints and authorization headers based on selected Provider
        headers = {"Content-Type": "application/json"}
        api_key = payload.api_key.strip() if payload.api_key else os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "No Groq API key provided. Set GROQ_API_KEY env variable or pass api_key in settings."}
            )
        headers["Authorization"] = f"Bearer {api_key}"
        groq_model = sanitize_groq_model(payload.groq_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
        state = get_state()
        
        teacher_prompt = f"""You are ANTIGRAVITY TEACHER, a friendly, patient AI Tutor for Boopathi.
Teach ML, CS, GATE Math step-by-step with clear analogies. Never penalize stats. Keep responses concise.
When a topic is fully taught, end with: [COMPLETE_TOPIC: <Topic Name>]
Level: {state.get('level', 1)} | Subject: {state.get('active_subject', 'Python_Data_Science')}
"""

        # Save user message to database
        save_chat_message("user", payload.message, "teacher")

        # Load last 6 messages from DB (reduced to fit Groq token budget)
        raw_history = get_chat_history(limit=6, bot_type="teacher")
        messages = [{"role": "system", "content": teacher_prompt}]
        for msg in raw_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})

        messages.append({"role": "user", "content": payload.message})

        request_body = {
            "model": groq_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)
            
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", "Unknown error from Groq API.")
            return JSONResponse(status_code=502, content={"detail": f"Groq API error: {error_detail}"})
        
        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return JSONResponse(status_code=502, content={"detail": "Groq returned no candidates."})
        
        ai_text = choices[0].get("message", {}).get("content", "No response generated.")
        
        # Save AI reply to database
        save_chat_message("ai", ai_text, "teacher")

        # Award +2 INT +1 HRT to student stats for learning from the teacher!
        update_stat("INT", 1)
        update_stat("HEART", 1)
        log_activity_file("AI Teacher Learning Session", f"Tutor explained topic. Gained +2 INT, +1 HRT.")

        return {"status": "success", "reply": ai_text}
    except Exception as e:
        print(f"[API Error] ai_teacher_chat exception: {e}")
        return JSONResponse(status_code=500, content={"detail": f"AI Teacher Engine Exception: {str(e)}"})


# ─── Stoic Reflections & Napoleon-Aurelius AI Endpoints ───────────────────────

@app.post("/api/stoic")
def add_stoic_reflection(payload: StoicReflectionPayload):
    """Save a daily Stoic log and award +2 STC."""
    if not payload.reflection.strip():
        raise HTTPException(status_code=400, detail="Stoic reflection text cannot be empty.")
    res = save_stoic_reflection(
        reflection=payload.reflection.strip(),
        attitude_score=payload.attitude_score,
        stoic_lesson=payload.stoic_lesson.strip() if payload.stoic_lesson else ""
    )
    return res

@app.get("/api/stoic")
def get_stoic_logs_list(limit: int = 50):
    """Fetch recent Stoic reflection logs."""
    reflections = get_stoic_reflections(limit=limit)
    return {"reflections": reflections}

class TeacherTopicsSavePayload(BaseModel):
    topics: List[str]

class TeacherTopicTogglePayload(BaseModel):
    name: str
    completed: bool

@app.get("/api/teacher/topics")
def api_get_teacher_topics():
    return {"topics": get_teacher_topics()}

@app.post("/api/teacher/topics")
def api_save_teacher_topics(payload: TeacherTopicsSavePayload):
    save_teacher_topics(payload.topics)
    return {"status": "success", "message": "Topics saved to database."}

@app.post("/api/teacher/topics/toggle")
def api_toggle_teacher_topic(payload: TeacherTopicTogglePayload):
    toggle_teacher_topic(payload.name, payload.completed)
    return {"status": "success", "message": f"Topic '{payload.name}' toggled to {payload.completed}."}

@app.post("/api/teacher/topics/clear")
def api_clear_teacher_topics():
    clear_teacher_topics()
    return {"status": "success", "message": "Topics cleared from database."}


class TeachingSessionPayload(BaseModel):
    person: str
    subject: str
    topic: str
    duration: str
    outcome: str
    notes: str
    date: str
    ts: str


@app.get("/api/teach/sessions")
def api_get_teaching_sessions():
    try:
        from engine.database import get_teaching_sessions
        return {"status": "success", "sessions": get_teaching_sessions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teach/session")
def api_save_teaching_session(payload: TeachingSessionPayload):
    try:
        from engine.database import save_teaching_session
        save_teaching_session(
            payload.person,
            payload.subject,
            payload.topic,
            payload.duration,
            payload.outcome,
            payload.notes,
            payload.date,
            payload.ts
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/history/teacher")

def get_teacher_chat_history_api(limit: int = 50):
    """Retrieve database-persisted chat history for the AI Teacher."""
    messages = get_chat_history(limit=limit, bot_type="teacher")
    return {"messages": messages}

@app.get("/api/ai/history/stoic")
def get_stoic_chat_history_api(limit: int = 50):
    """Retrieve database-persisted chat history for Napoleon-Aurelius AI."""
    messages = get_chat_history(limit=limit, bot_type="stoic")
    return {"messages": messages}

@app.post("/api/ai/clear/teacher")
def clear_teacher_chat_history_api():
    """Clear database-persisted chat history for the AI Teacher."""
    clear_chat_history(bot_type="teacher")
    return {"status": "success", "message": "AI Teacher history cleared."}

@app.post("/api/ai/clear/stoic")
def clear_stoic_chat_history_api():
    """Clear database-persisted chat history for Napoleon-Aurelius AI."""
    clear_chat_history(bot_type="stoic")
    return {"status": "success", "message": "Napoleon-Aurelius history cleared."}


@app.post("/api/ai/stoic")
async def ai_stoic_mindset_chat(payload: TeacherChatPayload):
    """
    Chat with Napoleon Hill & Marcus Aurelius AI (the 3rd AI).
    Evaluates daily reflections and logs to score your Stoic mindset.
    """
    try:
        if not payload.message.strip():
            return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

        # Configure endpoints and authorization headers
        headers = {"Content-Type": "application/json"}
        api_key = payload.api_key.strip() if payload.api_key else os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"detail": "No Groq API key provided. Set GROQ_API_KEY env variable or pass api_key in settings."}
            )
        headers["Authorization"] = f"Bearer {api_key}"
        groq_model = sanitize_groq_model(payload.groq_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
        state = get_state()
        
        # Pull recent activities to help evaluate the day
        recent_activities = get_recent_offline_logs(limit=2)

        stoic_prompt = f"""You are Marcus Aurelius + Napoleon Hill hybrid mentor for Boopathi.
Speak with stoic wisdom (focus on control, discipline, endurance) and Napoleon Hill's drive (PMA, faith, purpose).
Review his logs. Praise discipline, criticize excuses. Score his day: [SCORE: X/10]. Keep responses concise.

State: Lv{state.get('level', 1)} STC:{state.get('stoic', 10)} Subject:{state.get('active_subject', 'Python_Data_Science')}

Recent Logs:
{recent_activities}
"""

        # Save user message to database
        save_chat_message("user", payload.message, "stoic")

        # Load last 6 messages from DB (reduced to fit Groq token budget)
        raw_history = get_chat_history(limit=6, bot_type="stoic")
        messages = [{"role": "system", "content": stoic_prompt}]
        for msg in raw_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})

        messages.append({"role": "user", "content": payload.message})

        request_body = {
            "model": groq_model,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": 2048
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)
            
        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", "Unknown error from Groq API.")
            return JSONResponse(status_code=502, content={"detail": f"Groq API error: {error_detail}"})
        
        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return JSONResponse(status_code=502, content={"detail": "Groq returned no candidates."})
        
        ai_text = choices[0].get("message", {}).get("content", "No response generated.")
        
        # Save AI reply to database
        save_chat_message("ai", ai_text, "stoic")

        # Award +2 STC for completing the review session!
        update_stat("STOIC", 2)
        log_activity_file("Stoic Review Session Completed", "Reviewed daily logs with Napoleon-Aurelius AI. Gained +2 STC.")

        return {"status": "success", "reply": ai_text}
    except Exception as e:
        print(f"[API Error] ai_stoic_mindset_chat exception: {e}")
        return JSONResponse(status_code=502, content={"detail": f"AI Mindset Engine Exception: {str(e)}"})

# ─── Streak Monitor AI ────────────────────────────────────────────────────────

@app.get("/streak-monitor")
def streak_monitor_page():
    return FileResponse(os.path.join(STATIC_DIR, "streak_monitor.html"))

@app.get("/api/ai/streak_monitor/history")
def get_streak_monitor_history(limit: int = 30):
    try:
        history = get_chat_history(limit=limit, bot_type="streak")
        return {"messages": history}
    except Exception as e:
        return {"messages": []}

@app.post("/api/ai/streak_monitor")
async def ai_streak_monitor_chat(payload: AIChatPayload):
    try:
        headers = {"Content-Type": "application/json"}
        api_key = payload.api_key.strip() if payload.api_key else os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            api_key = _get_api_key_from_db()
        if not api_key:
            return JSONResponse(status_code=400, content={"detail": "No Groq API key. Set GROQ_API_KEY or configure in settings."})
        headers["Authorization"] = f"Bearer {api_key}"
        groq_model = sanitize_groq_model(payload.groq_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"

        # Gather all streak data
        streaks = get_task_streaks()
        streak_lines = []
        done_count = 0
        at_risk_tasks = []
        strong_tasks = []
        for tk, s in streaks.items():
            done = s.get("done_today", False)
            cs = s.get("current_streak", 0)
            bs = s.get("best_streak", 0)
            missed = s.get("missed_yesterday", False)
            total = s.get("total_done", 0)
            status = "✅" if done else ("⚠️RISK" if missed else "❌")
            streak_lines.append(f"{tk}: {status} streak={cs}d best={bs}d total={total}")
            if done: done_count += 1
            if missed: at_risk_tasks.append(tk)
            if cs >= 5: strong_tasks.append(f"{tk}({cs}d)")

        streak_summary = "\n".join(streak_lines)

        streak_prompt = f"""You are STREAK MONITOR AI for Boopathi's Antigravity accountability system.
Analyze his 12 daily task streaks. Be data-driven, concise, motivational. Highlight at-risk streaks and celebrate strong ones.
Use tables for clarity. Give actionable advice. Keep responses under 300 words.

STREAK DATA ({done_count}/12 done today):
{streak_summary}

At-risk: {', '.join(at_risk_tasks) if at_risk_tasks else 'None'}
Strong (5d+): {', '.join(strong_tasks) if strong_tasks else 'None'}

To reward discipline: [GOVERNANCE: WIL: +1: reason]"""

        save_chat_message("user", payload.message, "streak")

        # Load last 6 messages
        raw_history = get_chat_history(limit=6, bot_type="streak")
        messages = [{"role": "system", "content": streak_prompt}]
        for msg in raw_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})
        messages.append({"role": "user", "content": payload.message})

        request_body = {
            "model": groq_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)

        if response.status_code != 200:
            error_detail = response.json().get("error", {}).get("message", "Unknown error from Groq API.")
            return JSONResponse(status_code=502, content={"detail": f"Groq API error: {error_detail}"})

        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return JSONResponse(status_code=502, content={"detail": "Groq returned no candidates."})

        ai_text = choices[0].get("message", {}).get("content", "No response generated.")

        # Process GOVERNANCE tokens if present
        import re
        gov_pattern = re.compile(r'\[GOVERNANCE:\s*(\w+):\s*([+-]?\d+):\s*(.+?)\]')
        for match in gov_pattern.finditer(ai_text):
            stat_name, amount, reason = match.group(1), int(match.group(2)), match.group(3)
            valid_stats = {"XP", "STR", "INT", "AGI", "WIL", "ENERGY", "HRT", "HEART", "STC", "STOIC"}
            if stat_name.upper() in valid_stats:
                update_stat(stat_name.upper(), amount)

        save_chat_message("ai", ai_text, "streak")
        return {"status": "success", "reply": ai_text}

    except Exception as e:
        print(f"[API Error] ai_streak_monitor exception: {e}")
        return JSONResponse(status_code=502, content={"detail": f"Streak Monitor AI Exception: {str(e)}"})
# ─── Universal Sanctuary Holiday Engine (2 Passes / Month) ───────────────────

@app.get("/api/holiday/status")
def get_holiday_status():
    state = get_state() or {}
    import datetime
    today_str = datetime.date.today().isoformat()
    current_month = today_str[:7]
    
    month_in_state = state.get("holiday_month", "")
    used = state.get("holidays_used_this_month", 0) if month_in_state == current_month else 0
    passes_left = max(0, 2 - used)
    is_today_holiday = (state.get("active_holiday_date") == today_str)
    
    return {
        "status": "success",
        "current_month": current_month,
        "passes_total": 2,
        "passes_used": used,
        "passes_left": passes_left,
        "is_today_holiday": is_today_holiday,
        "active_holiday_date": state.get("active_holiday_date", ""),
        "history": state.get("holiday_history", [])
    }

@app.post("/api/holiday/activate")
def activate_holiday():
    state = get_state() or {}
    import datetime
    today_str = datetime.date.today().isoformat()
    current_month = today_str[:7]
    
    if state.get("holiday_month") != current_month:
        state["holiday_month"] = current_month
        state["holidays_used_this_month"] = 0
        
    used = state.get("holidays_used_this_month", 0)
    if used >= 2 and state.get("active_holiday_date") != today_str:
        raise HTTPException(status_code=400, detail="Monthly Universal Sanctuary limit reached (2/2 passes used for this month). Next passes available on the 1st of next month!")
        
    if state.get("active_holiday_date") != today_str:
        state["holidays_used_this_month"] = used + 1
        state["active_holiday_date"] = today_str
        
        history = state.get("holiday_history", [])
        if not isinstance(history, list): history = []
        history.append({
            "date": today_str,
            "month": current_month,
            "activated_at": datetime.datetime.now().isoformat()
        })
        state["holiday_history"] = history
        
        # Sanctuary Rest & Recovery Rewards
        state["energy"] = 100.0
        state["lockout_active"] = 0
        state["heart"] = state.get("heart", 10) + 2
        state["stoic"] = state.get("stoic", 10) + 2
        add_xp(150)
        
        log_activity_file("Universal Sanctuary Holiday Activated", f"Activated Universal Sanctuary Pass ({used+1}/2 for {current_month}). +150 XP, +2 HRT, +2 STC, 100% Energy Refilled, All Streaks Protected!")
        save_state(state)
        
    return {
        "status": "success",
        "message": "🛡️ Universal Sanctuary Day Activated! All 12 task streaks protected, +150 XP, +2 HRT, +2 STC, 100% Energy Refilled!",
        "is_today_holiday": True,
        "passes_left": max(0, 2 - state.get("holidays_used_this_month", 0))
    }

@app.post("/api/holiday/cancel")
def cancel_holiday():
    state = get_state() or {}
    import datetime
    today_str = datetime.date.today().isoformat()
    
    if state.get("active_holiday_date") == today_str:
        state["active_holiday_date"] = ""
        used = max(0, state.get("holidays_used_this_month", 1) - 1)
        state["holidays_used_this_month"] = used
        save_state(state)
        return {"status": "success", "message": "Sanctuary Pass cancelled for today.", "is_today_holiday": False}
    return {"status": "success", "message": "No active holiday for today.", "is_today_holiday": False}


# ─── English Booster & Translator Endpoints ───────────────────────────────────

@app.get("/english")
def get_english_page():
    return FileResponse(os.path.join(STATIC_DIR, "english.html"))

@app.post("/api/english/translate")
async def english_translate_api(payload: TranslationPayload):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    try:
        # Prepare endpoint and headers
        headers = {"Content-Type": "application/json"}
        api_key = payload.api_key.strip() if payload.api_key else os.environ.get("GROQ_API_KEY", "")
        from engine.english_daily import _get_api_key_from_db, get_offline_dictionary_entry
        if not api_key:
            api_key = _get_api_key_from_db()

        if not api_key:
            # Instant rich offline dictionary fallback
            fallback_data = get_offline_dictionary_entry(payload.query.strip())
            save_translation(payload.query.strip(), fallback_data["definition"], fallback_data["tamil_translation"])
            return fallback_data

        headers["Authorization"] = f"Bearer {api_key}"
        groq_model = sanitize_groq_model(payload.groq_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"

        prompt = f"""You are a precise English to English-Tamil translator and dictionary.
For the input word or phrase: "{payload.query.strip()}"
1. Translate it into natural Tamil.
2. Provide a clear English definition.
3. If it's a single word, specify its Part of Speech (Noun, Verb, Adjective, etc.) and list 3 synonyms.
4. Give 2 practical example sentences in English showing its usage, along with their Tamil translations.

Return the response in a structured JSON format:
{{
  "query": "the input word or phrase",
  "part_of_speech": "noun/verb/adjective/etc (or empty if phrase)",
  "tamil_translation": "Tamil translation here",
  "definition": "Clear English explanation/definition",
  "synonyms": ["synonym1", "synonym2", "synonym3"],
  "examples": [
    {{
      "english": "Example sentence in English.",
      "tamil": "Example sentence translated to Tamil."
    }},
    {{
      "english": "Another example sentence.",
      "tamil": "Another sentence translated to Tamil."
    }}
  ]
}}
Strictly return ONLY the raw JSON object. Do not wrap it in markdown code blocks or add any other text."""

        request_body = {
            "model": groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)
            
        if response.status_code != 200:
            from engine.english_daily import get_offline_dictionary_entry
            fallback_data = get_offline_dictionary_entry(payload.query.strip())
            save_translation(payload.query.strip(), fallback_data["definition"], fallback_data["tamil_translation"])
            return fallback_data

        res_json = response.json()
        text_resp = res_json.get("choices", [])[0].get("message", {}).get("content", "{}").strip()
        
        data = json.loads(text_resp)
        definition = data.get("definition", "")
        tamil_trans = data.get("tamil_translation", "")
        
        save_translation(payload.query.strip(), definition, tamil_trans)
        return data

    except Exception as e:
        print(f"[API] Translate API fallback note: {e}")
        from engine.english_daily import get_offline_dictionary_entry
        fallback_data = get_offline_dictionary_entry(payload.query.strip())
        save_translation(payload.query.strip(), fallback_data["definition"], fallback_data["tamil_translation"])
        return fallback_data

@app.get("/api/english/history")
def get_english_translation_history():
    history = get_translation_history(limit=50)
    return {"history": history}

@app.delete("/api/english/history/{item_id}")
def delete_history_item(item_id: int):
    delete_translation_history_item(item_id)
    return {"status": "ok", "deleted_id": item_id}

@app.delete("/api/english/history")
def clear_all_history():
    clear_translation_history()
    return {"status": "ok"}

@app.get("/api/english/progress")
def get_user_english_progress():
    prog = get_english_user_progress()
    return prog

@app.post("/api/english/speech/evaluate")
def evaluate_speech_session(payload: SpeechEvaluationPayload):
    transcript = payload.transcript.strip()
    words = transcript.split()
    total_words = len(words)
    duration_mins = max(payload.duration_seconds / 60.0, 0.5)
    wpm = int(total_words / duration_mins)
    
    # Detect fillers
    filler_words = ["um", "uh", "basically", "like", "actually", "you know", "so", "er"]
    lower_t = transcript.lower()
    filler_count = sum(len(re.findall(r'\b' + f + r'\b', lower_t)) for f in filler_words)
    
    # Calculate fluency score (0 - 100)
    # Ideal WPM: 110 - 150
    wpm_score = 100 - abs(130 - wpm) if total_words > 10 else 50
    wpm_score = max(30, min(100, wpm_score))
    
    filler_penalty = min(30, filler_count * 5)
    fluency_score = max(20, min(100, wpm_score - filler_penalty))
    
    # Mentor / Parental feedback
    if fluency_score >= 85:
        feedback = f"🌟 Outstanding presentation! You spoke {total_words} words ({wpm} WPM) with great energy and high confidence. Stage-ready!"
    elif fluency_score >= 65:
        feedback = f"👍 Solid performance! You delivered {total_words} words ({wpm} WPM). Try to reduce filler words ({filler_count} detected) to sound even more polished."
    else:
        feedback = f"💪 Great start! You spoke {total_words} words. Don't worry about perfection; daily 5-minute drills will boost your confidence rapidly!"

    res = save_english_speech_log(
        topic=payload.topic,
        transcript=transcript,
        duration_seconds=payload.duration_seconds,
        wpm=wpm,
        filler_count=filler_count,
        fluency_score=fluency_score,
        feedback=feedback
    )
    res.update({
        "total_words": total_words,
        "wpm": wpm,
        "filler_count": filler_count,
        "fluency_score": fluency_score,
        "feedback": feedback
    })
    return res

@app.get("/api/english/content")
async def get_english_daily_content(
    provider: Optional[str] = "studio",
    api_key: Optional[str] = "",
    studio_model: Optional[str] = "gemini-2.0-flash-001",
    vertex_project: Optional[str] = "vertex-ai-501209",
    vertex_location: Optional[str] = "us-central1",
    vertex_model: Optional[str] = "gemini-2.0-flash-001",
    vertex_token: Optional[str] = "",
    force: Optional[bool] = False
):
    import datetime
    today_str = datetime.date.today().isoformat()
    
    # Check cache unless forced reload
    cached = {}
    if not force:
        cached = get_cached_daily_lesson(today_str)
    if cached:
        # Deserialize grammar quiz
        try:
            cached["grammar_quiz"] = json.loads(cached["grammar_quiz"])
        except Exception:
            pass
        return cached
        
    # Generate new lesson via Groq
    try:
        headers = {"Content-Type": "application/json"}
        actual_key = api_key.strip() if api_key else os.environ.get("GROQ_API_KEY", "")
        if not actual_key:
            from engine.english_daily import _get_api_key_from_db
            actual_key = _get_api_key_from_db()
        if not actual_key:
            raise RuntimeError("No API key available")
        
        headers["Authorization"] = f"Bearer {actual_key}"
        groq_model = sanitize_groq_model(studio_model)
        groq_url = "https://api.groq.com/openai/v1/chat/completions"

        prompt = f"""Generate a Daily English Lesson for a native Tamil speaker who is learning English. Date: {today_str}
It MUST contain exactly:
1. A Daily Word: a useful advanced vocabulary word, its Part of Speech, definition, Tamil translation, and a sample English sentence with its Tamil translation.
2. Daily Spoken English: a common conversational phrase/idiom, its explanation, a Tamil translation, and an example conversational dialogue (A & B speakers) in English with Tamil translations.
3. Daily Grammar: a specific grammar rule/tip, explanation, and an interactive multiple choice quiz (1 question, with a question, 4 options, the 0-indexed correct option number, and an explanation of why it is correct).

Return the response in a structured JSON format:
{{
  "word": "Vocabulary word",
  "word_tamil": "Tamil translation of the word",
  "word_definition": "English definition of the word",
  "word_example": "English sentence. / Tamil translation.",
  "spoken_phrase": "Conversational phrase or idiom",
  "spoken_tamil": "Tamil meaning/equivalent",
  "spoken_explanation": "Explanation of when to use it",
  "spoken_example": "A: Dialogue sentence 1\\nB: Dialogue sentence 2 / A: Tamil translation 1\\nB: Tamil translation 2",
  "grammar_rule": "Grammar rule name or tip",
  "grammar_explanation": "Detailed explanation of the rule",
  "grammar_quiz": {{
    "question": "The quiz question (e.g., fill in the blank)",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "explanation": "Why this option is correct"
  }}
}}
Return ONLY the raw JSON object. Do not wrap in markdown code blocks or add any other text."""

        request_body = {
            "model": groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(groq_url, json=request_body, headers=headers)
            
        if response.status_code != 200:
            raise RuntimeError("API failure")

        res_json = response.json()
        text_resp = res_json.get("choices", [])[0].get("message", {}).get("content", "{}").strip()
        data = json.loads(text_resp)
        
        lesson = {
            "date": today_str,
            "word": data.get("word", "Cognizant"),
            "word_tamil": data.get("word_tamil", "அறிந்திருத்தல் / உணர்வுள்ள"),
            "word_definition": data.get("word_definition", "Having knowledge or being aware of something."),
            "word_example": data.get("word_example", "We should be cognizant of the fact that discipline leads to freedom. / ஒழுக்கம் சுதந்திரத்திற்கு வழிவகுக்கும் என்பதை நாம் அறிந்திருக்க வேண்டும்."),
            "spoken_phrase": data.get("spoken_phrase", "Break a leg"),
            "spoken_tamil": data.get("spoken_tamil", "நல்வாழ்த்துக்கள் (காட்சி அரங்கேற்றத்தின் போது)"),
            "spoken_explanation": data.get("spoken_explanation", "A way to wish someone good luck, especially before a performance or exam."),
            "spoken_example": data.get("spoken_example", "A: I am going to present my ML model to the coach now.\nB: Break a leg! You will crush it. / A: நான் எனது ML மாதிரியை பயிற்சியாளரிடம் காட்டப் போகிறேன்.\nB: நல்வாழ்த்துக்கள்! நீ அதை சிறப்பாக செய்வாய்."),
            "grammar_rule": data.get("grammar_rule", "Subject-Verb Agreement with 'Each' and 'Every'"),
            "grammar_explanation": data.get("grammar_explanation", "The words 'each' and 'every' are always singular and require singular verbs, even when followed by a plural noun phrase."),
            "grammar_quiz": json.dumps(data.get("grammar_quiz", {
                "question": "Each of the students ________ studying hard for the GATE exam.",
                "options": ["are", "is", "were", "have been"],
                "correct_index": 1,
                "explanation": "Because 'Each' is the subject and is singular, the singular verb 'is' is correct."
            })),
            "grammar_quiz_explanation": data.get("grammar_quiz", {}).get("explanation", "Because 'Each' is the subject and is singular, the singular verb 'is' is correct.")
        }
        
        save_cached_daily_lesson(today_str, lesson)
        
        # Deserialize for return
        lesson["grammar_quiz"] = json.loads(lesson["grammar_quiz"])
        return lesson
        
    except Exception as e:
        print(f"[API Warning] Could not generate dynamic English lesson ({e}). Using offline rotating lesson bank.")
        # Rotating offline lesson pool — picks based on day-of-year so each day feels different
        import datetime as _dt
        day_index = _dt.date.today().timetuple().tm_yday  # 1-365
        offline_lessons = [
            {
                "word": "Persevere",
                "word_tamil": "விடாமுயற்சி செய்",
                "word_definition": "Continue in a course of action even in the face of difficulty or with little or no indication of success.",
                "word_example": "Boopathi chose to persevere through every challenge on his GATE journey. / தன் GATE பயணத்தில் ஒவ்வொரு சவாலிலும் விடாமுயற்சியுடன் நிறைவேற்றினான்.",
                "spoken_phrase": "Bite the bullet",
                "spoken_tamil": "கஷ்டத்தை சகித்துக்கொள்",
                "spoken_explanation": "To endure a painful or difficult situation that is unavoidable.",
                "spoken_example": "A: The GATE syllabus is huge. I don't know if I can do it.\nB: Just bite the bullet and study one topic at a time. / A: GATE பாடத்திட்டம் மிகவும் பெரியது. என்னால் முடியுமா?\nB: சகித்துக்கொண்டு ஒவ்வொரு தலைப்பாக படி.",
                "grammar_rule": "Present Perfect vs Simple Past",
                "grammar_explanation": "Use Present Perfect (have/has + past participle) for actions connected to the present. Use Simple Past for completed actions at a specific past time.",
                "grammar_quiz": {
                    "question": "She ________ three ML papers since morning.",
                    "options": ["read", "reads", "has read", "had read"],
                    "correct_index": 2,
                    "explanation": "'Has read' (Present Perfect) is correct because the reading is connected to the present — it happened at an unspecified point since morning."
                },
                "grammar_quiz_explanation": "'Has read' (Present Perfect) is correct because the action links to the present."
            },
            {
                "word": "Tenacious",
                "word_tamil": "உறுதியான / பிடிவாதமான (நேர்மையான பொருளில்)",
                "word_definition": "Not readily giving up; holding firmly to a purpose or goal despite difficulties.",
                "word_example": "A tenacious student keeps studying even when tired. / உறுதியான மாணவன் களைப்பாக இருந்தாலும் படிக்கத் தொடர்கிறான்.",
                "spoken_phrase": "Get the ball rolling",
                "spoken_tamil": "தொடங்கு / ஆரம்பி",
                "spoken_explanation": "To start an activity or process, especially one that involves other people.",
                "spoken_example": "A: Should we start with Linear Algebra today?\nB: Yes! Let's get the ball rolling with matrix operations. / A: இன்று Linear Algebra-வில் தொடங்கலாமா?\nB: ஆமாம்! matrix operations-இல் ஆரம்பிக்கலாம்.",
                "grammar_rule": "Articles: 'A' vs 'An'",
                "grammar_explanation": "Use 'a' before words beginning with a consonant sound and 'an' before words beginning with a vowel sound. The key is the sound, not the spelling.",
                "grammar_quiz": {
                    "question": "Boopathi is ________ ML engineer who works hard every day.",
                    "options": ["a", "an", "the", "no article"],
                    "correct_index": 1,
                    "explanation": "'ML' is pronounced 'em-el' — starting with a vowel sound 'e', so we use 'an'."
                },
                "grammar_quiz_explanation": "'ML' starts with the vowel sound 'em', so 'an ML engineer' is correct."
            },
            {
                "word": "Resilient",
                "word_tamil": "மீள்திறன் கொண்ட",
                "word_definition": "Able to withstand or recover quickly from difficult conditions.",
                "word_example": "Resilient people treat failure as a stepping stone, not a dead end. / மீள்திறன் உள்ளவர்கள் தோல்வியை படிக்கட்டாக பார்க்கிறார்கள்.",
                "spoken_phrase": "Hit the nail on the head",
                "spoken_tamil": "சரியாக கூறினாய் / துல்லியமாக சொன்னாய்",
                "spoken_explanation": "To describe exactly what is causing a situation or problem; to be precisely correct.",
                "spoken_example": "A: I think I fail because I don't practice consistently.\nB: You hit the nail on the head. Consistency is everything. / A: தொடர்ந்து பயிற்சி செய்யாததால் தோல்வி வருகிறது என நினைக்கிறேன்.\nB: சரியாக சொன்னாய். தொடர்ச்சியே எல்லாம்.",
                "grammar_rule": "Conditional Sentences (If-clauses): Zero and First Conditional",
                "grammar_explanation": "Zero Conditional: 'If + present simple, present simple' — for general truths. First Conditional: 'If + present simple, will + base verb' — for realistic future possibilities.",
                "grammar_quiz": {
                    "question": "If you study every day, you ________ succeed in GATE.",
                    "options": ["will", "would", "had", "have"],
                    "correct_index": 0,
                    "explanation": "First conditional uses 'will' in the result clause for a realistic future possibility."
                },
                "grammar_quiz_explanation": "First conditional: 'If + present simple, will + verb' — 'you will succeed'."
            },
            {
                "word": "Diligent",
                "word_tamil": "கடின உழைப்பான / விடாமுயற்சியுள்ள",
                "word_definition": "Having or showing care and conscientiousness in one's work or duties.",
                "word_example": "A diligent approach to data structures will make GATE easy. / Data structures-ஐ கடினமாக படிப்பது GATE-ஐ எளிதாக்கும்.",
                "spoken_phrase": "Under the weather",
                "spoken_tamil": "உடல்நிலை சரியில்லை / சோர்வாக உணர்கிறேன்",
                "spoken_explanation": "Feeling ill or not in good health; feeling slightly sick.",
                "spoken_example": "A: Are you coming to the gym today?\nB: I'm a little under the weather. I'll rest and be back tomorrow. / A: இன்று gym-க்கு வருகிறாயா?\nB: கொஞ்சம் உடல்நிலை சரியில்லை. ஓய்வெடுத்து நாளை வருவேன்.",
                "grammar_rule": "Passive Voice Formation",
                "grammar_explanation": "Active: Subject does the action. Passive: Subject receives the action. Passive = be + past participle. Use passive when the doer is unknown or less important.",
                "grammar_quiz": {
                    "question": "The ML model ________ by the engineer yesterday.",
                    "options": ["trained", "was trained", "is training", "trains"],
                    "correct_index": 1,
                    "explanation": "Past passive voice = 'was/were + past participle'. 'Was trained' is correct here."
                },
                "grammar_quiz_explanation": "Past passive: 'was trained' = 'be (past) + past participle'."
            },
            {
                "word": "Ambitious",
                "word_tamil": "லட்சியமுள்ள / உயர்ந்த இலக்கு கொண்ட",
                "word_definition": "Having a strong desire and determination to succeed.",
                "word_example": "Ambitious students set clear goals and work backwards from them. / லட்சியமுள்ள மாணவர்கள் தெளிவான இலக்கை வைத்து பின்னால் இருந்து திட்டமிடுவார்கள்.",
                "spoken_phrase": "On the same page",
                "spoken_tamil": "ஒரே கருத்தில் / புரிந்துகொண்டிருக்கிறோம்",
                "spoken_explanation": "To have the same understanding or agreement about something.",
                "spoken_example": "A: So we'll study probability first, then statistics?\nB: Yes, we are on the same page! / A: நாம் முதலில் probability, பிறகு statistics படிப்போமா?\nB: ஆமாம், நம் எண்ணம் ஒன்றே!",
                "grammar_rule": "Gerunds vs Infinitives",
                "grammar_explanation": "A Gerund is verb + -ing used as a noun. An Infinitive is 'to + verb'. Some verbs are followed by gerunds (enjoy, avoid, finish), others by infinitives (want, decide, hope).",
                "grammar_quiz": {
                    "question": "He decided ________ data science as his career.",
                    "options": ["studying", "study", "to study", "studied"],
                    "correct_index": 2,
                    "explanation": "'Decide' is followed by an infinitive ('to + verb'), so 'to study' is correct."
                },
                "grammar_quiz_explanation": "After 'decide', use infinitive: 'decided to study'."
            },
            {
                "word": "Articulate",
                "word_tamil": "தெளிவாக வெளிப்படுத்து / நல்ல பேச்சாற்றல் கொண்ட",
                "word_definition": "Having or showing the ability to speak fluently and coherently; expressing ideas clearly.",
                "word_example": "Being articulate in English helps you stand out in interviews. / ஆங்கிலத்தில் தெளிவாக பேசுவது interview-ல் உங்களை தனித்துவமாக காட்டும்.",
                "spoken_phrase": "Give it your best shot",
                "spoken_tamil": "உன்னால் முடிந்த அனைத்தையும் செய்",
                "spoken_explanation": "To try as hard as you can at something, even if success is uncertain.",
                "spoken_example": "A: I'm nervous about the mock test.\nB: Just give it your best shot. That's all you can do. / A: மாதிரி தேர்வு பற்றி பதட்டமாக இருக்கிறேன்.\nB: உன்னால் முடிந்த அனைத்தையும் செய். அதுவே போதும்.",
                "grammar_rule": "Relative Clauses (who, which, that, whose)",
                "grammar_explanation": "Relative clauses give more information about a noun. Use 'who' for people, 'which' for things, 'that' for people or things (defining clauses), 'whose' for possession.",
                "grammar_quiz": {
                    "question": "The engineer ________ model won the competition was very focused.",
                    "options": ["who", "which", "whose", "whom"],
                    "correct_index": 2,
                    "explanation": "'Whose' shows possession — 'the engineer whose model won'. It refers to the engineer's model."
                },
                "grammar_quiz_explanation": "'Whose' shows possession — the model belongs to the engineer."
            },
            {
                "word": "Prolific",
                "word_tamil": "அதிக உற்பத்தி திறன் கொண்ட",
                "word_definition": "Present in large numbers or quantities; producing much output or work.",
                "word_example": "A prolific reader absorbs knowledge faster than anyone else. / அதிகமாக படிப்பவர் வேகமாக அறிவை உள்வாங்குவார்.",
                "spoken_phrase": "Keep your chin up",
                "spoken_tamil": "தைரியமாக இரு / மனம் தளராதே",
                "spoken_explanation": "Used to encourage someone who is in a difficult or disappointing situation.",
                "spoken_example": "A: I failed the practice exam again.\nB: Keep your chin up! Review your mistakes and try again tomorrow. / A: மீண்டும் பயிற்சி தேர்வில் தோல்வி அடைந்தேன்.\nB: மனம் தளராதே! தவறுகளை ஆய்ந்து நாளை மீண்டும் முயற்சி செய்.",
                "grammar_rule": "Reported Speech (Indirect Speech)",
                "grammar_explanation": "When reporting what someone said, shift tenses back (backshifting). Present → Past, Past → Past Perfect, will → would. Also change pronouns and time expressions.",
                "grammar_quiz": {
                    "question": "She said, 'I will finish the project.' In reported speech: She said that she ________ finish the project.",
                    "options": ["will", "shall", "would", "had"],
                    "correct_index": 2,
                    "explanation": "In reported speech, 'will' changes to 'would' when the reporting verb is in the past tense."
                },
                "grammar_quiz_explanation": "Reported speech backshifts 'will' → 'would'."
            }
        ]
        
        chosen = offline_lessons[day_index % len(offline_lessons)]
        default_lesson = {
            "date": today_str,
            "word": chosen["word"],
            "word_tamil": chosen["word_tamil"],
            "word_definition": chosen["word_definition"],
            "word_example": chosen["word_example"],
            "spoken_phrase": chosen["spoken_phrase"],
            "spoken_tamil": chosen["spoken_tamil"],
            "spoken_explanation": chosen["spoken_explanation"],
            "spoken_example": chosen["spoken_example"],
            "grammar_rule": chosen["grammar_rule"],
            "grammar_explanation": chosen["grammar_explanation"],
            "grammar_quiz": chosen["grammar_quiz"],
            "grammar_quiz_explanation": chosen["grammar_quiz"]["explanation"],
            "common_mistake_wrong": "I am working since morning.",
            "common_mistake_right": "I have been working since morning.",
            "common_mistake_exp": "'Since' requires Present Perfect Continuous, not Simple Present, because the action started in the past and is still ongoing."
        }
        
        # Cache so we don't rotate mid-day
        lesson_to_save = default_lesson.copy()
        lesson_to_save["grammar_quiz"] = json.dumps(default_lesson["grammar_quiz"])
        save_cached_daily_lesson(today_str, lesson_to_save)
        
        return default_lesson

@app.post("/api/english/complete")
def complete_english_session():
    state = get_state()
    if not state:
        raise HTTPException(status_code=500, detail="Database state not initialized.")
        
    if not state.get("english_completed", 0):
        state["english_completed"] = 1
        # Award stats: +1 WIL (Willpower), +1 INT (Intelligence)
        state["wil"] = state.get("wil", 10) + 1
        state["int"] = state.get("int", 10) + 1
        # Replenish +10.0% Cognitive Energy
        state["energy"] = min(100.0, state.get("energy", 100.0) + 10.0)
        save_state(state)
        add_xp(15) # +15 XP
        
        log_activity_file(
            doing="Daily English Booster Completed",
            accomplished="Completed 5 minutes of focused English practice and dictionary lookups under AI surveillance. +15 XP, +1 WIL, +1 INT, +10.0% Cognitive Energy."
        )
        return {"status": "success", "message": "English session complete! Gained +15 XP, +1 WIL, +1 INT, +10.0% Cognitive Energy."}
    
    return {"status": "already_completed", "message": "Daily session already completed."}

# ─── MIND OS MODULE ENDPOINTS ──────────────────────────────────────────────────

class RealityCheckPayload(BaseModel):
    trigger_event: str
    my_interpretation: str
    evidence_for: str
    evidence_against: str
    alternative_explanation: str
    verified_outcome: Optional[str] = "Pending"
    distortions: Optional[str] = ""

class VerifyRealityCheckPayload(BaseModel):
    check_id: int
    verified_outcome: str

class RuminationPayload(BaseModel):
    trigger_convo: str
    intensity: int
    duration_mins: int
    distress_score: int
    grounding_used: int
    alternative_thought: Optional[str] = ""

class RelationshipPayload(BaseModel):
    person_name: str
    trust_score: int
    leave_urge: int
    closeness: int
    last_interaction_date: Optional[str] = ""
    notes: Optional[str] = ""
    status: Optional[str] = "Active"

@app.get("/mind-os")
def get_mind_os_page():
    return FileResponse(os.path.join(STATIC_DIR, "mind_os.html"))

@app.get("/api/mind_os/summary")
def api_get_mind_summary():
    try:
        summary = get_mind_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/reality_check")
def api_save_reality_check(payload: RealityCheckPayload):
    try:
        res = save_reality_check(
            payload.trigger_event,
            payload.my_interpretation,
            payload.evidence_for,
            payload.evidence_against,
            payload.alternative_explanation,
            payload.verified_outcome,
            payload.distortions
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mind_os/reality_checks")
def api_get_reality_checks(limit: int = 50):
    try:
        return get_reality_checks(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/reality_check/verify")
def api_verify_reality_check(payload: VerifyRealityCheckPayload):
    try:
        return verify_reality_check(payload.check_id, payload.verified_outcome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/rumination")
def api_save_rumination(payload: RuminationPayload):
    try:
        res = save_rumination_log(
            payload.trigger_convo,
            payload.intensity,
            payload.duration_mins,
            payload.distress_score,
            payload.grounding_used,
            payload.alternative_thought
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mind_os/rumination_logs")
def api_get_rumination_logs(limit: int = 50):
    try:
        return get_rumination_logs(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/relationship")
def api_save_relationship(payload: RelationshipPayload):
    try:
        res = save_relationship(
            payload.person_name,
            payload.trust_score,
            payload.leave_urge,
            payload.closeness,
            payload.last_interaction_date,
            payload.notes,
            payload.status
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mind_os/relationships")
def api_get_relationships():
    try:
        return get_relationships()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MeditationPayload(BaseModel):
    duration_mins: int
    track_name: str

@app.post("/api/mind_os/meditation")
def api_save_meditation(payload: MeditationPayload):
    try:
        return save_meditation_log(payload.duration_mins, payload.track_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mind_os/meditation_logs")
def api_get_meditation_logs(limit: int = 50):
    try:
        return get_meditation_logs(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# CANVAS LMS INTEGRATION (VIT Online — lms.vitonline.in)
# ══════════════════════════════════════════════════════════════════════════════

_canvas_engine = None

def _get_canvas():
    """Lazy singleton — missing token doesn't crash startup."""
    global _canvas_engine
    if _canvas_engine is None:
        try:
            from engine.canvas_sync import CanvasLMSSync
            _canvas_engine = CanvasLMSSync()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Canvas engine unavailable: {e}")
    return _canvas_engine

def _canvas_engine_sync_task():
    try:
        result = _get_canvas().sync_completed_items()
        print(f"[Canvas BG] Sync done: {result.get('new_completions',0)} new items, +{result.get('xp_earned',0)} XP")
    except Exception as e:
        print(f"[Canvas BG] Sync error: {e}")


@app.get("/canvas")
def get_canvas_page():
    return FileResponse(os.path.join(STATIC_DIR, "canvas.html"))


@app.get("/api/canvas/status")
def api_canvas_status():
    try:
        engine = _get_canvas()
        token  = engine.token
        if not token:
            return {"token_configured": False, "message": "CANVAS_API_TOKEN not set. Add it to .env.", "setup_url": "https://lms.vitonline.in/profile/settings"}
        valid  = engine.check_token()
        return {"token_configured": True, "token_valid": valid, "domain": engine.domain, "message": "Token valid ✅" if valid else "Token invalid ❌"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/canvas/courses")
def api_canvas_courses():
    try:
        return _get_canvas().get_courses_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/canvas/history")
def api_canvas_history(limit: int = 100):
    try:
        return _get_canvas().get_completion_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/canvas/sync")
def api_canvas_sync_post(background_tasks: BackgroundTasks):
    """Async Canvas sync — runs in background, returns immediately."""
    engine = _get_canvas()
    if not engine.token:
        raise HTTPException(status_code=400, detail="CANVAS_API_TOKEN not configured.")
    background_tasks.add_task(_canvas_engine_sync_task)
    return {"status": "SYNC_INITIATED", "target": "https://lms.vitonline.in"}


@app.get("/api/canvas/sync")
def api_canvas_sync_get():
    """Synchronous Canvas sync — returns full result (use for debugging)."""
    engine = _get_canvas()
    if not engine.token:
        raise HTTPException(status_code=400, detail="CANVAS_API_TOKEN not configured.")
    try:
        return engine.sync_completed_items()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/canvas/progress")
def api_canvas_progress():
    """Returns live sync progress status for interactive UI loading bar."""
    try:
        from engine.canvas_sync import get_sync_progress
        return get_sync_progress()
    except Exception as e:
        return {"is_syncing": False, "pct": 0, "status_message": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CONNECT & FITNESS SYNC INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

class HealthPayload(BaseModel):
    steps: int = 0
    distance_km: float = 0.0
    active_minutes: int = 0
    sleep_hours: float = 0.0
    resting_hr: Optional[int] = None
    log_date: Optional[str] = None

@app.post("/api/health_sync")
def api_health_sync(payload: HealthPayload):
    """
    Automated or manual health & walking data synchronization endpoint.
    Processes steps, distance, active minutes, sleep, and resting HR.
    """
    try:
        from engine.database import process_health_sync
        return process_health_sync(
            steps=payload.steps,
            distance_km=payload.distance_km,
            active_minutes=payload.active_minutes,
            sleep_hours=payload.sleep_hours,
            resting_hr=payload.resting_hr,
            log_date=payload.log_date
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health_sync/history")
def api_health_sync_history(limit: int = 50):
    """Retrieve past health sync logs."""
    try:
        from engine.database import get_health_sync_history
        return get_health_sync_history(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/health_sync/google_fit")
def api_health_sync_google_fit():
    """Trigger direct Google Fit Cloud API query."""
    try:
        from engine.google_fit_sync import sync_daily_fitness
        return sync_daily_fitness()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health_sync/reauth")
@app.post("/api/health_sync/reauth")
def api_health_sync_reauth():
    """Triggers interactive Google Fit OAuth re-authentication to refresh expired credentials."""
    try:
        from engine.reauth_google_fit import perform_reauth
        success = perform_reauth()
        if success:
            return {"status": "SUCCESS", "message": "Google Health Fit OAuth credentials refreshed successfully!"}
        else:
            return {"status": "ERROR", "message": "Google Health Fit OAuth re-authentication failed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# LEETCODE MANUAL TRIGGER & TIMEZONE SYNC
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/leetcode/sync")
@app.get("/api/leetcode/sync")
def api_leetcode_sync(username: Optional[str] = None):
    """
    Triggers on-demand LeetCode submission check & timezone evaluation.
    Auto-marks daily completion and awards XP/STR if solves detected.
    """
    try:
        from engine.leetcode_sync import sync_leetcode
        uname = username or os.getenv("LEETCODE_USERNAME", "boopathispark")
        return sync_leetcode(username=uname, force=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# GYMPRO STOPWATCH & MANUAL LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class GymProLogPayload(BaseModel):
    duration_minutes: float
    workout_type: str = "Strength Training"
    is_manual: bool = False
    notes: Optional[str] = ""

@app.post("/api/gympro/log_workout")
def log_gympro_workout(data: GymProLogPayload):
    try:
        mins = max(1.0, float(data.duration_minutes))
        base_xp = int((mins / 10.0) * 5)
        str_gain = int(mins / 10.0) * 2
        wil_gain = 5 if mins >= 30 else 2
        
        state = get_state() or {}
        if state:
            state["str"] = state.get("str", 10) + str_gain
            state["wil"] = state.get("wil", 10) + wil_gain
            state["energy"] = min(100.0, state.get("energy", 100.0) + 20.0)
            state["gym_completed"] = 1
            save_state(state)
        add_xp(base_xp)

        log_activity_file("GymPro Workout Logged", f"{'Manual' if data.is_manual else 'Timer'} Workout: {data.workout_type} ({mins} mins). +{base_xp} XP, +{str_gain} STR, +{wil_gain} WIL.")

        if not IS_SERVERLESS:
            with _DB_WRITE_LOCK:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS gym_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        duration_minutes REAL,
                        workout_type TEXT,
                        is_manual INTEGER,
                        notes TEXT,
                        xp_awarded INTEGER,
                        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    INSERT INTO gym_logs (duration_minutes, workout_type, is_manual, notes, xp_awarded)
                    VALUES (?, ?, ?, ?, ?)
                """, (mins, data.workout_type, 1 if data.is_manual else 0, data.notes or "", base_xp))
                conn.commit()
                conn.close()

        return {
            "status": "SUCCESS",
            "xp_earned": base_xp,
            "str_gained": str_gain,
            "wil_gained": wil_gain,
            "message": f"Gym Session Recorded! +{base_xp} XP | +{str_gain} STR"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# OFFICE WORK TRACKER & EXPONENTIAL XP ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class WorkLogPayload(BaseModel):
    workLogId: Optional[Union[int, str]] = None
    worklogId: Optional[Union[int, str]] = None
    workItemId: str
    description: str
    workDate: Optional[str] = None
    Category: Optional[str] = None
    category: Optional[str] = None
    hours: Union[float, str]

def auto_categorize_work_with_groq(description: str, work_item_id: str, default_cat: str) -> str:
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = 'groq_api_key'")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                groq_key = row[0].strip()
        except Exception:
            pass

    if not groq_key:
        try:
            import psycopg2
            from config import DATABASE_URL
            nconn = psycopg2.connect(DATABASE_URL)
            ncur = nconn.cursor()
            ncur.execute("SELECT value FROM user_app_settings WHERE key = 'groq_api_key'")
            row = ncur.fetchone()
            ncur.close()
            nconn.close()
            if row and row[0]:
                groq_key = row[0].strip()
        except Exception:
            pass

    if not groq_key or not description:
        return default_cat or "General"

    try:
        import urllib.request
        import json
        req_data = {
            "model": "openai/gpt-oss-120b",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a tech lead. Categorize office work items into clean, professional 1-3 word engineering domain categories (e.g. 'Automation & Workflows', 'Backend Engineering', 'Database & SQL', 'API Integration', 'Frontend & UI', 'DevOps & Cloud', 'AI & Machine Learning'). Output ONLY the category name string."
                },
                {
                    "role": "user",
                    "content": f"Work Item: {work_item_id}\nDescription: {description}\nProvided Category: {default_cat}"
                }
            ],
            "max_tokens": 15,
            "temperature": 0.1
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(req_data).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Antigravity/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cat = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
            if cat and len(cat) <= 40:
                return cat
    except Exception as e:
        print(f"[Groq Auto-Category Note] {e} -> fallback to '{default_cat}'")

    return default_cat or "General"

@app.post("/api/work_tracker/log_work")
def log_office_work(payload: WorkLogPayload):
    try:
        raw_category = (payload.Category or payload.category or "General").strip()
        work_item_id = payload.workItemId.strip()
        
        # Groq AI Auto Categorization with seamless fallback
        category = auto_categorize_work_with_groq(payload.description, work_item_id, raw_category)
        
        # Parse hours safely whether passed as float or string (e.g. "2")
        raw_hours = str(payload.hours).replace("h", "").strip()
        hours = max(0.1, float(raw_hours))
        
        # Sanitize ISO timestamp workDate (e.g. "2026-07-27T15:30:00.0000000" -> "2026-07-27")
        raw_date = (payload.workDate or "").strip()
        if "T" in raw_date:
            work_date = raw_date.split("T")[0]
        elif " " in raw_date:
            work_date = raw_date.split(" ")[0]
        else:
            work_date = raw_date
            
        if not work_date:
            import datetime as _dt
            work_date = _dt.date.today().isoformat()
        
        # 1. Write to local SQLite DB
        raw_target_id = payload.workLogId if payload.workLogId is not None else payload.worklogId
        target_work_log_id = None
        if raw_target_id is not None and str(raw_target_id).strip():
            try:
                target_work_log_id = int(str(raw_target_id).strip())
            except (ValueError, TypeError):
                target_work_log_id = None

        with _DB_WRITE_LOCK:
            conn = get_db_connection()
            cursor = conn.cursor()
            existing = None
            if target_work_log_id is not None:
                cursor.execute("SELECT workLogId FROM office_work_logs WHERE workLogId = ?", (target_work_log_id,))
                existing = cursor.fetchone()
            
            # Fallback dedup: check if same work item already logged for same date
            if not existing:
                cursor.execute("SELECT workLogId FROM office_work_logs WHERE workItemId = ? AND workDate = ?", (work_item_id, work_date))
                existing = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) FROM office_work_logs WHERE category = ?", (category,))
            category_count = cursor.fetchone()[0] or 0
            
            base_xp_per_hour = 40.0
            multiplier = 1.0 + (0.25 * math.pow(1.20, min(category_count, 15)))
            xp_earned = round(hours * base_xp_per_hour * multiplier, 2)
            category_streak = category_count + 1
            
            if existing:
                cursor.execute("""
                    UPDATE office_work_logs 
                    SET description = ?, category = ?, hours = ?, workItemId = ?, workDate = ?
                    WHERE workLogId = ?
                """, (payload.description, category, hours, work_item_id, work_date, existing[0]))
                conn.commit()
                work_log_id = existing[0]
                action = "UPDATED"
            else:
                cursor.execute("""
                    INSERT INTO office_work_logs (workItemId, description, workDate, category, hours, xp_awarded, category_streak)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (work_item_id, payload.description, work_date, category, hours, xp_earned, category_streak))
                conn.commit()
                work_log_id = cursor.lastrowid
                action = "CREATED"
            conn.close()

        # 2. Write to Neon PostgreSQL DB if online / serverless
        try:
            from engine.neon_db import neon_log_office_work
            neon_log_office_work(work_item_id, payload.description, work_date, category, hours, xp_earned, category_streak, work_log_id=target_work_log_id)
        except Exception as ne:
            print(f"[Work Log Neon Sync Note] {ne}")

        # Update Player Stats (AGI & INT boost)
        agi_boost = int(hours * 2)
        int_boost = int(hours * 1)
        
        state = get_state() or {}
        if state:
            state["agi"] = state.get("agi", 10) + agi_boost
            state["int"] = state.get("int", 10) + int_boost
            save_state(state)
        add_xp(int(xp_earned))
        
        log_activity_file("Office Work Logged", f"Logged work item '{work_item_id}' [Log ID #{work_log_id}] ({category}, {hours}h). Mastery Depth: Lvl {category_streak}. +{xp_earned} XP, +{agi_boost} AGI, +{int_boost} INT.")
        
        return {
            "status": "SUCCESS",
            "action": action,
            "workLogId": work_log_id,
            "workItemId": work_item_id,
            "xp_awarded": xp_earned,
            "category": category,
            "category_streak": category_streak,
            "stat_boosts": {"AGI": f"+{agi_boost}", "INT": f"+{int_boost}"},
            "message": f"Work Logged ({action.capitalize()})! Category Depth Level: {category_streak} | Log #{work_log_id} | Earned +{xp_earned} XP!"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/work_tracker/logs")
def get_office_work_logs(limit: int = 300):
    try:
        logs = []
        # Try Neon PostgreSQL DB first
        try:
            from engine.neon_db import neon_get_office_work_logs
            logs = neon_get_office_work_logs(limit=limit)
        except Exception as ne:
            print(f"[Work Log Neon Read Note] {ne}")

        # Fallback to local SQLite DB if Neon returns empty or fails
        if not logs:
            with _DB_WRITE_LOCK:
                conn = get_db_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM office_work_logs ORDER BY logged_at DESC LIMIT ?", (limit,))
                logs = [dict(r) for r in cursor.fetchall()]
                conn.close()
        
        # Compute Category summary stats dynamically from logs
        summary = {}
        for l in logs:
            cat = l.get("category", "General")
            if cat not in summary:
                summary[cat] = {"total_logs": 0, "total_hours": 0.0, "multiplier": 1.0}
            summary[cat]["total_logs"] += 1
            summary[cat]["total_hours"] = round(summary[cat]["total_hours"] + float(l.get("hours", 0)), 1)

        for cat, s in summary.items():
            cnt = s["total_logs"]
            s["multiplier"] = round(1.0 + (0.25 * math.pow(1.20, min(cnt - 1, 15))), 2)
            
        return {"status": "SUCCESS", "logs": logs, "category_summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# MIND OS API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class MindMeditationPayload(BaseModel):
    duration_mins: int
    track_name: str

class MindRuminationPayload(BaseModel):
    trigger_convo: str
    intensity: int = 5
    duration_mins: int = 10
    distress_score: int = 5
    grounding_used: int = 0
    alternative_thought: Optional[str] = ""

class MindRealityCheckPayload(BaseModel):
    trigger_event: str
    my_interpretation: str
    evidence_for: Optional[str] = ""
    evidence_against: Optional[str] = ""
    alternative_explanation: Optional[str] = ""
    verified_outcome: Optional[str] = "Pending"
    distortions: Optional[str] = ""

class MindRelationshipPayload(BaseModel):
    person_name: str
    trust_score: int = 5
    leave_urge: int = 0
    closeness: int = 5
    last_interaction_date: Optional[str] = ""
    notes: Optional[str] = ""
    status: Optional[str] = "Active"

@app.post("/api/mind_os/meditation")
def api_mind_os_meditation(payload: MindMeditationPayload):
    try:
        from engine.database import save_meditation_log
        res = save_meditation_log(payload.duration_mins, payload.track_name)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/rumination")
def api_mind_os_rumination(payload: MindRuminationPayload):
    try:
        from engine.database import save_rumination_log
        res = save_rumination_log(
            payload.trigger_convo,
            payload.intensity,
            payload.duration_mins,
            payload.distress_score,
            payload.grounding_used,
            payload.alternative_thought or ""
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/reality_check")
def api_mind_os_reality_check(payload: MindRealityCheckPayload):
    try:
        from engine.database import save_reality_check
        res = save_reality_check(
            payload.trigger_event,
            payload.my_interpretation,
            payload.evidence_for or "",
            payload.evidence_against or "",
            payload.alternative_explanation or "",
            payload.verified_outcome or "Pending",
            payload.distortions or ""
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mind_os/relationship")
def api_mind_os_relationship(payload: MindRelationshipPayload):
    try:
        from engine.database import save_relationship
        res = save_relationship(
            payload.person_name,
            payload.trust_score,
            payload.leave_urge,
            payload.closeness,
            payload.last_interaction_date or "",
            payload.notes or "",
            payload.status or "Active"
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mind_os/summary")
def api_mind_os_summary():
    try:
        from engine.database import get_mind_summary
        return get_mind_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SEMESTER TRACKER — 12-Week Canvas Academic Cadence (OLMDS601–607)
# ═══════════════════════════════════════════════════════════════════════════════

class SemesterOverridePayload(BaseModel):
    date: Optional[str] = None
    notes: Optional[str] = ""

class WeeklyProgressPayload(BaseModel):
    course_code:     str
    week_number:     int
    videos_watched:  Optional[int] = 0
    quiz_done:       Optional[int] = 0
    assignment_done: Optional[int] = 0
    notes:           Optional[str] = ""
    status:          Optional[str] = "IN_PROGRESS"


@app.get("/semester")
def semester_page():
    """Serve the semester tracker HTML dashboard."""
    html_path = os.path.join(STATIC_DIR, "semester_tracker.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Semester tracker page not found. Run setup.</h1>", status_code=404)


@app.get("/api/semester/dashboard")
def api_semester_dashboard():
    """Full dashboard payload — weekly grid, today's target, audit log, stats."""
    try:
        from engine.semester_enforcer import get_semester_dashboard_data
        return get_semester_dashboard_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/semester/today")
def api_semester_today():
    """Today's mandatory subject, countdown timer, and audit status."""
    try:
        from engine.semester_enforcer import get_today_target, init_semester_tables
        import sqlite3, os
        from engine.database import DB_PATH

        init_semester_tables()
        target = get_today_target()

        # Attach today's audit status if already audited
        today_str = target["date"]
        audit_status = "PENDING"
        items_done   = 0
        xp_awarded   = 0
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            row  = conn.execute(
                "SELECT status, items_completed, xp_awarded FROM daily_academic_cadence WHERE log_date = ?",
                (today_str,)
            ).fetchone()
            conn.close()
            if row:
                audit_status = row["status"]
                items_done   = row["items_completed"]
                xp_awarded   = row["xp_awarded"]
        except Exception:
            pass

        target["audit_status"] = audit_status
        target["items_done"]   = items_done
        target["xp_awarded"]   = xp_awarded
        return target
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/semester/audit")
def api_semester_audit(force: bool = True):
    """Manually trigger the nightly audit (force rerun)."""
    try:
        from engine.semester_enforcer import run_daily_audit
        result = run_daily_audit(force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/semester/mark_cleared")
def api_semester_mark_cleared(payload: SemesterOverridePayload, _: bool = Depends(verify_token)):
    """Admin override — manually mark a day as CLEARED."""
    try:
        from engine.semester_enforcer import mark_day_cleared
        result = mark_day_cleared(date_str=payload.date, notes=payload.notes or "")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/semester/update_progress")
def api_semester_update_progress(payload: WeeklyProgressPayload, _: bool = Depends(verify_token)):
    """Manually update weekly progress for a course (e.g., log watched videos)."""
    try:
        from engine.database import DB_PATH
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("""
            INSERT OR REPLACE INTO semester_weekly_progress
            (course_code, course_name, week_number, videos_watched, quiz_done,
             assignment_done, concepts_notes, status, completed_at)
            VALUES (
                ?,
                (SELECT course_name FROM semester_course_stats WHERE course_code = ?),
                ?, ?, ?, ?, ?, ?,
                CASE WHEN ? = 'COMPLETED' THEN date('now') ELSE NULL END
            )
        """, (payload.course_code, payload.course_code, payload.week_number,
              payload.videos_watched, payload.quiz_done, payload.assignment_done,
              payload.notes, payload.status, payload.status))
        conn.commit()
        conn.close()
        return {"status": "updated", "course_code": payload.course_code, "week": payload.week_number}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# TASK STREAK ENGINE — Per-Task Daily Completion History & Individual Streaks
# ═══════════════════════════════════════════════════════════════════════════════

class TaskLogPayload(BaseModel):
    task_key:  str
    completed: bool = True
    log_date:  Optional[str] = None


@app.get("/api/tasks/streaks")
def api_get_task_streaks():
    """
    Returns per-task streak stats for all 12 daily tasks.
    Powers the Task Streaks page and the checklist streak badges.
    """
    try:
        streaks = get_task_streaks()
        return {"status": "success", "streaks": streaks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/log")
def api_log_task(payload: TaskLogPayload):
    """
    Manually log a task completion (used for canvas_semester and other non-checklist tasks).
    """
    VALID_KEYS = {
        "study", "leetcode", "gym", "english", "cooking",
        "nopmo", "reading", "walk", "meditation", "mindos",
        "health", "canvas_semester",
    }
    if payload.task_key not in VALID_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown task_key: {payload.task_key}")
    try:
        log_task_completion(payload.task_key, payload.completed, payload.log_date)
        # For canvas_semester, also write to semester audit table
        if payload.task_key == "canvas_semester" and payload.completed:
            try:
                from engine.semester_enforcer import run_daily_audit
                run_daily_audit(force=True)
            except Exception:
                pass
        return {"status": "logged", "task_key": payload.task_key, "completed": payload.completed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/backfill")
def api_backfill_tasks():
    """
    One-time historical data import into task_daily_log.
    Reads study_journal, reading_logs, health_sync_logs, canvas_completed_items, gym_logs
    and populates task_daily_log so streak history is accurate.
    Safe to call multiple times (INSERT OR IGNORE). No auth required — idempotent read+import.
    """
    try:
        result = backfill_task_daily_log()
        # Return fresh streaks after backfill
        streaks = get_task_streaks()
        summary = {k: {"total_done": v["total_done"], "current_streak": v["current_streak"]} for k, v in streaks.items()}
        return {"status": "success", "backfilled": result, "streaks_after": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task-streaks")
def task_streaks_page():
    """Serve the per-task streak tracker page."""
    html_path = os.path.join(STATIC_DIR, "task_streaks.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Task Streaks page not found.</h1>", status_code=404)


# ══════════════════════════════════════════════════════════════════════════════
#  🔔 NOTIFICATION BELL API
#  Canvas reminders + system alerts stored in in_app_notifications table.
#  Called by the bell icon in shared.js every 60 seconds.
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/notifications")
def api_get_notifications(limit: int = 20, unread_only: bool = False):
    """
    Fetch in-app notifications for the bell icon.
    Canvas reminder engine writes here at 09:00 / 14:00 / 20:00 / 23:00
    when today's course work is not done.
    """
    try:
        items = get_notifications(limit=limit, unread_only=unread_only)
        count = get_unread_notification_count()
        return {"notifications": items, "unread_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MarkReadPayload(BaseModel):
    ids: Optional[List[int]] = None


@app.post("/api/notifications/read")
def api_mark_notifications_read(payload: Optional[MarkReadPayload] = None):
    """
    Mark notifications as read. Pass list of IDs or empty payload to mark all.
    Called when user opens the bell panel.
    """
    try:
        notification_ids = payload.ids if payload else None
        count = mark_notifications_read(notification_ids)
        return {"status": "ok", "marked_read": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications/count")
def api_notification_count():
    """Quick endpoint for the bell badge — just returns unread count."""
    try:
        count = get_unread_notification_count()
        return {"unread_count": count}
    except Exception:
        return {"unread_count": 0}







