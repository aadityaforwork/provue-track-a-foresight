from flask import Flask, jsonify, request
import requests
from urllib.parse import urlparse
from challenge.app.auth import issue_token, verify_token, admin_gate

FS1 = "FS1_recon_a17c"
FS2 = "FS2_analyst_5b29"
FS3 = "FS3_admin_9d3e"
DEMO_USER, DEMO_PASS = "analyst", "analyst"


def _bearer():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    return verify_token(h[7:])


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="")

    @app.get("/api/v1/forecasts")
    def forecasts():
        return jsonify(
            forecasts=[{"symbol": "ACME", "q3": 1.12}, {"symbol": "GLOB", "q3": 0.87}],
            _meta={"hint": FS1, "api": "/api/v1"},
        )

    @app.post("/api/v1/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        if data.get("username") == DEMO_USER and data.get("password") == DEMO_PASS:
            return jsonify(token=issue_token("analyst", "analyst", False))
        return jsonify(error="invalid credentials"), 401

    @app.get("/api/v1/me")
    def me():
        claims = _bearer()
        if not claims:
            return jsonify(error="unauthorized"), 401
        return jsonify(user=claims.get("sub"), role=claims.get("role"), hint=FS2)

    @app.get("/api/v1/admin/feeds")
    def admin_feeds():
        claims = _bearer()
        ok, reason = admin_gate(claims)
        if not ok:
            code = 403 if reason == "mfa_required" else 401
            return jsonify(error=reason), code
        return jsonify(
            feeds=[{"name": "internal-default", "url": "http://127.0.0.1:9000/feeds"}],
            note="import fetches a feed URL server-side; default engine runs on loopback:9000",
            hint=FS3,
        )

    @app.post("/api/v1/admin/feeds/import")
    def admin_import():
        claims = _bearer()
        ok, reason = admin_gate(claims)
        if not ok:
            code = 403 if reason == "mfa_required" else 401
            return jsonify(error=reason), code
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        # Naive SSRF denylist (CTF): blocks obvious loopback spellings only.
        if parsed.scheme not in ("http", "https"):
            return jsonify(error="blocked", reason="scheme"), 400
        if "localhost" in host or "127.0.0.1" in host:
            return jsonify(error="blocked", reason="host"), 400
        try:
            resp = requests.get(url, timeout=2)
        except Exception as e:
            return jsonify(error="fetch_failed", detail=str(e)), 502
        return jsonify(imported=True, content=resp.text[:800])

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080)
