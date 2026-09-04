import sys
import os
import datetime
import sqlite3

# Ensure antigravity_core is on pythonpath
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('./antigravity_core'))

from antigravity_core.engine.database import process_health_sync, get_health_sync_history

print("--- Testing Health Sync Upsert ---")
today_str = datetime.date.today().isoformat()

# Initial sync
res1 = process_health_sync(steps=5000, distance_km=3.5, active_minutes=30, sleep_hours=7.0, resting_hr=68, log_date=today_str, force_override=True)
print("Sync 1 Result:", res1)

# Second sync for same today_str (should UPSERT / update today's record, not create duplicate row)
res2 = process_health_sync(steps=8420, distance_km=6.3, active_minutes=45, sleep_hours=7.5, resting_hr=66, log_date=today_str, force_override=True)
print("Sync 2 Result (Upsert):", res2)

# Check history
logs = get_health_sync_history(limit=10)
print(f"Total Logs count returned: {len(logs)}")
today_logs = [l for l in logs if l.get('log_date') == today_str]
print(f"Today logs count: {len(today_logs)} (Should be 1)")
print("Today's updated log content:", today_logs[0] if today_logs else None)

assert len(today_logs) == 1, "Failed: Multiple rows created for today instead of upsert!"
assert today_logs[0]['steps'] >= 8420, "Failed: Upsert did not preserve steps count!"
print("\n>>> ALL GOOGLE FIT HEALTH SYNC DB & UPSERT TESTS PASSED CLEANLY! <<<")
