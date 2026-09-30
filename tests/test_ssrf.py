import threading
from werkzeug.serving import make_server
import jwt
from challenge.app.server import create_app
from challenge.internal.engine import create_engine_app
from tests.conftest import FS4

def forge_admin():
    return jwt.encode({"sub": "x", "role": "admin", "mfa": True}, key="", algorithm="none")

class Bg:
    def __init__(self, app, port):
        self.srv = make_server("0.0.0.0", port, app)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
    def __enter__(self):
        self.t.start(); return self
    def __exit__(self, *a):
        self.srv.shutdown()

def test_ssrf_direct_loopback_is_blocked():
    c = create_app().test_client()
    h = {"Authorization": f"Bearer {forge_admin()}"}
    for url in ["http://127.0.0.1:9000/", "http://localhost:9000/"]:
        r = c.post("/api/v1/admin/feeds/import", json={"url": url}, headers=h)
        assert r.status_code == 400

def test_ssrf_non_http_scheme_blocked():
    c = create_app().test_client()
    h = {"Authorization": f"Bearer {forge_admin()}"}
    r = c.post("/api/v1/admin/feeds/import", json={"url": "file:///etc/passwd"}, headers=h)
    assert r.status_code == 400

def test_ssrf_bypass_reaches_internal_fs4():
    with Bg(create_engine_app(), 9000):
        c = create_app().test_client()
        h = {"Authorization": f"Bearer {forge_admin()}"}
        r = c.post("/api/v1/admin/feeds/import", json={"url": "http://127.0.0.2:9000/"}, headers=h)
        assert r.status_code == 200
        assert FS4 in r.get_json()["content"]

def test_ssrf_requires_admin_mfa():
    c = create_app().test_client()
    r = c.post("/api/v1/admin/feeds/import", json={"url": "http://2130706433:9000/"})
    assert r.status_code == 401

def test_non_string_url_is_400_not_500():
    c = create_app().test_client()
    h = {"Authorization": f"Bearer {forge_admin()}"}
    r = c.post("/api/v1/admin/feeds/import", json={"url": 123}, headers=h)
    assert r.status_code == 400
