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
"""

import json
import os
import csv
import time
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_LOG_CSV = os.path.join(BASE_DIR, "sync_log.csv")
SYNC_LOCK_FILE = os.path.join(BASE_DIR, ".sync_lock")

CSV_FIELDS = ["timestamp_utc", "user_id", "field", "old_value", "new_value", "synced_to_db"]


# ──────────────────────────────────────────────
# CSV Changelog helpers
# ──────────────────────────────────────────────

def _ensure_csv():
    if not os.path.exists(SYNC_LOG_CSV):
        with open(SYNC_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def log_change_to_csv(user_id: str, field: str, old_value, new_value, synced: bool = False):
    """Append a single field change to the sync log CSV."""
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
# Online check
# ──────────────────────────────────────────────

def is_online() -> bool:
    """Returns True if Neon DB is reachable."""
    try:
        from config import DATABASE_URL
        if not DATABASE_URL:
            return False
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=4)
        conn.close()
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Merge logic (last-write-wins, Neon wins on tie)
# ──────────────────────────────────────────────

def merge_states(local_state: dict, remote_state: dict) -> dict:
    """
    Merge local and remote state.
    Strategy: field-level merge using 'last_update' timestamp.
    For non-timestamped fields, remote (Neon) wins if it differs.
    XP/level/energy are always taken as max to avoid rollbacks.
    """
    merged = dict(local_state)

    local_ts = local_state.get("last_update", "")
    remote_ts = remote_state.get("last_update", "")

    # For cumulative numeric progress fields, always take the higher value
    for key in ("xp", "level", "streak_days", "continuous_study_days", "willpower"):
        local_val = local_state.get(key, 0)
        remote_val = remote_state.get(key, 0)
        merged[key] = max(local_val, remote_val)

    # Energy: take the most recent (newer timestamp wins)
    if remote_ts >= local_ts:
        merged["energy"] = remote_state.get("energy", local_state.get("energy", 100.0))
        merged["lockout_active"] = remote_state.get("lockout_active", local_state.get("lockout_active", False))
        merged["last_update"] = remote_ts or local_ts
        # Merge completed lists (union)
        merged["completed_quests_today"] = list(set(
            local_state.get("completed_quests_today", []) +
            remote_state.get("completed_quests_today", [])
        ))
        merged["gym_completed"] = local_state.get("gym_completed") or remote_state.get("gym_completed")
        merged["cooking_completed"] = local_state.get("cooking_completed") or remote_state.get("cooking_completed")
        merged["nopmo_completed"] = local_state.get("nopmo_completed") or remote_state.get("nopmo_completed")
    else:
        # Local is newer — keep local values for daily fields
        merged["last_update"] = local_ts

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

    # Claimed rewards: union
    merged["claimed_rewards_today"] = list(set(
        local_state.get("claimed_rewards_today", []) +
        remote_state.get("claimed_rewards_today", [])
    ))

    # Active subject: remote wins if more recent
    if remote_ts >= local_ts:
        merged["active_subject"] = remote_state.get("active_subject", local_state.get("active_subject"))
        merged["active_quests"] = remote_state.get("active_quests", local_state.get("active_quests"))
        merged["daily_telemetry"] = remote_state.get("daily_telemetry", local_state.get("daily_telemetry"))

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
        save_state_to_db(merged)
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

    # Try Neon DB
    if is_online():
        try:
            save_state_to_db(state)
        except Exception as e:
            print(f"[Sync] Neon save failed, state queued locally. Error: {e}")
    else:
        print("[Sync] Offline — state saved locally, will sync when online.")
