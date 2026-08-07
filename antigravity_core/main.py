import sys
import os
import time
import signal
import datetime
import threading
import subprocess
import uvicorn

# Append project root and antigravity_core to sys.path to ensure modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.database import init_db, get_state
from engine.leetcode_sync import run_leetcode_sync_loop
from engine.fatigue_governor import check_circuit_breaker
from engine.tech_news import run_tech_news_loop
from engine.english_daily import run_english_daily_loop
from engine.git_watcher import run_git_watcher
from api.server import app

ACTIVITY_LOG_PATH = r"c:\Users\sboopathi\projects\CryoSoftWare\antigravity_core\data\activity_log.md"

def prompt_user_powershell(prompt_text: str, title: str = "Antigravity Check-in") -> str:
    """Spawns a native Windows InputBox popup using PowerShell and returns the user's input."""
    escaped_prompt = prompt_text.replace('"', '`"')
    ps_cmd = f'[System.Reflection.Assembly]::LoadWithPartialName("Microsoft.VisualBasic") | Out-Null; $res = [Microsoft.VisualBasic.Interaction]::InputBox("{escaped_prompt}", "{title}"); Write-Output $res'
    try:
        # Run PowerShell in a subprocess to display the GUI dialog box on top
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=180 # 3 minutes timeout
        )
        return proc.stdout.strip()
    except Exception as e:
        print(f"[Activity Tracker] Error spawning PowerShell prompt: {e}")
        return ""

def trigger_checkin_manual() -> bool:
    """Manually triggers the check-in and logs it."""
    print("[Activity Tracker] Manual check-in triggered.")
    doing = prompt_user_powershell("What are you studying or doing right now?", "Antigravity - Current Activity")
    if doing:
        did = prompt_user_powershell("What did you accomplish in the last 3 hours?", "Antigravity - Accomplished Tasks")
        if did:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"\n## {timestamp} Check-in\n- **Current Activity**: {doing}\n- **Accomplished**: {did}\n"
            os.makedirs(os.path.dirname(ACTIVITY_LOG_PATH), exist_ok=True)
            with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(entry)
            print("[Activity Tracker] Check-in logged successfully.")
            return True
    return False

# Bind manual trigger to API so it can be called from frontend UI
@app.post("/api/trigger_checkin")
def api_trigger_checkin():
    success = trigger_checkin_manual()
    return {"status": "success" if success else "cancelled"}

def run_activity_checkin_loop(stop_event: threading.Event):
    """Loop running every 3 hours to query the user's activity status."""
    print("[Activity Tracker] 3-Hour activity check-in daemon loop running...")
    
    # Wait 3 hours (10800 seconds) between checks
    interval = 10800
    last_run = time.time()
    
    while not stop_event.is_set():
        if time.time() - last_run >= interval:
            last_run = time.time()
            try:
                trigger_checkin_manual()
            except Exception as e:
                print(f"[Activity Tracker] Exception in check-in loop: {e}")
        # Sleep short intervals to allow quick exit on daemon shutdown
        stop_event.wait(10)

def main():
    print("=========================================================")
    print("        ANTIGRAVITY BACKGROUND DAEMON STARTING UP        ")
    print("=========================================================")
    
    # Initialize SQLite tables and state
    init_db()
    
    state = get_state()
    print(f"Current State: Level {state.get('level')} | XP {state.get('xp')} | STR {state.get('str')} | INT {state.get('int')} | AGI {state.get('agi')} | WIL {state.get('wil')} | Energy {state.get('energy')}% | Lockout: {bool(state.get('lockout_active'))}")
    
    stop_event = threading.Event()
    
    # Spawn LeetCode sync thread
    leetcode_thread = threading.Thread(
        target=run_leetcode_sync_loop, 
        args=(stop_event,), 
        name="LeetCodeSyncThread", 
        daemon=True
    )
    
    # Spawn Git watcher thread
    git_thread = threading.Thread(
        target=run_git_watcher, 
        args=(stop_event,), 
        name="GitWatcherThread", 
        daemon=True
    )
    
    # Spawn Activity popup tracker thread
    activity_thread = threading.Thread(
        target=run_activity_checkin_loop,
        args=(stop_event,),
        name="ActivityPopupThread",
        daemon=True
    )
    
    # Spawn Tech News thread
    news_thread = threading.Thread(
        target=run_tech_news_loop,
        args=(stop_event,),
        name="TechNewsThread",
        daemon=True
    )
    
    # Spawn English Daily auto-update thread
    english_thread = threading.Thread(
        target=run_english_daily_loop,
        args=(stop_event,),
        name="EnglishDailyThread",
        daemon=True
    )
    
    leetcode_thread.start()
    git_thread.start()
    activity_thread.start()
    news_thread.start()
    english_thread.start()
    
    print("[Master Control] Background worker threads spawned successfully.")
    
    # Signal handling for clean exit
    def exit_gracefully(signum, frame):
        print("\n[Master Control] Shutdown signal received. Stopping threads...")
        stop_event.set()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    
    # Run FastAPI app
    print("[Master Control] Starting Uvicorn API server on 127.0.0.1:8000...")
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except KeyboardInterrupt:
        pass
    finally:
        print("[Master Control] Initiating daemon cleanup...")
        stop_event.set()
        # Wait a moment for threads to close
        time.sleep(1)
        print("[Master Control] Daemon shut down.")

if __name__ == "__main__":
    main()
