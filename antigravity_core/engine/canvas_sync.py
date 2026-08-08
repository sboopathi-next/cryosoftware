"""
canvas_sync.py — Canvas LMS REST API Integration for Antigravity
================================================================
Connects to https://lms.vitonline.in via Canvas API v1.
Tracks completed videos, quizzes, assignments, and awards XP.

Canvas API Docs: https://developerdocs.instructure.com/services/canvas
API Rate Limits: Max 700 req/10 min per user token. We respect these with
                 automatic back-off on HTTP 429.
"""

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# ── Path Setup ─────────────────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR   = os.path.dirname(_ENGINE_DIR)
_ROOT_DIR   = os.path.dirname(_CORE_DIR)

for _p in [_ROOT_DIR, _CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from config import IS_SERVERLESS, DATABASE_URL, CANVAS_API_TOKEN, CANVAS_DOMAIN
except ImportError:
    IS_SERVERLESS = False
    DATABASE_URL  = ""
    CANVAS_API_TOKEN = "9nMCKvXP9AkA6kZxZ6huDMf39ABv9n7Euvw2aHerm3mEDWmQhM3XfUryA4uMzXAh"
    CANVAS_DOMAIN = "lms.vitonline.in"

# Load .env so token is available when running standalone (Vercel injects env directly)
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(
        dotenv_path=os.path.join(_ROOT_DIR, ".env"),
        override=False  # don't overwrite already-set system env vars
    )
except ImportError:
    pass


# ── Dynamic Canvas LMS Action Reward Matrix & Multiplier Engine ────────────────

def calculate_canvas_xp(
    item_type: str,
    title: str,
    score: Optional[float] = None,
    max_score: Optional[float] = None,
    submitted_at: Optional[str] = None,
    due_at: Optional[str] = None,
    streak_days: int = 0
) -> tuple[int, dict]:
    """
    Calculates XP and attribute gains dynamically based on Canvas item criteria,
    score bonuses, early bird conditions, and player streak multiplier (Ms).

    Reward Matrix:
    - Orientation / Page          :  15 XP | +1 INT
    - Lecture Video (10-35m)      :  25 XP | +1 INT
    - Weekly Feedback Survey      :  15 XP | +1 WIL
    - Q&A Discussion Contribution :  30 XP | +1 INT, +1 AGI
    - Live Session Recording      :  40 XP | +2 INT
    - Weekly Quiz (20 pts)        : 100 XP | +5 INT
      └ Perfect Quiz Bonus (100%) : +20 XP | +2 INT
      └ Early Bird Bonus (>=48h)  : +25 XP | +1 WIL
    - Digital Assignment (50 pts) : 350 XP | +15 INT, +10 AGI
    - Continuous Assessment (CAT) : 600 XP | +25 INT, +15 WIL
    - Full Module Wipe Bonus     : +100 XP | +5 WIL

    Streak Multiplier (Ms):
      Ms = 1.0 + min(1.0, streak_days / 30.0)
      XP_earned = round(XP_base * Ms)
    """
    title_upper = (title or "").upper()
    xp_base = 15
    stats = {"INT": 1, "AGI": 0, "WIL": 0}

    # 1. Continuous Assessment / CAT / Final Exam (Top Tier Evaluation)
    if any(k in title_upper for k in ("CAT", "CONTINUOUS ASSESSMENT", "MID TERM", "MID-TERM", "FINAL EXAM", "END TERM")):
        xp_base = 600
        stats = {"INT": 25, "AGI": 0, "WIL": 15}

    # 2. Digital Assignments & Projects
    elif item_type == "Assignment" or any(k in title_upper for k in ("ASSIGNMENT", "PROJECT", "DIGITAL ASSIGNMENT", "SUBMISSION")):
        xp_base = 350
        stats = {"INT": 15, "AGI": 10, "WIL": 0}

    # 3. Quizzes & Tests
    elif item_type == "Quiz" or any(k in title_upper for k in ("QUIZ", "TEST", "MCQ")):
        xp_base = 100
        stats = {"INT": 5, "AGI": 0, "WIL": 0}

        # Perfect Score Bonus check (100% score)
        if score is not None and max_score is not None and max_score > 0:
            if (score / max_score) >= 1.0:
                xp_base += 20
                stats["INT"] += 2

        # Early Bird Quiz Bonus check (submitting >= 48 hours before due date)
        if submitted_at and due_at:
            try:
                sub_dt = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
                due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                hours_early = (due_dt - sub_dt).total_seconds() / 3600.0
                if hours_early >= 48.0:
                    xp_base += 25
                    stats["WIL"] += 1
            except Exception:
                pass

    # 4. Live Session Recordings & Webinars
    elif any(k in title_upper for k in ("LIVE SESSION", "RECORDING", "WEBINAR", "LIVE LECTURE")):
        xp_base = 40
        stats = {"INT": 2, "AGI": 0, "WIL": 0}

    # 5. Discussions & Q&A
    elif item_type == "Discussion" or any(k in title_upper for k in ("DISCUSSION", "FORUM", "INTERACT", "Q&A")):
        xp_base = 30
        stats = {"INT": 1, "AGI": 1, "WIL": 0}

    # 6. Weekly Feedback Surveys
    elif any(k in title_upper for k in ("SURVEY", "FEEDBACK")):
        xp_base = 15
        stats = {"INT": 0, "AGI": 0, "WIL": 1}

    # 7. Lecture Videos & Video Pages
    elif item_type in ("ExternalUrl", "ExternalTool") or "VIDEO" in title_upper or "LECTURE" in title_upper:
        xp_base = 25
        stats = {"INT": 1, "AGI": 0, "WIL": 0}

    # 8. Standard Reading Page / Default
    else:
        xp_base = 15
        stats = {"INT": 1, "AGI": 0, "WIL": 0}

    # ── Apply Streak Multiplier Engine (Ms) ──
    ms = 1.0 + min(1.0, max(0, streak_days) / 30.0)
    xp_earned = int(round(xp_base * ms))

    return xp_earned, stats


# ── Global Live Sync Progress Tracker ──────────────────────────────────────────
_CURRENT_SYNC_PROGRESS = {
    "is_syncing": False,
    "courses_scanned": 0,
    "total_courses": 0,
    "current_course_name": "",
    "new_items_found": 0,
    "total_xp_gained": 0,
    "pct": 0,
    "status_message": "Ready to sync",
    "updated_at": ""
}

def get_sync_progress() -> dict:
    return dict(_CURRENT_SYNC_PROGRESS)




class CanvasLMSSync:
    """
    Full Canvas LMS REST API client for lms.vitonline.in.
    Follows Canvas API pagination (Link header) and respects rate limits.
    """

    CANVAS_DOMAIN = "lms.vitonline.in"

    def __init__(self, token: Optional[str] = None, domain: Optional[str] = None):
        self.domain   = domain or os.getenv("CANVAS_DOMAIN") or CANVAS_DOMAIN or self.CANVAS_DOMAIN
        self.base_url = f"https://{self.domain}/api/v1"
        self.token    = token or os.getenv("CANVAS_API_TOKEN") or CANVAS_API_TOKEN or ""
        self.headers  = {
            "Authorization": f"Bearer {self.token}",
            "Accept":        "application/json",
            "User-Agent":    "AntigravityEngine/2.0 (VIT Online Integration)",
        }
        # Local SQLite path (falls back gracefully on serverless)
        if IS_SERVERLESS:
            self.db_path = None
        else:
            _db_dir = os.path.join(_CORE_DIR, "data")
            if not os.access(_db_dir, os.W_OK):
                _db_dir = "/tmp/antigravity_data"
            os.makedirs(_db_dir, exist_ok=True)
            self.db_path = os.path.join(_db_dir, "system_solo.db")

    # ─── Internal Helpers ──────────────────────────────────────────────────────

    def _get(self, url: str, params: dict = None) -> Any:
        """
        GET with automatic pagination via Canvas Link headers.
        Returns list (if paginated) or dict.  Retries on 429.
        """
        results = []
        next_url = url
        while next_url:
            for attempt in range(3):
                try:
                    resp = requests.get(next_url, headers=self.headers,
                                        params=params if next_url == url else None,
                                        timeout=20)
                    if resp.status_code == 429:
                        # Canvas rate-limit: wait and retry
                        wait = int(resp.headers.get("X-Rate-Limit-Delay", 5))
                        print(f"[Canvas] Rate-limited, waiting {wait}s…")
                        time.sleep(wait)
                        continue
                    if resp.status_code == 401:
                        print("[Canvas] ❌ 401 Unauthorized — check your CANVAS_API_TOKEN in .env")
                        return []
                    if resp.status_code == 404:
                        print(f"[Canvas] 404 Not Found: {next_url}")
                        return []
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        return data  # single object endpoint
                    # Follow pagination
                    link = resp.headers.get("Link", "")
                    next_url = None
                    for part in link.split(","):
                        if 'rel="next"' in part:
                            next_url = part[part.index("<") + 1: part.index(">")]
                            break
                    break  # success — exit retry loop
                except requests.exceptions.Timeout:
                    print(f"[Canvas] Timeout on attempt {attempt + 1}/3 — {next_url}")
                    time.sleep(2 ** attempt)
                except requests.exceptions.ConnectionError:
                    print(f"[Canvas] Connection error — lms.vitonline.in may be unreachable")
                    return results
                except Exception as e:
                    print(f"[Canvas] Request error: {e}")
                    return results
            else:
                break  # exhausted retries
        return results

    def _init_canvas_table(self, conn: sqlite3.Connection):
        """Ensure the canvas tracking table exists in SQLite."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS canvas_completed_items (
                canvas_item_id   TEXT PRIMARY KEY,
                item_title       TEXT NOT NULL,
                course_id        INTEGER NOT NULL,
                course_name      TEXT,
                item_type        TEXT,
                xp_awarded       INTEGER DEFAULT 0,
                completed_at     TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS canvas_courses_cache (
                course_id    INTEGER PRIMARY KEY,
                course_name  TEXT,
                course_code  TEXT,
                last_synced  TEXT
            );
        """)
        conn.commit()

    # ─── Public API Methods ────────────────────────────────────────────────────

    def check_token(self) -> bool:
        """Quick token validity check using the /users/self endpoint."""
        data = self._get(f"{self.base_url}/users/self")
        if isinstance(data, dict) and data.get("id"):
            print(f"[Canvas] ✅ Token valid — User: {data.get('name', 'Unknown')}")
            return True
        print("[Canvas] ❌ Token invalid or Canvas unreachable.")
        return False

    def get_active_courses(self) -> List[Dict[str, Any]]:
        """Fetch all active enrolled courses."""
        courses = self._get(f"{self.base_url}/courses", params={
            "enrollment_state": "active",
            "enrollment_type":  "student",
            "state[]":          ["available"],
            "per_page":         50,
        })
        return [c for c in courses if isinstance(c, dict) and c.get("id")]

    def get_course_modules(self, course_id: int) -> List[Dict[str, Any]]:
        """Fetch modules with item completion states for a course."""
        return self._get(
            f"{self.base_url}/courses/{course_id}/modules",
            params={"include[]": ["items", "content_details"], "per_page": 100},
        )

    def get_course_assignments(self, course_id: int) -> List[Dict[str, Any]]:
        """Fetch assignments with submission status."""
        return self._get(
            f"{self.base_url}/courses/{course_id}/assignments",
            params={"include[]": ["submission"], "per_page": 100},
        )

    def get_course_quizzes(self, course_id: int) -> List[Dict[str, Any]]:
        """Fetch quizzes with submission info."""
        return self._get(
            f"{self.base_url}/courses/{course_id}/quizzes",
            params={"per_page": 100},
        )

    def get_quiz_submissions(self, course_id: int, quiz_id: int) -> List[Dict[str, Any]]:
        """Fetch user quiz submissions."""
        data = self._get(
            f"{self.base_url}/courses/{course_id}/quizzes/{quiz_id}/submissions",
        )
        if isinstance(data, dict):
            return data.get("quiz_submissions", [])
        return data

    def get_course_progress(self, course_id: int) -> Dict[str, Any]:
        """Get overall course completion percentage."""
        data = self._get(f"{self.base_url}/courses/{course_id}/completion_summary")
        if isinstance(data, dict):
            return data
        return {}

    # ─── Core Sync Logic ───────────────────────────────────────────────────────

    def sync_completed_items(self) -> Dict[str, Any]:
        """
        Full sync: scan all courses for newly completed modules/quizzes/assignments.
        Awards XP for each new completion. Returns a summary dict.

        Follows Canvas API policy:
        - Uses per_page=100 to minimize request count
        - Stores completed item IDs locally to avoid duplicate XP
        - Respects X-Rate-Limit-Delay on 429 responses
        """
        if not self.token:
            return {"error": "CANVAS_API_TOKEN not set. See .env file.", "xp_earned": 0}

        courses = self.get_active_courses()
        if not courses:
            return {"error": "No active courses found or token invalid.", "xp_earned": 0}

        total_new_xp       = 0
        total_int_gained   = 0
        total_agi_gained   = 0
        total_wil_gained   = 0
        new_completions    = []
        verified_courses   = []

        # Get current player state & streak days
        streak_days = 0
        try:
            from engine.database import get_state
            st = get_state()
            streak_days = st.get("streak_days", 0) if st else 0
        except Exception:
            streak_days = 0

        # ── Local SQLite tracking ──────────────────────────────────────────────
        conn = None
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                self._init_canvas_table(conn)
            except Exception as e:
                print(f"[Canvas] SQLite init warning: {e}")
                conn = None

        # ── Neon PostgreSQL tracking (serverless) ─────────────────────────────
        neon_conn = None
        if IS_SERVERLESS and DATABASE_URL:
            try:
                import psycopg2
                neon_conn = psycopg2.connect(DATABASE_URL)
                with neon_conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS pg_canvas_completed_items (
                            canvas_item_id  TEXT PRIMARY KEY,
                            item_title      TEXT NOT NULL,
                            course_id       INTEGER NOT NULL,
                            course_name     TEXT,
                            item_type       TEXT,
                            xp_awarded      INTEGER DEFAULT 0,
                            completed_at    TEXT DEFAULT now()
                        );
                    """)
                neon_conn.commit()
            except Exception as e:
                print(f"[Canvas] Neon init warning: {e}")
                neon_conn = None

        def _already_tracked(item_id: str) -> bool:
            """Check if item was already awarded XP."""
            if conn:
                cur = conn.execute(
                    "SELECT 1 FROM canvas_completed_items WHERE canvas_item_id = ?",
                    (item_id,)
                )
                if cur.fetchone():
                    return True
            if neon_conn:
                with neon_conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM pg_canvas_completed_items WHERE canvas_item_id = %s",
                        (item_id,)
                    )
                    if cur.fetchone():
                        return True
            return False

        def _record_completion(item_id: str, title: str, cid: int, cname: str, itype: str, xp: int):
            ts = datetime.now().isoformat()
            if conn:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO canvas_completed_items "
                        "(canvas_item_id, item_title, course_id, course_name, item_type, xp_awarded, completed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (item_id, title, cid, cname, itype, xp, ts)
                    )
                    conn.commit()
                except Exception:
                    pass
            if neon_conn:
                try:
                    with neon_conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pg_canvas_completed_items "
                            "(canvas_item_id, item_title, course_id, course_name, item_type, xp_awarded, completed_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                            (item_id, title, cid, cname, itype, xp, ts)
                        )
                    neon_conn.commit()
                except Exception:
                    pass

        global _CURRENT_SYNC_PROGRESS
        _CURRENT_SYNC_PROGRESS["is_syncing"] = True
        _CURRENT_SYNC_PROGRESS["total_courses"] = len(courses)
        _CURRENT_SYNC_PROGRESS["courses_scanned"] = 0
        _CURRENT_SYNC_PROGRESS["pct"] = 5
        _CURRENT_SYNC_PROGRESS["status_message"] = "Initializing Canvas API Scan..."
        _CURRENT_SYNC_PROGRESS["updated_at"] = datetime.now().isoformat()

        # ── Iterate Courses ────────────────────────────────────────────────────
        for idx, course in enumerate(courses):
            course_id   = course.get("id")
            course_name = course.get("name", "Unknown Course")
            course_code = course.get("course_code", "")

            _CURRENT_SYNC_PROGRESS["courses_scanned"] = idx + 1
            _CURRENT_SYNC_PROGRESS["current_course_name"] = course_name
            _CURRENT_SYNC_PROGRESS["pct"] = int(round((idx + 1) / len(courses) * 90))
            _CURRENT_SYNC_PROGRESS["status_message"] = f"Scanning [{idx+1}/{len(courses)}]: {course_name[:35]}"
            _CURRENT_SYNC_PROGRESS["updated_at"] = datetime.now().isoformat()

            # Cache course info
            if conn:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO canvas_courses_cache "
                        "(course_id, course_name, course_code, last_synced) VALUES (?, ?, ?, ?)",
                        (course_id, course_name, course_code, datetime.now().isoformat())
                    )
                    conn.commit()
                except Exception:
                    pass

            course_xp = 0

            # 1. Module items (videos, pages, assignments embedded in modules)
            modules = self.get_course_modules(course_id)
            for module in modules:
                items = module.get("items", [])
                mod_items_req = [it for it in items if it.get("completion_requirement")]
                mod_items_done = [it for it in mod_items_req if it.get("completion_requirement", {}).get("completed")]
                
                # Check for Full Week Module Wipe Bonus (100% completed)
                module_wipe_bonus = len(mod_items_req) > 0 and len(mod_items_req) == len(mod_items_done)
                mod_id = str(module.get("id", ""))
                if module_wipe_bonus and mod_id and not _already_tracked(f"modwipe_{mod_id}"):
                    wipe_xp = int(round(100 * (1.0 + min(1.0, streak_days / 30.0))))
                    _record_completion(
                        f"modwipe_{mod_id}", f"👑 FULL MODULE WIPE: {module.get('name', 'Module')}",
                        course_id, course_name, "ModuleWipe", wipe_xp
                    )
                    total_new_xp += wipe_xp
                    course_xp += wipe_xp
                    total_wil_gained += 5
                    new_completions.append({
                        "course": course_name,
                        "item": f"👑 MODULE WIPE: {module.get('name', 'Module')}",
                        "type": "ModuleWipe",
                        "xp": wipe_xp
                    })
                    print(f"[Canvas 👑 WIPE] {module.get('name', '')[:50]} | +{wipe_xp} XP | +5 WIL")

                for item in items:
                    item_id    = str(item.get("id", ""))
                    item_title = item.get("title", "Unknown")
                    item_type  = item.get("type", "Page")
                    req        = item.get("completion_requirement", {})
                    completed  = req.get("completed", False)

                    if completed and item_id and not _already_tracked(f"module_{item_id}"):
                        xp, stat_gains = calculate_canvas_xp(
                            item_type=item_type,
                            title=item_title,
                            streak_days=streak_days
                        )
                        _record_completion(
                            f"module_{item_id}", item_title,
                            course_id, course_name, item_type, xp
                        )
                        total_new_xp += xp
                        course_xp    += xp
                        total_int_gained += stat_gains.get("INT", 0)
                        total_agi_gained += stat_gains.get("AGI", 0)
                        total_wil_gained += stat_gains.get("WIL", 0)
                        new_completions.append({
                            "course":   course_name,
                            "item":     item_title,
                            "type":     item_type,
                            "xp":       xp,
                            "stats":    stat_gains
                        })
                        print(f"[Canvas ✓] {item_title[:60]} | {course_code} | +{xp} XP | {stat_gains}")

            # 2. Standalone Quiz submissions
            quizzes = self.get_course_quizzes(course_id)
            for quiz in quizzes:
                quiz_id    = quiz.get("id")
                quiz_title = quiz.get("title", "Quiz")
                key        = f"quiz_{quiz_id}"

                if not quiz_id or _already_tracked(key):
                    continue

                submissions = self.get_quiz_submissions(course_id, quiz_id)
                best_sub = None
                for s in submissions:
                    if s.get("workflow_state") in ("complete", "pending_review", "graded"):
                        best_sub = s
                        break
                if best_sub:
                    score = best_sub.get("score")
                    max_score = quiz.get("points_possible")
                    sub_at = best_sub.get("submitted_at")
                    due_at = quiz.get("due_at")

                    xp, stat_gains = calculate_canvas_xp(
                        item_type="Quiz",
                        title=quiz_title,
                        score=score,
                        max_score=max_score,
                        submitted_at=sub_at,
                        due_at=due_at,
                        streak_days=streak_days
                    )
                    _record_completion(key, quiz_title, course_id, course_name, "Quiz", xp)
                    total_new_xp += xp
                    course_xp    += xp
                    total_int_gained += stat_gains.get("INT", 0)
                    total_agi_gained += stat_gains.get("AGI", 0)
                    total_wil_gained += stat_gains.get("WIL", 0)
                    new_completions.append({
                        "course": course_name, "item": quiz_title,
                        "type": "Quiz", "xp": xp, "stats": stat_gains
                    })
                    print(f"[Canvas ✓] Quiz: {quiz_title[:60]} | +{xp} XP | {stat_gains}")

            # 3. Assignments (standalone submissions)
            assignments = self.get_course_assignments(course_id)
            for asgn in assignments:
                asgn_id  = asgn.get("id")
                title    = asgn.get("name", "Assignment")
                key      = f"asgn_{asgn_id}"
                sub      = asgn.get("submission", {})
                wf_state = sub.get("workflow_state", "")

                if not asgn_id or _already_tracked(key):
                    continue

                if wf_state in ("submitted", "graded", "pending_review"):
                    xp, stat_gains = calculate_canvas_xp(
                        item_type="Assignment",
                        title=title,
                        score=sub.get("score"),
                        max_score=asgn.get("points_possible"),
                        submitted_at=sub.get("submitted_at"),
                        due_at=asgn.get("due_at"),
                        streak_days=streak_days
                    )
                    _record_completion(key, title, course_id, course_name, "Assignment", xp)
                    total_new_xp += xp
                    course_xp    += xp
                    total_int_gained += stat_gains.get("INT", 0)
                    total_agi_gained += stat_gains.get("AGI", 0)
                    total_wil_gained += stat_gains.get("WIL", 0)
                    new_completions.append({
                        "course": course_name, "item": title,
                        "type": "Assignment", "xp": xp, "stats": stat_gains
                    })
                    print(f"[Canvas ✓] Assignment: {title[:60]} | +{xp} XP | {stat_gains}")

            if course_xp:
                verified_courses.append({
                    "name": course_name,
                    "code": course_code,
                    "xp_earned": course_xp,
                })

        # ── Award total XP and Stat Boosts to player ───────────────────────────
        if total_new_xp > 0:
            try:
                from engine.database import add_xp, get_state, save_state
                add_xp(total_new_xp)
                state = get_state()
                if state:
                    state["int"] = state.get("int", 10) + total_int_gained
                    state["agi"] = state.get("agi", 10) + total_agi_gained
                    state["wil"] = state.get("wil", 10) + total_wil_gained
                    save_state(state)
                print(f"[Canvas] 🎉 Total XP awarded: +{total_new_xp} | STAT BOOSTS: +{total_int_gained} INT, +{total_agi_gained} AGI, +{total_wil_gained} WIL")
            except Exception as e:
                print(f"[Canvas] XP award error: {e}")
                if conn:
                    try:
                        conn.execute(
                            "UPDATE system_state SET xp = xp + ?, int = int + ?, agi = agi + ?, wil = wil + ? WHERE id = 1",
                            (total_new_xp, total_int_gained, total_agi_gained, total_wil_gained)
                        )
                        conn.commit()
                    except Exception:
                        pass

        if conn:
            conn.close()
        if neon_conn:
            neon_conn.close()

        _CURRENT_SYNC_PROGRESS["is_syncing"] = False
        _CURRENT_SYNC_PROGRESS["pct"] = 100
        _CURRENT_SYNC_PROGRESS["new_items_found"] = len(new_completions)
        _CURRENT_SYNC_PROGRESS["total_xp_gained"] = total_new_xp
        _CURRENT_SYNC_PROGRESS["status_message"] = f"Sync Complete! +{total_new_xp} XP Earned ({len(new_completions)} items)"
        _CURRENT_SYNC_PROGRESS["updated_at"] = datetime.now().isoformat()

        return {
            "status":            "success",
            "courses_scanned":   len(courses),
            "new_completions":   len(new_completions),
            "xp_earned":         total_new_xp,
            "completions":       new_completions,
            "courses_with_xp":   verified_courses,
            "synced_at":         datetime.now().isoformat(),
        }

    def get_completion_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve past Canvas completions from local tracking table."""
        results = []

        if self.db_path and os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path, timeout=10)
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT * FROM canvas_completed_items ORDER BY completed_at DESC LIMIT ?",
                    (limit,)
                )
                results = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception as e:
                print(f"[Canvas] History error: {e}")

        if not results and IS_SERVERLESS and DATABASE_URL:
            try:
                import psycopg2, psycopg2.extras
                conn = psycopg2.connect(DATABASE_URL)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM pg_canvas_completed_items ORDER BY completed_at DESC LIMIT %s",
                        (limit,)
                    )
                    results = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception as e:
                print(f"[Canvas] Neon history error: {e}")

        return results

    def get_courses_summary(self) -> List[Dict[str, Any]]:
        """Quick summary: course name + total XP earned from Canvas."""
        courses = self.get_active_courses()
        history = self.get_completion_history(limit=10000)

        # Map course_id -> xp
        xp_by_course: Dict[int, int] = {}
        count_by_course: Dict[int, int] = {}
        for item in history:
            cid = item.get("course_id", 0)
            xp_by_course[cid]    = xp_by_course.get(cid, 0) + (item.get("xp_awarded") or 0)
            count_by_course[cid] = count_by_course.get(cid, 0) + 1

        summary = []
        for c in courses:
            cid = c.get("id", 0)
            summary.append({
                "id":            cid,
                "name":          c.get("name", ""),
                "course_code":   c.get("course_code", ""),
                "xp_earned":     xp_by_course.get(cid, 0),
                "items_done":    count_by_course.get(cid, 0),
            })
        return summary


# ── CLI Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("  ANTIGRAVITY — Canvas LMS Sync (lms.vitonline.in)")
    print("=" * 60)

    token = os.getenv("CANVAS_API_TOKEN", "")
    if not token:
        print("\n❌ ERROR: CANVAS_API_TOKEN not set.")
        print("   1. Log in to https://lms.vitonline.in")
        print("   2. Account → Settings → Approved Integrations → + New Access Token")
        print("   3. Set purpose as 'Antigravity Engine'")
        print("   4. Add to .env:  CANVAS_API_TOKEN=your_token_here")
        sys.exit(1)

    syncer = CanvasLMSSync()

    print("\n[1] Verifying API token…")
    syncer.check_token()

    print("\n[2] Fetching active courses…")
    courses = syncer.get_active_courses()
    if courses:
        print(f"  Found {len(courses)} active course(s):")
        for c in courses:
            print(f"    [{c.get('id')}] {c.get('name')} ({c.get('course_code', '')})")
    else:
        print("  No active courses found.")

    print("\n[3] Running full progress sync…")
    result = syncer.sync_completed_items()
    print(json.dumps(result, indent=2))
