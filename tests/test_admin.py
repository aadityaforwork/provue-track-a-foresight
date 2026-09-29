import jwt
from challenge.app.server import create_app
from tests.conftest import FS3


def client():
    return create_app().test_client()


def forge(role, mfa):
    return jwt.encode({"sub": "x", "role": role, "mfa": mfa}, key="", algorithm="none")


def test_admin_feeds_requires_auth():
    r = client().get("/api/v1/admin/feeds")
    assert r.status_code == 401
    assert FS3 not in r.get_data(as_text=True)


def test_admin_without_mfa_gets_403_and_no_fs3():
    tok = forge("admin", False)
    r = client().get("/api/v1/admin/feeds", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert r.get_json()["error"] == "mfa_required"
    assert FS3 not in r.get_data(as_text=True)


def test_admin_with_mfa_gets_fs3():
    tok = forge("admin", True)
    r = client().get("/api/v1/admin/feeds", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.get_json()["hint"] == FS3
