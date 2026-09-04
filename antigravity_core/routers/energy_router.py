from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from engine.energy_engine import EnergyEngine

router = APIRouter(prefix="/api/energy", tags=["Energy Engine"])
engine = EnergyEngine()

class TaskActionPayload(BaseModel):
    category: str
    duration_minutes: float
    difficulty: int  # 1 to 10
    quest_id: Optional[str] = None

class RecoveryPayload(BaseModel):
    recovery_type: str  # POWER_NAP, MEDITATION, NUTRITION, NATURE_WALK, WORKOUT_RECOVERY
    units: float = 0.0

class SleepRolloverPayload(BaseModel):
    sleep_hours: float

@router.get("/state")
def get_energy_state():
    return engine.get_current_state()

@router.post("/consume")
def log_task_consumption(payload: TaskActionPayload):
    if not (1 <= payload.difficulty <= 10):
        raise HTTPException(status_code=400, detail="Difficulty must be scaled between 1 and 10.")
    result = engine.consume_energy(
        category=payload.category,
        duration_minutes=payload.duration_minutes,
        difficulty=payload.difficulty,
        quest_id=payload.quest_id
    )
    if result.get("status") == "REJECTED":
        raise HTTPException(status_code=429, detail=result["reason"])
    return result

@router.post("/recover")
def apply_restoration(payload: RecoveryPayload):
    return engine.apply_recovery(payload.recovery_type, payload.units)

@router.post("/rollover")
def execute_midnight_reset(payload: SleepRolloverPayload):
    return engine.midnight_fatigue_rollover(payload.sleep_hours)
