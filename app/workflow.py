"""
Multi-Agent Safety Orchestrator (LangGraph)
=============================================
Implements a 4-agent pipeline using LangGraph StateGraph:

    eval_telemetry → eval_permits → eval_vision → decision_engine

Each agent independently evaluates its safety dimension, and the
decision engine fuses all signals into a compound risk assessment.
"""

import os
import requests
from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.risk_engine import calculate_dynamic_risk_index
from app.rule_engine import get_rules

ERP_SERVICE_URL = os.getenv("ERP_SERVICE_URL", "http://localhost:8001")
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL", "http://localhost:8002")


class SafetyState(TypedDict):
    """Shared state flowing through the multi-agent pipeline."""
    zone_id: str
    telemetry_risk: float       # Raw LEL percentage from SCADA
    permit_factor: float        # Operational risk from permit context
    vision_factor: float        # Visual compliance risk from CCTV
    personnel_risk: float       # Fatigue & authorization risk from HR DB
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
    
    Reads dynamic multipliers from the rule engine.
    """
    p_factor = state['permit_factor']
    trace = state.get('agent_trace', '')
    rules = get_rules()
    
    # We apply the dynamic HOT_WORK multiplier (default 1.15) if conditions are met
    # In a real system, permit_type would be passed in the state dict.
    hot_work_mult = rules.get("permit_multipliers", {}).get("HOT_WORK", 1.15)
    
    if state['telemetry_risk'] > 0.3 and p_factor > 0.5:
        p_factor = min(1.0, p_factor * hot_work_mult)
    
    trace += f" → [PermitAgent] Factor={p_factor:.3f}"
    return {"permit_factor": p_factor, "agent_trace": trace}


def eval_vision(state: SafetyState) -> dict:
    """
    AGENT 3: Vision Compliance Agent
    Evaluates safety compliance by querying the Computer Vision Microservice.
    """
    trace = state.get('agent_trace', '')
    rules = get_rules()
    vision_mult = rules.get("vision_multiplier", 1.2)
    
    # Query CV Microservice
    try:
        response = requests.get(f"{CV_SERVICE_URL}/api/cv/analytics/{state['zone_id']}", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            analytics = data.get("analytics", {})
            violations = analytics.get("ppe_violations", [])
            violation_count = len(violations)
            
            # Base vision factor calculation
            v_factor = 0.0
            if violation_count >= 3:
                v_factor = 0.9
            elif violation_count >= 2:
                v_factor = 0.7
            elif violation_count >= 1:
                v_factor = 0.5
        else:
            v_factor = state['vision_factor'] # fallback to state
    except requests.RequestException:
        # Network failure, fallback to existing state data
        v_factor = state['vision_factor']
        trace += " [CV_SVC_TIMEOUT]"
    
    # Vision violations are more dangerous during high-risk operations
    if state['permit_factor'] > 0.5 and v_factor > 0.0:
        v_factor = min(1.0, v_factor * vision_mult)
    
    trace += f" → [VisionAgent] Factor={v_factor:.3f}"
    return {"vision_factor": v_factor, "agent_trace": trace}


def eval_personnel(state: SafetyState) -> dict:
    """
    AGENT 4: Personnel Intelligence Agent
    Cross-references current personnel by querying the ERP Microservice.
    """
    trace = state.get('agent_trace', '')
    rules = get_rules()
    
    fatigue_thresh = rules.get("fatigue_threshold_hours", 10.0)
    fatigue_pen = rules.get("fatigue_penalty", 0.3)
    unauth_pen = rules.get("unauthorized_penalty", 0.6)
    
    hr_risk = 0.0
    fatigue_count = 0
    unauthorized = False
    
    # Query ERP Microservice
    try:
        response = requests.get(f"{ERP_SERVICE_URL}/api/erp/personnel/{state['zone_id']}", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            personnel = data.get("personnel", [])
        else:
            personnel = []
    except requests.RequestException:
        # Network failure
        personnel = []
        trace += " [ERP_SVC_TIMEOUT]"
    
    for worker in personnel:
        if worker["hours_worked"] >= fatigue_thresh:
            fatigue_count += 1
            hr_risk += fatigue_pen
        
        if state['permit_factor'] > 0.5 and worker["role"] in ["Clerk", "Admin"]:
            unauthorized = True
            hr_risk += unauth_pen
            
    hr_risk = min(1.0, hr_risk)
    
    msg = f" → [PersonnelAgent] {len(personnel)} workers. Fatigue: {fatigue_count}."
    if unauthorized:
        msg += " UNAUTHORIZED ROLE DETECTED."
    
    trace += msg
    return {"personnel_risk": hr_risk, "agent_trace": trace}


def decision_engine(state: SafetyState) -> dict:
    """
    AGENT 5: Decision Engine
    Fuses all agent outputs into a final compound risk assessment
    and determines the appropriate orchestrated response.
    """
    dri = calculate_dynamic_risk_index(
        state['telemetry_risk'],
        state['permit_factor'],
        state['vision_factor'],
        state.get('personnel_risk', 0.0)
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
workflow.add_node("eval_personnel", eval_personnel)
workflow.add_node("decision_engine", decision_engine)

workflow.set_entry_point("eval_telemetry")
workflow.add_edge("eval_telemetry", "eval_permits")
workflow.add_edge("eval_permits", "eval_vision")
workflow.add_edge("eval_vision", "eval_personnel")
workflow.add_edge("eval_personnel", "decision_engine")
workflow.add_edge("decision_engine", END)

safety_orchestrator = workflow.compile()
