"""
Dynamic Risk Index (DRI) Engine
================================
Computes a weighted compound risk score from multiple safety dimensions.

Formula:
    DRI = (W_s × S_anomaly) + (W_p × P_factor) + (W_v × V_factor)
    
Where:
    S_anomaly = Normalized sensor/telemetry risk [0.0 - 1.0]
    P_factor  = Permit-to-work operational risk factor [0.0 - 1.0]
    V_factor  = Visual compliance risk from CCTV analytics [0.0 - 1.0]

Weights:
    W_s = 0.50 (50% — sensor anomaly is primary signal)
    W_p = 0.30 (30% — operational context from permits)
    W_v = 0.20 (20% — visual compliance from CCTV)

Thresholds:
    DRI >= 0.85 → CRITICAL: Emergency evacuation & shutdown
    DRI >= 0.60 → HIGH: Dispatch safety officer for inspection
    DRI >= 0.35 → ELEVATED: Increase monitoring frequency
    DRI <  0.35 → NORMAL: Continuous monitoring
"""


def calculate_dynamic_risk_index(s_anomaly: float, p_factor: float, v_factor: float) -> float:
    """
    Calculate the Dynamic Risk Index from three safety dimensions.
    
    Args:
        s_anomaly: Normalized sensor anomaly score [0.0 - 1.0]
        p_factor: Permit operational risk factor [0.0 - 1.0]
        v_factor: Visual compliance factor [0.0 - 1.0]
    
    Returns:
        DRI value clamped between 0.0 and 1.0
    """
    # Formula weights
    w_s, w_p, w_v = 0.50, 0.30, 0.20

    # Non-linear amplification for compound risk:
    # When multiple factors are elevated simultaneously, the risk
    # compounds faster than a linear model would suggest.
    compound_bonus = 0.0
    elevated_count = sum(1 for f in [s_anomaly, p_factor, v_factor] if f > 0.3)
    if elevated_count >= 3:
        compound_bonus = 0.10  # All three factors elevated = extra 10%
    elif elevated_count >= 2:
        compound_bonus = 0.05  # Two factors elevated = extra 5%

    # Calculate weighted DRI with compound risk bonus
    dri = (w_s * s_anomaly) + (w_p * p_factor) + (w_v * v_factor) + compound_bonus

    # Clamp between 0.0 and 1.0
    return max(0.0, min(1.0, dri))


def get_risk_level(dri: float) -> dict:
    """
    Classify DRI into risk levels with recommended actions.
    
    Returns:
        dict with 'level', 'color', 'action' keys
    """
    if dri >= 0.85:
        return {
            "level": "CRITICAL",
            "color": "#ff0040",
            "action": "TRIGGER_EMERGENCY_EVACUATION_AND_SHUTDOWN"
        }
    elif dri >= 0.60:
        return {
            "level": "HIGH",
            "color": "#ff6600",
            "action": "DISPATCH_SAFETY_OFFICER_FOR_INSPECTION"
        }
    elif dri >= 0.35:
        return {
            "level": "ELEVATED",
            "color": "#ffaa00",
            "action": "INCREASE_MONITORING_FREQUENCY"
        }
    else:
        return {
            "level": "NORMAL",
            "color": "#00ff88",
            "action": "CONTINUOUS_MONITORING"
        }
