import sqlite3
import datetime

db_path = r'c:\Users\sboopathi\projects\CryoSoftWare\antigravity_core\data\antigravity.db'
conn = sqlite3.connect(db_path)

# List all tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Clear the lesson cache for today so new rotating lesson loads
today = datetime.date.today().isoformat()
for table_name in [t[0] for t in tables]:
    if 'lesson' in table_name.lower() or 'english' in table_name.lower() or 'cache' in table_name.lower() or 'daily' in table_name.lower():
        print(f"Found relevant table: {table_name}")
        try:
            # Try to delete by date
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
            print(f"  Columns: {cols}")
            date_col = next((c for c in cols if 'date' in c.lower()), None)
            if date_col:
                result = conn.execute(f"DELETE FROM {table_name} WHERE {date_col} = ?", (today,))
                conn.commit()
                print(f"  Deleted {result.rowcount} row(s) for {today}")
            else:
                print(f"  No date column found, skipping.")
        except Exception as e:
            print(f"  Error: {e}")

conn.close()
print("Done.")
