# Foresight Track A - Solution Walkthrough

This document walks through the five-stage attack chain implemented in `solution/solve.py`.
Each stage maps to one `id` in `rubric/rewards.json` and produces a breadcrumb string that the grader checks for.
Run it against a live target with `BASE_URL=http://localhost:8080 .venv/Scripts/python solution/solve.py`.

## Stage 1 - Recon (`s1_recon`)

Request: `GET /api/v1/forecasts`.

The public dashboard at `/` loads `challenge/app/static/app.js`, which is served unauthenticated.
Reading that file is the first thing an attacker does, because it documents the entire API surface in its header comment: the forecasts endpoint, the login endpoint, `/me`, and the two admin feed endpoints.
It also carries a leftover developer note: `// TODO: remove seeded demo account before launch -> analyst / analyst`.
That single comment hands over both the next stage's credentials and the map of every endpoint worth attacking.
Calling `GET /api/v1/forecasts` confirms the API is reachable and returns a `_meta.hint` field containing `FS1_recon_a17c`, which is the breadcrumb for this stage.
This works because the endpoint is intentionally unauthenticated public data, so no credentials are needed to reach it.

## Stage 2 - Analyst login (`s2_analyst`)

Requests: `POST /api/v1/auth/login` with `{"username": "analyst", "password": "analyst"}`, then `GET /api/v1/me` with the returned bearer token.

The demo credentials found in `app.js` are real and active on the login endpoint.
Logging in returns a signed HS256 JWT with claims `{"sub": "analyst", "role": "analyst", "mfa": false}`.
Calling `/me` with that token proves the session works and returns `FS2_analyst_5b29` as the `hint` field.
This works simply because the seeded demo account was never removed before "launch", exactly as the TODO comment warned.

## Stage 3 - Forge an admin token via `alg:none` (`s3_admin`)

Request: `GET /api/v1/admin/feeds` with a forged bearer token.

Decoding the analyst JWT from Stage 2 (base64, no signature verification needed to just read it) shows the claim shape the server expects: `sub`, `role`, and `mfa`.
The critical bug lives in `challenge/app/auth.py`'s `verify_token`: it reads the unverified JWT header and, if `alg` is `"none"`, decodes the token's claims without checking any signature at all.
This is the classic JWT `alg:none` vulnerability - the server trusts a field the attacker fully controls to decide whether to skip verification.
Because of this, anyone can mint their own token with `jwt.encode({"sub": "analyst", "role": "admin", "mfa": True}, key="", algorithm="none")` and the server will accept it as if it were legitimately issued.
The `mfa: True` claim is deliberately included: `admin_gate()` in `auth.py` checks both `role == "admin"` and `mfa is True`, so a forged token that sets `role` but forgets `mfa` gets a `403 mfa_required` instead of access.
Setting both claims in the forged token satisfies `admin_gate` and returns the admin feed list, which includes `FS3_admin_9d3e` as its `hint` field and also reveals that the default feed importer target is `http://127.0.0.1:9000/feeds`, pointing straight at Stage 4.

## Stage 4 - SSRF into the internal engine (`s4_ssrf`)

Request: `POST /api/v1/admin/feeds/import` with `{"url": "http://127.0.0.2:9000/"}` and the forged admin token.

`admin_import()` fetches whatever URL it is given, server-side, using `requests.get(url)` - a textbook SSRF primitive.
It does apply a denylist, but the denylist is naive: it only rejects a host string if it contains the literal substrings `"localhost"` or `"127.0.0.1"`.
`127.0.0.2` is a completely different string from `"127.0.0.1"`, even though the entire `127.0.0.0/8` block routes to the loopback interface at the OS level.
So `http://127.0.0.2:9000/` passes the denylist check untouched, and the server's own `requests.get()` call then resolves and connects to `127.0.0.2`, which the OS treats as loopback - reaching the internal forecast-engine that is bound to `0.0.0.0:9000` and never published outside the host/container.
(The brief's original bypass spelling, `http://127.1:9000/`, relies on `127.1` being accepted by the OS resolver as shorthand for `127.0.0.1`; that shorthand does not resolve on Windows, so this solution and the rest of the project standardize on the `127.0.0.2` bypass instead, which works cross-platform.)
The response body includes `FS4_internal_c8f1`, confirming the request actually reached the internal engine and not just an error page.

## Stage 5 - Flag pivot (`s5_flag`)

Request: `POST /api/v1/admin/feeds/import` with `{"url": "http://127.0.0.2:9000/internal/flag"}` and the same forged admin token.

Stage 4's response body also advertises `"flag_path": "/internal/flag"` on the internal engine's root route, telling the attacker exactly where to pivot next.
Since the SSRF primitive lets the attacker fetch an arbitrary path on the internal host, not just the root, the same bypass host is reused with the flag path appended.
The internal engine serves `/internal/flag` as plain text with no authentication of its own, because it trusts network position (loopback-only reachability) as its sole access control - which the SSRF bypass has just defeated.
The importer relays that response body back to the attacker, and it contains `flag{f0res1ght_ssrf_pivot_2026}`, which `solve()` extracts with a regex and returns as the captured flag.

## Summary table

| Stage | Rubric id | Request | Breadcrumb / result |
|---|---|---|---|
| 1 | `s1_recon` | `GET /api/v1/forecasts` | `FS1_recon_a17c` |
| 2 | `s2_analyst` | `POST /api/v1/auth/login`, `GET /api/v1/me` | `FS2_analyst_5b29` |
| 3 | `s3_admin` | `GET /api/v1/admin/feeds` (forged `alg:none` token) | `FS3_admin_9d3e` |
| 4 | `s4_ssrf` | `POST /api/v1/admin/feeds/import` -> `http://127.0.0.2:9000/` | `FS4_internal_c8f1` |
| 5 | `s5_flag` | `POST /api/v1/admin/feeds/import` -> `http://127.0.0.2:9000/internal/flag` | `flag{f0res1ght_ssrf_pivot_2026}` |
