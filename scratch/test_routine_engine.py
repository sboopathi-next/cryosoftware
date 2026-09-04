import sys
import os

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('./antigravity_core'))

from antigravity_core.engine.routine_engine import RoutineEngine

print("--- TESTING CIRCADIAN ROUTINE ENGINE ---")

engine = RoutineEngine()

# 1. Test Exponential Decay XP Math
print("\n[1] Testing Exponential Decay Math:")
math_cases = [
    (0.0, 486),
    (0.2, 486),
    (0.9, 486),
    (1.0, 162),
    (1.5, 162),
    (2.1, 54),
    (3.5, 18),
    (4.8, 6),
    (5.0, 2),
    (8.2, 2)
]

for delay, expected_xp in math_cases:
    actual_xp = engine.calculate_punctuality_xp(delay)
    print(f"Delay: {delay}h => XP: {actual_xp} (Expected: {expected_xp})")
    assert actual_xp == expected_xp, f"XP Math mismatch for delay {delay}h: got {actual_xp}, expected {expected_xp}"

print("-> Exponential XP Math Verified!")

# 2. Test Get Status
print("\n[2] Testing RoutineEngine.get_status():")
status = engine.get_status()
print(f"Date: {status['date']} | Total XP Minted: {status['total_xp_minted']} | Synchrony: {status['synchrony_pct']}%")
print(f"Milestones Count: {len(status['milestones'])}")
print(f"Next Impending Milestone: {status['next_impending']['name'] if status['next_impending'] else 'None'}")
assert len(status['milestones']) == 8, "Expected 8 milestones!"

# 3. Test Milestone Trigger
print("\n[3] Testing Milestone Trigger ('wake'):")
trig_res = engine.trigger_milestone('wake')
print("Trigger Result:", trig_res)
assert trig_res['status'] in ['SUCCESS', 'REJECTED'], f"Unexpected trigger status: {trig_res['status']}"

# 4. Test Duplicate Trigger Rejection
print("\n[4] Testing Duplicate Trigger Rejection:")
dup_res = engine.trigger_milestone('wake')
print("Duplicate Trigger Result:", dup_res)
assert dup_res['status'] == 'REJECTED', f"Expected REJECTED status for duplicate trigger, got: {dup_res['status']}"

print("\n>>> ALL CIRCADIAN ROUTINE ENGINE TESTS PASSED CLEANLY! <<<")
