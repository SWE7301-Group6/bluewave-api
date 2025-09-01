# observations.py
from flask_smorest import Blueprint, abort
from flask import request
from db import db
from models import Observation
from schemas import (
    ObservationBaseSchema,
    ObservationCreateSchema,
    ObservationUpdateSchema,
    BulkUpdateItemsSchema,
)
from flask_jwt_extended import jwt_required, get_jwt
from utils import require_roles, require_tiers, quarter_start, ensure_aware_utc
from datetime import datetime, timezone
from dateutil import parser as dtparser
from marshmallow import Schema, fields  
from typing import Optional
import math

blp = Blueprint(
    "Observations",
    "observations",
    url_prefix="/observations",
    description="Processed observation data",
)

LIST_SCHEMA = ObservationBaseSchema(many=True)
ITEM_SCHEMA = ObservationBaseSchema()
CREATE_SCHEMA = ObservationCreateSchema()
UPDATE_SCHEMA = ObservationUpdateSchema()

# ----------------- Helpers -----------------

def _block_if_old(obs: Observation):
    """Prevent edits/deletes if record is prior to current quarter (UTC)."""
    now_utc = datetime.now(timezone.utc)
    observed_utc = ensure_aware_utc(obs.observed_at)
    if observed_utc < quarter_start(now_utc):
        abort(409, message="Edits to records prior to the current quarter are not allowed.")

def _int_arg(name: str, default: int, *, minimum: int = 1, maximum: int = 500) -> int:
    """Parse an int query param, with sane defaults and clamping."""
    raw = request.args.get(name, None)
    try:
        val = int(raw) if raw not in (None, "") else default
    except Exception:
        val = default
    if val < minimum:
        val = minimum
    if maximum is not None and val > maximum:
        val = maximum
    return val

def _parse_iso_dt_optional(val: Optional[str], label: str):
    """Parse ISO8601 datetime if present, else None. 422 on failure."""
    if not val:
        return None
    try:
        return dtparser.isoparse(val)
    except Exception:
        abort(422, message=f"Invalid '{label}' ISO datetime")

def _apply_filters(q):
    """
    Apply supported filters directly and robustly:
      - start / end (or start_date / end_date), inclusive
      - buoy_id
      - bbox=min_lat,min_lon,max_lat,max_lon
      - latitude_min / latitude_max
      - longitude_min / longitude_max

    NOTE: If no params are provided, this applies **no filters** so
    default calls return the full dataset (ordered by observed_at DESC).
    """
    # time range (accept aliases for back-compat)
    start = request.args.get("start") or request.args.get("start_date")
    end = request.args.get("end") or request.args.get("end_date")
    start_dt = _parse_iso_dt_optional(start, "start")
    end_dt = _parse_iso_dt_optional(end, "end")
    if start_dt:
        q = q.filter(Observation.observed_at >= start_dt)
    if end_dt:
        q = q.filter(Observation.observed_at <= end_dt)

    # buoy_id
    buoy_id = request.args.get("buoy_id")
    if buoy_id:
        q = q.filter(Observation.buoy_id == buoy_id)

    # bbox: min_lat,min_lon,max_lat,max_lon
    bbox = request.args.get("bbox")
    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError
            min_lat, min_lon, max_lat, max_lon = parts
        except Exception:
            abort(422, message="Invalid 'bbox'. Expected 'min_lat,min_lon,max_lat,max_lon'")
        q = q.filter(Observation.latitude >= min_lat,
                     Observation.latitude <= max_lat,
                     Observation.longitude >= min_lon,
                     Observation.longitude <= max_lon)

    # individual lat/lon bounds
    def _as_float(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except Exception:
            abort(422, message="Latitude/longitude bounds must be numbers")

    lat_min = _as_float(request.args.get("latitude_min"))
    lat_max = _as_float(request.args.get("latitude_max"))
    lon_min = _as_float(request.args.get("longitude_min"))
    lon_max = _as_float(request.args.get("longitude_max"))

    if lat_min is not None:
        q = q.filter(Observation.latitude >= lat_min)
    if lat_max is not None:
        q = q.filter(Observation.latitude <= lat_max)
    if lon_min is not None:
        q = q.filter(Observation.longitude >= lon_min)
    if lon_max is not None:
        q = q.filter(Observation.longitude <= lon_max)

    return q

def _serialize_page(q):
    """
    Robust manual pagination:
      - defaults: page=1, page_size=50
      - clamps to [1..500]
      - sorts by observed_at DESC
      - if requested page is beyond last page, it snaps to the last page
        so users don't see an empty list accidentally.
    """
    page = _int_arg("page", 1, minimum=1, maximum=10_000)
    page_size = _int_arg("page_size", 50, minimum=1, maximum=500)

    total = q.count()
    q = q.order_by(Observation.observed_at.desc())

    
    last_page = max(1, math.ceil(total / page_size)) if total else 1
    if page > last_page:
        page = last_page

    offset = (page - 1) * page_size
    items = q.limit(page_size).offset(offset).all()

    claims = get_jwt()
    data = ObservationBaseSchema(many=True).dump(items)
    if claims.get("tier") != "raw" and claims.get("role") != "admin":
        for d in data:
            d.pop("raw_payload", None)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": data,
    }

# ----------------- Filters / list / get -----------------

@blp.route("", methods=["GET"])
@jwt_required()
@require_tiers("processed", "raw")
@blp.doc(parameters=[
  {"in":"query","name":"start","schema":{"type":"string","format":"date-time"},
   "description":"ISO 8601 start (inclusive), e.g. 2025-08-26T00:00:00Z"},
  {"in":"query","name":"end","schema":{"type":"string","format":"date-time"},
   "description":"ISO 8601 end (inclusive), e.g. 2025-08-27T00:00:00Z"},
  {"in":"query","name":"start_date","schema":{"type":"string","format":"date-time"},
   "description":"Alias of 'start' (back-compat)"},
  {"in":"query","name":"end_date","schema":{"type":"string","format":"date-time"},
   "description":"Alias of 'end' (back-compat)"},
  {"in":"query","name":"buoy_id","schema":{"type":"string"}},
  {"in":"query","name":"bbox","schema":{"type":"string"},"example":"-2,36.5,0,37",
   "description":"Bounding box: min_lat,min_lon,max_lat,max_lon"},
  {"in":"query","name":"latitude_min","schema":{"type":"number"}},
  {"in":"query","name":"latitude_max","schema":{"type":"number"}},
  {"in":"query","name":"longitude_min","schema":{"type":"number"}},
  {"in":"query","name":"longitude_max","schema":{"type":"number"}},
  {"in":"query","name":"page","schema":{"type":"integer","default":1}},
  {"in":"query","name":"page_size","schema":{"type":"integer","default":50}},
])
def list_observations():
    """
    List observations with parameter-based filtering & robust pagination.

    With **no query parameters**, this returns the most recent observations
    ordered by `observed_at` descending (i.e., default inputs show data).
    """
    q = Observation.query
    q = _apply_filters(q)
    return _serialize_page(q), 200

@blp.route("/<int:obs_id>", methods=["GET"])
@jwt_required()
@require_tiers("processed", "raw")
def get_observation(obs_id):
    obs = db.session.get(Observation, obs_id)
    if not obs:
        abort(404, message="Observation not found")
    data = ITEM_SCHEMA.dump(obs)
    claims = get_jwt()
    if claims.get("tier") != "raw" and claims.get("role") != "admin":
        data.pop("raw_payload", None)
    return data, 200

# ----------------- Create / Update / Delete -----------------

@blp.route("", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.arguments(ObservationCreateSchema)
@blp.response(201, ObservationBaseSchema)
def create_observation(body):
    claims = get_jwt()
    if claims.get("role") == "device":
        
        body["buoy_id"] = claims.get("buoy_id")
    
    obs = Observation(**body)
    db.session.add(obs)
    db.session.commit()
    return obs

@blp.route("/<int:obs_id>", methods=["PUT"])
@jwt_required()
@require_roles("admin")
@blp.arguments(ObservationCreateSchema)
@blp.response(200, ObservationBaseSchema)
def replace_observation(body, obs_id):
    obs = db.session.get(Observation, obs_id)
    if not obs:
        abort(404, message="Observation not found")
    _block_if_old(obs)
    for k, v in body.items():
        setattr(obs, k, v)
    db.session.commit()
    return obs

@blp.route("/<int:obs_id>", methods=["PATCH"])
@jwt_required()
@require_roles("admin")
@blp.arguments(ObservationUpdateSchema)
@blp.response(200, ObservationBaseSchema)
def update_observation(body, obs_id):
    obs = db.session.get(Observation, obs_id)
    if not obs:
        abort(404, message="Observation not found")
    _block_if_old(obs)
    for k, v in body.items():
        setattr(obs, k, v)
    db.session.commit()
    return obs

@blp.route("/<int:obs_id>", methods=["DELETE"])
@jwt_required()
@require_roles("admin")
def delete_observation(obs_id):
    obs = db.session.get(Observation, obs_id)
    if not obs:
        abort(404, message="Observation not found")
    _block_if_old(obs)
    db.session.delete(obs)
    db.session.commit()
    return {"message": "Deleted"}, 204

# ----------------- Bulk endpoints -----------------

class BulkCreateDocSchema(Schema):
    """
    Minimal schema so Swagger UI shows a request body for POST /observations/bulk.
    We keep validation loose: just require an 'items' list of dicts.
    """
    items = fields.List(fields.Dict(), required=True, description="List of observation objects to create")

def _normalize_observed_at_value(val):
    """Return a UTC-aware datetime for observed_at, or raise ValueError."""
    if val is None:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return ensure_aware_utc(val)
    if isinstance(val, str):
        try:
            return ensure_aware_utc(dtparser.isoparse(val))
        except Exception:
            raise ValueError("Invalid observed_at; must be ISO 8601 datetime")
    raise ValueError("Invalid observed_at type")

@blp.route("/bulk", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.arguments(BulkCreateDocSchema)  
def bulk_create(payload):
    """
    Create many observations in one request.
    Commit each successful item immediately so one bad item doesn't poison the session.
    """
    items_in = payload.get("items", [])
    if not isinstance(items_in, list):
        return {"message": "'items' must be a list"}, 400

    claims = get_jwt()
    created = []
    errors = []

    for i, item in enumerate(items_in):
        if not isinstance(item, dict):
            errors.append({"index": i, "error": "Item must be an object"})
            continue

        try:
            if claims.get("role") == "device":
                item["buoy_id"] = claims.get("buoy_id")

            if not item.get("buoy_id"):
                errors.append({"index": i, "error": "Missing required field 'buoy_id'"})
                continue

            item["observed_at"] = _normalize_observed_at_value(item.get("observed_at"))

            obs = Observation(**item)
            db.session.add(obs)
            db.session.commit()
            created.append(obs)
        except Exception as e:
            db.session.rollback()
            errors.append({"index": i, "error": str(e)})

    return {
        "created": ObservationBaseSchema(many=True).dump(created),
        "errors": errors
    }, (207 if errors else 201)

@blp.route("/bulk", methods=["PATCH"])
@jwt_required()
@require_roles("admin")
@blp.arguments(BulkUpdateItemsSchema)  
def bulk_update(payload):
    updated = []
    errors = []
    for i, item in enumerate(payload["items"]):
        obs_id = item.get("id")
        if not obs_id:
            errors.append({"index": i, "error": "Missing id"})
            continue
        obs = db.session.get(Observation, obs_id)
        if not obs:
            errors.append({"index": i, "error": f"Observation {obs_id} not found"})
            continue
        try:
            _block_if_old(obs)
            for k, v in item.items():
                if k == "id":
                    continue
                if k == "observed_at" and isinstance(v, str):
                    v = _normalize_observed_at_value(v)
                setattr(obs, k, v)
            db.session.commit()
            updated.append(obs)
        except Exception as e:
            db.session.rollback()
            errors.append({"index": i, "id": obs_id, "error": str(e)})
    return {
        "updated": ObservationBaseSchema(many=True).dump(updated),
        "errors": errors
    }, (207 if errors else 200)
