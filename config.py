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

# Burnout mitigation coefficients
ALPHA = 15.0  # Cognitive drawdown per hour of heavy study
BETA = 25.0   # Gym discipline replenishment per hour
GAMMA = 10.0  # Micro-dopamine reward replenishment

# Circuit breaker trigger threshold (20% energy)
CIRCUIT_BREAKER_LIMIT = 20.0
MAX_STREAK_LIMIT = 21

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

IS_SERVERLESS = not _check_fs_writable()
if IS_SERVERLESS:
    print("[Config] Read-only filesystem detected — running in serverless/Neon-only mode.")

