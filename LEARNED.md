# Core Learnings & Architectural Context for Antigravity AI

This document serves as a persistent guide for any AI assistant pairing on this repository. It documents critical codebase structures, discovered pitfalls, and fixed bugs to prevent regression and ensure consistency.

---

## 1. State Management & Day Transitions (Critical)

### The Bug
Previously, day transitions (resets and streak increments) were defined in three separate modules:
1. `check_date_transition(state)` in [state.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/state.py)
2. `check_date_transition_db(state)` in [database.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/antigravity_core/engine/database.py)
3. `check_date_transition(state)` in [server.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/antigravity_core/api/server.py)

Because both `state.py` and `database.py` reset the completed status of daily targets (study, leetcode, gym, english) to `0` or `False` immediately upon database state load (before `server.py` could evaluate them), the day transition in `server.py` always saw the completion status as `0`/`False`. This blocked the daily streak from ever incrementing.

### The Fix
* **Unified Day Transition**: All day transition checks, daily checklist resets, LeetCode pre-checks, energy updates, circuit breaker checks, and activity logs are now handled centrally in [state.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/state.py) at the database state loading level.
* **IST Timezone Alignment**: Transitions are checked against India Standard Time (IST, UTC+5:30) via `get_today_ist_str()` to prevent timezone mismatches between local execution and cloud/Vercel serverless environments.
* **Checklist Resets**: On transition, all daily targets—including newer ones (`walk_completed`, `meditation_completed`, `mindos_completed`, `health_completed`)—are reset to `0` cleanly.

---

## 2. Google Fit Sync & Checklist Persistence

### The Bug
The checklist item for `Google Health & Walking Sync` (`chk-health`) was not backed by a state attribute in the backend database. Every page reload cleared its "done" status, and there was no way for the state API to verify its completion.

### The Fix
* **Added `health_completed`**: Registered `health_completed` in `DEFAULT_STATE` and as a toggleable attribute in the state dictionary.
* **Auto-completion**: Tapping the **[ Sync Fit ]** button triggers the Google Fit Cloud API sync, which sets `health_completed = 1` and `walk_completed = 1` (if steps $\ge 1000$ or distance $\ge 0.5$ km) in the state.
* **Manual override**: Added `health_completed` to `/api/checklist/toggle` in [server.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/antigravity_core/api/server.py) to allow manual toggling on/off from the UI.

---

## 3. Shadowed Database Functions

### The Bug
[neon_db.py](file:///c:/Users/sboopathi/projects/CryoSoftWare/antigravity_core/engine/neon_db.py) had duplicate, conflicting definitions of `neon_save_workout_log` and `neon_get_workout_history`. The server endpoint imported the first definitions, which pointed to the obsolete `pg_workout_logs` table (which lacked auto-creation logic), causing workout logging to fail at the database level.

### The Fix
* Duplicate shadowed definitions were deleted.
* Unified implementation now targets `pg_workout_log` (singular) and executes `CREATE TABLE IF NOT EXISTS pg_workout_log` before any read/write operations to guarantee table initialization.

---

## 4. Guidelines for Future Updates
1. **Timezone**: Always use India Standard Time (IST, UTC+5:30) for daily metric transitions.
2. **State Updates**: Always modify state by updating the dictionary returned by `get_state()` and calling `save_state(state)`.
3. **No Duplicate Day Transitions**: Do not add new date transition check functions. Rely on `state.py` for day boundary handling.
