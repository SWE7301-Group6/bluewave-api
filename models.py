from datetime import datetime
from sqlalchemy import func
from db import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="researcher")  # admin, researcher, device
    tier = db.Column(db.String(50), nullable=False, default="processed")   # processed, raw
    buoy_id = db.Column(db.String(64), nullable=True)  # for device accounts
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

class Observation(db.Model):
    __tablename__ = "observations"
    id = db.Column(db.Integer, primary_key=True)
    buoy_id = db.Column(db.String(64), nullable=True, index=True)

    # When the observation was made (ISO 8601). Stored as timezone-aware UTC.
    observed_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    timezone = db.Column(db.String(64), nullable=True)  # IANA tz name if provided

    # Coordinates
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)

    # Environmental readings (optional where device lacks a sensor)
    sea_surface_temp_c = db.Column(db.Float, nullable=True)
    air_temp_c = db.Column(db.Float, nullable=True)
    humidity_pct = db.Column(db.Float, nullable=True)
    wind_speed_mps = db.Column(db.Float, nullable=True)
    wind_direction_deg = db.Column(db.Float, nullable=True)
    precipitation_mm = db.Column(db.Float, nullable=True)
    haze = db.Column(db.Boolean, nullable=True)

    # Optional additional indicators to reflect scenario (salinity, pH, pollutant index)
    salinity_psu = db.Column(db.Float, nullable=True)
    ph = db.Column(db.Float, nullable=True)
    pollutant_index = db.Column(db.Float, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    # Raw telemetry payload (JSON/dict) for raw-tier users
    raw_payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), index=True)
