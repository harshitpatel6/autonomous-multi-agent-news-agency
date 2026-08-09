"""
Digest mode state (Task 5.3): daily vs weekly, persisted so the CEO Agent can
switch modes at runtime without editing config.py or restarting with new env vars.
"""
import json
import os
from typing import Literal

MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "digest_mode.json")

DAILY = "daily"
WEEKLY = "weekly"
VALID_MODES = (DAILY, WEEKLY)

# Lookback window per mode. Weekly aggregates a full 7 days; daily uses config's default.
MODE_LOOKBACK_HOURS = {DAILY: None, WEEKLY: 24 * 7}  # None = defer to config.LOOKBACK_HOURS

# Weekly digests apply a stricter "Best of" quality bar than the daily min score.
MODE_MIN_IMPORTANCE = {DAILY: None, WEEKLY: 7}  # None = defer to config.MIN_IMPORTANCE_SCORE


def get_mode() -> str:
    if not os.path.exists(MODE_FILE):
        return DAILY
    try:
        with open(MODE_FILE) as f:
            mode = json.load(f).get("mode", DAILY)
        return mode if mode in VALID_MODES else DAILY
    except Exception:
        return DAILY


def set_mode(mode: str) -> bool:
    if mode not in VALID_MODES:
        return False
    os.makedirs(os.path.dirname(MODE_FILE), exist_ok=True)
    with open(MODE_FILE, "w") as f:
        json.dump({"mode": mode}, f)
    return True


def get_lookback_hours() -> int:
    from config import LOOKBACK_HOURS
    override = MODE_LOOKBACK_HOURS.get(get_mode())
    return override if override is not None else LOOKBACK_HOURS


def get_min_importance_score() -> int:
    from config import MIN_IMPORTANCE_SCORE
    override = MODE_MIN_IMPORTANCE.get(get_mode())
    return override if override is not None else MIN_IMPORTANCE_SCORE
