import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
DATA_DIR = ROOT_DIR / "data"
UI_DIR = ROOT_DIR / "ui"
LOGS_DIR = ROOT_DIR / "logs"

LOGS_DIR.mkdir(exist_ok=True)

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Console handler
        ch = logging.StreamHandler(sys.stderr)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(ch)
        # File handler
        fh = logging.FileHandler(LOGS_DIR / "app.log")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(fh)
    return logger

SUPPORTED_OPERATIONS = [
    "derivative", "integral_indefinite", "integral_definite",
    "limit", "series", "taylor_series", "differential_eq", "simplify",
]

MAX_ANIMATION_STEPS = 50
DEFAULT_ANIMATION_SPEED = 1.0