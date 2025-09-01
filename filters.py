# filters.py
# Parameter-based filtering for Observation queries.
# Meets DoD: supports date range + location query params and reduces returned items.

from sqlalchemy import and_
from dateutil import parser as dtparser
from flask_smorest import abort

from models import Observation
from utils import ensure_aware_utc


def _parse_dt(val: str):
    """Parse ISO-8601 to a UTC-aware datetime. Returns None if empty/invalid."""
    if not val:
        return None
    try:
        dt = dtparser.isoparse(val)
        return ensure_aware_utc(dt)
    except Exception:
        return None


def apply_observation_filters(query, args):
    """
    Supported query parameters (all optional):

      Time window (ISO-8601):
        - start, end
        - (aliases) start_date, end_date

      Location:
        - bbox = min_lat,min_lon,max_lat,max_lon
        - latitude_min, latitude_max
        - longitude_min, longitude_max

      Other:
        - buoy_id (exact match)

    Pagination (page, page_size) is handled in the view, not here.
    """

    # --- Time window ---
    start = args.get("start") or args.get("start_date")
    end   = args.get("end")   or args.get("end_date")

    start_dt = _parse_dt(start)
    end_dt   = _parse_dt(end)

    if start and start_dt is None:
        abort(400, message="Invalid 'start' datetime. Use ISO 8601 (e.g., 2025-08-26T00:00:00Z).")
    if end and end_dt is None:
        abort(400, message="Invalid 'end' datetime. Use ISO 8601 (e.g., 2025-08-27T00:00:00Z).")

    if start_dt is not None:
        query = query.filter(Observation.observed_at >= start_dt)
    if end_dt is not None:
        query = query.filter(Observation.observed_at <= end_dt)

    # --- Buoy exact match ---
    buoy_id = args.get("buoy_id")
    if buoy_id:
        query = query.filter(Observation.buoy_id == buoy_id)

    # --- Bounding box (preferred location filter) ---
    bbox = args.get("bbox")
    if bbox:
        try:
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox requires 4 comma-separated numbers.")
            min_lat, min_lon, max_lat, max_lon = map(float, parts)
            if min_lat > max_lat or min_lon > max_lon:
                raise ValueError("bbox min values must be <= max values.")
        except Exception as e:
            abort(400, message=f"Invalid bbox: {e}. Use min_lat,min_lon,max_lat,max_lon")

        query = query.filter(and_(
            Observation.latitude  >= min_lat,
            Observation.latitude  <= max_lat,
            Observation.longitude >= min_lon,
            Observation.longitude <= max_lon
        ))

    # --- Individual min/max ranges (also supported) ---
    lat_min = args.get("latitude_min")
    lat_max = args.get("latitude_max")
    lon_min = args.get("longitude_min")
    lon_max = args.get("longitude_max")

    def _to_float_or_400(name, val):
        if val is None or val == "":
            return None
        try:
            return float(val)
        except ValueError:
            abort(400, message=f"Invalid '{name}': must be a number.")

    lat_min_f = _to_float_or_400("latitude_min", lat_min)
    lat_max_f = _to_float_or_400("latitude_max", lat_max)
    lon_min_f = _to_float_or_400("longitude_min", lon_min)
    lon_max_f = _to_float_or_400("longitude_max", lon_max)

    if lat_min_f is not None:
        query = query.filter(Observation.latitude >= lat_min_f)
    if lat_max_f is not None:
        query = query.filter(Observation.latitude <= lat_max_f)
    if lon_min_f is not None:
        query = query.filter(Observation.longitude >= lon_min_f)
    if lon_max_f is not None:
        query = query.filter(Observation.longitude <= lon_max_f)

    return query
