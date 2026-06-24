import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:safe_password_2026@localhost:5432/sentinelsafe"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables with PostGIS extensions. Retries on connection failure."""
    for attempt in range(15):
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS plant_zones (
                        zone_id VARCHAR(50) PRIMARY KEY,
                        zone_name VARCHAR(100),
                        geom geometry(Polygon, 4326),
                        current_gas_lel_percentage DOUBLE PRECISION DEFAULT 0.0
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS active_permits (
                        permit_id VARCHAR(50) PRIMARY KEY,
                        permit_type VARCHAR(50),
                        zone_id VARCHAR(50),
                        valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        valid_to TIMESTAMP DEFAULT CURRENT_TIMESTAMP + INTERVAL '8 hours'
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS worker_telemetry (
                        worker_id VARCHAR(50),
                        last_known_location geometry(Point, 4326),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS incident_log (
                        id SERIAL PRIMARY KEY,
                        zone_id VARCHAR(50),
                        event_type VARCHAR(50),
                        severity VARCHAR(20),
                        description TEXT,
                        dri_value DOUBLE PRECISION,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                # Seed sample zones if empty
                result = conn.execute(text("SELECT COUNT(*) FROM plant_zones"))
                count = result.scalar()
                if count == 0:
                    conn.execute(text("""
                        INSERT INTO plant_zones (zone_id, zone_name, geom, current_gas_lel_percentage) VALUES
                        ('ZONE_COKE_OVEN_04', 'Coke Oven Battery #4', ST_GeomFromText('POLYGON((80.30 17.70, 80.31 17.70, 80.31 17.71, 80.30 17.71, 80.30 17.70))', 4326), 0.0),
                        ('ZONE_BF_02', 'Blast Furnace #2', ST_GeomFromText('POLYGON((80.32 17.70, 80.33 17.70, 80.33 17.71, 80.32 17.71, 80.32 17.70))', 4326), 0.0),
                        ('ZONE_SMS_01', 'Steel Melting Shop #1', ST_GeomFromText('POLYGON((80.34 17.70, 80.35 17.70, 80.35 17.71, 80.34 17.71, 80.34 17.70))', 4326), 0.0),
                        ('ZONE_ROLLING_03', 'Rolling Mill #3', ST_GeomFromText('POLYGON((80.30 17.72, 80.31 17.72, 80.31 17.73, 80.30 17.73, 80.30 17.72))', 4326), 0.0),
                        ('ZONE_GAS_HOLDER', 'Gas Holder Station', ST_GeomFromText('POLYGON((80.32 17.72, 80.33 17.72, 80.33 17.73, 80.32 17.73, 80.32 17.72))', 4326), 0.0),
                        ('ZONE_POWER_PLANT', 'Captive Power Plant', ST_GeomFromText('POLYGON((80.34 17.72, 80.35 17.72, 80.35 17.73, 80.34 17.73, 80.34 17.72))', 4326), 0.0);
                    """))
                conn.commit()
                print("[OK] Database tables initialized with seed data.")
                return
        except Exception as e:
            print(f"[WAIT] Waiting for DB (attempt {attempt+1}/15)... {e}")
            time.sleep(2)
    print("[FAIL] Failed to connect to database after 15 attempts.")


def execute_spatial_safety_check():
    """Find workers in hazardous zones with active hot work permits and elevated gas levels."""
    query = text("""
        SELECT 
            w.worker_id, 
            z.zone_name, 
            p.permit_id, 
            z.current_gas_lel_percentage 
        FROM 
            worker_telemetry w 
        JOIN 
            plant_zones z ON ST_Contains(z.geom, w.last_known_location) 
        JOIN 
            active_permits p ON p.zone_id = z.zone_id 
        WHERE 
            p.permit_type = 'HOT_WORK' 
            AND z.current_gas_lel_percentage > 10.0;
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            return [dict(row) for row in result.mappings()]
    except Exception as e:
        print(f"Spatial query error: {e}")
        return []


def update_zone_gas_level(zone_id: str, lel_percentage: float):
    """Update the current gas LEL percentage for a zone."""
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE plant_zones SET current_gas_lel_percentage = :lel WHERE zone_id = :zid"),
                {"lel": lel_percentage, "zid": zone_id}
            )
            conn.commit()
    except Exception as e:
        print(f"Error updating zone gas level: {e}")


def log_incident(zone_id: str, event_type: str, severity: str, description: str, dri_value: float):
    """Log a safety incident to the database."""
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO incident_log (zone_id, event_type, severity, description, dri_value) 
                    VALUES (:zid, :etype, :sev, :desc, :dri)
                """),
                {"zid": zone_id, "etype": event_type, "sev": severity, "desc": description, "dri": dri_value}
            )
            conn.commit()
    except Exception as e:
        print(f"Error logging incident: {e}")
