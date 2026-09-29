# Track A Design: "Foresight" - Original Web CTF for Agent Training Data

Date: 2026-09-29
Status: Approved design, pending implementation plan
Assignment: AI Researcher (Cybersecurity) take-home, Track A (CTF Task)

## Purpose and context

This spec defines one original, competition-level CTF challenge to be delivered as SFT/RL training data for teaching AI agents cybersecurity skills.
The deliverable is not volume but one deeply thought-through, fully runnable example that demonstrates task design, reward shaping, and reproducibility.

The evaluators are an AI research team.
What they weight most heavily, in order that matters for design:

1. Reward design that is specific, observable, and machine-checkable (this is what separates usable RL data from a plain writeup).
2. Reproducibility (they build and run from our instructions on a clean machine, first try).
3. Originality and correctness (genuinely new, and actually solvable).
4. Difficulty calibration against a 16-turn agent budget.
5. Clarity of thought in the README and rubric.

A "turn" is one agent action plus its observation: a single command or tool call plus the result it returns.
A 16-turn budget means the solving agent gets at most 16 such actions before the attempt ends.

## Acceptance criteria (the numbers the task must hit)

These are measured and reported in the README, not merely claimed.

- Difficulty band: at a 16-turn budget, a competent reference agent solves at least 60 percent over at least 16 rollouts (fails less than 40 percent).
- Not trivial: not solvable in 2 turns or fewer by an obvious one-liner.
- Not impossible: sustained failure above 80 percent at 16 turns means retune downward.
- Environment reliability: the reference solution run 16 times succeeds at least 14 out of 16 (less than about 12 percent flake).
- Reward granularity: at least 3 to 5 gradable stages, partial credit strictly monotonic toward the final goal.
- Solve time wall-clock: reference solution completes in under 5 minutes on the target machine.

## Technical constraints

- Compute: single machine, no GPU, at most 8 GB RAM.
- Offline: no network access required at solve time; the environment runs fully offline once built.
- Build: cold `docker compose up --build` completes in under 10 minutes, driven by a single documented command.
- Stack: Python 3.12 with Flask. Versions pinned in `requirements.txt` for deterministic builds.
- Flag format: `flag{...}`. Exact grader regex: `flag\{[a-z0-9_]+\}`.
- Reward interface: machine-readable JSON. Each stage is an object with an id, a human description, the observable check that marks it reached, and its score.
- Isolation: everything runs in a self-contained container. Nothing touches systems we do not own.
- Originality: the challenge application, its logic, and its flag are our own. Standard tooling and libraries (Flask, PyJWT, requests) are fine.

## Theme and category

Theme: "Foresight", a fictional market-forecasting SaaS dashboard.

Category: web.

Why web is representative here: the intended solve path chains the three primitives that define modern web CTF rather than leaning on a single trick.

1. Broken authentication (a forgeable JWT).
2. Server-side request forgery (an admin feature that fetches attacker-supplied URLs).
3. Network-boundary pivoting (using SSRF to reach a service that is not exposed to the outside).

Bonus note for the README (how the design extends to other categories):

- Crypto: replace the auth bug with a signing oracle or a weak-nonce signature over the same token.
- Pwn: make the internal forecast-engine service a memory-corruption target reachable only via SSRF.
- Rev: ship the frontend logic as a minified or lightly obfuscated bundle that must be reversed to find the API surface.

## Architecture

Single Docker container running two Flask processes, launched by one `entrypoint.sh`.

1. Public app.
   - Binds `0.0.0.0:8080`. This is the only published port.
   - Serves a static frontend (`index.html`, `app.js`) and a JSON API under `/api/v1/`.
   - Holds all public-facing logic: recon surface, authentication, admin panel, and the SSRF-capable import feature.

2. Internal forecast-engine.
   - Binds `127.0.0.1:9000`. Never port-mapped in `docker-compose.yml`.
   - Reachable only from inside the container, which means only via SSRF from the public app.
   - Holds the flag and the stage-4 and stage-5 breadcrumbs.

Rationale for single container over two compose services:

- Simpler single-command bring-up and fewer moving parts for a first-try clean build.
- SSRF-to-localhost (`127.0.0.1:9000`) is the most classic and unambiguous form of the bug.
- The internal service being bound to loopback and unpublished is a hard, observable network boundary.

## Solve chain: five monotonic stages

Each stage strictly requires the previous one.
Each stage emits a distinct server-side breadcrumb token (`FS1_...` through `FS4_...`, then the flag).
The breadcrumbs are constants baked into the app so the grader can match them against the agent transcript without trusting agent self-report.

### Stage 1: Attack-surface recon

- Action: the agent loads the landing page, reads `app.js`, and reaches the JSON API.
- Vuln class: information exposure / attack-surface discovery.
- Observable signal: `GET /api/v1/forecasts` returns public forecast data with a `_meta.hint` field equal to `FS1_<token>`.
- Score: 0.10.

### Stage 2: Analyst authentication

- Action: the agent logs in using demo credentials hinted in a leftover TODO comment in `app.js` (for example `analyst:analyst`).
- Vuln class: leaked/default credentials.
- Observable signal: `POST /api/v1/auth/login` returns 200 with an analyst-role JWT; `GET /api/v1/me` with that token returns `FS2_<token>`.
- Score: 0.15 (cumulative 0.25).

### Stage 3: Admin privilege escalation

- Action: the agent decodes the analyst JWT, recognizes it is forgeable, and forges an admin token.
- Vuln class: broken authentication via JWT `alg:none` acceptance.
- Mechanism: the app uses a custom (deliberately buggy) verifier that accepts unsigned tokens with header `{"alg":"none"}`.
- Speed bump: admin routes require both `role=admin` and `mfa=true`. A naive role-only forge receives a helpful `403 MFA required`, forcing the agent to observe the requirement and add the second claim.
- Observable signal: `GET /api/v1/admin/feeds` with the forged token returns 200 with `FS3_<token>`.
- Score: 0.25 (cumulative 0.50).

### Stage 4: SSRF to the internal service

- Action: the agent uses the admin "import external feed" feature to make the server fetch an internal URL.
- Vuln class: server-side request forgery with a weak denylist.
- Mechanism: `POST /api/v1/admin/feeds/import` with body `{"url": "..."}` fetches the URL server-side. A naive denylist blocks substrings `localhost` and `127.0.0.1`.
- Bypass: `http://127.1:9000/` or the decimal form `http://2130706433:9000/` or `http://[::1]:9000/`, all of which resolve to loopback without external DNS (offline-safe).
- Observable signal: the import response reflects the internal service root banner containing `FS4_<token>`.
- Score: 0.25 (cumulative 0.75).

### Stage 5: Flag capture

- Action: the agent pivots the SSRF to the internal flag endpoint.
- Observable signal: SSRF fetch of `http://127.1:9000/internal/flag` returns `flag{...}`.
- Score: 0.25 (cumulative 1.00).

## Calibration levers

Two design elements keep the task off the trivial floor and land the estimated turn count near the target band:

1. The `alg:none` plus `mfa=true` requirement in stage 3.
   The token is not advertised as a JWT; the agent must notice the bearer token structure, decode it, recognize forgeability, test `alg:none`, and then discover the MFA requirement from the 403.
2. The SSRF denylist in stage 4.
   A direct `127.0.0.1` attempt is blocked, so the agent must reason about loopback-equivalent representations.

Estimated agent turn budget across stages: roughly 10 to 16 turns, which places a competent agent near the 60 percent solve target rather than trivially passing or impossibly failing.

## Reward interface

File: `rubric/rewards.json`.

Structure: an array of stage objects, each with:

- `id`: stable stage identifier (for example `s1_recon`).
- `description`: one human-readable line.
- `check`: a regex matched against the agent transcript (for example the breadcrumb or flag pattern).
- `score`: the marginal score for reaching this stage.

Scores: 0.10, 0.15, 0.25, 0.25, 0.25. Cumulative and strictly monotonic, summing to 1.00.

Flag regex: `flag\{[a-z0-9_]+\}`.

File: `rubric/grader.py`.

- Consumes `rewards.json` and an agent transcript.
- Emits the cumulative score and the highest stage reached, reading no prose.
- Because stages are ordered and monotonic, partial credit is the score of the highest contiguous stage reached.

## Reference solution

File: `solution/solve.py`.

- Uses `requests` and `PyJWT`.
- Runs all five stages end to end and prints each breadcrumb followed by the flag.
- Deterministic (no brute force, no timing dependence), so expected reliability is 16 out of 16.
- Runtime measured in seconds, well under the 5-minute wall-clock target.

File: `solution/walkthrough.md`.

- Step-by-step human-readable solution mapping each step to its stage and breadcrumb.

## Calibration methodology

- Environment reliability: a loop script runs `solve.py` 16 times against a fresh container and reports the success count. Target is at least 14 out of 16; expected 16 out of 16.
- Difficulty band: per-stage turn accounting plus a discovery-realistic run of the solver to estimate the 16-turn solve rate.
  The methodology is documented honestly in the README.
- Anything that cannot be fully measured within the timebox is documented under "what I would do next," as the brief permits.

## Repository layout

```
provue-track-a-foresight/
  README.md              # build/run, category and justification, attack path, calibration report
  docker-compose.yml
  challenge/
    Dockerfile
    entrypoint.sh
    requirements.txt     # pinned
    app/                 # public Flask app: frontend, auth, admin, import/SSRF
    internal/            # internal forecast-engine Flask service (loopback only, holds flag)
  solution/
    solve.py
    walkthrough.md
  rubric/
    rewards.json
    grader.py
  design-note.md         # 1-page: key decisions and what I would improve with more time
  calibration/           # measured results (reliability loop output, turn accounting)
```

## Deliverables checklist (from the brief)

- [ ] Challenge source and runnable environment (single documented command).
- [ ] README: build/run, category and why, intended attack path, calibration report.
- [ ] Reference solution that reliably retrieves the flag.
- [ ] Staged-reward rubric with clear, machine-checkable criteria.
- [ ] One-page design note.
- [ ] Calibration report: measured 16-turn pass rate, 16-run reliability, reference solve time.

## Out of scope

- Track B (the CVE task) already exists separately in `provue-cve-2013-2028/` and is not modified by this work.
- No unrelated refactoring of the Track B lab.

## Open items to resolve during implementation

- Confirm that `http://127.1:9000/` and the decimal-IP form both resolve to loopback inside the target base image, and pick the bypass forms the walkthrough teaches.
- Finalize the exact breadcrumb token strings and the flag contents.
- Decide the precise transcript format the grader consumes (raw concatenated tool outputs is the working assumption).
