# AISX Enterprise AI Operating System — Production Deployment and Portfolio Setup Guide

**Version:** 3.0 (2026-11-10)  
**Scope:** rebuilt modular Enterprise AI OS, 9 organizational groups / 40 enabled role adapters / 8 approval-gated workflows  
**Deployment status:** local HTTP service verified; external cloud deployment **not performed**.

## 1. What was preserved and what was rebuilt

The previous reference implementation guide describes a draft-only command-line prototype with 9 groups, 40 roles, 8 workflows, and disabled commercial lending. Its original code archive was not available to inspect in this build. This package **reconstructs the documented baseline** with a new API, dashboard, durable SQLite state, role-scoped approvals, per-tenant run access, Prometheus metrics, hash-chained audit records, CI, and repeatable measurements. The exact prior agents/IDs may differ; review `config/catalog.json` before moving work forward from the earlier deployment.

**No automatic external actions or model-generated decisions** are enabled: agent outputs are deterministic, explanatory drafts. The integration entries for RAG, MLOps, and SentinelForge are interface intentions, **not live connectors**. Do not describe them otherwise in an interview.

## 2. Architecture and boundaries

Open `docs/architecture.png` or `docs/architecture.svg` to see the deployed-local logical architecture. The editable Graphviz source is `docs/architecture.dot`.

Client (dashboard or API) → FastAPI (authentication and tenant/role access) → workflow controller → 40-role catalog → safe draft provider → SQLite durable state. Every state transition adds a chained audit record. Health/ready and Prometheus endpoints support monitoring. Production integration adapters remain future work.

**Key guarantees demonstrated locally:** workflow stops at a review gate; reviewer/admin credential required to proceed; a second approval returns 409; cross-tenant run reads/approvals return 404; audit tampering is detected. **Not guaranteed:** tamper-proof externally anchored audit history, cryptographically signed identity, 24/7 uptime, or distributed high availability.

## 3. Prerequisites on Windows 11

Install:

1. Python 3.12 from https://www.python.org/downloads/
2. Docker Desktop with WSL 2 from https://docs.docker.com/desktop/setup/install/windows-install/
3. Git from https://git-scm.com/downloads/
4. VS Code from https://code.visualstudio.com/
5. Optional Graphviz if modifying `docs/architecture.dot`: https://graphviz.org/download/

Confirm:

```powershell
python --version
docker version
docker compose version
git --version
```

## 4. Reproducible local installation

1. Unzip `AISX_Enterprise_AI_OS_Rebuilt_v3.zip` to `C:\AI-Projects\AISX_Enterprise_AI_OS_Production`.
2. Open the extracted folder in VS Code. Confirm `aisx_os/`, `config/`, `tests/`, `benchmarks/`, and `docker-compose.yml` exist.
3. Open the VS Code terminal, then:

```powershell
Copy-Item .env.example .env
Get-Content .env
```

4. **Localhost only:** keep `AISX_ALLOW_LOCAL_DEMO=true` in `.env`; this permits pre-shipped demonstration API tokens and is unsuitable for Internet exposure.
5. Start Docker Desktop, then:

```powershell
docker compose up --build -d
docker compose ps
curl.exe http://127.0.0.1:8000/healthz
curl.exe http://127.0.0.1:8000/readyz
```

Expected health: `{ "status": "ok", "service": "aisx-ai-os" }`; readiness: `{ "status": "ready" }`. Docker has not been independently run in the build environment: use these commands to verify on your machine.
6. Open http://127.0.0.1:8000. In the API-key field enter `local-analyst-key-change-me-now`; select `Government Bid Qualification`, enter a **fictional** solicitation task, and start a workflow.
7. Observe `awaiting_approval`. The first three agent drafts should be present; the final step is withheld.
8. Switch to the separate `local-approver-key-change-me-now` token; select the run and approve. The fourth draft now appears and the run completes. A rejection should yield status `rejected`. This is not actual procurement submission.
9. For audit verification, use the local admin token `local-admin-key-change-me-now` and call:

```powershell
curl.exe -H "Authorization: Bearer local-admin-key-change-me-now" http://127.0.0.1:8000/api/v1/audit/verify
```

Expected `valid: true` unless records have been tampered with. Hash-chaining alone does not prevent an administrator who controls the database from replacing or deleting the entire chain.

## 5. Run automated tests and local benchmarks

From the extracted directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m aisx_os validate
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m benchmarks.workflow
.\.venv\Scripts\python.exe benchmarks/run.py --url http://127.0.0.1:8000 --requests 300 --workers 8 --output benchmarks/http_results_local.json
```

The workflow benchmark uses an ephemeral SQLite database and runs 100 simulated, approval-gated security workflows. The HTTP benchmark measures 300 real local requests against the current API. The supplied `benchmarks/http_results.json` and `benchmarks/workflow_results.json` were measured on the build host and may vary by system.

**Local measured results on 2026-11-10:**

- 27 automated tests passed.
- HTTP catalog endpoint: 300 requests, 8 concurrent workers, zero errors, 239.70 requests/second, p50 20.367 ms, p95 98.542 ms, p99 105.633 ms.
- End-to-end workflow: 100/100 simulated four-step security workflows completed with mocked human role approval; audit chain valid; p50 6.489 ms, p95 7.916 ms, p99 8.618 ms (in-process TestClient timing).

**Interpretation:** These numbers validate a local baseline only. They exclude live LLM inference, real external integrations, real-world business task quality, cold starts, cloud networking, and sustained concurrent workload. The HTTP benchmark includes fresh client construction for each request.

## 6. Configure a non-demo identity environment

Generate secrets and configure three separate roles. Do not store genuine secrets in source control.

```powershell
python -c "import secrets; [print(secrets.token_urlsafe(36)) for _ in range(3)]"
```

Set `AISX_ALLOW_LOCAL_DEMO=false`, and provide `AISX_IDENTITIES_JSON` using your approved secrets manager or an environment-injection mechanism. Example structure (replace all values):

```json
[
  {"tenant":"company-one","role":"analyst","user":"analyst-01","key":"REPLACE_WITH_RANDOM_24_PLUS_CHARS"},
  {"tenant":"company-one","role":"approver","user":"reviewer-01","key":"REPLACE_WITH_ANOTHER_RANDOM_24_PLUS_CHARS"},
  {"tenant":"company-one","role":"admin","user":"admin-01","key":"REPLACE_WITH_THIRD_RANDOM_24_PLUS_CHARS"}
]
```

The current API-key mechanism is only a stepping stone. **Replace it with centralized OIDC authentication, short-lived user sessions, MFA, fine-grained permissions and service identity before broad organizational use.** Restrict dashboard access behind authenticated ingress. Protect the database volume and avoid public API exposure.

## 7. Production engineering acceptance gates (required before real enterprise use)

| Gate | Required implementation | Acceptance evidence |
|---|---|---|
| Database | Replace SQLite with managed PostgreSQL; tenant-aware schema and transactions, migration tool | Backup/restore drill, tenant isolation integration tests |
| Durable work queue | Add Redis/SQS/RabbitMQ-backed worker; idempotency keys, retries, dead-letter handling | Restart/retry tests, no duplicated actions |
| Identity | OIDC (Entra ID/Keycloak/Cognito), MFA, least-privilege RBAC/ABAC | Cross-tenant penetration tests, reviewer separation |
| AI providers | Pluggable LLM provider, model pinning, prompt registry, eval/guardrails, token budget | Reproducible prompt/eval suite, red-team tests |
| Tools | Strict allowlisted adapters for RAG, MLOps, SentinelForge with per-service credentials | Contract tests + safe failure behavior |
| Governance | DLP, approved data scopes, retention/deletion, redaction, human approval policy | Privacy review and approval-rejection audit traces |
| Audit | Append-only off-host sink with cryptographic anchors; time sync and correlation IDs | Tamper detection across system/backup boundaries |
| Observability | Traces, metrics, structured logs, SLO alerts, dependency telemetry | Alert drill and dashboard evidence |
| Security | WAF/TLS, secret management, SAST/SCA, signed images, scanning, network segmentation | Independent security review and scan report |
| Reliability | Multi-instance workload test, HA, backups, rollback, incident response plan | Load test and recovery point/recovery time drill |

The current repository **does not implement the items in this table**; they are required future work. A Docker image and local passing tests alone are not sufficient to claim production readiness.

## 8. Suggested cloud deployment blueprint (AWS reference)

A recommended production target, **not already provisioned**, is:

1. Create AWS accounts/environments for dev/staging/prod with AWS Organizations, CloudTrail, and budget alerts.
2. Use Infrastructure-as-Code (Terraform or CDK) to create private VPC subnets, ECS Fargate, Application Load Balancer, ACM TLS certificate, Route 53 DNS, and CloudWatch.
3. Migrate database code to PostgreSQL and deploy RDS in a private subnet with backup, encryption, and tested restoration.
4. Provision SQS work queue and workers for persistent tasks with retry/dead-letter processing.
5. Install OIDC/SSO integration and validate claims, tenants, role scopes, approval separation, and revocation.
6. Create Secrets Manager entries for model-provider and connector credentials; grant scoped ECS task roles.
7. Establish a GitHub Actions OIDC trust relationship with AWS (no long-lived AWS keys). Require code review, testing, container scanning, and protected production approvals.
8. Push a signed container image to ECR, then deploy to staging with migration jobs.
9. Enable HTTPS/WAF, request limits, egress allowlists, customer-data encryption, and all dependency probes.
10. Run functional, cross-tenant, prompt-injection, load, failover, backup/restore, and audit-chain verification tests. Obtain security signoff.
11. Roll out to production only after passing the gates above, with staged traffic, error-rate alarms, rollback, and incident contact details.
12. Save deployment manifests, architecture, evidence and an incident recovery runbook with the portfolio project (without exposing secrets).

**Current deployment:** the provided Docker Compose deliberately binds only to `127.0.0.1:8000`. Do not change this to a public bind or put the demo credentials on the Internet.

## 9. GitHub CI/CD

The included `.github/workflows/ci.yml` performs catalog validation, automated tests, workflow benchmark, localhost HTTP benchmark and container build on pushes / pull requests. **The workflow file is configured but has not been executed on GitHub in this environment.**

To publish:

```powershell
git init
git add .
git commit -m "Rebuild enterprise AI OS with durable workflows and governance"
# Create an empty GitHub repository in your account, then add its remote:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

Never commit `.env`, API keys, tenant documents, or real customer information. Protect the `main` branch and require a passing workflow before merging changes. Container publishing/deployment is **not configured** by this repository; add it only after AWS OIDC trust and production release approvals are in place.

## 10. Modular integration with existing AISX services

- **Enterprise RAG:** read-only knowledge lookup adapter; require document-level permissions on every retrieval. No connection implemented yet.
- **MLOps & LLMOps:** scoped model metadata/deployment status adapter; any promotion/rollback must retain distinct human authorization. No connection implemented yet.
- **SentinelForge:** read-only incident/case summary adapter; never pass unrestricted response actions to a conversational agent. No connection implemented yet.
- **Future lending:** department remains disabled; requires regulatory counsel, licensing, underwriting policy, fair lending controls, and authorized human decision-makers before enablement.

Integration contracts must specify versioned endpoints, request/response schemas, data classifications, identity claims, authorization scopes, retry/timeout semantics, audit correlation and failure policies. Use API contract tests before enabling a connector.

## 11. Portfolio interview demonstration

A five-to-seven-minute demonstration:

1. Show architecture diagram, count of 9 organizational groups, 40 active role adapters, and eight workflow templates.
2. Show local dashboard and submit an obviously synthetic government procurement analysis.
3. Explain why the final step cannot proceed without reviewer approval.
4. Attempt approval using analyst credentials and show HTTP 403.
5. Approve with a reviewer identity, verify completion, and show duplicate approval is rejected (409).
6. Show cross-tenant isolation and the audit integrity endpoint.
7. Show measured test/benchmark JSON files and explain that these are local, non-LLM performance measurements.
8. Explain what you would need to change to meet cloud production requirements (SSO, PostgreSQL, job queue, managed secrets, SLOs, and independent security testing).

**Accurate resume wording now:** "Rebuilt and locally validated a modular enterprise AI operating system featuring 40 configured department-specific role adapters, eight durable approval-gated workflows, tenant-scoped APIs, access-controlled human review, tamper-evident local audit history, automated tests, and benchmarked HTTP endpoints."

**Do not yet claim:** live AI model orchestration, connected RAG/MLOps/SIEM services, enterprise SSO, production load availability, real decisions made autonomously, or a live cloud-hosted application.

## 12. Troubleshooting

- `401` means no valid bearer key; `403` means valid identity but insufficient role; `404` on a run may mean it belongs to a different tenant; `409` means approval was already resolved.
- `docker compose ps` and `docker compose logs ai-os` help diagnose application startup failures.
- `readyz` errors indicate environment config, catalog validation or database startup issues.
- If port 8000 is occupied, change the host-side `127.0.0.1:8000` binding to another localhost port in `docker-compose.yml`.
- If tests fail on a clean checkout, verify you are in the extracted package root and ran `pip install -r requirements-dev.txt`.
- To preserve business workflow state, retain the `aisx-data` Docker volume; `docker compose down -v` **deletes** local state.
- To amend workflow catalog settings, modify `config/catalog.json`, run `python -m aisx_os validate`, rerun tests, and rebuild containers. The catalog is loaded on process startup.

## 13. Reference links

- FastAPI: https://fastapi.tiangolo.com/
- Docker Compose: https://docs.docker.com/compose/
- GitHub Actions: https://docs.github.com/en/actions
- AWS ECS Fargate: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP LLM Top 10: https://genai.owasp.org/llm-top-10/
