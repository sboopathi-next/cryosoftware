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
    print(f"Loaded initial state: {state}")
    assert state["level"] == 1, "Initial level should be 1"
    assert state["xp"] == 0, "Initial XP should be 0"
    assert state["energy"] == 100.0, "Initial energy should be 100%"
    assert state["lockout_active"] is False, "Lockout should be inactive"

    print("\n--- 2. Testing XP & Level-Up Math ---")
    state = add_xp(state, 120)
    print(f"State after adding 120 XP: Level {state['level']}, XP {state['xp']}")
    assert state["level"] == 2, "Level should be 2"
    assert state["xp"] == 20, "XP should be 20"

    print("\n--- 3. Testing Energy Formula & Circuit Breaker ---")
    state = update_daily_energy(state, study_hours=6.0, gym_hours=0.0, dopamine_rewards=0)
    print(f"State after 6h study drawdown: Energy {state['energy']}%, Lockout Active: {state['lockout_active']}")
    assert state["energy"] == 10.0, "Energy should be 10%"
    assert state["lockout_active"] is True, "Circuit breaker should have triggered lockout"

    state = update_daily_energy(state, study_hours=0.0, gym_hours=2.0, dopamine_rewards=1)
    print(f"State after replenishment: Energy {state['energy']}%, Lockout Active: {state['lockout_active']}")
    assert state["energy"] == 70.0, "Energy should be 70%"
    assert state["lockout_active"] is False, "Lockout should have cleared"

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
