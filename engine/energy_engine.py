import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CORE_ENGINE_DIR = os.path.join(PROJECT_ROOT, "antigravity_core")

if CORE_ENGINE_DIR not in sys.path:
    sys.path.insert(0, CORE_ENGINE_DIR)

from engine.energy_engine import EnergyEngine, DB_PATH

__all__ = ["EnergyEngine", "DB_PATH"]
