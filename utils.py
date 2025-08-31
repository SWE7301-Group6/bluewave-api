from datetime import datetime, timezone
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def quarter_start(dt: datetime) -> datetime:
    # Compute start of the current quarter (UTC) for edit-protection
    q_month = ((dt.month - 1) // 3) * 3 + 1
    return datetime(dt.year, q_month, 1, tzinfo=timezone.utc)

def ensure_aware_utc(dt: datetime) -> datetime:
    """Return a UTC-aware datetime (treat naive as UTC)."""
    if dt is None:
        return None
    # tz-naive or tzinfo with no offset => treat as UTC
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in roles:
                return jsonify({"message": "Forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_tiers(*tiers):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("tier") not in tiers and claims.get("role") != "admin":
                return jsonify({"message": "Forbidden: insufficient data tier"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def current_user_claims():
    verify_jwt_in_request(optional=True)
    try:
        return get_jwt()
    except Exception:
        return {}
