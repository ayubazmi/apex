# Apex Operations API

FastAPI backend + SQLite/Postgres + vanilla JS frontend (same server se serve hota hai).

## Local run (bina Docker)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```
- UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: /health | Ready: /ready | Metrics: /metrics

## Tests & lint
```bash
flake8 .
pytest -v
DEMO_FAIL=true pytest -v      # intentional failure demo (Windows PowerShell: $env:DEMO_FAIL="true"; pytest -v)
```
