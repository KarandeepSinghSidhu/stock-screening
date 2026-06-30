"""
Simple local profile storage — single user, no auth.
Saves preferences to a JSON file on disk.
"""
import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "profile.json")

DEFAULT_PROFILE = {
    "name": "",
    "sectors": ["tech", "health"],
    "risk_appetite": "balanced",
    "default_horizon": "long",
    "onboarded": False,
}


def get_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return DEFAULT_PROFILE.copy()
    try:
        with open(PROFILE_PATH, "r") as f:
            data = json.load(f)
            merged = DEFAULT_PROFILE.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_PROFILE.copy()


def save_profile(profile: dict) -> dict:
    current = get_profile()
    current.update(profile)
    current["onboarded"] = True
    with open(PROFILE_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current