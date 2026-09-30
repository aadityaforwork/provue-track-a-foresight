import json
from challenge.app.server import create_app
from tests.conftest import FS1, FS2


def client():
    return create_app().test_client()


def test_forecasts_leaks_fs1_hint():
    r = client().get("/api/v1/forecasts")
    assert r.status_code == 200
    assert r.get_json()["_meta"]["hint"] == FS1


def test_login_with_demo_creds_returns_token():
    r = client().post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst"})
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_with_bad_creds_401():
    r = client().post("/api/v1/auth/login", json={"username": "analyst", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_token_and_returns_fs2():
    c = client()
    tok = c.post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst"}).get_json()["token"]
    r = c.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.get_json()["hint"] == FS2


def test_me_without_header_is_401_not_500():
    r = client().get("/api/v1/me")
    assert r.status_code == 401
