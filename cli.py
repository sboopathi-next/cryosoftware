import sys
import os
import random

from state import load_state, save_state, add_xp, update_daily_energy, check_date_transition, calculate_xp_required
from leetcode import has_solved_today, get_user_solved_stats
from main import MATH_CHALLENGES

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import ProgressBar
    from rich.text import Text
    from rich.table import Table
    USE_RICH = True
    console = Console()
except ImportError:
    USE_RICH = False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_energy_color(energy: float) -> str:
    if energy <= 20:
        return "red"
    elif energy <= 50:
        return "yellow"
    else:
        return "green"

def print_lockdown_screen(state: dict):
    clear_screen()
    title = """
    ================================================================
    ||                  !!! SYSTEM LOCKDOWN !!!                  ||
    ||       CRITICAL COGNITIVE DEPLETION / OVERLOAD ACTIVE      ||
    ================================================================
    """
    if USE_RICH:
        console.print(Panel(Text(title, justify="center", style="bold red"), border_style="red"))
        console.print("\n[bold yellow]To restore system operational access, you must execute the Dungeon Cleanse payload.[/bold yellow]")
        console.print("[bold cyan]Select your Payload Challenge:[/bold cyan]")
        console.print("1. Physical Strain: 100 Muscular challenge repetitions (pushups).")
        console.print("2. Mathematical Strain: Solve an analytical ML/stats proof.\n")
    else:
        print(title)
        print("To restore system operational access, you must execute the Dungeon Cleanse payload.")
        print("Select your Payload Challenge:")
        print("1. Physical Strain: 100 Muscular challenge repetitions (pushups).")
        print("2. Mathematical Strain: Solve an analytical ML/stats proof.\n")
        
    choice = input("Enter payload choice (1 or 2): ").strip()
    if choice == "1":
        confirm = input("Confirm you executed 100 reps (Enter '100' to submit): ").strip()
        if confirm == "100":
            state["lockout_active"] = False
            state["energy"] = 30.0
            save_state(state)
            if USE_RICH:
                console.print("[bold green]Success: Physical strain verified. System operational access restored![/bold green]")
            else:
                print("Success: Physical strain verified. System operational access restored!")
            input("Press Enter to continue...")
        else:
            if USE_RICH:
                console.print("[bold red]Cleanse payload verification failed.[/bold red]")
            else:
                print("Cleanse payload verification failed.")
            input("Press Enter to retry...")
    elif choice == "2":
        challenge = random.choice(MATH_CHALLENGES)
        print(f"\nCHALLENGE: {challenge['question']}")
        ans = input("Your derived solution string (e.g. formula format): ").strip()
        if ans.replace(" ", "") == challenge["expected_answer"].replace(" ", ""):
            state["lockout_active"] = False
            state["energy"] = 30.0
            save_state(state)
            if USE_RICH:
                console.print("[bold green]Success: Mathematical derivation verified. System unlocked.[/bold green]")
            else:
                print("Success: Mathematical derivation verified. System unlocked.")
            input("Press Enter to continue...")
        else:
            if USE_RICH:
                console.print(f"[bold red]Validation failed. Correct formula expected: {challenge['expected_answer']}[/bold red]")
            else:
                print(f"Validation failed. Correct formula expected: {challenge['expected_answer']}")
            input("Press Enter to retry...")

def draw_dashboard(state: dict):
    clear_screen()
    energy = state["energy"]
    level = state["level"]
    xp = state["xp"]
    req_xp = calculate_xp_required(level)
    streak = state["streak_days"]
    willpower = state.get("willpower", 10)
    
    energy_color = get_energy_color(energy)
    
    if USE_RICH:
        console.print(Panel(Text("ANTIGRAVITY CORE v1.0", justify="center", style="bold cyan"), border_style="cyan"))
        
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=1)
        
        status_text = Text()
        status_text.append(f"Level: {level}\n", style="bold white")
        status_text.append(f"XP: {xp} / {req_xp}\n", style="cyan")
        status_text.append(f"Willpower (WIL): {willpower}\n", style="bold purple")
        status_text.append(f"Streak: {streak} days\n", style="green")
        status_text.append(f"Energy (Et): {energy}%\n", style=f"bold {energy_color}")
        
        energy_bar = "█" * int(energy // 5) + "░" * (20 - int(energy // 5))
        status_text.append(f"[{energy_bar}]\n", style=energy_color)
        
        quests_text = Text()
        c_status = "[x]" if "core_skill" in state["completed_quests_today"] else "[ ]"
        a_status = "[x]" if "agility_code" in state["completed_quests_today"] else "[ ]"
        
        quests_text.append(f"{c_status} Core Skill: {state['active_quests']['core_skill']}\n", style="bold green" if c_status == "[x]" else "yellow")
        quests_text.append(f"{a_status} Agility Code: {state['active_quests']['agility_code']}\n", style="bold green" if a_status == "[x]" else "yellow")
        
        quests_text.append("\nDiscipline Anchors:\n", style="bold white")
        gym_ok = "[x]" if state.get("gym_completed", False) else "[ ]"
        cook_ok = "[x]" if state.get("cooking_completed", False) else "[ ]"
        pmo_ok = "[x]" if state.get("nopmo_completed", False) else "[ ]"
        quests_text.append(f"{gym_ok} Gym Attendance\n", style="green" if gym_ok == "[x]" else "white")
        quests_text.append(f"{cook_ok} Cook Daily Meal\n", style="green" if cook_ok == "[x]" else "white")
        quests_text.append(f"{pmo_ok} No PMO (Porn/Masturbation Skip)\n", style="green" if pmo_ok == "[x]" else "white")
        
        table.add_row(
            Panel(status_text, title="Status Metrics", border_style="blue"),
            Panel(quests_text, title="Active Actions", border_style="yellow")
        )
        
        console.print(table)
        
        rec_vector = "Mindful walk + Chat with Ammu ❤️ (restores +10% energy)"
        console.print(Panel(Text(f"Recovery Vector: {rec_vector}", style="italic green"), title="Dopamine Economy Recommendation", border_style="green"))
    else:
        print("=" * 60)
        print("ANTIGRAVITY CORE v1.0")
        print("=" * 60)
        print(f"Level: {level} | XP: {xp} / {req_xp} | Willpower: {willpower}")
        print(f"Energy (Et): {energy}% [{'#' * int(energy // 5)}{'-' * (20 - int(energy // 5))}]")
        print("-" * 60)
        print("ACTIVE ACTIONS:")
        c_status = "[x]" if "core_skill" in state["completed_quests_today"] else "[ ]"
        a_status = "[x]" if "agility_code" in state["completed_quests_today"] else "[ ]"
        print(f"{c_status} Core Skill: {state['active_quests']['core_skill']}")
        print(f"{a_status} Agility Code: {state['active_quests']['agility_code']}")
        print(f"{'[x]' if state.get('gym_completed', False) else '[ ]'} Gym Daily")
        print(f"{'[x]' if state.get('cooking_completed', False) else '[ ]'} Cook Daily")
        print(f"{'[x]' if state.get('nopmo_completed', False) else '[ ]'} No PMO (Willpower Anchor)")
        print("-" * 60)
        print("Recovery Vector: Chat with Ammu + listen to music tracks")
        print("=" * 60)

def main_loop():
    while True:
        state = load_state()
        state = check_date_transition(state)
        save_state(state)
        
        if state["lockout_active"]:
            print_lockdown_screen(state)
            continue
            
        draw_dashboard(state)
        
        print("\nCommands:")
        print("1. Log Daily Telemetry (study hours, gym hours, dopamine count)")
        print("2. Verify LeetCode daily quest (Core Skill)")
        print("3. Log Agility Code quest completion")
        print("4. Toggle Discipline Checks (Gym / Cooking / No-PMO)")
        print("5. Exit CLI")
        
        choice = input("\nSelect action: ").strip()
        
        if choice == "1":
            try:
                study = float(input("Enter study/strain hours (e.g. 2.5): ").strip())
                gym = float(input("Enter gym/exercise hours (e.g. 1.0): ").strip())
                rewards = int(input("Enter completed dopamine rewards count: ").strip())
                state = update_daily_energy(state, study, gym, rewards)
                save_state(state)
                print("Telemetry successfully updated!")
            except ValueError:
                print("Invalid input values.")
            input("Press Enter to continue...")
            
        elif choice == "2":
            print("Checking LeetCode GraphQL API metrics...")
            if "core_skill" in state["completed_quests_today"]:
                print("Core skill quest is already completed for today.")
            elif has_solved_today():
                state["completed_quests_today"].append("core_skill")
                state = add_xp(state, 30)
                state["active_quests"]["core_skill"] = "Solve another Medium/Hard LeetCode problem"
                save_state(state)
                print("Verification Success: Accepted LeetCode submission found! +30 XP.")
            else:
                print("No accepted submissions found on LeetCode within the last 24 hours.")
            input("Press Enter to continue...")
            
        elif choice == "3":
            if "agility_code" in state["completed_quests_today"]:
                print("Agility code quest is already completed for today.")
            else:
                confirm = input("Have you successfully implemented/verified the local changes? (y/n): ").strip().lower()
                if confirm == 'y':
                    state["completed_quests_today"].append("agility_code")
                    state = add_xp(state, 20)
                    state["active_quests"]["agility_code"] = "Optimize clean code pipeline"
                    save_state(state)
                    print("Quest completed! +20 XP.")
            input("Press Enter to continue...")
            
        elif choice == "4":
            print("\nToggle Actions:")
            print(f"1. Gym Attendance (Current: {state.get('gym_completed', False)})")
            print(f"2. Daily Cooking (Current: {state.get('cooking_completed', False)})")
            print(f"3. No PMO discipline (Current: {state.get('nopmo_completed', False)})")
            toggle_choice = input("Select item to toggle (1-3): ").strip()
            
            if toggle_choice == "1":
                val = not state.get("gym_completed", False)
                state["gym_completed"] = val
                if val: state = add_xp(state, 10)
                print(f"Gym Attendance set to {val}.")
            elif toggle_choice == "2":
                val = not state.get("cooking_completed", False)
                state["cooking_completed"] = val
                if val: state = add_xp(state, 10)
                print(f"Daily Cooking set to {val}.")
            elif toggle_choice == "3":
                val = not state.get("nopmo_completed", False)
                state["nopmo_completed"] = val
                if val:
                    state = add_xp(state, 15)
                    state["willpower"] = state.get("willpower", 10) + 1
                print(f"No PMO discipline set to {val}.")
            save_state(state)
            input("Press Enter to continue...")
            
        elif choice == "5":
            print("Shutting down CLI.")
            break
        else:
            print("Invalid selection.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main_loop()
