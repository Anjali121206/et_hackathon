"""
MOCK COMPUTER VISION MICROSERVICE (Port 8002)
Simulates an Edge AI Node running YOLOv8 on CCTV RTSP streams.
"""
from fastapi import FastAPI
import random

app = FastAPI(title="SentinelSafe Vision Microservice")

@app.get("/api/cv/analytics/{zone_id}")
async def get_vision_analytics(zone_id: str):
    """
    Simulate running bounding box inference to detect personnel
    and check for Hardhat/Vest PPE compliance.
    """
    # Base person count between 1 and 8
    person_count = random.randint(1, 8)
    
    ppe_violations = []
    
    # 30% chance someone is missing a hardhat or vest in a dangerous zone
    if random.random() < 0.3:
        if random.random() < 0.5:
            ppe_violations.append("MISSING_HARDHAT")
        else:
            ppe_violations.append("MISSING_VEST")
            
        # 10% chance of multiple violations
        if random.random() < 0.1:
            ppe_violations.append("NO_SAFETY_GLASSES")

    return {
        "zone_id": zone_id,
        "analytics": {
            "person_count": person_count,
            "ppe_violations": ppe_violations,
            "crowd_density": person_count / 10.0 # simulated metric
        },
        "model_version": "YOLOv8-Sentinel-v2",
        "status": "INFERENCE_OK"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
