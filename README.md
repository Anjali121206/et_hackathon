# 🛡️ SentinelSafe: Multi-Agent Industrial Safety Intelligence

**SentinelSafe** is an advanced, AI-driven industrial safety platform designed to prevent catastrophic accidents in high-risk environments (like steel plants, refineries, and mines). It moves beyond traditional siloed alarms by using a **Multi-Agent AI Architecture (LangGraph)** to fuse telemetry, operational context, computer vision, and personnel data into a single, real-time **Compound Risk Score**.

---

## ⚠️ The Problem
In industrial settings, catastrophic failures rarely happen due to a single isolated event. They occur due to **compound risks**. 
For example: A 15% gas leak alone might only trigger a low-priority warning. However, if that 15% leak occurs while a contractor is performing **Hot Work (welding)** nearby, and the worker has been on shift for **12 hours (fatigue)**, the situation is actually a **critical emergency**. 

Traditional systems treat these as separate data points. SentinelSafe connects them to save lives.

---

## 🚀 The Solution
SentinelSafe uses a **5-Agent AI Pipeline** to evaluate safety from multiple dimensions simultaneously. It dynamically calculates a **Dynamic Risk Index (DRI)** and autonomously triggers orchestrated responses (e.g., dispatching an officer or triggering a shutdown).

### Key Features
1. **Compound Risk Engine**: Fuses multiple data streams to detect complex threat signatures that traditional systems miss, drastically reducing false negatives.
2. **Dynamic Plant Layouts**: Industries can instantly map their specific plant zones by uploading a simple `layout.json` configuration file directly from the dashboard.
3. **Real-time Web UI**: A stunning, dark-mode dashboard featuring a live SVG heatmap, a compound risk gauge, and a real-time safety event timeline.
4. **Automated Incident Response**: The Decision Engine automatically escalates responses based on the DRI threshold (Normal → Elevated → High → Critical).

---

## 🧠 Multi-Agent Architecture (LangGraph)
The intelligence of SentinelSafe is powered by a directed StateGraph of AI agents:

1. **Telemetry Agent (40%)**: Normalizes raw SCADA/IoT sensor readings (e.g., Methane LEL, CO ppm) into a baseline risk score.
2. **Permit Agent (25%)**: Cross-references active Permits-to-Work. High-risk operations (e.g., Confined Space, Hot Work) act as multipliers for the risk score.
3. **Vision Agent (20%)**: Analyzes CCTV feeds to track personnel volume and detect PPE violations in hazardous zones.
4. **Personnel Agent (15%)**: Integrates with corporate ERP/HR systems to detect worker fatigue (e.g., >10 hours on shift) and unauthorized roles in restricted areas.
5. **Decision Engine**: Fuses the evaluations from the 4 sub-agents, applies non-linear compound risk bonuses, computes the final DRI, and dispatches the action.

---

## 🧮 Dynamic Risk Index (DRI) Formula
The DRI is a weighted algorithm designed to amplify risk when multiple factors fail simultaneously:

```text
DRI = (0.40 × Telemetry) + (0.25 × Permits) + (0.20 × Vision) + (0.15 × Personnel) + Compound_Bonus
```
*If 3 or more safety dimensions are elevated simultaneously, a non-linear compound bonus is applied, driving the system to a critical state faster.*

---

## 💻 Tech Stack
*   **Backend framework**: FastAPI (Python)
*   **AI Orchestration**: LangGraph / LangChain
*   **Real-time Comms**: WebSockets
*   **Frontend UI**: HTML5, Vanilla JavaScript, CSS3 (Glassmorphism, CSS Grid)
*   **Database**: PostgreSQL (SQLAlchemy ORM) 
*   **Deployment**: Docker

---

## 🚧 Current Prototype Gaps & Future Roadmap
To maintain complete transparency for evaluation, we acknowledge the following gaps in our current MVP, which form our immediate production roadmap:

1. **No RAG over Regulatory Docs**: The regulatory rules (like permit multipliers) are currently hardcoded. Future iterations will implement Retrieval-Augmented Generation (RAG) over actual regulatory PDFs (OISD, Factory Act) to dynamically inform the decision agent.
2. **CCTV is Simulated (Not Actual CV)**: To demonstrate the compound risk engine within the hackathon timeframe, the vision analytics (PPE tracking, person counts) are fed via simulated JSON payloads. In production, this would be replaced with an actual Computer Vision model (e.g., YOLOv8) processing live RTSP camera feeds.
3. **Full ERP Integration**: While the Personnel Agent logic is fully functional, it currently reads from a mock `hr_database.py` rather than a live SAP/Oracle ERP system.

---

## ⚙️ How to Run Locally

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Start the Backend**:
   ```bash
   uvicorn app.main:app --port 8000
   ```
3. **Access the Dashboard**:
   Open your browser and navigate to `http://localhost:8000`

*To test the dynamic layouts, click "Upload Config" and select `custom_layout_example.json`!*
