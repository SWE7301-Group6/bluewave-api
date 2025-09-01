# telemetry.py
from flask_smorest import Blueprint, abort
from flask import request
from db import db
from models import Observation
from flask_jwt_extended import jwt_required, get_jwt
from utils import require_roles, require_tiers, ensure_aware_utc
from datetime import datetime, timezone, date as dt_date, time as dt_time
from dateutil import parser as dtparser
from dateutil import tz as dttz
from marshmallow import Schema, fields

blp = Blueprint(
    "Telemetry",
    "telemetry",
    url_prefix="/telemetry",
    description="Raw telemetry ingestion & access",
)

# ---- Request body schema so Swagger shows a JSON editor & sets Content-Type ----
class TelemetryIngestSchema(Schema):
    buoy_id = fields.Str(required=False)              
    observed_at = fields.DateTime(allow_none=True)    
    date = fields.Date(allow_none=True)               
    time = fields.Time(allow_none=True)               
    timezone = fields.Str(allow_none=True)            
    latitude = fields.Float(allow_none=True)
    longitude = fields.Float(allow_none=True)
    sea_surface_temp_c = fields.Float(allow_none=True)
    air_temp_c = fields.Float(allow_none=True)
    humidity_pct = fields.Float(allow_none=True)
    wind_speed_mps = fields.Float(allow_none=True)
    wind_direction_deg = fields.Float(allow_none=True)
    precipitation_mm = fields.Float(allow_none=True)
    haze = fields.Boolean(allow_none=True)
    salinity_psu = fields.Float(allow_none=True)
    ph = fields.Float(allow_none=True)
    pollutant_index = fields.Float(allow_none=True)
    notes = fields.Str(allow_none=True)
    sensors = fields.Dict(allow_none=True)            
    extra = fields.Dict(allow_none=True)              


def _json_safe(obj):
    """Recursively convert datetime/date/time to ISO strings so JSON column accepts it."""
    if isinstance(obj, (datetime, dt_date, dt_time)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_json_safe(v) for v in obj)
    return obj


def _int_arg(name, default):
    """Robust int parsing for query params with sensible defaults."""
    try:
        val = request.args.get(name, None)
        return int(val) if val not in (None, "") else default
    except Exception:
        return default


@blp.route("", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.arguments(TelemetryIngestSchema)   
@blp.response(201)
def ingest(body):
    if not isinstance(body, dict):
        abort(400, message="JSON body required")

    claims = get_jwt()

    # Map known fields (others remain only in raw_payload)
    known_keys = [
        "buoy_id", "timezone", "latitude", "longitude",
        "sea_surface_temp_c", "air_temp_c", "humidity_pct",
        "wind_speed_mps", "wind_direction_deg", "precipitation_mm", "haze",
        "salinity_psu", "ph", "pollutant_index", "notes"
    ]
    known = {k: body.get(k) for k in known_keys if k in body}

    # Device role cannot spoof buoy_id
    if claims.get("role") == "device":
        known["buoy_id"] = claims.get("buoy_id")

    # --- Normalize observed_at to UTC-aware datetime ---
    val = body.get("observed_at")
    if val is not None:
        # Case 1: observed_at provided (Marshmallow may have parsed it already)
        if isinstance(val, datetime):
            dt_val = val
        elif isinstance(val, str):
            try:
                dt_val = dtparser.isoparse(val)
            except Exception:
                abort(422, message="Invalid observed_at. Use ISO 8601 (e.g., 2025-08-26T09:10:00Z).")
        else:
            abort(422, message="Invalid observed_at type.")
        known["observed_at"] = ensure_aware_utc(dt_val)

    elif body.get("date") is not None and body.get("time") is not None:
        # Case 2: date + time (+ optional timezone)
        tzname = body.get("timezone") or "UTC"
        d, t = body.get("date"), body.get("time")

        # Combine date+time whether parsed or string
        if isinstance(d, dt_date) and isinstance(t, dt_time):
            dt_local = datetime.combine(d, t)
        else:
            iso_local = f"{d}T{t}"
            try:
                dt_local = dtparser.isoparse(iso_local)
            except Exception:
                abort(422, message="Invalid date/time. Expect date like 2025-08-26 and time like 09:10:00.")

        tzinfo = dttz.gettz(tzname)
        if tzinfo is None:
            abort(422, message=f"Invalid timezone '{tzname}'. Use a valid IANA name, e.g., 'UTC'.")

        if dt_local.tzinfo is None or dt_local.tzinfo.utcoffset(dt_local) is None:
            dt_local = dt_local.replace(tzinfo=tzinfo)

        known["observed_at"] = ensure_aware_utc(dt_local)

    else:
        # Case 3: default to now (UTC)
        known["observed_at"] = datetime.now(timezone.utc)
    # --- end observed_at normalize ---

    # Ensure raw_payload is JSON-serializable (dates -> strings)
    raw_payload = _json_safe(body)

    obs = Observation(**known, raw_payload=raw_payload)
    db.session.add(obs)
    db.session.commit()
    return {"id": obs.id, "message": "Ingested"}, 201


@blp.route("", methods=["GET"])
@jwt_required()
@require_tiers("raw")
@blp.doc(parameters=[
    {"in":"query","name":"page","schema":{"type":"integer","default":1}},
    {"in":"query","name":"page_size","schema":{"type":"integer","default":50}},
    {"in":"query","name":"buoy_id","schema":{"type":"string"}},
    {"in":"query","name":"start","schema":{"type":"string","format":"date-time"},
     "description":"ISO 8601 start (inclusive)"},
    {"in":"query","name":"end","schema":{"type":"string","format":"date-time"},
     "description":"ISO 8601 end (inclusive)"},
])
def list_raw():
    """List recent telemetry with optional filters."""
    from sqlalchemy import desc

    page = _int_arg("page", 1)
    page_size = _int_arg("page_size", 50)

    q = Observation.query

    # Optional filters: buoy_id, start/end on observed_at
    buoy_id = request.args.get("buoy_id")
    if buoy_id:
        q = q.filter(Observation.buoy_id == buoy_id)

    start = request.args.get("start")
    if start:
        try:
            q = q.filter(Observation.observed_at >= dtparser.isoparse(start))
        except Exception:
            # explicit JSON to keep message predictable for tests/clients
            return {"message": "Invalid 'start' ISO datetime"}, 422

    end = request.args.get("end")
    if end:
        try:
            q = q.filter(Observation.observed_at <= dtparser.isoparse(end))
        except Exception:
            
            return {"message": "Invalid 'end' ISO datetime"}, 422

    q = q.order_by(desc(Observation.created_at)).paginate(
        page=page, per_page=page_size, error_out=False
    )

    # Serialize to JSON-friendly primitives
    items = []
    for obs in q.items:
        items.append({
            "id": obs.id,
            "buoy_id": obs.buoy_id,
            "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
            "latitude": obs.latitude,
            "longitude": obs.longitude,
            "raw_payload": obs.raw_payload,
            "created_at": obs.created_at.isoformat() if obs.created_at else None,
        })

    return {
        "page": page,
        "page_size": page_size,
        "total": q.total,
        "items": items,
    }, 200


@blp.route("/<int:obs_id>", methods=["GET"])
@jwt_required()
@require_tiers("raw")
def get_raw_by_id(obs_id: int):
    """Fetch a single telemetry record by id."""
    obs = db.session.get(Observation, obs_id)
    if not obs:
        abort(404, message="Observation not found")
    return {
        "id": obs.id,
        "buoy_id": obs.buoy_id,
        "observed_at": obs.observed_at.isoformat() if obs.observed_at else None,
        "latitude": obs.latitude,
        "longitude": obs.longitude,
        "raw_payload": obs.raw_payload,
        "created_at": obs.created_at.isoformat() if obs.created_at else None,
    }, 200
