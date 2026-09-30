import threading

from werkzeug.serving import make_server

from challenge.app.server import create_app
from challenge.internal.engine import create_engine_app
from solution.solve import solve
from tests.conftest import FLAG


class Bg:
    def __init__(self, app, port):
        self.srv = make_server("0.0.0.0", port, app)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *a):
        self.srv.shutdown()


def test_reference_solution_captures_flag():
    with Bg(create_engine_app(), 9000), Bg(create_app(), 8080):
        out = solve("http://127.0.0.1:8080")
        assert out["flag"] == FLAG
        for crumb in ["FS1_", "FS2_", "FS3_", "FS4_"]:
            assert crumb in out["transcript"]
