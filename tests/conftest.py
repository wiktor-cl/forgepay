import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in [
    "libs/common",
    "libs/events",
    "libs/security",
    "libs/observability",
    "services/payment_service",
]:
    sys.path.insert(0, str(ROOT / rel))
