from challenge.app.server import create_app


def client():
    return create_app().test_client()


def test_index_served():
    r = client().get("/")
    assert r.status_code == 200
    assert b"Foresight" in r.data


def test_appjs_reveals_api_and_demo_creds():
    r = client().get("/app.js")
    body = r.get_data(as_text=True)
    assert "/api/v1/auth/login" in body
    assert "/api/v1/admin/" in body
    assert "analyst" in body  # demo cred hint in a TODO comment
