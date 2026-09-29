from flask import Flask, jsonify, Response

FS4 = "FS4_internal_c8f1"
FLAG = "flag{f0res1ght_ssrf_pivot_2026}"

def create_engine_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def root():
        return jsonify(
            service="forecast-engine",
            note="internal only - not exposed externally",
            hint=FS4,
            flag_path="/internal/flag",
        )

    @app.get("/internal/flag")
    def flag():
        return Response(FLAG + "\n", mimetype="text/plain")

    return app

if __name__ == "__main__":
    # Bind all interfaces INSIDE the container; port 9000 is never published (compose maps only 8080), so this stays reachable only via SSRF, not externally. 0.0.0.0 also accepts the 127.0.0.2 loopback-bypass spelling on Linux.
    create_engine_app().run(host="0.0.0.0", port=9000)
