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
│   ├── main.py           # FastAPI server (Port 8000), WebSockets, Simulation loop
│   ├── workflow.py       # LangGraph multi-agent pipeline with HTTP clients
│   ├── risk_engine.py    # DRI mathematical formulas and thresholds
│   ├── rule_engine.py    # Dynamic rules injection
│   ├── database.py       # SQLAlchemy ORM models
│   └── schemas.py        # Pydantic schemas
├── services/
│   ├── erp_service.py    # Standalone mock SAP/HR Microservice (Port 8001)
│   └── cv_service.py     # Standalone mock CV/YOLO Microservice (Port 8002)
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
3.  **Vision Agent**: Makes HTTP requests to the CV Microservice (`http://localhost:8002`). Analyzes CCTV analytics to detect PPE violations and personnel density, increasing risk if density is high near hazardous zones.
4.  **Personnel Agent**: Makes HTTP requests to the ERP Microservice (`http://localhost:8001`). Identifies if workers have been on shift for `> 10 hours` (Fatigue Risk) or if unauthorized roles (e.g., `Clerk`) are in a restricted zone.
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
*   `GET /api/config/rules`: Returns the active safety rules, fatigue thresholds, and risk penalties.
*   `POST /api/config/rules`: Accepts a JSON upload to dynamically update safety rules in the active engine.
*   `WS /ws`: Primary WebSocket endpoint streaming serialized `SafetyState` and event timelines to the frontend.

---

## 6. Frontend Dynamic Rendering
The frontend (`static/app.js`) is completely agnostic to the physical layout of the plant. 
1.  On load, it fetches `/api/config/layout`.
2.  It dynamically constructs `<rect>` and `<text>` SVG elements inside the `#plant-map` container based on the `x`, `y`, `width`, and `height` properties in the JSON.
3.  When WebSocket data arrives, it maps the `zone_id` to the drawn SVG elements, updating their `fill` color based on the computed DRI risk level.

---

## 7. Scaling to Production
Because SentinelSafe utilizes a distributed microservice architecture, scaling to production simply involves replacing the external endpoints:
1.  **Computer Vision Integration**: Replace `http://localhost:8002` with the IP of an edge-deployed YOLOv8 or RT-DETR model processing live RTSP camera feeds. The main orchestrator's code remains completely unchanged.
2.  **LLM / RAG Integration**: Replace the JSON rule uploads with a Vector Database (e.g., ChromaDB) containing regulatory documents. Use a LangChain Retriever to dynamically supply the `rule_engine.py` with multipliers.
3.  **ERP / SAP Integration**: Replace `http://localhost:8001` with the secure API gateway of a corporate SAP HR module. The personnel agent will continue fetching data flawlessly.
4.  **Message Queueing**: Shift from `asyncio` background tasks to a robust event bus like Apache Kafka or RabbitMQ to handle millions of IoT events per second.
