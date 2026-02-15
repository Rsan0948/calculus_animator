from pathlib import Path

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
UI_DIR = ROOT_DIR / "ui"

SUPPORTED_OPERATIONS = [
    "derivative", "integral_indefinite", "integral_definite",
    "limit", "series", "taylor_series", "differential_eq", "simplify",
]

MAX_ANIMATION_STEPS = 50
DEFAULT_ANIMATION_SPEED = 1.0