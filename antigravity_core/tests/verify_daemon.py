import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.database
# Override the database path to a test database file
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_system_solo.db")
engine.database.DB_PATH = TEST_DB_PATH

from engine.database import init_db, get_state, save_state, add_xp, calculate_xp_required
from engine.fatigue_governor import update_daily_energy, CIRCUIT_BREAKER_LIMIT
from engine.git_watcher import match_commit_to_modules

def run_tests():
    print("--- 1. Initializing Database ---")
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
            print("[Test] Existing test database removed.")
        except Exception as e:
            print(f"[Test] Warning: could not delete test database: {e}")
            
    init_db()
    state = get_state()
    print(f"[Test] Loaded state: {state}")
    assert state["level"] == 1, "Initial level should be 1"
    assert state["xp"] == 0, "Initial XP should be 0"
    assert state["str"] == 10, "Initial STR should be 10"
    assert state["int"] == 10, "Initial INT should be 10"
    assert state["agi"] == 10, "Initial AGI should be 10"
    assert state["wil"] == 10, "Initial WIL should be 10"
    assert state["energy"] == 100.0, "Initial energy should be 100%"
    assert state["lockout_active"] == 0, "Lockout should be inactive"

    print("\n--- 2. Testing XP Progression Math ---")
    # At Level 1, XP req = 100 * 1^1.5 = 100.
    # Adding 120 XP should bring level to 2 with 20 XP.
    state = add_xp(120)
    print(f"[Test] State after 120 XP: Level {state['level']}, XP {state['xp']}")
    assert state["level"] == 2, "Level should be 2"
    assert state["xp"] == 20, "XP should be 20"
    
    # At Level 2, XP req = 100 * 2^1.5 = 100 * 2.8284 = 282.
    # Let's verify progression requirement:
    req_level_2 = calculate_xp_required(2)
    print(f"[Test] XP required for Level 2: {req_level_2}")
    assert req_level_2 == 282, "XP required for level 2 should be 282"

    print("\n--- 3. Testing Fatigue Governor & Circuit Breaker ---")
    # Drawdown of energy: study hours = 6.0
    # 100 - (15.0 * 6.0) = 10.0% energy.
    state = update_daily_energy(study_hours=6.0, gym_hours=0.0, dopamine_rewards=0)
    print(f"[Test] State after 6h study: Energy {state['energy']}%, Lockout Active: {bool(state['lockout_active'])}")
    assert state["energy"] == 10.0, "Energy should be 10.0%"
    assert state["lockout_active"] == 1, "Circuit breaker should trigger lockout for <= 20% energy"
    
    # Replenishment: gym hours = 2.0, dopamine_rewards = 2
    # 10.0 + (25.0 * 2.0) + (10.0 * 2) = 80.0% energy.
    state = update_daily_energy(study_hours=0.0, gym_hours=2.0, dopamine_rewards=2)
    print(f"[Test] State after replenishment: Energy {state['energy']}%, Lockout Active: {bool(state['lockout_active'])}")
    assert state["energy"] == 80.0, "Energy should be 80.0%"
    assert state["lockout_active"] == 0, "Lockout should clear when energy goes back above 20%"

    print("\n--- 4. Testing Git Commit Message Matching ---")
    # Setup test mock module matrices list
    mock_modules = [
        {"full_module_name": "L44: Principal Component Analysis (PCA) Covariance Eigen-Asset Derivations", "module_id": "L44", "course": "EDA", "level_required": 12, "xp_earned": 130},
        {"full_module_name": "L01: Axiomatic Probability Theory & Set-Theoretic Sample Space Formulations", "module_id": "L01", "course": "Probability_Stats", "level_required": 1, "xp_earned": 30}
    ]
    
    # Match test 1: Valid match
    commit_1 = "feat: cleared L01 under Probability_Stats"
    matches_1 = match_commit_to_modules(commit_1, mock_modules)
    print(f"[Test] Commit: '{commit_1}' matched modules count: {len(matches_1)}")
    assert len(matches_1) == 1, "Should match exactly 1 module"
    assert matches_1[0]["module_id"] == "L01", "Should match L01"
    
    # Match test 2: Case insensitivity and spacer robustness
    commit_2 = "docs: finished L44 for eda"
    matches_2 = match_commit_to_modules(commit_2, mock_modules)
    print(f"[Test] Commit: '{commit_2}' matched modules count: {len(matches_2)}")
    assert len(matches_2) == 1, "Should match exactly 1 module"
    assert matches_2[0]["module_id"] == "L44", "Should match L44"

    # Match test 3: No match
    commit_3 = "fix: solved L44 on some other course"
    matches_3 = match_commit_to_modules(commit_3, mock_modules)
    print(f"[Test] Commit: '{commit_3}' matched modules count: {len(matches_3)}")
    assert len(matches_3) == 0, "Should not match any modules"
    print("\n--- ALL DAEMON TESTS PASSED SUCCESSFULLY! ---")

    # Cleanup test database files
    for ext in ["", "-wal", "-shm"]:
        db_file = TEST_DB_PATH + ext
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass

if __name__ == "__main__":
    run_tests()
