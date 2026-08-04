import sys
import os
import time
import threading
import requests

# Ensure parent directory (antigravity_core) is in sys.path when script is executed directly
pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from engine.database import get_db_connection, get_state, save_state, add_xp, log_activity_file


LEETCODE_ENDPOINT = "https://leetcode.com/graphql"
LEETCODE_USERNAME = "boopathispark"

def fetch_leetcode_solved_stats(username: str = LEETCODE_USERNAME) -> dict:
    """
    Queries LeetCode GraphQL endpoint for total solved problems by difficulty.
    """
    query = """
    query userProblemsSolved($username: String!) {
      matchedUser(username: $username) {
        submitStats {
          acSubmissionNum {
            difficulty
            count
          }
        }
      }
    }
    """
    try:
        response = requests.post(
            LEETCODE_ENDPOINT,
            json={"query": query, "variables": {"username": username}},
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if response.status_code == 200:
            res_data = response.json()
            stats = res_data.get("data", {}).get("matchedUser", {}).get("submitStats", {}).get("acSubmissionNum", [])
            return {item["difficulty"]: item["count"] for item in stats}
    except Exception as e:
        print(f"[LeetCode Sync] Error querying solved stats: {e}")
    return {}

def fetch_leetcode_recent_ac(username: str = LEETCODE_USERNAME, limit: int = 15) -> list:
    """
    Fetches recent accepted submissions for the given username.
    """
    query = """
    query userRecentAcSubmissions($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    try:
        response = requests.post(
            LEETCODE_ENDPOINT,
            json={"query": query, "variables": {"username": username, "limit": limit}},
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if response.status_code == 200:
            res_data = response.json()
            return res_data.get("data", {}).get("recentAcSubmissionList", [])
    except Exception as e:
        print(f"[LeetCode Sync] Error querying recent AC submissions: {e}")
    return []

def has_solved_leetcode_today(username: str = LEETCODE_USERNAME) -> bool:
    """
    Checks if the user has completed an accepted submission in the last 24 hours (86400 seconds).
    """
    submissions = fetch_leetcode_recent_ac(username, limit=10)
    if not submissions:
        return False
    
    now = time.time()
    for sub in submissions:
        try:
            sub_time = int(sub.get("timestamp", 0))
            if now - sub_time < 86400:
                return True
        except (ValueError, TypeError):
            continue
    return False

def get_stored_leetcode_stats() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT difficulty, solved_count FROM leetcode_stats")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def update_stored_leetcode_stats(stats: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    for diff, count in stats.items():
        cursor.execute(
            "INSERT OR REPLACE INTO leetcode_stats (difficulty, solved_count) VALUES (?, ?)",
            (diff, count)
        )
    conn.commit()
    conn.close()

def sync_leetcode(username: str = LEETCODE_USERNAME, force: bool = False) -> dict:
    """
    Main synchronization function:
    1. Fetches current LeetCode solved counts & recent accepted submissions.
    2. Compares against local database cache.
    3. Calculates XP (+20 Easy, +50 Medium, +100 Hard) & STR (+1 Easy, +2 Medium, +3 Hard).
    4. Auto-marks daily leetcode_completed = 1 if user solved problems today or new solves detected.
    5. Returns sync report dictionary.
    """
    print(f"[LeetCode Sync] Starting synchronization check for user '{username}'...")
    current_stats = fetch_leetcode_solved_stats(username)
    if not current_stats:
        print("[LeetCode Sync] Failed to fetch stats or user profile not found.")
        return {"status": "error", "message": "Failed to fetch LeetCode stats."}

    recent_subs = fetch_leetcode_recent_ac(username, limit=10)
    solved_today = has_solved_leetcode_today(username)
    stored_stats = get_stored_leetcode_stats()
    
    total_stored = sum(stored_stats.values())
    
    # Handle initial database state
    if total_stored == 0:
        print("[LeetCode Sync] Initializing stored stats with current LeetCode profile values.")
        update_stored_leetcode_stats(current_stats)
        if solved_today:
            state = get_state()
            state["leetcode_completed"] = 1
            save_state(state)
        return {
            "status": "success",
            "initialized": True,
            "solved_today": solved_today,
            "current_stats": current_stats,
            "recent_submissions": recent_subs
        }

    delta_easy = max(0, current_stats.get("Easy", 0) - stored_stats.get("Easy", 0))
    delta_medium = max(0, current_stats.get("Medium", 0) - stored_stats.get("Medium", 0))
    delta_hard = max(0, current_stats.get("Hard", 0) - stored_stats.get("Hard", 0))

    xp_gain = 0
    str_gain = 0

    if delta_easy > 0 or delta_medium > 0 or delta_hard > 0:
        xp_gain = (delta_easy * 20) + (delta_medium * 50) + (delta_hard * 100)
        str_gain = (delta_easy * 1) + (delta_medium * 2) + (delta_hard * 3)
        
        print(f"[LeetCode Sync] Detected new solves! Easy:+{delta_easy}, Medium:+{delta_medium}, Hard:+{delta_hard}")
        print(f"[LeetCode Sync] Awarding {xp_gain} XP and +{str_gain} STR")
        
        # 1. Update stats (STR) and checklist completion
        state = get_state()
        state["str"] = state.get("str", 10) + str_gain
        state["leetcode_completed"] = 1
        save_state(state)
        
        # 2. Add XP and level up
        add_xp(xp_gain)
        
        # 3. Update cached LeetCode counts in database
        update_stored_leetcode_stats(current_stats)
        
        # 4. Log user activity
        log_activity_file(
            doing="LeetCode Solves Synced",
            accomplished=f"Solved new problems (Easy: +{delta_easy}, Medium: +{delta_medium}, Hard: +{delta_hard}). Awarded +{xp_gain} XP, +{str_gain} STR."
        )
    elif solved_today:
        print("[LeetCode Sync] Solved problem today! Marking daily checklist item completed.")
        state = get_state()
        if not state.get("leetcode_completed"):
            state["leetcode_completed"] = 1
            save_state(state)
    else:
        print("[LeetCode Sync] No new solves detected.")

    return {
        "status": "success",
        "solved_today": solved_today,
        "deltas": {"Easy": delta_easy, "Medium": delta_medium, "Hard": delta_hard},
        "xp_awarded": xp_gain,
        "str_awarded": str_gain,
        "current_stats": current_stats,
        "recent_submissions": recent_subs
    }

def run_leetcode_sync_loop(stop_event: threading.Event):
    """
    Hourly background worker daemon for LeetCode sync.
    """
    # Perform initial sync
    try:
        sync_leetcode()
    except Exception as e:
        print(f"[LeetCode Sync] Error on initial sync: {e}")
    
    # Hourly background loop
    while not stop_event.wait(3600):  # Wait 3600 seconds (60 minutes) unless stopped
        try:
            sync_leetcode()
        except Exception as e:
            print(f"[LeetCode Sync] Exception in background loop: {e}")

if __name__ == "__main__":
    import json
    res = sync_leetcode()
    print("\n--- LeetCode Sync Result ---")
    print(json.dumps(res, indent=2))

