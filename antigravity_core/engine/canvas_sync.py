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
    from config import IS_SERVERLESS, DATABASE_URL
except ImportError:
    IS_SERVERLESS = False
    DATABASE_URL  = ""


# ── XP Weights (Canvas item types) ────────────────────────────────────────────
XP_VIDEO_PAGE    = 25   # Watching a lecture video / reading a page
XP_QUIZ          = 150  # Completing a weekly quiz
XP_ASSIGNMENT    = 300  # Submitting a graded assignment / CAT
XP_DISCUSSION    = 50   # Discussion participation
XP_CAT_EXAM      = 500  # CAT exam / major evaluation


def _classify_xp(item_title: str, item_type: str) -> int:
    """Return XP based on item title keywords and Canvas item type."""
    title_upper = item_title.upper()
    if any(k in title_upper for k in ("CAT", "CONTINUOUS ASSESSMENT", "FINAL EXAM", "END TERM")):
        return XP_CAT_EXAM
    if any(k in title_upper for k in ("ASSIGNMENT", "PROJECT", "SUBMISSION")):
        return XP_ASSIGNMENT
    if any(k in title_upper for k in ("QUIZ", "TEST", "MCQ")):
        return XP_QUIZ
    if any(k in title_upper for k in ("DISCUSSION", "FORUM", "INTERACT")):
        return XP_DISCUSSION
    if item_type in ("Quiz", "Assignment"):
        return XP_QUIZ
    return XP_VIDEO_PAGE  # default: lecture video / page


class CanvasLMSSync:
    """
    Full Canvas LMS REST API client for lms.vitonline.in.
    Follows Canvas API pagination (Link header) and respects rate limits.
    """

    CANVAS_DOMAIN = "lms.vitonline.in"

    def __init__(self, token: Optional[str] = None, domain: Optional[str] = None):
        self.domain   = domain or os.getenv("CANVAS_DOMAIN", self.CANVAS_DOMAIN)
        self.base_url = f"https://{self.domain}/api/v1"
        self.token    = token or os.getenv("CANVAS_API_TOKEN", "")
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
        new_completions    = []
        verified_courses   = []

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

        # ── Iterate Courses ────────────────────────────────────────────────────
        for course in courses:
            course_id   = course.get("id")
            course_name = course.get("name", "Unknown Course")
            course_code = course.get("course_code", "")

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
                for item in items:
                    item_id    = str(item.get("id", ""))
                    item_title = item.get("title", "Unknown")
                    item_type  = item.get("type", "Page")
                    req        = item.get("completion_requirement", {})
                    completed  = req.get("completed", False)

                    if completed and item_id and not _already_tracked(f"module_{item_id}"):
                        xp = _classify_xp(item_title, item_type)
                        _record_completion(
                            f"module_{item_id}", item_title,
                            course_id, course_name, item_type, xp
                        )
                        total_new_xp += xp
                        course_xp    += xp
                        new_completions.append({
                            "course":   course_name,
                            "item":     item_title,
                            "type":     item_type,
                            "xp":       xp,
                        })
                        print(f"[Canvas ✓] {item_title[:60]} | {course_code} | +{xp} XP")

            # 2. Standalone Quiz submissions
            quizzes = self.get_course_quizzes(course_id)
            for quiz in quizzes:
                quiz_id    = quiz.get("id")
                quiz_title = quiz.get("title", "Quiz")
                key        = f"quiz_{quiz_id}"

                if not quiz_id or _already_tracked(key):
                    continue

                submissions = self.get_quiz_submissions(course_id, quiz_id)
                submitted   = any(
                    s.get("workflow_state") in ("complete", "pending_review", "graded")
                    for s in submissions
                )
                if submitted:
                    xp = _classify_xp(quiz_title, "Quiz")
                    _record_completion(key, quiz_title, course_id, course_name, "Quiz", xp)
                    total_new_xp += xp
                    course_xp    += xp
                    new_completions.append({
                        "course": course_name, "item": quiz_title,
                        "type": "Quiz", "xp": xp,
                    })
                    print(f"[Canvas ✓] Quiz: {quiz_title[:60]} | +{xp} XP")

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
                    xp = _classify_xp(title, "Assignment")
                    _record_completion(key, title, course_id, course_name, "Assignment", xp)
                    total_new_xp += xp
                    course_xp    += xp
                    new_completions.append({
                        "course": course_name, "item": title,
                        "type": "Assignment", "xp": xp,
                    })
                    print(f"[Canvas ✓] Assignment: {title[:60]} | +{xp} XP")

            if course_xp:
                verified_courses.append({
                    "name": course_name,
                    "code": course_code,
                    "xp_earned": course_xp,
                })

        # ── Award total XP to player ───────────────────────────────────────────
        if total_new_xp > 0:
            try:
                from engine.database import add_xp, get_state, save_state, update_stat
                add_xp(total_new_xp)
                state = get_state()
                state["int"] = state.get("int", 10) + max(1, len(new_completions))
                save_state(state)
                print(f"[Canvas] 🎉 Total XP awarded: +{total_new_xp} | +{len(new_completions)} INT")
            except Exception as e:
                print(f"[Canvas] XP award error: {e}")
                # Fallback: update SQLite directly
                if conn:
                    try:
                        conn.execute(
                            "UPDATE system_state SET xp = xp + ?, int = int + ? WHERE id = 1",
                            (total_new_xp, max(1, len(new_completions)))
                        )
                        conn.commit()
                    except Exception:
                        pass

        if conn:
            conn.close()
        if neon_conn:
            neon_conn.close()

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
        history = self.get_completion_history(limit=1000)

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
