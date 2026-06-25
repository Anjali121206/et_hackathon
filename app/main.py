"""
SentinelSafe Core Platform — FastAPI Application
==================================================
Multi-agent industrial safety intelligence platform.

Endpoints:
    POST /api/telemetry      — Ingest SCADA/IoT sensor data
    POST /api/permit          — Register active permits
    POST /api/vision          — Submit CCTV vision analytics
    GET  /api/status/{zone}   — Get zone safety status
    GET  /api/zones           — Get all zones with status
    GET  /api/events          — Get event timeline
    GET  /api/spatial-violations — PostGIS spatial safety check
    WS   /ws                  — WebSocket for real-time dashboard updates
"""

import os
import json
import asyncio
import random
from datetime import datetime
from typing import List, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import redis

from app.schemas import SCADAPayload, CCTVPayload, ActivePermit, SafetyEvent
from app.database import init_db, execute_spatial_safety_check, update_zone_gas_level, log_incident
from app.workflow import safety_orchestrator
from app.risk_engine import get_risk_level


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Dashboard connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[WS] Dashboard disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected dashboards."""
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.remove(d)


manager = ConnectionManager()

# ─── Event History ─────────────────────────────────────────────────────────────

event_history: List[dict] = []
MAX_EVENTS = 200


def add_event(event: dict):
    """Add event to history and trim if too large."""
    event_history.insert(0, event)
    if len(event_history) > MAX_EVENTS:
        event_history.pop()


# ─── Dynamic Layout Configuration ──────────────────────────────────────────────

LAYOUT_FILE = "layout.json"
DEFAULT_LAYOUT = {
    "zones": [
        { "id": "ZONE_COKE_OVEN_04", "name": "COKE OVEN BATTERY #4", "x": 50, "y": 60, "width": 220, "height": 170 },
        { "id": "ZONE_BF_02", "name": "BLAST FURNACE #2", "x": 290, "y": 60, "width": 220, "height": 170 },
        { "id": "ZONE_SMS_01", "name": "STEEL MELTING SHOP #1", "x": 530, "y": 60, "width": 230, "height": 170 },
        { "id": "ZONE_ROLLING_03", "name": "ROLLING MILL #3", "x": 50, "y": 260, "width": 220, "height": 190 },
        { "id": "ZONE_GAS_HOLDER", "name": "GAS HOLDER STATION", "x": 290, "y": 260, "width": 220, "height": 190 },
        { "id": "ZONE_POWER_PLANT", "name": "CAPTIVE POWER PLANT", "x": 530, "y": 260, "width": 230, "height": 190 }
    ]
}

def get_layout():
    if not os.path.exists(LAYOUT_FILE):
        with open(LAYOUT_FILE, "w") as f:
            json.dump(DEFAULT_LAYOUT, f, indent=4)
        return DEFAULT_LAYOUT
    try:
        with open(LAYOUT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_LAYOUT

def save_layout(layout_data):
    with open(LAYOUT_FILE, "w") as f:
        json.dump(layout_data, f, indent=4)

# ─── Application Lifecycle ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    print("[*] SentinelSafe Platform Starting...")
    try:
        init_db()
        print("[OK] Database ready.")
    except Exception as e:
        print(f"[WARN] Database init warning (non-fatal): {e}")
    
    # Add system startup event
    add_event({
        "timestamp": datetime.now().isoformat(),
        "zone_id": "SYSTEM",
        "event_type": "SYSTEM",
        "severity": "INFO",
        "title": "Platform Online",
        "description": "SentinelSafe Multi-Agent Safety Intelligence Platform initialized. All agents operational.",
        "dri": None,
        "agent": "System"
    })
    
    task = asyncio.create_task(realtime_simulator())
    
    yield
    
    task.cancel()
    print("[STOP] SentinelSafe Platform Shutting Down...")


async def realtime_simulator():
    """Background task to simulate real-time telemetry across zones."""
    zone_ids = [
        "ZONE_COKE_OVEN_04", "ZONE_BF_02", "ZONE_SMS_01",
        "ZONE_ROLLING_03", "ZONE_GAS_HOLDER", "ZONE_POWER_PLANT"
    ]
    
    await asyncio.sleep(5)  # Wait for startup
    print("[*] Real-time telemetry simulator started.")
    
    while True:
        try:
            for zone_id in zone_ids:
                # Add slight random walk to baseline values
                payload = SCADAPayload(
                    sensor_id=f"SCADA_{zone_id}",
                    zone_id=zone_id,
                    carbon_monoxide_ppm=round(random.uniform(2.0, 15.0), 2),
                    methane_percentage_lel=round(random.uniform(0.0, 8.0), 2),
                    ambient_temperature_celsius=round(random.uniform(30.0, 42.0), 1),
                    pressure_bar=round(random.uniform(1.0, 1.1), 2)
                )
                await submit_telemetry(payload)
                await asyncio.sleep(0.5)  # Stagger updates slightly
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WARN] Simulator error: {e}")
            
        await asyncio.sleep(3)  # Loop every 3 seconds


# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SentinelSafe — Industrial Safety Intelligence",
    description="Multi-agent AI platform for compound industrial risk detection",
    version="1.0.0",
    lifespan=lifespan
)

# Redis connection (with graceful fallback)
try:
    redis_host = os.getenv("REDIS_HOST", "localhost")
    r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
    r.ping()
    print("[OK] Redis connected.")
except Exception:
    print("[WARN] Redis not available -- using in-memory fallback.")
    r = None

# In-memory fallback store when Redis is unavailable
memory_store: dict = {}


def cache_set(key: str, value: str):
    if r:
        r.set(key, value)
    else:
        memory_store[key] = value


def cache_get(key: str):
    if r:
        return r.get(key)
    return memory_store.get(key)


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/telemetry")
async def submit_telemetry(payload: SCADAPayload):
    """Ingest SCADA/IoT sensor telemetry and run multi-agent risk evaluation."""
    now = datetime.now().isoformat()
    
    # Store dynamic state
    cache_set(f"telemetry:{payload.zone_id}", json.dumps(payload.model_dump()))
    
    # Update database gas level
    try:
        update_zone_gas_level(payload.zone_id, payload.methane_percentage_lel)
    except Exception:
        pass
    
    # Check for active permits in this zone
    permit_data = cache_get(f"permit:{payload.zone_id}")
    p_factor = 0.1
    if permit_data:
        permit_info = json.loads(permit_data)
        permit_type = permit_info.get("permit_type", "ROUTINE")
        if permit_type == "HOT_WORK":
            p_factor = 0.9
        elif permit_type == "CONFINED_SPACE":
            p_factor = 0.8
        elif permit_type == "ELECTRICAL_ISOLATION":
            p_factor = 0.6
        else:
            p_factor = 0.3
    
    # Check for active vision violations
    vision_data = cache_get(f"vision:{payload.zone_id}")
    v_factor = 0.0
    ppe_violations = []
    person_count = 0
    if vision_data:
        v_details = json.loads(vision_data)
        ppe_violations = v_details.get("ppe_violations", [])
        person_count = v_details.get("person_count", 0)
        violation_count = len(ppe_violations)
        if violation_count >= 3:
            v_factor = 0.9
        elif violation_count >= 2:
            v_factor = 0.7
        elif violation_count >= 1:
            v_factor = 0.5
    
    # Execute the LangGraph Multi-Agent Pipeline
    inputs = {
        "zone_id": payload.zone_id,
        "telemetry_risk": payload.methane_percentage_lel,
        "permit_factor": p_factor,
        "vision_factor": v_factor,
        "computed_dri": 0.0,
        "critical_flag": False,
        "recommended_action": "",
        "risk_level": "NORMAL",
        "agent_trace": ""
    }
    
    result = safety_orchestrator.invoke(inputs)
    
    # Determine severity
    severity = "INFO"
    if result['critical_flag']:
        severity = "EMERGENCY"
    elif result['computed_dri'] >= 0.60:
        severity = "WARNING"
    elif result['computed_dri'] >= 0.35:
        severity = "WARNING"
    
    # Store the computed DRI state
    zone_status = {
        **result,
        "active_permits": 1 if permit_data else 0,
        "ppe_violations": ppe_violations,
        "person_count": person_count,
        "last_updated": now,
        "carbon_monoxide_ppm": payload.carbon_monoxide_ppm,
        "methane_percentage_lel": payload.methane_percentage_lel,
        "ambient_temperature_celsius": payload.ambient_temperature_celsius,
        "pressure_bar": payload.pressure_bar
    }
    cache_set(f"dri:{payload.zone_id}", json.dumps(zone_status))
    
    # Create event
    event = {
        "timestamp": now,
        "zone_id": payload.zone_id,
        "event_type": "TELEMETRY",
        "severity": severity,
        "title": f"Telemetry Update - DRI: {result['computed_dri']}",
        "description": f"CH4: {payload.methane_percentage_lel}% LEL | CO: {payload.carbon_monoxide_ppm} ppm | "
                       f"Temp: {payload.ambient_temperature_celsius}C | Action: {result['recommended_action']}",
        "dri": result['computed_dri'],
        "agent": "Multi-Agent Pipeline"
    }
    add_event(event)
    
    # Log critical incidents to DB
    if result['critical_flag']:
        try:
            log_incident(
                payload.zone_id, "CRITICAL_DRI", "EMERGENCY",
                f"DRI={result['computed_dri']} triggered emergency protocol. {result['agent_trace']}",
                result['computed_dri']
            )
        except Exception:
            pass
    
    # Broadcast to all connected dashboards
    await manager.broadcast({
        "type": "telemetry_update",
        "event": event,
        "zone_status": zone_status
    })
    
    return result


@app.post("/api/permit")
async def register_permit(payload: ActivePermit):
    """Register an active Permit-to-Work."""
    now = datetime.now().isoformat()
    cache_set(f"permit:{payload.zone_id}", json.dumps(payload.model_dump()))
    
    severity = "INFO"
    if payload.permit_type in ("HOT_WORK", "CONFINED_SPACE"):
        severity = "WARNING"
    
    event = {
        "timestamp": now,
        "zone_id": payload.zone_id,
        "event_type": "PERMIT",
        "severity": severity,
        "title": f"Permit Registered: {payload.permit_type}",
        "description": f"Permit {payload.permit_id} ({payload.permit_type}) active in {payload.zone_id}. "
                       f"Personnel: {', '.join(payload.authorized_personnel)}",
        "dri": None,
        "agent": "Permit Intelligence Agent"
    }
    add_event(event)
    
    await manager.broadcast({
        "type": "permit_update",
        "event": event,
        "permit": payload.model_dump()
    })
    
    return {"status": "Permit Registered", "permit_id": payload.permit_id}


@app.post("/api/vision")
async def submit_vision_state(payload: CCTVPayload):
    """Submit CCTV vision analytics state."""
    now = datetime.now().isoformat()
    cache_set(f"vision:{payload.zone_id}", json.dumps(payload.model_dump()))
    
    severity = "INFO"
    if len(payload.ppe_violations) > 0:
        severity = "WARNING"
    if len(payload.ppe_violations) >= 3:
        severity = "CRITICAL"
    
    violation_text = ", ".join(payload.ppe_violations) if payload.ppe_violations else "None"
    
    event = {
        "timestamp": now,
        "zone_id": payload.zone_id,
        "event_type": "VISION",
        "severity": severity,
        "title": f"CCTV Update — {len(payload.ppe_violations)} PPE Violations",
        "description": f"Camera {payload.camera_id}: {payload.person_count} persons detected. "
                       f"Violations: {violation_text}",
        "dri": None,
        "agent": "Vision Compliance Agent"
    }
    add_event(event)
    
    await manager.broadcast({
        "type": "vision_update",
        "event": event,
        "vision": payload.model_dump()
    })
    
    return {"status": "Vision State Updated", "violations": len(payload.ppe_violations)}


@app.get("/api/status/{zone_id}")
async def get_zone_status(zone_id: str):
    """Get the current safety status for a zone."""
    data = cache_get(f"dri:{zone_id}")
    if not data:
        raise HTTPException(status_code=404, detail="No safety state recorded for this zone.")
    return json.loads(data)


@app.get("/api/zones")
async def get_all_zones():
    """Get status of all known zones."""
    zone_ids = [
        "ZONE_COKE_OVEN_04", "ZONE_BF_02", "ZONE_SMS_01",
        "ZONE_ROLLING_03", "ZONE_GAS_HOLDER", "ZONE_POWER_PLANT"
    ]
    zones = []
    for zid in zone_ids:
        data = cache_get(f"dri:{zid}")
        if data:
            zone_data = json.loads(data)
            zone_data["zone_id"] = zid
            zones.append(zone_data)
        else:
            zones.append({
                "zone_id": zid,
                "computed_dri": 0.0,
                "critical_flag": False,
                "recommended_action": "CONTINUOUS_MONITORING",
                "risk_level": "NORMAL",
                "telemetry_risk": 0.0,
                "permit_factor": 0.0,
                "vision_factor": 0.0,
                "last_updated": None
            })
    return zones


@app.get("/api/events")
async def get_events(limit: int = 50):
    """Get recent safety events for the timeline."""
    return event_history[:limit]


@app.get("/api/spatial-violations")
async def get_spatial_violations():
    """Execute PostGIS spatial containment check for workers in hazardous zones."""
    try:
        return execute_spatial_safety_check()
    except Exception as e:
        return {"error": str(e), "violations": []}


# ─── Configuration Endpoints ───────────────────────────────────────────────────

@app.get("/api/config/layout")
async def api_get_layout():
    return get_layout()

@app.post("/api/config/layout")
async def api_post_layout(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        data = json.loads(contents)
        if "zones" not in data:
            raise HTTPException(status_code=400, detail="Invalid layout format. Missing 'zones' array.")
        save_layout(data)
        return {"status": "success", "message": "Layout updated successfully"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Serve Static Frontend ────────────────────────────────────────────────────

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse("static/index.html")


# ─── WebSocket Endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await manager.connect(websocket)
    
    # Send initial state
    try:
        zones_data = []
        zone_ids = [
            "ZONE_COKE_OVEN_04", "ZONE_BF_02", "ZONE_SMS_01",
            "ZONE_ROLLING_03", "ZONE_GAS_HOLDER", "ZONE_POWER_PLANT"
        ]
        for zid in zone_ids:
            data = cache_get(f"dri:{zid}")
            if data:
                zone_data = json.loads(data)
                zone_data["zone_id"] = zid
                zones_data.append(zone_data)
        
        await websocket.send_json({
            "type": "initial_state",
            "zones": zones_data,
            "events": event_history[:50]
        })
    except Exception:
        pass
    
    try:
        while True:
            # Keep connection alive, handle any incoming messages
            data = await websocket.receive_text()
            # Client can send ping/pong or commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
