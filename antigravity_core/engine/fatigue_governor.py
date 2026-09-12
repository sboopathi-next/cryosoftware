from engine.database import get_state, save_state

# Burnout mitigation coefficients
ALPHA = 15.0  # Cognitive drawdown per hour of heavy study
BETA = 25.0   # Gym discipline replenishment per hour
GAMMA = 10.0  # Micro-dopamine reward replenishment

CIRCUIT_BREAKER_LIMIT = 20.0
MAX_STREAK_LIMIT = 21

def _sync_energy_engine(new_energy: float):
    """Pushes the fatigue-governor energy value into EnergyEngine's energy_state table,
    keeping the dashboard's Cognitive Energy Engine ring from drifting out of sync."""
    try:
        from engine.energy_engine import EnergyEngine
        EnergyEngine().set_energy(new_energy)
    except Exception as e:
        print(f"[FatigueGovernor] Cognitive Energy Engine sync error: {e}")

def update_daily_energy(study_hours: float, gym_hours: float, dopamine_rewards: int) -> dict:
    """
    E_{t+1} = E_t - (ALPHA * study_hours) + (BETA * gym_hours) + (GAMMA * dopamine_rewards)
    """
    state = get_state()
    current_energy = state.get("energy", 100.0)
    
    drawdown = ALPHA * study_hours
    gain_gym = BETA * gym_hours
    gain_dopamine = GAMMA * dopamine_rewards
    
    new_energy = current_energy - drawdown + gain_gym + gain_dopamine
    state["energy"] = max(0.0, min(100.0, round(new_energy, 2)))
    
    # Run the circuit breaker check
    check_circuit_breaker(state)
    
    save_state(state)
    _sync_energy_engine(state["energy"])
    return state

def check_circuit_breaker(state: dict):
    """
    Triggers lockout if energy <= 20% or if continuous study streak >= 21 days.
    Waived if today is an active Universal Sanctuary Holiday.
    """
    import datetime
    today_str = datetime.date.today().isoformat()
    if state.get("active_holiday_date") == today_str:
        state["lockout_active"] = 0
        state["energy"] = 100.0
        _sync_energy_engine(100.0)
        return

    energy_depleted = state.get("energy", 100.0) <= CIRCUIT_BREAKER_LIMIT
    streak_overload = state.get("continuous_study_days", 0) >= MAX_STREAK_LIMIT
    
    if energy_depleted or streak_overload:
        state["lockout_active"] = 1
    else:
        state["lockout_active"] = 0
