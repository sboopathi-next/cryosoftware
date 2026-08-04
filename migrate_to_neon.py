import json
import os
from config import STATE_FILE, DATABASE_URL, USER_PROFILE_ID
from state import save_state_to_db, init_db

def migrate():
    print("Starting migration to Neon PostgreSQL...")
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable is not set!")
        return

    init_db()

    if os.path.exists(STATE_FILE):
        print(f"Reading local state file: {STATE_FILE}")
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        
        print(f"Migrating state for user profile: '{USER_PROFILE_ID}'")
        save_state_to_db(local_state)
        print("Successfully migrated local state.json to Neon PostgreSQL database!")
    else:
        print("No local state.json found to migrate.")

if __name__ == "__main__":
    migrate()
