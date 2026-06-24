"""
Multi-Agent Safety Orchestrator (LangGraph)
=============================================
Implements a 4-agent pipeline using LangGraph StateGraph:

    eval_telemetry → eval_permits → eval_vision → decision_engine

Each agent independently evaluates its safety dimension, and the
decision engine fuses all signals into a compound risk assessment.
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.risk_engine import calculate_dynamic_risk_index


class SafetyState(TypedDict):
    """Shared state flowing through the multi-agent pipeline."""
    zone_id: str
    telemetry_risk: float       # Raw LEL percentage from SCADA
    permit_factor: float        # Operational risk from permit context
    vision_factor: float        # Visual compliance risk from CCTV
    computed_dri: float         # Final Dynamic Risk Index
    critical_flag: bool         # Emergency threshold crossed
    recommended_action: str     # Orchestrated response action
    risk_level: str             # NORMAL / ELEVATED / HIGH / CRITICAL
    agent_trace: str            # Trace of agent evaluations


def eval_telemetry(state: SafetyState) -> dict:
    """
    AGENT 1: Telemetry Evaluation Agent
    Normalizes raw SCADA sensor readings into a 0-1 risk score.
    
    - LEL > 50% → maximum risk (1.0)
    - LEL 25-50% → high risk (0.5-1.0)
    - LEL 10-25% → elevated risk (0.2-0.5)
    - LEL < 10% → low risk (0.0-0.2)
    """
    raw_lel = state['telemetry_risk']
    
    # Piecewise-linear normalization with risk amplification at higher levels
    if raw_lel >= 50.0:
        normalized = 1.0
    elif raw_lel >= 25.0:
        normalized = 0.5 + (raw_lel - 25.0) / 50.0
    elif raw_lel >= 10.0:
        normalized = 0.2 + (raw_lel - 10.0) / 50.0
    else:
        normalized = raw_lel / 50.0
    
    normalized = min(1.0, max(0.0, normalized))
    
    trace = f"[TelemetryAgent] Raw LEL={raw_lel}% → Normalized={normalized:.3f}"
    return {"telemetry_risk": normalized, "agent_trace": trace}


def eval_permits(state: SafetyState) -> dict:
    """
    AGENT 2: Permit Intelligence Agent
    Evaluates operational risk based on active permit context.
    
    High-risk permits (HOT_WORK, CONFINED_SPACE) amplify the risk
    factor, especially when combined with elevated sensor readings.
    """
    p_factor = state['permit_factor']
    trace = state.get('agent_trace', '')
    
    # If telemetry risk is already elevated AND permit is high-risk,
    # we slightly amplify the permit factor (compound risk)
    if state['telemetry_risk'] > 0.3 and p_factor > 0.5:
        p_factor = min(1.0, p_factor * 1.15)
    
    trace += f" → [PermitAgent] Factor={p_factor:.3f}"
    return {"permit_factor": p_factor, "agent_trace": trace}


def eval_vision(state: SafetyState) -> dict:
    """
    AGENT 3: Vision Compliance Agent
    Evaluates safety compliance from CCTV analytics.
    
    PPE violations in hazardous zones significantly increase risk,
    especially during active high-risk operations.
    """
    v_factor = state['vision_factor']
    trace = state.get('agent_trace', '')
    
    # Vision violations are more dangerous during high-risk operations
    if state['permit_factor'] > 0.5 and v_factor > 0.0:
        v_factor = min(1.0, v_factor * 1.2)
    
    trace += f" → [VisionAgent] Factor={v_factor:.3f}"
    return {"vision_factor": v_factor, "agent_trace": trace}


def decision_engine(state: SafetyState) -> dict:
    """
    AGENT 4: Decision Engine
    Fuses all agent outputs into a final compound risk assessment
    and determines the appropriate orchestrated response.
    """
    dri = calculate_dynamic_risk_index(
        state['telemetry_risk'],
        state['permit_factor'],
        state['vision_factor']
    )
    
    critical = False
    action = "CONTINUOUS_MONITORING"
    risk_level = "NORMAL"
    
    if dri >= 0.85:
        critical = True
        action = "TRIGGER_EMERGENCY_EVACUATION_AND_SHUTDOWN"
        risk_level = "CRITICAL"
    elif dri >= 0.60:
        action = "DISPATCH_SAFETY_OFFICER_FOR_INSPECTION"
        risk_level = "HIGH"
    elif dri >= 0.35:
        action = "INCREASE_MONITORING_FREQUENCY"
        risk_level = "ELEVATED"
    
    trace = state.get('agent_trace', '')
    trace += f" → [DecisionEngine] DRI={dri:.4f} Level={risk_level}"
    
    return {
        "computed_dri": round(dri, 4),
        "critical_flag": critical,
        "recommended_action": action,
        "risk_level": risk_level,
        "agent_trace": trace
    }


# ─── Build LangGraph State Flow ───────────────────────────────────────────────

workflow = StateGraph(SafetyState)

workflow.add_node("eval_telemetry", eval_telemetry)
workflow.add_node("eval_permits", eval_permits)
workflow.add_node("eval_vision", eval_vision)
workflow.add_node("decision_engine", decision_engine)

workflow.set_entry_point("eval_telemetry")
workflow.add_edge("eval_telemetry", "eval_permits")
workflow.add_edge("eval_permits", "eval_vision")
workflow.add_edge("eval_vision", "decision_engine")
workflow.add_edge("decision_engine", END)

safety_orchestrator = workflow.compile()
