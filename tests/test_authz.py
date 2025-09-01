# tests/test_authz.py
import pytest

def test_telemetry_post_requires_role_device_or_admin(client, raw_user_token):
    # raw_user_token has role=user, so POST must be forbidden by require_roles
    res = client.post(
        "/telemetry",
        json={"observed_at": "2025-08-26T09:10:00Z"},
        headers={"Authorization": f"Bearer {raw_user_token}"}
    )
    assert res.status_code in (401, 403)

def test_telemetry_list_requires_raw_tier(client, processed_user_token):
    # processed tier is not allowed on /telemetry GET
    res = client.get("/telemetry", headers={"Authorization": f"Bearer {processed_user_token}"})
    assert res.status_code in (401, 403)

def test_observations_list_allows_processed_or_raw(client, processed_user_token):
    res = client.get("/observations", headers={"Authorization": f"Bearer {processed_user_token}"})
    # It can be empty initially, but must be authorized
    assert res.status_code == 200
