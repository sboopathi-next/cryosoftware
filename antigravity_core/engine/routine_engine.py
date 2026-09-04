"""
routine_engine.py — Circadian Cadence & Exponential Punctuality Engine
Manages daily routine transition milestones, calculates time drift & exponential XP decay rewards,
and updates player state attributes in Antigravity OS.
"""

import math
import sqlite3
import datetime
from typing import Dict, Any, List, Optional

from engine.database import (
    get_db_connection,
    IS_SERVERLESS,
    get_state,
    save_state,
    _DB_WRITE_LOCK,
    log_activity_file
)

DEFAULT_MILESTONES = [
    ("wake", "Wake Up Protocol", "06:45", "wil", 3),
    ("reset", "20-Min Reset & Meditation", "07:00", "stc", 2),
    ("cook", "Cook & Nutrition", "07:20", "heart", 2),
    ("gym", "Gym & Physical Conditioning", "08:30", "str", 5),
    ("work", "Office Work Focus Block", "11:30", "agi", 4),
    ("study", "Career / MSc Study Block", "18:30", "int", 5),
    ("prep", "Shutdown & Plan Tomorrow", "22:00", "wil", 2),
    ("sleep", "Bedtime / System Stop", "23:00", "cognitive_energy", 100)
]

def init_routine_tables():
    """Initializes routine_milestones and routine_triggers tables if they do not exist."""
    if IS_SERVERLESS:
        return
    with _DB_WRITE_LOCK:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routine_milestones (
                id TEXT PRIMARY KEY,
                milestone_name TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                attribute_boost TEXT NOT NULL,
                boost_value INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routine_triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                milestone_id TEXT NOT NULL,
                scheduled_timestamp TEXT NOT NULL,
                triggered_timestamp TEXT NOT NULL,
                delay_hours REAL NOT NULL,
                xp_awarded INTEGER NOT NULL,
                log_date TEXT DEFAULT (date('now', 'localtime')),
                FOREIGN KEY(milestone_id) REFERENCES routine_milestones(id)
            )
        """)
        # Pre-seed milestones if empty
        cursor.execute("SELECT COUNT(*) FROM routine_milestones")
        count = cursor.fetchone()[0]
        if count == 0:
            for id_, name, time_str, attr, boost in DEFAULT_MILESTONES:
                cursor.execute("""
                    INSERT OR IGNORE INTO routine_milestones (id, milestone_name, scheduled_time, attribute_boost, boost_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (id_, name, time_str, attr, boost))
        conn.commit()
        conn.close()

# Ensure tables exist on module import
init_routine_tables()


class RoutineEngine:
    """Circadian Routine & Punctuality Reward Engine."""

    @staticmethod
    def calculate_punctuality_xp(delay_hours: float) -> int:
        """
        Calculates XP payout based on delay hours using base-3 exponential decay:
        - delay < 1h: 2 * 3^5 = 486 XP
        - 1h <= delay < 2h: 2 * 3^4 = 162 XP
        - 2h <= delay < 3h: 2 * 3^3 = 54 XP
        - 3h <= delay < 4h: 2 * 3^2 = 18 XP
        - 4h <= delay < 5h: 2 * 3^1 = 6 XP
        - delay >= 5h: 2 * 3^0 = 2 XP (floor)
        """
        if delay_hours < 0.0:
            delay_hours = 0.0

        tier = int(math.floor(delay_hours))
        if tier >= 5:
            return 2
        return 2 * (3 ** (5 - tier))

    def get_status(self) -> Dict[str, Any]:
        """
        Returns status of all 8 routine milestones for today,
        including triggered status, current potential XP yield, delay hours, and overall synchrony %.
        """
        init_routine_tables()
        now = datetime.datetime.now()
        today_date = now.strftime("%Y-%m-%d")

        # Fetch today's triggers from DB (SQLite local or Neon serverless)
        triggered_map = {}
        if IS_SERVERLESS:
            try:
                from engine.neon_db import neon_get_routine_triggers_today
                triggered_map = neon_get_routine_triggers_today(today_date)
            except Exception as e:
                print(f"[RoutineEngine] Neon trigger fetch error: {e}")
        else:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM routine_triggers WHERE log_date = ?", (today_date,))
            rows = cursor.fetchall()
            conn.close()
            for r in rows:
                triggered_map[r["milestone_id"]] = dict(r)

        milestones_list = []
        total_xp_minted = 0
        completed_count = 0
        next_impending = None
        min_seconds_until_next = float("inf")

        for id_, name, sched_time_str, attr, boost in DEFAULT_MILESTONES:
            hour, minute = map(int, sched_time_str.split(":"))
            sched_dt = datetime.datetime.combine(now.date(), datetime.time(hour, minute))
            delay_sec = (now - sched_dt).total_seconds()

            if delay_sec < -900:
                # Early
                delay_hours = 0.0
            elif delay_sec < 0:
                # Within 15m early window
                delay_hours = 0.0
            else:
                delay_hours = delay_sec / 3600.0

            potential_xp = self.calculate_punctuality_xp(delay_hours)
            is_triggered = id_ in triggered_map
            trigger_data = triggered_map.get(id_)

            if is_triggered:
                completed_count += 1
                total_xp_minted += trigger_data.get("xp_awarded", 0)

            # Find next impending milestone (first uncompleted milestone)
            if not is_triggered and next_impending is None:
                secs_diff = (sched_dt - now).total_seconds()
                next_impending = {
                    "id": id_,
                    "name": name,
                    "scheduled_time": sched_time_str,
                    "attr": attr,
                    "boost": boost,
                    "potential_xp": potential_xp,
                    "seconds_remaining": max(0, int(secs_diff)) if secs_diff > 0 else 0
                }

            milestones_list.append({
                "id": id_,
                "name": name,
                "scheduled_time": sched_time_str,
                "attribute_boost": attr,
                "boost_value": boost,
                "is_triggered": is_triggered,
                "triggered_data": trigger_data,
                "current_delay_hours": round(delay_hours, 2),
                "potential_xp": potential_xp
            })

        # Calculate synchrony %
        max_possible_xp = 486 * 8 # 3,888 XP
        synchrony_pct = round((total_xp_minted / max_possible_xp) * 100, 1) if completed_count > 0 else 0.0

        state = get_state() or {}
        attrs = state.get("attributes", {})

        return {
            "status": "SUCCESS",
            "date": today_date,
            "total_xp_minted": total_xp_minted,
            "completed_count": completed_count,
            "total_milestones": len(DEFAULT_MILESTONES),
            "synchrony_pct": synchrony_pct,
            "next_impending": next_impending or (milestones_list[0] if milestones_list else None),
            "milestones": milestones_list,
            "cumulative_attributes": {
                "WIL": attrs.get("WIL", 10),
                "STC": attrs.get("STC", 10),
                "HRT": attrs.get("HRT", 10),
                "STR": attrs.get("STR", 10),
                "AGI": attrs.get("AGI", 10),
                "INT": attrs.get("INT", 10)
            }
        }

    def trigger_milestone(self, milestone_id: str) -> Dict[str, Any]:
        """
        Triggers a routine milestone, calculates delay & XP payout, updates player DB state,
        and logs the trigger event.
        """
        init_routine_tables()
        now = datetime.datetime.now()
        today_date = now.strftime("%Y-%m-%d")

        # Check milestone definition
        ms_def = next((m for m in DEFAULT_MILESTONES if m[0] == milestone_id), None)
        if not ms_def:
            return {"status": "NOT_FOUND", "message": f"Milestone '{milestone_id}' does not exist."}

        id_, name, sched_time_str, attr, boost = ms_def

        # Check if already triggered today
        if IS_SERVERLESS:
            try:
                from engine.neon_db import neon_check_routine_trigger_exists
                if neon_check_routine_trigger_exists(milestone_id, today_date):
                    return {
                        "status": "REJECTED",
                        "message": f"Milestone '{name}' has already been triggered today!"
                    }
            except Exception as e:
                print(f"[RoutineEngine] Neon duplicate check error: {e}")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM routine_triggers WHERE milestone_id = ? AND log_date = ?", (milestone_id, today_date))
            existing = cursor.fetchone()
            conn.close()
            if existing:
                return {
                    "status": "REJECTED",
                    "message": f"Milestone '{name}' has already been triggered today!"
                }

        # Calculate scheduled datetime
        hour, minute = map(int, sched_time_str.split(":"))
        sched_dt = datetime.datetime.combine(now.date(), datetime.time(hour, minute))
        delay_sec = (now - sched_dt).total_seconds()

        # Calculate delay hours (0.0 if on or before scheduled time)
        if delay_sec <= 0:
            delay_hours = 0.0
        else:
            delay_hours = delay_sec / 3600.0

        xp_earned = self.calculate_punctuality_xp(delay_hours)

        # Save trigger to DB
        if IS_SERVERLESS:
            try:
                from engine.neon_db import neon_save_routine_trigger
                neon_save_routine_trigger(
                    milestone_id=milestone_id,
                    milestone_name=name,
                    scheduled_ts=sched_dt.isoformat(),
                    triggered_ts=now.isoformat(),
                    delay_hours=round(delay_hours, 2),
                    xp_awarded=xp_earned,
                    log_date=today_date
                )
            except Exception as e:
                print(f"[RoutineEngine] Neon trigger save error: {e}")
        else:
            with _DB_WRITE_LOCK:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO routine_triggers (milestone_id, scheduled_timestamp, triggered_timestamp, delay_hours, xp_awarded, log_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (milestone_id, sched_dt.isoformat(), now.isoformat(), round(delay_hours, 2), xp_earned, today_date))
                conn.commit()
                conn.close()

        # Update Player State
        state = get_state() or {}
        state["xp"] = state.get("xp", 0) + xp_earned
        attrs = state.get("attributes", {})

        attr_key_map = {
            "wil": "WIL",
            "stc": "STC",
            "heart": "HRT",
            "str": "STR",
            "agi": "AGI",
            "int": "INT"
        }

        if attr == "cognitive_energy":
            state["energy"] = 100.0
            stat_msg = "Cognitive Energy Restored to 100%"
        else:
            mapped_key = attr_key_map.get(attr, attr.upper())
            attrs[mapped_key] = attrs.get(mapped_key, 10) + boost
            state["attributes"] = attrs
            stat_msg = f"+{boost} {mapped_key}"

        save_state(state)

        log_activity_file(
            f"Circadian Milestone Trigger: {name}",
            f"Triggered '{name}' with {round(delay_hours, 2)}h delay. Minted +{xp_earned} XP ({stat_msg})."
        )

        return {
            "status": "SUCCESS",
            "milestone_id": milestone_id,
            "milestone_name": name,
            "scheduled_time": sched_time_str,
            "delay_hours": round(delay_hours, 2),
            "xp_awarded": xp_earned,
            "stat_boost": stat_msg,
            "message": f"Milestone '{name}' triggered! Minted +{xp_earned} XP ({stat_msg})."
        }
