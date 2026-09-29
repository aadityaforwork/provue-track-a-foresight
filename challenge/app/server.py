from flask import Flask, jsonify, request
from challenge.app.auth import issue_token, verify_token, admin_gate

FS1 = "FS1_recon_a17c"
FS2 = "FS2_analyst_5b29"
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

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080)
