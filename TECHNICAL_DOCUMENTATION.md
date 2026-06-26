# SentinelSafe: Technical Documentation

## 1. Executive Summary
SentinelSafe is a multi-agent industrial safety intelligence platform built to mitigate compound risks in hazardous environments. Rather than relying on isolated alarms, it fuses telemetry, operational context, computer vision analytics, and personnel shift records into a singular **Dynamic Risk Index (DRI)**.

---

## 2. System Architecture
The application follows a decoupled client-server architecture powered by a real-time event-driven backend.

### 2.1 Component Breakdown
*   **Frontend**: Vanilla HTML5/CSS3/JS utilizing WebSockets for real-time updates and DOM manipulation for dynamic SVG layout rendering.
*   **Backend**: FastAPI (Python 3.12+), handling REST endpoints for configuration and WebSocket connections for telemetry streaming.
*   **Intelligence Layer**: LangGraph (StateGraph) coordinating 5 specialized AI agents.
*   **Data Persistence**: SQLite/PostgreSQL (via SQLAlchemy) logging all safety events and metrics.

### 2.2 Project Structure
```text
et_hackathon/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI server, WebSockets, Simulation loop
│   ├── workflow.py       # LangGraph multi-agent pipeline
│   ├── risk_engine.py    # DRI mathematical formulas and thresholds
│   ├── hr_database.py    # Mock ERP/HR shift database
│   ├── database.py       # SQLAlchemy ORM models
│   └── models.py         # Pydantic schemas
├── static/
│   ├── index.html        # Main dashboard UI
│   ├── index.css         # Styling (Glassmorphism, CSS Grid)
│   └── app.js            # WebSocket client, SVG rendering, UI updates
├── custom_layout.json    # User-uploaded dynamic plant zones
├── README.md             # Project Pitch & Quickstart
└── requirements.txt      # Python dependencies
```

---

## 3. The Multi-Agent Pipeline (LangGraph)
The core of SentinelSafe is located in `app/workflow.py`. It uses a directed acyclic graph (DAG) to process safety dimensions sequentially.

### 3.1 Shared State (`SafetyState`)
As data moves through the pipeline, agents mutate a shared `TypedDict`:
*   `telemetry_risk`: Raw SCADA sensor data.
*   `permit_factor`: Operational risk multiplier.
*   `vision_factor`: Computer vision risk multiplier.
*   `personnel_risk`: Fatigue and authorization risk.

### 3.2 The Agents
1.  **Telemetry Agent**: Reads raw IoT data (Methane LEL, CO ppm). Uses piecewise-linear normalization to convert physical readings into a `0.0 - 1.0` risk scale.
2.  **Permit Agent**: Reads from the active permit registry. Operations like `HOT_WORK` or `CONFINED_SPACE` act as direct multipliers to base risk.
3.  **Vision Agent**: Simulates CCTV analytics. Detects PPE violations and personnel density, increasing risk if density is high near hazardous zones.
4.  **Personnel Agent**: Cross-references the `hr_database.py`. Identifies if workers have been on shift for `> 10 hours` (Fatigue Risk) or if unauthorized roles (e.g., `Clerk`) are in a restricted zone.
5.  **Decision Engine**: Fuses the factors, calculates the DRI, and triggers the orchestrated response.

---

## 4. Dynamic Risk Index (DRI) Deep Dive
Located in `app/risk_engine.py`, the DRI is the master metric for the platform.

### 4.1 The Formula
The DRI is calculated using a weighted sum of the agent outputs, plus a non-linear compound bonus:

`DRI = (0.40 × Telemetry) + (0.25 × Permits) + (0.20 × Vision) + (0.15 × Personnel) + Compound_Bonus`

### 4.2 Compound Bonus
If multiple safety dimensions fail simultaneously, the system escalates faster than linear addition:
*   **2 dimensions elevated (>0.3)**: +5% Bonus
*   **3+ dimensions elevated (>0.3)**: +10% Bonus

### 4.3 Escalation Thresholds
*   `0.00 - 0.34` **[NORMAL]**: Continuous Monitoring.
*   `0.35 - 0.59` **[ELEVATED]**: Increase Monitoring Frequency.
*   `0.60 - 0.84` **[HIGH]**: Dispatch Safety Officer for Inspection.
*   `0.85 - 1.00` **[CRITICAL]**: Trigger Emergency Evacuation and Shutdown.

---

## 5. API Endpoints
*   `GET /`: Serves the static `index.html` frontend.
*   `GET /api/config/layout`: Returns the currently active plant layout (zones and coordinates) for dynamic SVG rendering.
*   `POST /api/config/layout`: Accepts a JSON upload to overwrite the current plant layout and restart the simulation logic.
*   `WS /ws/safety`: Primary WebSocket endpoint streaming serialized `SafetyState` and event timelines to the frontend at ~1Hz.

---

## 6. Frontend Dynamic Rendering
The frontend (`static/app.js`) is completely agnostic to the physical layout of the plant. 
1.  On load, it fetches `/api/config/layout`.
2.  It dynamically constructs `<rect>` and `<text>` SVG elements inside the `#plant-map` container based on the `x`, `y`, `width`, and `height` properties in the JSON.
3.  When WebSocket data arrives, it maps the `zone_id` to the drawn SVG elements, updating their `fill` color based on the computed DRI risk level.

---

## 7. Scaling to Production
To move this prototype to an enterprise production environment, the following architectural upgrades are required:
1.  **Computer Vision Integration**: Replace the simulated vision JSON payloads with an edge-deployed YOLOv8 or RT-DETR model processing live RTSP camera feeds via OpenCV/GStreamer.
2.  **LLM / RAG Integration**: Replace the hardcoded permit multipliers with a Vector Database (e.g., ChromaDB) containing regulatory documents (Factory Act, OISD). Use a LangChain Retriever to dynamically query rule compliance.
3.  **ERP / SAP Integration**: Replace `app/hr_database.py` with secure REST/SOAP calls to a live corporate SAP HR module to retrieve real-time shift data.
4.  **Message Queueing**: Shift from `asyncio` background tasks to a robust event bus like Apache Kafka or RabbitMQ to handle millions of IoT events per second.
