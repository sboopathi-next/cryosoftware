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

