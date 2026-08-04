import os
import re
import csv
import glob
import time
import threading
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from engine.database import get_db_connection, get_state, save_state, add_xp, log_activity_file

# Base watch directory - will watch projects folder if exists
WATCH_DIR = os.getenv("WATCH_DIR", r"c:\Users\sboopathi\projects" if os.path.exists(r"c:\Users\sboopathi\projects") else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MATRICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "course_matrices")


def load_all_course_modules() -> list:
    """Loads all course modules from the exported CSV files."""
    modules = []
    csv_pattern = os.path.join(MATRICES_DIR, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    for csv_file in csv_files:
        try:
            with open(csv_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Expecting columns: Course_Module, Level_Required, XP_Points_Earned, Course
                    if not row.get("Course_Module") or not row.get("Course"):
                        continue
                    
                    mod_name = row["Course_Module"].strip()
                    course_name = row["Course"].strip()
                    
                    # Extract module ID (e.g. L01, L44, CAT, DA)
                    # Let's extract any prefix before the colon or the whole string prefix
                    m = re.match(r"^([A-Za-z0-9]+):", mod_name)
                    mod_id = m.group(1) if m else mod_name.split()[0].replace(":", "")
                    
                    # Extract level required
                    lvl_req_str = row.get("Level_Required", "Level 1")
                    lvl_match = re.search(r"\d+", lvl_req_str)
                    lvl_required = int(lvl_match.group(0)) if lvl_match else 1
                    
                    # Extract XP
                    xp_earned = int(row.get("XP_Points_Earned", 20))
                    
                    modules.append({
                        "full_module_name": mod_name,
                        "module_id": mod_id,
                        "course": course_name,
                        "level_required": lvl_required,
                        "xp_earned": xp_earned
                    })
        except Exception as e:
            print(f"[Git Watcher] Error loading {csv_file}: {e}")
            
    print(f"[Git Watcher] Loaded {len(modules)} syllabus modules for matching.")
    return modules

def is_module_completed(module_name: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM completed_modules WHERE module_name = ?", (module_name,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def mark_module_completed(module_name: str, course: str, xp_earned: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO completed_modules (module_name, course, xp_earned, completed_at) VALUES (?, ?, ?, ?)",
        (module_name, course, xp_earned, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def match_commit_to_modules(commit_msg: str, modules: list) -> list:
    """
    Searches commit message for course name and module ID.
    Example commit message: 'feat: cleared L44 under Linear_Algebra'
    This would match course 'Linear_Algebra' and module ID 'L44'.
    """
    matched = []
    msg_lower = commit_msg.lower()
    
    for mod in modules:
        course_clean = mod["course"].lower().replace("_", " ")
        course_raw = mod["course"].lower()
        mod_id_lower = mod["module_id"].lower()
        
        # Check if BOTH the course name (or its clean version) and the module ID (e.g. L44) are in the commit message
        has_course = (course_raw in msg_lower) or (course_clean in msg_lower)
        # Match module ID as a word or substring
        has_mod = re.search(r'\b' + re.escape(mod_id_lower) + r'\b', msg_lower) is not None
        
        if has_course and has_mod:
            matched.append(mod)
            
    return matched

def process_commit(commit_msg: str):
    print(f"[Git Watcher] Processing commit message: '{commit_msg.strip()}'")
    modules = load_all_course_modules()
    matches = match_commit_to_modules(commit_msg, modules)
    
    if not matches:
        print("[Git Watcher] No syllabus module matches found in commit message.")
        return
        
    state = get_state()
    player_level = state.get("level", 1)
    
    for match in matches:
        mod_name = match["full_module_name"]
        course = match["course"]
        lvl_req = match["level_required"]
        xp_earned = match["xp_earned"]
        
        print(f"[Git Watcher] Matched module: '{mod_name}' (Course: {course})")
        
        if is_module_completed(mod_name):
            print(f"[Git Watcher] Module '{mod_name}' is already completed. Skipping reward.")
            continue
            
        if player_level < lvl_req:
            print(f"[Git Watcher] Level authorization failed. Required level: {lvl_req}, current level: {player_level}.")
            continue
            
        # Reward XP and increment INT stat (studying increases intelligence!)
        print(f"[Git Watcher] Authorization success! Awarding +{xp_earned} XP and +1 INT.")
        state = get_state()
        state["int"] = state.get("int", 10) + 1
        state["study_completed"] = 1
        save_state(state)
        
        add_xp(xp_earned)
        mark_module_completed(mod_name, course, xp_earned)
        
        log_activity_file(
            doing=f"Git Commit Sync: Completed {mod_name}",
            accomplished=f"Committed code for course module: {mod_name} (Course: {course}). Awarded +{xp_earned} XP, +1 INT."
        )

class GitCommitHandler(FileSystemEventHandler):
    def on_modified(self, event):
        self._check_event(event)

    def on_created(self, event):
        self._check_event(event)

    def _check_event(self, event):
        if event.is_directory:
            return
            
        filename = os.path.basename(event.src_path)
        if filename == "COMMIT_EDITMSG":
            # Wait briefly for git to finish writing the file
            time.sleep(0.5)
            try:
                with open(event.src_path, "r", encoding="utf-8") as f:
                    commit_msg = f.read()
                if commit_msg.strip():
                    process_commit(commit_msg)
            except Exception as e:
                print(f"[Git Watcher] Error reading COMMIT_EDITMSG: {e}")

def run_git_watcher(stop_event: threading.Event):
    if not os.path.exists(WATCH_DIR):
        print(f"[Git Watcher] Watch directory '{WATCH_DIR}' does not exist! Creating it...")
        os.makedirs(WATCH_DIR, exist_ok=True)
        
    event_handler = GitCommitHandler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIR, recursive=True)
    observer.start()
    print(f"[Git Watcher] Monitoring folders under '{WATCH_DIR}' recursively for commits...")
    
    try:
        while not stop_event.is_set():
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()
        print("[Git Watcher] Monitoring stopped.")
