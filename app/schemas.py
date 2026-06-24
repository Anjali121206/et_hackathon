from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SCADAPayload(BaseModel):
    """SCADA / IoT sensor telemetry data from plant instrumentation."""
    sensor_id: str
    zone_id: str
    carbon_monoxide_ppm: float = Field(ge=0, description="CO concentration in parts per million")
    methane_percentage_lel: float = Field(ge=0, description="Methane as percentage of Lower Explosive Limit")
    ambient_temperature_celsius: float = Field(description="Ambient temperature in Celsius")
    pressure_bar: float = Field(ge=0, description="Pressure in bar")


class CCTVPayload(BaseModel):
    """Computer vision output from CCTV safety analytics."""
    camera_id: str
    zone_id: str
    person_count: int = Field(ge=0, description="Number of persons detected in frame")
    ppe_violations: List[str] = Field(default_factory=list, description="List of PPE violations detected")


class ActivePermit(BaseModel):
    """Permit-to-Work registration payload."""
    permit_id: str
    permit_type: str = Field(description="e.g., HOT_WORK, CONFINED_SPACE, ROUTINE, ELECTRICAL_ISOLATION")
    zone_id: str
    authorized_personnel: List[str] = Field(default_factory=list)


class ShiftRecord(BaseModel):
    """Shift handover record."""
    shift_id: str
    zone_id: str
    supervisor: str
    crew_count: int
    handover_notes: Optional[str] = None


class SafetyEvent(BaseModel):
    """A safety event record for the timeline."""
    timestamp: str
    zone_id: str
    event_type: str  # TELEMETRY, PERMIT, VISION, ALERT, SYSTEM
    severity: str    # INFO, WARNING, CRITICAL, EMERGENCY
    title: str
    description: str
    dri: Optional[float] = None
    agent: Optional[str] = None  # Which agent generated this


class ZoneStatus(BaseModel):
    """Aggregated status of a plant zone."""
    zone_id: str
    zone_name: str
    computed_dri: float = 0.0
    critical_flag: bool = False
    recommended_action: str = "CONTINUOUS_MONITORING"
    telemetry_risk: float = 0.0
    permit_factor: float = 0.0
    vision_factor: float = 0.0
    active_permits: int = 0
    ppe_violations: List[str] = Field(default_factory=list)
    person_count: int = 0
    last_updated: Optional[str] = None
