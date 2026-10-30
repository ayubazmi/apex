# Apex Operations API: Delivery Documentation

## 1. Overview

Apex Operations API is a small incident/ops ticket tracker (FastAPI + PostgreSQL + a web UI served by the same app). It demonstrates a reliable path from commit to release: containerised, tested in CI, deployed with Docker Compose, versioned, observable and rollback-ready.

Endpoints: `/` UI, `/health` (liveness + version), `/ready` (checks DB, 503 if down), `/metrics` (request, 5xx, latency, uptime counters), `/api/tickets` (CRUD), `/api/stats`, `/api/debug/crash` (failure drill, 404 in production), `/docs` (Swagger).

## 2. Reproducibility (README)

Prerequisites: Git, Docker with Compose. Nothing else is needed on the host.

```
git clone https://github.com/ayubazmi/apex.git && cd apex
cp .env.example .env            # set POSTGRES_PASSWORD, APP_IMAGE
docker compose up -d --build    # app + Postgres + persistent volume
curl localhost:8000/health
```

Without Docker: create a venv, `pip install -r requirements-dev.txt`, run `uvicorn app.main:app --port 8000` (SQLite). Tests: `flake8 .` and `pytest -v` (8 tests; `DEMO_FAIL=true` triggers the intentional failure). Compose waits for the DB healthcheck before starting the app, and data survives `docker compose down` because it lives in the `pgdata` volume.

&#91;image: Compose stack healthy: app 1.0.6 and Postgres\]

*Evidence: `docker ps` shows the versioned image `ghcr.io/ayubazmi/apex:1.0.6` and `postgres:16-alpine`, both healthy.*

## 3. CI/CD pipeline

| Stage | What it does | Blocks next stage if it fails |
| --- | --- | --- |
| test | install, flake8 lint, pytest | yes (`needs:`) |
| build | docker build, Trivy scan (CRITICAL fails build), smoke test on `/ready` | yes |
| deploy | push image to GHCR as `1.0.<run number>` and commit SHA (main only) | yes |
| cd | self-hosted runner on the Kali VM runs `deploy.sh`, verifies `/health` shows the new version, auto-rolls back on failure | final |

Intentional failure: a manual run with `demo_fail`  test job, and build, deploy and cd are skipped. This is the evidence that a failing test blocks deployment.&#32;

&#91;image: CI run 22: all jobs green, including deploy to the Kali VM\]

*Evidence, successful deployment: CI run #22 on `main`. Lint and test, Build and scan image, Publish versioned image and Deploy to Kali VM all passed (8m 9s).*

&#91;image: CI run 23: Lint and test failed, later jobs skipped\]

*Evidence, intentional failure: CI run #23 (commit "Update test\_api.py"). Lint and test failed, so Build and scan image, Publish versioned image and Deploy to Kali VM were skipped. Nothing was deployed.*

## 4. Release and rollback (runbook)

```
bash scripts/deploy.sh 1.0.6      # pull versioned image, start, wait for /ready, record version
bash scripts/rollback.sh          # back to previous version (or: rollback.sh 1.0.5)
```

Manual equivalent: `export APP_VERSION=1.0.5; docker compose up -d --no-build; curl localhost:8000/health`. Rollback is fast because the older image is cached locally, and tickets are unaffected because data is in the DB volume. Caveat: if a release changes the DB schema, check backward compatibility before rolling back. Verify any release with `/health` (version), `/ready` (database up), `docker compose ps` (healthy) and the UI.

## 5. Observability

- **Logs:** structured JSON to stdout, one line per request with `request_id`, method, path, status, duration\_ms; errors include the stack trace. View with `docker compose logs app`.
- **Health:** `/health` says the process is alive, `/ready` says it can serve (DB reachable). Docker healthcheck uses `/ready`.
- **Metrics:** `/metrics` is scraped every 15 s by Prometheus, shown in a Grafana dashboard (status, request rate, 5xx ratio, latency, availability). Prometheus and Grafana run from a separate compose file with persistent volumes.
- **Alert proposal:**

&#91;image: Structured JSON request logs\]

*Evidence: structured JSON logs, one line per request with `request_id`, method, path, status and `duration_ms`.*

&#91;image: Grafana dashboard\]

*Evidence: Grafana dashboard with total requests, availability (up), request rate and 5xx errors.*

| Alert | Condition | Severity |
| --- | --- | --- |
| Service down | `up{job="apex-api"} == 0` for 2 min | SEV1 |
| High error rate | 5xx ratio above 5% for 5 min | SEV2 |
| High latency | average above 500 ms for 10 min | SEV2 |

Alerts are a proposal; notification would need Alertmanager.

## 6. Incident drill: database down

1. Break: `docker compose stop db`.
2. Detect: `curl -i localhost:8000/ready` returns 503 `not_ready` while `/health` stays 200, which shows the app is alive but not ready.
3. Investigate: `docker compose logs app --tail 20 | grep readiness_failed` shows the JSON error line.
4. Cause: DB container stopped, so `SELECT 1` fails.
5. Fix: `docker compose start db`; `/ready` returns 200 and existing tickets are intact.

&#91;image: Detection: /ready returns 503 and readiness\_failed log\]

*Evidence, detect and investigate: `/ready` returns 503 `not_ready` with the database stopped, and the log shows `readiness_failed`.*

&#91;image: Recovery: /ready returns 200\]

*Evidence, fix: after `docker compose start db`, `/ready` returns 200 with `database: up` on version 1.0.6.*

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `manifest unknown` on pull | tag or `APP_IMAGE` name wrong | copy the exact tag from GitHub Packages |
| `denied` on pull | private package, not logged in | `docker login ghcr.io` |
| `/ready` 503 | DB down | `docker compose ps`, start db, check logs |
| Version did not change | shell `APP_VERSION` overrides `.env` | `unset APP_VERSION`, `docker compose config` |
| CI red | lint, test or Trivy failure | read the failing step log, fix, push |

## 8. Security

- **Secrets:** `.env` is git-ignored and excluded from images by `.dockerignore`; Compose refuses an empty DB password; CI uses the built-in `GITHUB_TOKEN`; cloud would use a secrets manager.
- **Least privilege:** container runs as a non-root user; Postgres is not published to the host; only the deploy job gets `packages: write`; registry pulls need only `read:packages`; the crash endpoint is off in production; inputs are validated and UI output is escaped.
- **Scanning:** Trivy scans the image (OS and Python packages) and blocks on CRITICAL findings; dependency versions and the Trivy action are pinned.
- **Known gaps:** no API authentication or TLS (local demo), writable container filesystem, no Dependabot or image signing yet, and the self-hosted runner runs as root on a lab VM only.

&#91;image: Non-root container user\]

*Evidence: `docker exec apex-app-1 whoami` returns `app`, so the container does not run as root.*

## 9. Cost-aware path to cloud

Stage 1: one small ARM VM (EC2 or Lightsail) running the same Compose file, with disk snapshots and a billing alert; lowest and most predictable cost. Stage 2, only when uptime justifies it: ECS Fargate for the app and a small single-AZ RDS PostgreSQL for dev/staging, Multi-AZ for production; rollback maps to a previous task definition. Cost levers: right-size from metrics, stop non-production out of hours, log retention limits, image lifecycle cleanup, savings plans once usage is steady, and skipping the load balancer and NAT gateway until needed. Confirm all prices in the AWS Pricing Calculator.

## 10. Deliverables map and evidence

Dockerfile, `docker-compose.yml`, `.github/workflows/ci.yml` and app source are in the repo root; scripts are in `scripts/`; evidence screenshots are in `docs/evidence/` (non-root user, compose healthy, data persistence, CI red and green runs, Trivy, GHCR versions, deploy, rollback, failure drill, Grafana dashboard).
