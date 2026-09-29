from challenge.internal.engine import create_engine_app
from tests.conftest import FS4, FLAG

def test_engine_root_exposes_fs4_and_flag_path():
    app = create_engine_app()
    c = app.test_client()
    r = c.get("/")
    body = r.get_json()
    assert r.status_code == 200
    assert body["hint"] == FS4
    assert body["flag_path"] == "/internal/flag"

def test_engine_flag_endpoint_returns_flag():
    app = create_engine_app()
    c = app.test_client()
    r = c.get("/internal/flag")
    assert r.status_code == 200
    assert FLAG in r.get_data(as_text=True)
