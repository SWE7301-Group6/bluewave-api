from flask_smorest import Blueprint, abort
from flask import request, jsonify
from sqlalchemy import and_
from db import db
from models import Observation
from schemas import ObservationBaseSchema, ObservationCreateSchema, ObservationUpdateSchema, BulkItemsSchema, BulkUpdateItemsSchema
from flask_jwt_extended import jwt_required, get_jwt
from utils import require_roles, require_tiers, quarter_start
from datetime import datetime, timezone
from dateutil import parser as dtparser
from utils import require_roles, require_tiers, quarter_start, ensure_aware_utc
from filters import apply_observation_filters

blp = Blueprint("Observations", "observations", url_prefix="/observations", description="Processed observation data")

LIST_SCHEMA = ObservationBaseSchema(many=True)
ITEM_SCHEMA = ObservationBaseSchema()
CREATE_SCHEMA = ObservationCreateSchema()
UPDATE_SCHEMA = ObservationUpdateSchema()

def list_observations():
    query = Observation.query
    query = apply_observation_filters(query, request.args)  # <-- single call
    return _serialize_list(query), 200

def _block_if_old(obs: Observation):
    # Prevent edits/deletes if prior to current quarter (UTC)
    now_utc = datetime.now(timezone.utc)
    observed_utc = ensure_aware_utc(obs.observed_at)
    if observed_utc < quarter_start(now_utc):
        abort(409, message="Edits to records prior to the current quarter are not allowed.")

def _serialize_list(query):
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    items = query.order_by(Observation.observed_at.desc()).paginate(page=page, per_page=page_size, error_out=False)
    claims = get_jwt()
    data = LIST_SCHEMA.dump(items.items)
    # Hide raw_payload for processed tier
    if claims.get("tier") != "raw" and claims.get("role") != "admin":
        for d in data:
            d.pop("raw_payload", None)
    return {
        "page": page,
        "page_size": page_size,
        "total": items.total,
        "items": data
    }

@blp.route("", methods=["GET"])
@jwt_required()
@require_tiers("processed", "raw")
def list_observations():
    query = Observation.query
    query = _apply_filters(query)
    return _serialize_list(query), 200

@blp.route("/<int:obs_id>", methods=["GET"])
@jwt_required()
@require_tiers("processed", "raw")
def get_observation(obs_id):
    obs = Observation.query.get_or_404(obs_id)
    data = ITEM_SCHEMA.dump(obs)
    claims = get_jwt()
    if claims.get("tier") != "raw" and claims.get("role") != "admin":
        data.pop("raw_payload", None)
    return data, 200

@blp.route("", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.arguments(ObservationCreateSchema)
@blp.response(201, ObservationBaseSchema)
def create_observation(body):
    claims = get_jwt()
    if claims.get("role") == "device":
        # overwrite buoy_id with token's buoy_id for integrity
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
    obs = Observation.query.get_or_404(obs_id)
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
    obs = Observation.query.get_or_404(obs_id)
    _block_if_old(obs)
    for k, v in body.items():
        setattr(obs, k, v)
    db.session.commit()
    return obs

@blp.route("/<int:obs_id>", methods=["DELETE"])
@jwt_required()
@require_roles("admin")
def delete_observation(obs_id):
    obs = Observation.query.get_or_404(obs_id)
    _block_if_old(obs)
    db.session.delete(obs)
    db.session.commit()
    return {"message": "Deleted"}, 204

# Bulk endpoints
@blp.route("/bulk", methods=["POST"])
@jwt_required()
@require_roles("admin", "device")
@blp.arguments(BulkItemsSchema)
def bulk_create(payload):
    claims = get_jwt()
    created = []
    errors = []
    for i, item in enumerate(payload["items"]):
        try:
            if claims.get("role") == "device":
                item["buoy_id"] = claims.get("buoy_id")
            obs = Observation(**item)
            db.session.add(obs)
            created.append(obs)
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    db.session.commit()
    return {"created": ObservationBaseSchema(many=True).dump(created), "errors": errors}, (207 if errors else 201)

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
        obs = Observation.query.get(obs_id)
        if not obs:
            errors.append({"index": i, "error": f"Observation {obs_id} not found"})
            continue
        try:
            _block_if_old(obs)
            for k, v in item.items():
                if k == "id": 
                    continue
                setattr(obs, k, v)
            updated.append(obs)
        except Exception as e:
            errors.append({"index": i, "id": obs_id, "error": str(e)})
    db.session.commit()
    return {"updated": ObservationBaseSchema(many=True).dump(updated), "errors": errors}, (207 if errors else 200)
