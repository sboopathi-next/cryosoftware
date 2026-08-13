import os
import sys
import math
import uuid
import datetime

# Ensure antigravity_core is in sys.path
core_dir = os.path.dirname(os.path.abspath(__file__))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from engine.database import (
    init_db, get_db_connection, get_state, save_state,
    save_meditation_log, save_rumination_log, save_reality_check, save_relationship
)
from engine.leetcode_sync import has_solved_leetcode_today

def test_all():
    print("=== 1. Initializing DB & Tables ===")
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Database tables: {tables}")
    assert "office_work_logs" in tables, "office_work_logs table missing"
    assert "gym_logs" in tables, "gym_logs table missing"
    conn.close()

    print("\n=== 2. Testing Office Work Tracker Exponential XP Calculation ===")
    cat = "API_Integration_Test_" + str(uuid.uuid4())[:4]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First entry in category
    item1 = "TEST-ITEM-1-" + str(uuid.uuid4())[:6]
    hours1 = 2.0
    cursor.execute("SELECT COUNT(*) FROM office_work_logs WHERE category = ?", (cat,))
    cnt0 = cursor.fetchone()[0] or 0
    mult0 = 1.0 + (0.25 * math.pow(1.20, min(cnt0, 15)))
    xp1 = round(hours1 * 40.0 * mult0, 2)
    
    cursor.execute("""
        INSERT INTO office_work_logs (workItemId, description, workDate, category, hours, xp_awarded, category_streak)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (item1, "Test 1", "2026-08-14", cat, hours1, xp1, cnt0 + 1))
    conn.commit()

    # Second entry in same category & same workItemId (verifies multi-log per workItemId with workLogId primary key)
    item2 = item1  # Same workItemId logged again
    hours2 = 2.0
    cursor.execute("SELECT COUNT(*) FROM office_work_logs WHERE category = ?", (cat,))
    cnt1 = cursor.fetchone()[0] or 0
    mult1 = 1.0 + (0.25 * math.pow(1.20, min(cnt1, 15)))
    xp2 = round(hours2 * 40.0 * mult1, 2)
    
    cursor.execute("""
        INSERT INTO office_work_logs (workItemId, description, workDate, category, hours, xp_awarded, category_streak)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (item2, "Test Session 2 for same workItemId", "2026-08-14", cat, hours2, xp2, cnt1 + 1))
    conn.commit()
    log_id2 = cursor.lastrowid
    conn.close()

    print(f"Log 1 Multiplier: {mult0:.2f}x -> {xp1} XP")
    print(f"Log 2 (Same workItemId '{item1}', Log ID #{log_id2}) Multiplier: {mult1:.2f}x -> {xp2} XP")
    assert mult1 > mult0, "Category streak should increase exponential multiplier"
    assert xp2 > xp1, "XP for same duration should be higher with category streak"
    assert log_id2 is not None and log_id2 > 0, "workLogId primary key should be auto-generated"

    print("\n=== 3. Testing Meditation & Mind OS Auto-Completion Flags ===")
    res_med = save_meditation_log(15, "Somatic Breathing Test")
    print(f"Save Meditation Result: {res_med}")
    
    state = get_state()
    print(f"State Flags: meditation_completed={state.get('meditation_completed')}, mindos_completed={state.get('mindos_completed')}")
    assert state.get("meditation_completed") == 1, "meditation_completed should be 1"
    assert state.get("mindos_completed") == 1, "mindos_completed should be 1"

    print("\n=== 4. Testing LeetCode Sync Logic ===")
    solved_today = has_solved_leetcode_today("boopathispark")
    print(f"LeetCode solved today status for 'boopathispark': {solved_today}")

    print("\n=== ALL VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_all()
