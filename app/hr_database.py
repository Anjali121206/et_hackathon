"""
Mock HR/ERP Shift Record Database.
Simulates a real-time personnel database for the Personnel Agent to cross-reference.
"""

# Hardcoded shift records for demonstration
SHIFT_RECORDS = {
    "E1001": {"name": "Ravi Kumar", "role": "Technician", "assigned_zone": "ZONE_COKE_OVEN_04", "hours_worked": 4.5, "certifications": ["HOT_WORK"]},
    "E1002": {"name": "Priya Singh", "role": "Safety Officer", "assigned_zone": "ALL", "hours_worked": 8.0, "certifications": ["INSPECTION", "FIRST_AID"]},
    "E1003": {"name": "Amit Patel", "role": "Welder", "assigned_zone": "ZONE_SMS_01", "hours_worked": 11.5, "certifications": ["HOT_WORK"]},  # Fatigue risk!
    "E1004": {"name": "Neha Gupta", "role": "Clerk", "assigned_zone": "ZONE_ADMIN", "hours_worked": 6.0, "certifications": []}, # Unauthorized for hazardous zones
    "E1005": {"name": "Vikram Sharma", "role": "Engineer", "assigned_zone": "ZONE_BF_02", "hours_worked": 9.5, "certifications": ["CONFINED_SPACE"]},
}

def get_personnel_in_zone(zone_id: str) -> list:
    """
    Simulates querying the ERP system for personnel currently badged into a specific zone.
    For this mock, we just return everyone assigned to that zone, plus maybe a random clerk to trigger unauthorized access sometimes,
    or we just statically return based on the zone.
    """
    personnel = []
    for emp_id, data in SHIFT_RECORDS.items():
        if data["assigned_zone"] == zone_id or data["assigned_zone"] == "ALL":
            personnel.append(data)
            
    # Inject a fatigued worker into SMS_01
    if zone_id == "ZONE_SMS_01" and SHIFT_RECORDS["E1003"] not in personnel:
        personnel.append(SHIFT_RECORDS["E1003"])
        
    # Inject an unauthorized clerk into Coke Oven sometimes to simulate a breach
    if zone_id == "ZONE_COKE_OVEN_04":
        personnel.append(SHIFT_RECORDS["E1004"])
        
    return personnel
