# tests/test_observations.py
from datetime import datetime, timezone, timedelta
from utils import quarter_start

def _mk_obs_body(ts_iso="2025-08-26T10:00:00Z", buoy="BW-OBS-0001"):
    return {
        "buoy_id": buoy,
        "observed_at": ts_iso,
        "latitude": 1.0,
        "longitude": 2.0,
        "sea_surface_temp_c": 20.5,
    }

def test_create_and_get_observation(client, admin_token):
    res = client.post("/observations", json=_mk_obs_body(), headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201, res.get_json()
    created = res.get_json()
    oid = created["id"]

    res2 = client.get(f"/observations/{oid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 200
    got = res2.get_json()
    assert got["buoy_id"] == "BW-OBS-0001"
    assert "raw_payload" in got  # admin can see raw_payload

def test_list_observations_hides_raw_for_processed_tier(client, processed_user_token, admin_token):
    # seed one
    client.post("/observations", json=_mk_obs_body(), headers={"Authorization": f"Bearer {admin_token}"})

    res = client.get("/observations", headers={"Authorization": f"Bearer {processed_user_token}"})
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["total"] >= 1
    # processed tier should not see raw_payload
    assert all("raw_payload" not in item for item in payload["items"])

def test_bulk_create_and_partial_errors(client, admin_token):
    body = {
        "items": [
            _mk_obs_body("2025-08-26T10:01:00Z", "BW-BULK-1"),
            {"observed_at": "2025-08-26T10:02:00Z"},  # missing required buoy_id will likely error via schema/model
        ]
    }
    res = client.post("/observations/bulk", json=body, headers={"Authorization": f"Bearer {admin_token}"})
    # Could be 201 or 207 depending on your model validation; we accept both
    assert res.status_code in (201, 207)
    payload = res.get_json()
    assert "created" in payload and "errors" in payload
    assert len(payload["created"]) >= 1

def test_bulk_update_with_missing_id_gives_error(client, admin_token):
    # Create two
    ids = []
    for i in range(2):
        res = client.post("/observations", json=_mk_obs_body(f"2025-08-26T10:0{i}:00Z", f"BW-INIT-{i}"),
                          headers={"Authorization": f"Bearer {admin_token}"})
        ids.append(res.get_json()["id"])

    patch_body = {
        "items": [
            {"id": ids[0], "notes": "updated-a"},
            {"notes": "missing-id"},  # should trigger "Missing id"
        ]
    }
    res = client.patch("/observations/bulk", json=patch_body, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code in (200, 207)
    payload = res.get_json()
    assert any(err.get("error") == "Missing id" for err in payload["errors"])

def test_replace_and_update_observation(client, admin_token):
    res = client.post("/observations", json=_mk_obs_body(), headers={"Authorization": f"Bearer {admin_token}"})
    oid = res.get_json()["id"]

    # PUT (replace)
    body_replace = _mk_obs_body("2025-08-27T11:00:00Z", "BW-OBS-0002")
    res_put = client.put(f"/observations/{oid}", json=body_replace, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_put.status_code == 200
    assert res_put.get_json()["buoy_id"] == "BW-OBS-0002"

    # PATCH (partial)
    res_patch = client.patch(f"/observations/{oid}", json={"notes": "patched"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_patch.status_code == 200
    assert res_patch.get_json()["notes"] == "patched"

def test_no_edits_before_current_quarter(client, admin_token, app):
    # Make an observation dated strictly before the start of the current quarter
    now = datetime.now(timezone.utc)
    qstart = quarter_start(now)
    old_ts = (qstart - timedelta(days=1)).isoformat()

    res = client.post("/observations", json=_mk_obs_body(old_ts, "BW-OLD-1"),
                      headers={"Authorization": f"Bearer {admin_token}"})
    oid = res.get_json()["id"]

    # Attempt to patch should fail with 409
    res_patch = client.patch(f"/observations/{oid}", json={"notes": "should-fail"},
                             headers={"Authorization": f"Bearer {admin_token}"})
    assert res_patch.status_code == 409
