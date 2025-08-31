# BlueWave Solutions IoT Water API

Flask API for ingesting IoT buoy telemetry and serving processed environmental observations with role- and tier-based access.

## Features (mapped to user stories)

- **US-05 (Must, F):** Built with Flask. Run locally using Flask’s built-in server.
- **US-06 (Must, F):** Auto-generated **OpenAPI 3** spec and **Swagger UI** at `/docs` (via `flask-smorest`).
- **US-07 (Must, F):** Standard HTTP methods implemented across resources (GET, POST, PUT, PATCH, DELETE).
- **US-08 (Must, F):** JSON everywhere with `Content-Type: application/json`.
- **US-09 (Must, F):** Parameter-based filtering (`start`, `end`, `buoy_id`, `bbox`) + pagination.
- **US-10 (Must, F):** Observation fields include ISO 8601 timestamp (`observed_at`), timezone, coordinates, temperatures, humidity, wind, precipitation, haze, notes (+ salinity, pH, pollutant index).
- **US-11 (Should, F):** Edit guard: updates/deletes blocked for records prior to the **current quarter**.
- **US-12 (Should, F):** Bulk create and bulk patch endpoints with proper status codes (201/200/207).
- **US-13 (Should, NF):** **JWT** authentication with roles (`admin`, `researcher`, `device`) and data tiers (`processed`, `raw`).

Additionally (scenario-aligned):
- `/telemetry` POST for **raw ingestion**; raw payload preserved in DB.
- `/telemetry` GET for **raw-tier** users to access telemetry lake.
- `/observations` for **processed** data consumers (researchers); raw fields hidden unless tier = `raw` or role = `admin`.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run
python app.py  # Flask built-in server (http://localhost:5000)

# Seed some test users
python seed.py
```

### Swagger / OpenAPI

- OpenAPI JSON: `/openapi.json`
- Swagger UI: `/docs`

### Authentication

1. **Login** (get JWT):
   ```bash
   curl -X POST http://localhost:5000/auth/login -H "Content-Type: application/json"      -d '{"email":"admin@bluewave.io","password":"AdminPass123!"}'
   ```
   Copy the `access_token` and use it like:
   ```bash
   curl -H "Authorization: Bearer <token>" http://localhost:5000/observations
   ```

2. **Register a user** (admin-only):
   ```bash
   curl -X POST http://localhost:5000/auth/register      -H "Authorization: Bearer <ADMIN_TOKEN>" -H "Content-Type: application/json"      -d '{"email":"new@org.org","password":"Passw0rd!","role":"researcher","tier":"processed"}'
   ```

### Observations (processed)

- **GET /observations** with filters:
  - `start` / `end`: ISO 8601 datetimes
  - `buoy_id`: exact match
  - `bbox`: `min_lat,min_lon,max_lat,max_lon`
  - Pagination: `page`, `page_size`

- **POST /observations** (admin/device)
- **GET /observations/{id}**
- **PUT /observations/{id}** (admin, blocked if record before current quarter)
- **PATCH /observations/{id}** (admin, blocked if record before current quarter)
- **DELETE /observations/{id}** (admin, blocked if record before current quarter)

- **Bulk**:
  - **POST /observations/bulk** create many
  - **PATCH /observations/bulk** update many (each item must include `id`)
  - Mixed results return **207 Multi-Status**

### Telemetry (raw)

- **POST /telemetry** (admin/device): accept arbitrary JSON, stores `raw_payload` and mapped fields.
- **GET /telemetry** (tier `raw` or admin): paginated raw payloads.

### Data model (core)

Observation:
- `observed_at` (ISO 8601, timezone-aware; accepts `date`+`time`+`timezone` in requests)
- `timezone`
- `latitude`, `longitude`
- `sea_surface_temp_c`, `air_temp_c`, `humidity_pct`
- `wind_speed_mps`, `wind_direction_deg`
- `precipitation_mm`, `haze`
- `salinity_psu`, `ph`, `pollutant_index`
- `notes`
- `raw_payload` (JSON; raw-tier only)

### MoSCoW (US-01, process artefact)

See `docs/moscow_backlog.json` for categorised user stories reflecting priorities agreed before Sprint Planning.

## Running with different DB

Set `DATABASE_URL` env var (e.g., `postgresql+psycopg://user:pass@host/db`).

## Tests

You can extend with pytest easily; core routes are modular Blueprints.
