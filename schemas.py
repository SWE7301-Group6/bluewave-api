from marshmallow import Schema, fields, validate, pre_load, post_dump
from datetime import datetime
from dateutil import parser as dtparser
import pytz
from marshmallow import Schema, fields

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    role = fields.Str(validate=validate.OneOf(["admin", "researcher", "device"]))
    tier = fields.Str(validate=validate.OneOf(["processed", "raw"]))
    buoy_id = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)

class UserRegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    role = fields.Str(required=True, validate=validate.OneOf(["admin", "researcher", "device"]))
    tier = fields.Str(required=True, validate=validate.OneOf(["processed", "raw"]))
    buoy_id = fields.Str(allow_none=True)

class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)

class ObservationBaseSchema(Schema):
    id = fields.Int(dump_only=True)
    buoy_id = fields.Str(allow_none=True)

    # Stored as timezone-aware UTC in the DB; accepts ISO 8601 in requests.
    observed_at = fields.DateTime(required=True, metadata={"description": "ISO 8601 datetime"})
    timezone = fields.Str(allow_none=True, metadata={"description": "IANA timezone name"})

    # Coordinates
    latitude = fields.Float(required=True)
    longitude = fields.Float(required=True)

    # Environmental readings
    sea_surface_temp_c = fields.Float(allow_none=True)
    air_temp_c = fields.Float(allow_none=True)
    humidity_pct = fields.Float(allow_none=True)
    wind_speed_mps = fields.Float(allow_none=True)
    wind_direction_deg = fields.Float(allow_none=True)
    precipitation_mm = fields.Float(allow_none=True)
    haze = fields.Boolean(allow_none=True)

    # Scenario extras
    salinity_psu = fields.Float(allow_none=True)
    ph = fields.Float(allow_none=True)
    pollutant_index = fields.Float(allow_none=True)

    notes = fields.Str(allow_none=True)

    # Raw telemetry (only exposed to raw-tier/admin; dumped, not loaded)
    raw_payload = fields.Dict(dump_only=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @pre_load
    def combine_date_time(self, data, **kwargs):
        """
        Allow clients to send 'date' + 'time' (+ optional 'timezone') instead of 'observed_at'.
        We construct an ISO 8601 UTC timestamp for 'observed_at' and then remove the helper keys
        so they're not treated as unknown fields (avoids 422).
        """
        if isinstance(data, dict):
            if "observed_at" not in data and ("date" in data and "time" in data):
                tzname = data.get("timezone") or "UTC"
                dt_str = f"{data['date']}T{data['time']}"
                dt = dtparser.isoparse(dt_str)
                try:
                    tz = pytz.timezone(tzname)
                    # Localize then convert to UTC
                    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                        dt = tz.localize(dt)
                    dt = dt.astimezone(pytz.UTC)
                except Exception:
                    # Fallback: parse as-is and force UTC conversion if possible
                    dt = dtparser.isoparse(dt_str)
                    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                        # Treat naive as UTC
                        dt = dt.replace(tzinfo=pytz.UTC)
                    else:
                        dt = dt.astimezone(pytz.UTC)
                data["observed_at"] = dt.isoformat()

            # ✅ Remove helper keys so Marshmallow doesn't flag them as unknown
            data.pop("date", None)
            data.pop("time", None)

        return data

    @post_dump
    def ensure_isoformat(self, data, **kwargs):
        # Guarantee ISO 8601 strings on output for datetime fields
        for k in ["observed_at", "created_at", "updated_at"]:
            v = data.get(k)
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data

class ObservationCreateSchema(ObservationBaseSchema):
    pass

class ObservationUpdateSchema(Schema):
    """
    PATCH schema: all fields optional. (We intentionally do NOT accept 'date'/'time' here;
    clients should provide 'observed_at' directly for updates.)
    """
    buoy_id = fields.Str(allow_none=True)
    observed_at = fields.DateTime(allow_none=True)
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

class BulkItemsSchema(Schema):
    items = fields.List(fields.Nested(ObservationCreateSchema), required=True)

class BulkUpdateItemsSchema(Schema):
    # Each item must include 'id'; values are validated per ObservationUpdateSchema downstream
    items = fields.List(fields.Dict(), required=True)

class ObservationsListSchema(Schema):
    page = fields.Int(); page_size = fields.Int(); total = fields.Int()
    items = fields.List(fields.Nested(ObservationBaseSchema))

class TelemetryItemSchema(Schema):
    id = fields.Int(); buoy_id = fields.Str(allow_none=True)
    observed_at = fields.DateTime(allow_none=True)
    latitude = fields.Float(allow_none=True); longitude = fields.Float(allow_none=True)
    raw_payload = fields.Dict(); created_at = fields.DateTime(allow_none=True)

class TelemetryListSchema(Schema):
    page = fields.Int(); page_size = fields.Int(); total = fields.Int()
    items = fields.List(fields.Nested(TelemetryItemSchema))
