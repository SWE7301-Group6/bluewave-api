# telemetry.py
from flask_smorest import Blueprint, abort
from flask import request
from db import db
from models import Observation
from flask_jwt_extended import jwt_required, get_jwt
from utils import require_roles, require_tiers, ensure_aware_utc  # <-- add ensure_aware_utc
from datetime import datetime, timezone
from schemas import TelemetryListSchema
from dateutil import parser as dtparser  # <-- add dtparser
from dateutil import tz as dttz


blp = Blueprint("Telemetry", "telemetry", url_prefix="/telemetry", description="Raw telemetry ingestion & access")

@blp.route("", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.response(201)
def ingest():
    payload = request.get_json()
    if not payload:
        abort(400, message="JSON body required")

    claims = get_jwt()

    # Map known fields (others remain only in raw_payload)
    known = {k: payload.get(k) for k in [
        "buoy_id","timezone","latitude","longitude",
        "sea_surface_temp_c","air_temp_c","humidity_pct",
        "wind_speed_mps","wind_direction_deg","precipitation_mm","haze",
        "salinity_psu","ph","pollutant_index","notes"
    ] if k in payload}

    # integrity: device role can't spoof buoy_id
    if claims.get("role") == "device":
        known["buoy_id"] = claims.get("buoy_id")

    # --- FIX: normalize observed_at to a Python datetime (UTC-aware) ---
        # --- ROBUST observed_at handling ---
    if "observed_at" in payload and payload["observed_at"]:
        # Case 1: observed_at provided (ISO 8601)
        try:
            dt = dtparser.isoparse(payload["observed_at"])
            known["observed_at"] = ensure_aware_utc(dt)
        except Exception:
            abort(422, message="Invalid observed_at format. Use ISO 8601 (e.g., 2025-08-26T09:10:00Z).")

    elif payload.get("date") and payload.get("time"):
        # Case 2: date + time (+ optional timezone)
        tzname = payload.get("timezone") or "UTC"
        iso_local = f"{payload['date']}T{payload['time']}"
        try:
            dt_local = dtparser.isoparse(iso_local)
        except Exception:
            abort(422, message="Invalid date/time. Expected date like 2025-08-26 and time like 09:10:00.")
        # attach timezone if naive
        tzinfo = dttz.gettz(tzname)
        if tzinfo is None:
            abort(422, message=f"Invalid timezone '{tzname}'. Use a valid IANA tz, e.g., 'UTC' or 'Europe/London'.")
        if dt_local.tzinfo is None or dt_local.tzinfo.utcoffset(dt_local) is None:
            dt_local = dt_local.replace(tzinfo=tzinfo)
        # normalize to UTC
        known["observed_at"] = ensure_aware_utc(dt_local)

    else:
        # Case 3: default to now (UTC)
        known["observed_at"] = datetime.now(timezone.utc)
    # --- end robust observed_at handling ---

    # -------------------------------------------------------------------

    obs = Observation(**known, raw_payload=payload)
    db.session.add(obs)
    db.session.commit()
    return {"id": obs.id, "message": "Ingested"}, 201

@blp.route("", methods=["GET"])
@jwt_required()
@require_tiers("raw")
@blp.response(200, TelemetryListSchema)
def list_raw():
    from sqlalchemy import desc
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    q = Observation.query.order_by(desc(Observation.created_at)).paginate(page=page, per_page=page_size, error_out=False)
    items = []
    for obs in q.items:
        items.append({
            "id": obs.id,
            "buoy_id": obs.buoy_id,
            "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
            "latitude": obs.latitude,
            "longitude": obs.longitude,
            "raw_payload": obs.raw_payload,
            "created_at": obs.created_at.isoformat() if obs.created_at else None
        })
    return {"page": page, "page_size": page_size, "total": q.total, "items": items}, 200
