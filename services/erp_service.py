"""
MOCK ERP / HR MICROSERVICE (Port 8001)
Simulates an external enterprise SAP/Oracle HR database.
"""
import os
import json
import random
from fastapi import FastAPI

app = FastAPI(title="SentinelSafe ERP Microservice")

# Hardcoded shift records (Mock SAP Data)
SHIFT_RECORDS = {
    "E1001": {"name": "Ravi Kumar", "role": "Welder", "assigned_zone": "ZONE_COKE_OVEN_04", "hours_worked": 11.5},
    "E1002": {"name": "Amit Singh", "role": "Fitter", "assigned_zone": "ZONE_COKE_OVEN_04", "hours_worked": 8.0},
    "E1003": {"name": "Suresh Patel", "role": "Clerk", "assigned_zone": "ZONE_COKE_OVEN_04", "hours_worked": 4.0},
    "E2001": {"name": "Neha Sharma", "role": "Supervisor", "assigned_zone": "ZONE_POWER_PLANT", "hours_worked": 9.5},
    "E3001": {"name": "Rahul Verma", "role": "Electrician", "assigned_zone": "ZONE_GAS_HOLDER", "hours_worked": 6.0},
    "E4001": {"name": "Karan Gupta", "role": "Operator", "assigned_zone": "ZONE_ROLLING_03", "hours_worked": 12.5},
}

def get_active_zones():
    layout_path = os.path.join(os.path.dirname(__file__), "..", "layout.json")
    if os.path.exists(layout_path):
        try:
            with open(layout_path, "r") as f:
                layout = json.load(f)
                return [z["id"] for z in layout.get("zones", [])]
        except Exception:
            pass
    return ["ZONE_COKE_OVEN_04", "ZONE_BF_02", "ZONE_SMS_01", "ZONE_ROLLING_03", "ZONE_GAS_HOLDER", "ZONE_POWER_PLANT"]

@app.get("/api/erp/personnel/{zone_id}")
async def get_personnel(zone_id: str):
    """Fetch real-time personnel data for a given plant zone."""
    active_zones = get_active_zones()
    
    # If the default zones match active zones, use exact hardcoded mapping
    default_zones = {"ZONE_COKE_OVEN_04", "ZONE_BF_02", "ZONE_SMS_01", "ZONE_ROLLING_03", "ZONE_GAS_HOLDER", "ZONE_POWER_PLANT"}
    if set(active_zones) == default_zones:
        personnel = [record for record in SHIFT_RECORDS.values() if record["assigned_zone"] == zone_id]
    else:
        # Dynamically distribute mock workers across whatever zones are loaded
        personnel = []
        if active_zones:
            for i, (emp_id, record) in enumerate(SHIFT_RECORDS.items()):
                assigned_idx = i % len(active_zones)
                if active_zones[assigned_idx] == zone_id:
                    emp_copy = record.copy()
                    emp_copy["assigned_zone"] = zone_id
                    personnel.append(emp_copy)
    
    # Introduce some dynamic variance to simulate real-time worker movement
    if random.random() < 0.2:
        # 20% chance a random unauthorized clerk walks into the zone
        personnel.append({"name": "Random Visitor", "role": "Clerk", "assigned_zone": zone_id, "hours_worked": 2.0})
        
    return {"zone_id": zone_id, "personnel": personnel, "status": "SAP_OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
