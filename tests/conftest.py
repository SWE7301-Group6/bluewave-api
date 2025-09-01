# tests/conftest.py
import os
import pytest
from datetime import datetime, timezone
from flask_jwt_extended import create_access_token

from app import create_app, db as _db

@pytest.fixture(scope="session")
def app():
    # Build a testing app
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="test-secret",
        PROPAGATE_EXCEPTIONS=True,
        # Make errors bubble up to tests
        API_TITLE="BlueWave API (tests)",
        API_VERSION="1.0-test",
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def db(app):
    return _db

def make_token(app, *, role="user", tier="processed", **extra):
    """
    Create a JWT with the claims your decorators expect:
      - role: "admin" | "device" | "user"
      - tier: "raw" | "processed"
      - buoy_id: for device role, e.g. "BW-BOUY-0001"
    """
    with app.app_context():
        claims = {"role": role, "tier": tier}
        claims.update(extra or {})
        return create_access_token(identity="test-user", additional_claims=claims)

@pytest.fixture()
def admin_token(app):
    return make_token(app, role="admin", tier="raw")

@pytest.fixture()
def processed_user_token(app):
    # Has processed data tier (can access /observations list)
    return make_token(app, role="user", tier="processed")

@pytest.fixture()
def raw_user_token(app):
    # Can access /telemetry list
    return make_token(app, role="user", tier="raw")

@pytest.fixture()
def device_token(app):
    # Device token cannot spoof buoy_id in POST /telemetry
    return make_token(app, role="device", tier="raw", buoy_id="BW-DEV-0001")

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
