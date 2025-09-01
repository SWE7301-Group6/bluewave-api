# tests/test_telemetry.py
from datetime import datetime, timezone, timedelta

def test_post_telemetry_with_observed_at_iso(client, device_token):
    body = {
        "observed_at": "2025-08-26T11:00:00Z",
        "latitude": -1.23,
        "longitude": 36.78,
        "sensors": {"turbidity": 1.2},
        "notes": "sample"
    }
    res = client.post("/telemetry", json=body, headers={"Authorization": f"Bearer {device_token}"})
    assert res.status_code == 201, res.get_json()
    data = res.get_json()
    assert "id" in data

    # Fetch it back by id
    rid = data["id"]
    res2 = client.get(f"/telemetry/{rid}", headers={"Authorization": f"Bearer {device_token}"})
    assert res2.status_code == 200
    got = res2.get_json()
    assert got["buoy_id"] == "BW-DEV-0001"   
    assert got["raw_payload"]["sensors"]["turbidity"] == 1.2

def test_post_telemetry_with_date_time_timezone_is_json_safe(client, admin_token):
    # Use date+time form; ensure raw_payload stores strings (JSON-safe)
    body = {
        "date": "2025-08-26",
        "time": "11:05:06",
        "timezone": "UTC",
        "latitude": 0.1,
        "longitude": 0.2,
    }
    res = client.post("/telemetry", json=body, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201, res.get_json()
    rid = res.get_json()["id"]

    res2 = client.get(f"/telemetry/{rid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 200
    got = res2.get_json()
    # raw_payload date/time should be strings (no datetime objects)
    assert isinstance(got["raw_payload"]["date"], str)
    assert isinstance(got["raw_payload"]["time"], str)

def test_get_telemetry_pagination_and_filters(client, admin_token):
    # Create several telemetry rows
    for i in range(3):
        res = client.post(
            "/telemetry",
            json={
                "observed_at": f"2025-08-26T0{i}:00:00Z",
                "latitude": i * 1.0,
                "longitude": i * 2.0,
                "buoy_id": f"BW-BOUY-{i:04d}",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 201

    # Default list (page=1)
    res = client.get("/telemetry", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    payload = res.get_json()
    assert "items" in payload
    assert payload["page"] == 1
    assert payload["total"] >= 3

    # Filter by buoy_id
    res2 = client.get(
        "/telemetry?buoy_id=BW-BOUY-0001",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res2.status_code == 200
    items = res2.get_json()["items"]
    assert all(item["buoy_id"] == "BW-BOUY-0001" for item in items)

def test_get_telemetry_invalid_start_is_422(client, admin_token):
    res = client.get("/telemetry?start=not-a-date", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    msg = res.get_json().get("message", "").lower()
    assert "invalid 'start'" in msg or "invalid" in msg
