import urllib.request
import json
import time
from datetime import datetime, timezone
from config import LEETCODE_ENDPOINT, LEETCODE_USERNAME

def fetch_leetcode_data(query: str, variables: dict) -> dict:
    req_data = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        LEETCODE_ENDPOINT,
        data=req_data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res = response.read().decode("utf-8")
            return json.loads(res)
    except Exception as e:
        print(f"Error querying LeetCode GraphQL: {e}")
        return {}

def get_user_solved_stats(username: str = LEETCODE_USERNAME) -> dict:
    """
    Fetches aggregate counts of solved problems.
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
    data = fetch_leetcode_data(query, {"username": username})
    try:
        stats = data["data"]["matchedUser"]["submitStats"]["acSubmissionNum"]
        return {item["difficulty"]: item["count"] for item in stats}
    except (KeyError, TypeError):
        return {"All": 0, "Easy": 0, "Medium": 0, "Hard": 0}

def get_recent_ac_submissions(username: str = LEETCODE_USERNAME, limit: int = 15) -> list:
    """
    Fetches the list of recent accepted submissions.
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
    data = fetch_leetcode_data(query, {"username": username, "limit": limit})
    try:
        return data["data"]["recentAcSubmissionList"]
    except (KeyError, TypeError):
        return []

def has_solved_today(username: str = LEETCODE_USERNAME) -> bool:
    """
    Checks if the user has solved any problem in the last 24 hours (UTC/local day match).
    """
    submissions = get_recent_ac_submissions(username)
    if not submissions:
        return False
    
    current_time = time.time()
    # Check submissions within the last 24 hours (86400 seconds)
    for sub in submissions:
        sub_time = int(sub["timestamp"])
        if current_time - sub_time < 86400:
            return True
    return False
