"""
canvas_reminder.py — Smart Daily Canvas Reminder Engine
=========================================================
Fires desktop + in-app notifications at key times when today's
Canvas subject work is not done yet.

Notification Schedule (IST):
  09:00  → Morning reminder — "Today's subject: X. Start now!"
  14:00  → Afternoon nudge — "Half day gone. Still pending: X"
  20:00  → Evening warning — "3h left! X not done yet"
  23:00  → DANGER ALERT   — "LAST HOUR! Do it NOW or lose XP!"

The reminders stop as soon as the semester audit shows CLEARED
or canvas_completed_items has entries for today's target course.

How it integrates with Canvas sync:
  - canvas_sync.py scans Canvas LMS API (lms.vitonline.in) for newly
    completed modules, quizzes, and assignments every 3 hours (manual
    sync button also available).
  - When items are detected, XP is awarded and the semester audit
    marks the day CLEARED.
  - This reminder daemon checks that status and nags you until it's done.
"""

import os
import sys
import time
import sqlite3
import datetime
import threading
import subprocess

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR   = os.path.dirname(_ENGINE_DIR)
_ROOT_DIR   = os.path.dirname(_CORE_DIR)
for _p in [_ROOT_DIR, _CORE_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from engine.database import DB_PATH
except ImportError:
    DB_PATH = os.path.join(_CORE_DIR, "data", "system_solo.db")

try:
    from engine.semester_enforcer import get_today_target, get_current_week_number, CADENCE_SCHEDULE
except ImportError:
    def get_today_target(): return {}
    def get_current_week_number(d=None): return 1
    CADENCE_SCHEDULE = {}

# ── Notification levels ──────────────────────────────────────────────────────
REMINDER_SLOTS = [
    # (hour, minute, level, message_template)
    ( 9, 0,  "morning",  "📚 STUDY REMINDER — {course} (Week {week}/12)\nStart your Canvas work NOW. Quiz + 1 concept today!"),
    (14, 0,  "afternoon","⏰ HALF DAY GONE — {course} still not done!\n{hours}h {mins}m left. Open LMS now: lms.vitonline.in"),
    (20, 0,  "evening",  "⚠️  EVENING WARNING — Only {hours}h {mins}m left!\n{course} — Submit at least 1 quiz/assignment before midnight."),
    (23, 0,  "danger",   "🚨 LAST HOUR ALERT — {course}\nOne hour left! Submit NOW or lose −150 XP + −3 WIL tonight!"),
]

# Track which slots already fired today (resets at midnight)
_fired_today: set = set()
_last_reset_date: str = ""


def _is_canvas_done_today(course_name: str, course_code: str) -> bool:
    """
    Check if today's Canvas course has any completed items.
    Checks both task_daily_log (semester_audit) and canvas_completed_items.
    """
    today = datetime.date.today().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)

        # Check 1: semester audit says CLEARED today
        row = conn.execute(
            "SELECT status FROM daily_academic_cadence WHERE log_date = ?",
            (today,)
        ).fetchone()
        if row and row[0] == "CLEARED":
            conn.close()
            return True

        # Check 2: canvas_completed_items has entries today for this course
        row2 = conn.execute("""
            SELECT COUNT(*) FROM canvas_completed_items
            WHERE date(completed_at) = ?
              AND (course_name LIKE ? OR course_name LIKE ?)
        """, (today, f"%{course_name}%", f"%{course_code}%")).fetchone()
        count = int(row2[0] or 0) if row2 else 0

        conn.close()
        return count > 0
    except Exception as e:
        print(f"[Canvas Reminder] DB check error: {e}")
        return False  # assume not done — better to over-notify


def _is_weekend() -> bool:
    return datetime.date.today().weekday() >= 5


def _send_toast_notification(title: str, message: str, level: str = "normal"):
    """
    Send a Windows toast notification using PowerShell.
    Falls back to tkinter messagebox for DANGER level.
    """
    try:
        # Windows Toast via PowerShell BurntToast or fallback
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.BalloonTipIcon = 'Warning'
$notify.BalloonTipTitle = '{title}'
$notify.BalloonTipText = '{message}'
$notify.ShowBalloonTip(10000)
Start-Sleep -Seconds 12
$notify.Dispose()
"""
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        print(f"[Canvas Reminder] 🔔 Toast sent: {title}")
    except Exception as e:
        print(f"[Canvas Reminder] Toast error: {e}")

    # For DANGER level — also show a blocking tkinter dialog
    if level == "danger":
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showwarning(
                title,
                message + "\n\nOpen now: https://lms.vitonline.in",
                parent=root
            )
            root.destroy()
        except Exception:
            pass


def _push_in_app_notification(course: str, week: int, level: str, message: str):
    """
    Store a notification record in the DB so the web app's notification bell
    can display it without requiring a page refresh.
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS in_app_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                body        TEXT NOT NULL,
                level       TEXT DEFAULT 'info',
                is_read     INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO in_app_notifications (title, body, level)
            VALUES (?, ?, ?)
        """, (
            f"📚 Canvas Reminder — {course} (Week {week})",
            message,
            "danger" if level == "danger" else "warning"
        ))
        # Keep only last 50 notifications
        conn.execute("""
            DELETE FROM in_app_notifications
            WHERE id NOT IN (
                SELECT id FROM in_app_notifications ORDER BY id DESC LIMIT 50
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Canvas Reminder] In-app notification DB error: {e}")


def run_canvas_reminder_loop(stop_event: threading.Event):
    """
    Background daemon that fires reminders when today's Canvas work is not done.
    Checks every 60 seconds — fires at specific time slots.
    """
    global _fired_today, _last_reset_date
    print("[Canvas Reminder] 📚 Canvas daily reminder daemon started.")

    while not stop_event.is_set():
        now        = datetime.datetime.now()
        today_str  = now.date().isoformat()
        hour, minute = now.hour, now.minute

        # Reset fired slots at midnight
        if today_str != _last_reset_date:
            _fired_today.clear()
            _last_reset_date = today_str
            print(f"[Canvas Reminder] New day {today_str} — reminder slots reset.")

        # Skip weekends (Sat/Sun have DSA/MindOS slots, not Canvas work)
        if not _is_weekend():
            target = get_today_target()
            course_name = target.get("course_name", "Today's Subject")
            course_code = target.get("course_code", "")
            week_num    = target.get("week_number", 1)

            for slot_hour, slot_min, level, template in REMINDER_SLOTS:
                slot_key = f"{today_str}_{level}"
                if slot_key in _fired_today:
                    continue  # Already fired today

                # Check if we're within the 1-minute window for this slot
                if hour == slot_hour and abs(minute - slot_min) <= 1:
                    # Check if work is already done
                    if _is_canvas_done_today(course_name, course_code):
                        print(f"[Canvas Reminder] {level.upper()} slot — work already DONE! Skipping.")
                        _fired_today.add(slot_key)
                        continue

                    # Compute time remaining until midnight
                    midnight  = datetime.datetime.combine(now.date(), datetime.time(23, 59))
                    remaining = midnight - now
                    hrs  = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)

                    msg = template.format(
                        course=course_name,
                        week=week_num,
                        hours=hrs,
                        mins=mins
                    )
                    title = {
                        "morning":   f"📚 Start Canvas — {course_name}",
                        "afternoon": f"⏰ Pending: {course_name}",
                        "evening":   f"⚠️ Canvas Warning — {hrs}h left",
                        "danger":    f"🚨 LAST HOUR — {course_name}!",
                    }.get(level, f"Reminder: {course_name}")

                    print(f"[Canvas Reminder] Firing {level.upper()} reminder for {course_name}")
                    _send_toast_notification(title, msg, level)
                    _push_in_app_notification(course_name, week_num, level, msg)
                    _fired_today.add(slot_key)

        stop_event.wait(60)  # Check every 60 seconds

    print("[Canvas Reminder] Daemon stopped.")
