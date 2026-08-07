"""
sync.py — Offline/Online Sync Engine for Antigravity Core
==========================================================
Strategy:
  - All writes go to LOCAL first (state.json + sync_log.csv as a changelog).
  - A background sync pushes pending local changes to Neon DB when online.
  - On load, if Neon is reachable, we merge: Neon wins if its updated_at
    is newer, otherwise local wins (last-write-wins per field by timestamp).
  - The CSV changelog (sync_log.csv) records every mutation so nothing is
    lost even if the app is offline for days.
  - On read-only serverless environments (Vercel), all file-system writes
    are skipped and Neon DB is used as the sole persistent storage.
"""

import json
import os
import csv
import time
from datetime import datetime, timezone

try:
    from config import IS_SERVERLESS
except ImportError:
    IS_SERVERLESS = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_LOG_CSV = os.path.join(BASE_DIR, "sync_log.csv")
SYNC_LOCK_FILE = os.path.join(BASE_DIR, ".sync_lock")

CSV_FIELDS = ["timestamp_utc", "user_id", "field", "old_value", "new_value", "synced_to_db"]


# ──────────────────────────────────────────────
# CSV Changelog helpers
# ──────────────────────────────────────────────

def _ensure_csv():
    if IS_SERVERLESS:
        return  # No file writes in serverless mode
    if not os.path.exists(SYNC_LOG_CSV):
        with open(SYNC_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def log_change_to_csv(user_id: str, field: str, old_value, new_value, synced: bool = False):
    """Append a single field change to the sync log CSV."""
    if IS_SERVERLESS:
        return  # No file writes in serverless mode
    _ensure_csv()
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "field": field,
        "old_value": json.dumps(old_value, default=str),
        "new_value": json.dumps(new_value, default=str),
        "synced_to_db": "1" if synced else "0",
    }
    with open(SYNC_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(row)


def log_state_diff_to_csv(user_id: str, old_state: dict, new_state: dict, synced: bool = False):
    """Diff two states and log each changed field to CSV."""
    if IS_SERVERLESS:
        return  # No file writes in serverless mode
    _ensure_csv()
    rows = []
    all_keys = set(list(old_state.keys()) + list(new_state.keys()))
    now = datetime.now(timezone.utc).isoformat()
    for key in all_keys:
        ov = old_state.get(key)
        nv = new_state.get(key)
        if ov != nv:
            rows.append({
                "timestamp_utc": now,
                "user_id": user_id,
                "field": key,
                "old_value": json.dumps(ov, default=str),
                "new_value": json.dumps(nv, default=str),
                "synced_to_db": "1" if synced else "0",
            })
    if rows:
        with open(SYNC_LOG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerows(rows)


def get_unsynced_rows() -> list:
    """Return all CSV rows that have not yet been pushed to Neon DB."""
    _ensure_csv()
    unsynced = []
    with open(SYNC_LOG_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("synced_to_db") == "0":
                unsynced.append(row)
    return unsynced


def mark_all_synced():
    """Rewrite the CSV marking all rows as synced."""
    if IS_SERVERLESS:
        return  # No file writes in serverless mode
    _ensure_csv()
    rows = []
    with open(SYNC_LOG_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["synced_to_db"] = "1"
            rows.append(row)
    with open(SYNC_LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ──────────────────────────────────────────────
# Online check (Asynchronous & Cached)
# ──────────────────────────────────────────────

import threading
import queue

_ONLINE_STATUS = True
_ONLINE_CHECK_THREAD = None
_NEON_WRITE_QUEUE = queue.Queue()
_NEON_WRITE_THREAD = None

def _background_online_checker():
    global _ONLINE_STATUS
    while True:
        try:
            from config import DATABASE_URL
            if not DATABASE_URL:
                _ONLINE_STATUS = False
            else:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
                conn.close()
                _ONLINE_STATUS = True
        except Exception:
            _ONLINE_STATUS = False
        time.sleep(20)

def start_online_checker():
    global _ONLINE_CHECK_THREAD
    if _ONLINE_CHECK_THREAD is None:
        _ONLINE_CHECK_THREAD = threading.Thread(
            target=_background_online_checker,
            name="OnlineCheckerThread",
            daemon=True
        )
        _ONLINE_CHECK_THREAD.start()

def is_online() -> bool:
    """Returns True if Neon DB is reachable (instantly reads cached status)."""
    start_online_checker()
    return _ONLINE_STATUS

# ──────────────────────────────────────────────
# Background Neon PG Writer Queue (Producer-Consumer)
# ──────────────────────────────────────────────

def _background_neon_writer():
    while True:
        state = _NEON_WRITE_QUEUE.get()
        try:
            if is_online():
                from state import save_state_to_db
                save_state_to_db(state)
                # Sync any other pending local modifications recorded in CSV
                push_pending_to_neon()
        except Exception as e:
            print(f"[Sync] Asynchronous Neon write failed: {e}")
        finally:
            _NEON_WRITE_QUEUE.task_done()

def start_neon_writer():
    global _NEON_WRITE_THREAD
    if _NEON_WRITE_THREAD is None:
        _NEON_WRITE_THREAD = threading.Thread(
            target=_background_neon_writer,
            name="NeonWriterThread",
            daemon=True
        )
        _NEON_WRITE_THREAD.start()

def queue_neon_write(state: dict):
    start_neon_writer()
    _NEON_WRITE_QUEUE.put(state)


# ──────────────────────────────────────────────
# Merge logic (last-write-wins, Neon wins on tie)
# ──────────────────────────────────────────────

def merge_states(local_state: dict, remote_state: dict) -> dict:
    """
    Merge local and remote state.
    Strategy: field-level merge using 'last_update' date timestamp.
    If one state has a newer 'last_update' date string (e.g. 2026-08-08 > 2026-08-07),
    the daily completion flags of the NEWER date MUST prevail without merging old completed booleans.
    """
    local_ts = local_state.get("last_update", "")
    remote_ts = remote_state.get("last_update", "")

    if local_ts > remote_ts:
        # Local state is for a newer date than remote DB
        merged = {**remote_state, **local_state}
        merged["last_update"] = local_ts
    elif remote_ts > local_ts:
        # Remote DB state is for a newer date than local state
        merged = {**local_state, **remote_state}
        merged["last_update"] = remote_ts
    else:
        # Both are on the exact same date — perform same-day union merge
        merged = {**remote_state, **local_state}
        merged["last_update"] = local_ts or remote_ts
        merged["completed_quests_today"] = list(set(
            local_state.get("completed_quests_today", []) +
            remote_state.get("completed_quests_today", [])
        ))
        merged["gym_completed"] = bool(local_state.get("gym_completed") or remote_state.get("gym_completed"))
        merged["study_completed"] = bool(local_state.get("study_completed") or remote_state.get("study_completed"))
        merged["leetcode_completed"] = bool(local_state.get("leetcode_completed") or remote_state.get("leetcode_completed"))
        merged["cooking_completed"] = bool(local_state.get("cooking_completed") or remote_state.get("cooking_completed"))
        merged["nopmo_completed"] = bool(local_state.get("nopmo_completed") or remote_state.get("nopmo_completed"))
        merged["reading_completed"] = bool(local_state.get("reading_completed") or remote_state.get("reading_completed"))
        merged["english_completed"] = bool(local_state.get("english_completed") or remote_state.get("english_completed"))
        merged["claimed_rewards_today"] = list(set(
            local_state.get("claimed_rewards_today", []) +
            remote_state.get("claimed_rewards_today", [])
        ))

    # Attributes & streak: max values
    for key in ("streak_days", "continuous_study_days", "willpower", "str", "int", "agi", "wil", "heart", "stoic"):
        local_val = local_state.get(key, 0)
        remote_val = remote_state.get(key, 0)
        merged[key] = max(local_val, remote_val)

    # XP & Level: if same date, take max. If date differs, take the newer date's values to avoid overriding penalties/resets.
    if local_ts == remote_ts:
        merged["level"] = max(local_state.get("level", 1), remote_state.get("level", 1))
        merged["xp"] = max(local_state.get("xp", 0), remote_state.get("xp", 0))
    else:
        newer_state = local_state if local_ts > remote_ts else remote_state
        merged["level"] = newer_state.get("level", 1)
        merged["xp"] = newer_state.get("xp", 0)

    # Completed syllabus items: union across all subjects
    local_csi = local_state.get("completed_syllabus_items", {})
    remote_csi = remote_state.get("completed_syllabus_items", {})
    merged_csi = {}
    all_subjects = set(list(local_csi.keys()) + list(remote_csi.keys()))
    for subj in all_subjects:
        merged_csi[subj] = list(set(
            local_csi.get(subj, []) + remote_csi.get(subj, [])
        ))
    merged["completed_syllabus_items"] = merged_csi

    # Syllabus bonuses: union
    local_bonuses = local_state.get("syllabus_bonuses", {})
    remote_bonuses = remote_state.get("syllabus_bonuses", {})
    merged["syllabus_bonuses"] = {**local_bonuses, **remote_bonuses}

    # Active subject: newer timestamp wins
    newer_state = local_state if local_ts > remote_ts else (remote_state if remote_ts > local_ts else remote_state)
    merged["active_subject"] = newer_state.get("active_subject", local_state.get("active_subject"))
    merged["active_quests"] = newer_state.get("active_quests", local_state.get("active_quests"))
    merged["daily_telemetry"] = newer_state.get("daily_telemetry", local_state.get("daily_telemetry"))

    return merged


# ──────────────────────────────────────────────
# Push unsynced local changes to Neon DB
# ──────────────────────────────────────────────

def push_pending_to_neon() -> bool:
    """
    Attempts to sync any unsynced local state to Neon DB.
    Returns True if sync succeeded, False if offline or failed.
    """
    if not is_online():
        return False

    unsynced = get_unsynced_rows()
    if not unsynced:
        return True  # Nothing pending

    try:
        from state import load_state_file, save_state_to_db, load_state_from_db
        local_state = load_state_file()
        if local_state is None:
            return False

        # Load remote state and merge before pushing
        try:
            remote_state = load_state_from_db()
            merged = merge_states(local_state, remote_state)
        except Exception:
            merged = local_state

        save_state_to_db(merged)
        mark_all_synced()
        print(f"[Sync] Pushed {len(unsynced)} pending changes to Neon DB.")
        return True
    except Exception as e:
        print(f"[Sync] Failed to push pending changes: {e}")
        return False


# ──────────────────────────────────────────────
# Main sync: load with merge
# ──────────────────────────────────────────────

def sync_load_state() -> dict:
    """
    Load state with online/offline sync:
    1. Load local state.json (always available).
    2. If online, load Neon state, merge, and save merged back to both.
    3. If offline, return local state and queue any unsynced changes.
    Returns the best merged state.
    """
    from state import load_state_file, save_state_file, save_state_to_db, load_state_from_db, DEFAULT_STATE

    # In serverless mode, go directly to Neon DB
    if IS_SERVERLESS:
        try:
            remote_state = load_state_from_db()
            print("[Sync] Serverless — loaded state from Neon DB.")
            return remote_state
        except Exception as e:
            print(f"[Sync] Serverless Neon load failed: {e}")
            return DEFAULT_STATE.copy()

    local_state = load_state_file()
    if local_state is None:
        local_state = DEFAULT_STATE.copy()

    if not is_online():
        print("[Sync] Offline mode — using local state.")
        return local_state

    try:
        remote_state = load_state_from_db()
        merged = merge_states(local_state, remote_state)

        # Save merged state back to both local and remote
        if merged != local_state:
            log_state_diff_to_csv(
                user_id=merged.get("user_id", "Boopathi Subramaniyan"),
                old_state=local_state,
                new_state=merged,
                synced=True,
            )
        save_state_file(merged)
        queue_neon_write(merged)
        print("[Sync] Online — state merged and synced.")
        return merged
    except Exception as e:
        print(f"[Sync] Online merge failed, using local state. Error: {e}")
        return local_state


def sync_save_state(state: dict, old_state: dict = None):
    """
    Save state with sync:
    1. Always write to local state.json immediately.
    2. Log the diff to sync_log.csv.
    3. Try to push to Neon DB. If offline, mark CSV rows as unsynced (pending).
    """
    from config import USER_PROFILE_ID
    from state import save_state_file, save_state_to_db

    # Serverless mode: write directly to Neon DB only, skip all file writes
    if IS_SERVERLESS:
        try:
            save_state_to_db(state)
        except Exception as e:
            print(f"[Sync] Serverless Neon save failed: {e}")
        return

    # Log changes to CSV
    if old_state is not None:
        online_now = is_online()
        log_state_diff_to_csv(
            user_id=USER_PROFILE_ID,
            old_state=old_state,
            new_state=state,
            synced=online_now,
        )

    # Always persist locally first
    save_state_file(state)

    # Try Neon DB (Asynchronously)
    if is_online():
        queue_neon_write(state)
    else:
        print("[Sync] Offline — state saved locally, will sync when online.")
