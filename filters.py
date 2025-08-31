# filters.py

from models import Observation
from sqlalchemy import and_
from dateutil import parser as dtparser

def apply_observation_filters(query, args):
    """
    Apply common filters to Observation query based on request arguments.
    
    Supported filters:
    - buoy_id: string
    - start_date / end_date: ISO format date strings
    - latitude_min / latitude_max
    - longitude_min / longitude_max
    """
    
    # Filter by buoy_id
    buoy_id = args.get("buoy_id")
    if buoy_id:
        query = query.filter(Observation.buoy_id == buoy_id)
    
    # Filter by observed_at date range
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    if start_date:
        try:
            start_dt = dtparser.isoparse(start_date)
            query = query.filter(Observation.observed_at >= start_dt)
        except Exception:
            pass  # optionally log error
    
    if end_date:
        try:
            end_dt = dtparser.isoparse(end_date)
            query = query.filter(Observation.observed_at <= end_dt)
        except Exception:
            pass
    
    # Filter by latitude
    lat_min = args.get("latitude_min")
    lat_max = args.get("latitude_max")
    if lat_min:
        try:
            query = query.filter(Observation.latitude >= float(lat_min))
        except ValueError:
            pass
    if lat_max:
        try:
            query = query.filter(Observation.latitude <= float(lat_max))
        except ValueError:
            pass

    # Filter by longitude
    lon_min = args.get("longitude_min")
    lon_max = args.get("longitude_max")
    if lon_min:
        try:
            query = query.filter(Observation.longitude >= float(lon_min))
        except ValueError:
            pass
    if lon_max:
        try:
            query = query.filter(Observation.longitude <= float(lon_max))
        except ValueError:
            pass

    return query
