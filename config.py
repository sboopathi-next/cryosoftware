import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

USER_PROFILE_ID = os.getenv("USER_PROFILE_ID", "Boopathi Subramaniyan")
LEETCODE_USERNAME = os.getenv("LEETCODE_USERNAME", "boopathispark")
LEETCODE_ENDPOINT = os.getenv("LEETCODE_ENDPOINT", "https://leetcode.com/graphql")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN", "9nMCKvXP9AkA6kZxZ6huDMf39ABv9n7Euvw2aHerm3mEDWmQhM3XfUryA4uMzXAh")
CANVAS_DOMAIN = os.getenv("CANVAS_DOMAIN", "lms.vitonline.in")

# Burnout mitigation coefficients
ALPHA = 15.0  # Cognitive drawdown per hour of heavy study
BETA = 25.0   # Gym discipline replenishment per hour
GAMMA = 10.0  # Micro-dopamine reward replenishment

# Circuit breaker trigger threshold (20% energy)
CIRCUIT_BREAKER_LIMIT = 20.0
MAX_STREAK_LIMIT = 21

# ── Cognitive Energy Action Deltas ──────────────────────────────────────────
# Applied once, at the moment each real action is actually logged (checklist
# toggle, Canvas sync, LeetCode sync, health sync) — NOT via a manual timer.
# Negative = mental/physical exertion cost. Positive = recovery.
# This is what keeps state["energy"] moving instead of sitting at 100 forever.
ENERGY_ACTION_DELTAS = {
    "study":        -18.0,   # Deep focused study session — heaviest cognitive cost
    "leetcode":     -8.0,    # Algorithmic problem solving, once per day it flips to solved
    "english":      -6.0,    # Language practice session
    "reading":      -5.0,    # Book reading session
    "canvas_video": -3.0,    # Per auto-synced Canvas video/page watched
    "canvas_quiz":  -10.0,   # Per auto-synced Canvas quiz/assignment submitted
    "cooking":      4.0,     # Self-care / nourishment
    "nopmo":        3.0,     # Discipline win reduces internal stress
    "meditation":   8.0,     # Dedicated mindfulness recovery (was miscoded as gym before)
    "mindos":       5.0,     # Emotional processing / reality check relief
    "walk_5000":    10.0,    # Steps >= 5000 today (on top of existing sleep recovery)
    "walk_2000":    5.0,     # Steps >= 2000 today
}

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# ── Serverless / read-only filesystem detection ────────────────────────────
# On Vercel and other serverless platforms, /var/task is read-only.
# When IS_SERVERLESS is True, all file-system writes are skipped and
# Neon PostgreSQL is used as the sole persistent storage.
def _check_fs_writable() -> bool:
    """Returns False if the filesystem where STATE_FILE lives is read-only."""
    _dir = os.path.dirname(STATE_FILE) or "."
    try:
        _test_path = os.path.join(_dir, ".write_test_tmp")
        with open(_test_path, "w") as _f:
            _f.write("1")
        os.remove(_test_path)
        return True
    except OSError:
        return False

IS_SERVERLESS = bool(os.environ.get("VERCEL")) or (not _check_fs_writable())
if IS_SERVERLESS:
    print("[Config] Serverless / Read-only environment detected — running in serverless/Neon-only mode.")

