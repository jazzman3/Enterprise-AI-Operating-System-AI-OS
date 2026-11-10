# AISX Enterprise AI Operating System — Rebuilt v3.0

**Status:** Locally operational and tested. **Not publicly cloud-deployed or certified production-ready.**

This is a rebuilt, independently implemented successor to the earlier AISX reference MVP, based on its documented 9 organizational groups / 40 operational agent roles / 8 workflows baseline. The older application source ZIP was not available for a line-by-line migration. The commercial-lending department is registered as **disabled** and has no active agents until regulatory/compliance approval. The 40 agent roles are deterministic, draft-only *role adapters*, not autonomous LLM agents.

## Download package contents

- `aisx_os/`: FastAPI app, orchestration and audit engine, CLI
- `config/catalog.json`: 9 department groups, 40 enabled agent roles, 8 workflow definitions
- `static/index.html`: browser dashboard
- `docs/architecture.png`, `.svg`, `.dot`: diagram and editable Graphviz source
- `docs/PRODUCTION_SETUP_GUIDE.md`: step-by-step installation and production engineering plan
- `tests/`: 27 tests covering authorization, workflow status, tenant isolation, audit integrity
- `benchmarks/`: reproducible localhost HTTP and end-to-end workflow benchmarks
- `.github/workflows/ci.yml`: unit/HTTP benchmark and Docker build CI

## Local quick start (Windows PowerShell)

1. Install Python 3.12, Docker Desktop, and VS Code.
2. Extract the ZIP. In PowerShell from this directory, run:

```powershell
Copy-Item .env.example .env
# Do not use the demo settings beyond your own computer.
docker compose up --build -d
curl.exe http://127.0.0.1:8000/readyz
```

3. Visit http://127.0.0.1:8000. For **local only** demo, use `local-analyst-key-change-me-now` to create a workflow, then switch to `local-approver-key-change-me-now` to approve or reject it. It will *never* submit a contract, send an email, transfer money, or isolate a host.
4. Run verification using Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m aisx_os validate
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m benchmarks.workflow
.\.venv\Scripts\python.exe benchmarks/run.py
```

The HTTP benchmark uses the local demo token, so start the API before benchmarking it. **Do not benchmark a publicly accessible deployment using the demo token.**

## Run without Docker

```bash
python -m pip install -r requirements-dev.txt
export AISX_ALLOW_LOCAL_DEMO=true
python -m uvicorn aisx_os.api:app --host 127.0.0.1 --port 8000
```

The default `AISX_DB_PATH` is `./data/aisx.db`.

## API summary

| Method | Endpoint | Authorization |
|---|---|---|
| GET | `/healthz`, `/readyz` | Public (put behind internal ingress in real deployment) |
| GET | `/api/v1/catalog`, `/api/v1/capabilities` | Any authenticated |
| POST | `/api/v1/runs` | Analyst or admin |
| GET | `/api/v1/runs`, `/api/v1/runs/{id}` | Authenticated, tenant scoped |
| POST | `/api/v1/runs/{id}/review` | Approver or admin, tenant scoped |
| GET | `/api/v1/audit/verify`, `/metrics` | Admin |
| GET | `/` | Web dashboard (UI only; API protected) |

### Production restriction

This release uses SQLite and static bearer-key roles; it is appropriate for a **single-instance secure evaluation environment**, not multi-node production. It lacks production SSO/MFA, secrets rotation, external audit anchoring, background job queues, DLP, live connectors, neural LLM inference, disaster recovery, HA, network ingress, and data-retention automation. Do not use it to process sensitive data until these are implemented and reviewed.

**Benchmark and test data are synthetic.** Refer to `docs/PRODUCTION_SETUP_GUIDE.md` for the production hardening gates and cloud rollout instructions.
