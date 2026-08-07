import os
import sys

from config import STATE_FILE
from state import load_state, save_state, add_xp, update_daily_energy, calculate_xp_required
from leetcode import get_user_solved_stats, has_solved_today

def run_tests():
    print("--- 1. Testing State Initialization & Saving ---")
    if os.path.exists(STATE_FILE):
        print(f"Removing existing test state at {STATE_FILE}...")
        try:
            os.remove(STATE_FILE)
        except Exception as e:
            print(f"Could not remove state file: {e}")

    state = load_state()
    print(f"Loaded state (synced with Neon DB): Level {state.get('level')}, XP {state.get('xp')}, Energy {state.get('energy')}%")
    assert "level" in state and state["level"] >= 1, "Level should be >= 1"
    assert "xp" in state and state["xp"] >= 0, "XP should be >= 0"
    assert "energy" in state, "Energy key should exist in state"

    print("\n--- 2. Testing XP & Level-Up Math ---")
    test_state = {"level": 1, "xp": 0, "energy": 100.0, "lockout_active": False}
    test_state = add_xp(test_state, 120)
    print(f"State after adding 120 XP: Level {test_state['level']}, XP {test_state['xp']}")
    assert test_state["level"] == 2, "Level should be 2"
    assert test_state["xp"] == 20, "XP should be 20"

    print("\n--- 3. Testing Energy Formula & Circuit Breaker ---")
    test_state = update_daily_energy(test_state, study_hours=6.0, gym_hours=0.0, dopamine_rewards=0)
    print(f"State after 6h study drawdown: Energy {test_state['energy']}%, Lockout Active: {test_state['lockout_active']}")
    assert test_state["energy"] == 10.0, "Energy should be 10%"
    assert test_state["lockout_active"] is True, "Circuit breaker should have triggered lockout"

    test_state = update_daily_energy(test_state, study_hours=0.0, gym_hours=2.0, dopamine_rewards=1)
    print(f"State after replenishment: Energy {test_state['energy']}%, Lockout Active: {test_state['lockout_active']}")
    assert test_state["energy"] == 70.0, "Energy should be 70%"
    assert test_state["lockout_active"] is False, "Lockout should have cleared"

    print("\n--- 4. Testing LeetCode GraphQL Endpoint ---")
    print("Fetching solved statistics for user 'boopathispark'...")
    stats = get_user_solved_stats("boopathispark")
    print(f"Solved problem counts: {stats}")
    assert "All" in stats, "Stats should contain total solved count"
    
    print("Checking for recent submissions...")
    solved_today = has_solved_today("boopathispark")
    print(f"Has solved a problem in the last 24 hours: {solved_today}")

    print("\n--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_tests()
