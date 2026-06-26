"""
Dynamic Regulatory Rules Engine
===============================
Manages dynamic multipliers and thresholds injected by safety officers
via custom JSON uploads, replacing hardcoded logic.
"""

from typing import Dict, Any

# Default Baseline Rules (Used if no custom rules are uploaded)
DEFAULT_RULES = {
    "permit_multipliers": {
        "HOT_WORK": 1.15,
        "CONFINED_SPACE": 1.25,
        "WORK_AT_HEIGHT": 1.10
    },
    "vision_multiplier": 1.20,
    "fatigue_threshold_hours": 10.0,
    "fatigue_penalty": 0.30,
    "unauthorized_penalty": 0.60
}

# Current Active Rules in memory
_active_rules: Dict[str, Any] = DEFAULT_RULES.copy()

def update_rules(new_rules: Dict[str, Any]):
    """Update the active rules engine with uploaded JSON."""
    global _active_rules
    # Merge new rules into active rules
    for key, value in new_rules.items():
        if isinstance(value, dict) and key in _active_rules and isinstance(_active_rules[key], dict):
            _active_rules[key].update(value)
        else:
            _active_rules[key] = value

def get_rules() -> Dict[str, Any]:
    """Get the currently active rules."""
    return _active_rules

def get_permit_multiplier(permit_type: str) -> float:
    """Get the specific risk multiplier for a permit type."""
    multipliers = _active_rules.get("permit_multipliers", {})
    return multipliers.get(permit_type, 1.0) # Default to 1.0 (no amplification) if not found
