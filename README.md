# BorrowNear

BorrowNear is a neighbourhood item-sharing application for the DBMS Level 3 mini project. Members can publish useful belongings, request date-bounded loans, approve handovers, record returns, review completed exchanges and message the other participant.

## Architecture

- **Next.js, React, TypeScript and Tailwind CSS** provide the responsive web interface.
- **FastAPI** validates requests, applies authorization, runs MySQL transactions and coordinates Redis messaging/cache operations.
- **MySQL** is authoritative for users, locations, categories, items, borrow requests, transactions and reviews. Foreign keys, unique/check constraints and transaction boundaries protect relational integrity.
- **Redis** is the NoSQL key-value store. It uses hashes for conversation metadata, sets for participant membership, sorted sets for each user's recent conversations, streams for message history, strings for request-to-conversation mapping and short-lived strings for item-list cache and message rate limits.

The browser communicates only with FastAPI. MySQL and Redis credentials stay in the backend environment. See [backend/docs/architecture.md](backend/docs/architecture.md) for key names and the ER/service diagrams, [backend/docs/requirements-checklist.md](backend/docs/requirements-checklist.md) for requirement status, and [backend/docs/project-report.md](backend/docs/project-report.md) for the data dictionary and evaluation write-up.

## Existing MySQL schema

The seven base tables are `locations`, `users`, `categories`, `items`, `borrow_requests`, `borrow_transactions` and `reviews`. The original schema includes PKs, FKs, UNIQUE and CHECK constraints, status enums and a generated pending-request uniqueness guard. The supplied schema script includes a `DROP DATABASE`; **do not run it against your existing Workbench database**.

The available course requirements file is a draft DOCX, not the PDF mentioned in the pasted request. It was read fully. No matching official PDF was available in the workspace or Downloads at audit time; compare against the instructor's final PDF if one exists.

## Prerequisites

- Python 3.10+ and VS Code
- Node.js 20.9+ and npm
- Docker Desktop with Docker Engine running (Docker CLI alone is not enough)
- MySQL Workbench for inspecting the existing local database; Docker Compose also runs a separate MySQL 8.4 service and never mounts or replaces the Workbench server

## Local development (PowerShell)

The repository keeps the API under `backend/` and the web app under `frontend/`. `npm run dev` is only for the frontend; `backend/` has no `package.json` and must be started with Uvicorn. Run these commands in separate PowerShell terminals from the project root:

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r ..\requirements-dev.txt
Set-Location ..
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally. Set a strong `JWT_SECRET`, the existing MySQL connection fields if running FastAPI outside Docker, `REDIS_URL`, and the Docker-only `MYSQL_ROOT_PASSWORD`. Never commit `.env` or share its contents. Generate a JWT secret locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Local service defaults are MySQL `localhost:3306` and Redis `localhost:6379`. The Compose MySQL instance is published at `localhost:3307` by default to avoid colliding with an existing Workbench server on port 3306.

After starting MySQL and Redis locally, start the backend from its folder (the parent `.env` is auto-discovered):

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Start the frontend in another terminal from the project root:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

The browser calls the same-origin `/api/v1` path. Next.js proxies those requests to FastAPI, avoiding browser CORS and host-name mismatches. In Docker, the proxy target is `backend:8000`; for local `npm run dev`, it defaults to `127.0.0.1:8000`.

## Docker Compose (recommended complete stack)

Docker Desktop must be running. Add a fresh local `MYSQL_ROOT_PASSWORD` to `.env` if it is absent. Compose uses a separate named MySQL volume and a separate MySQL app account; the published MySQL port defaults to 3307. The pre-existing Workbench database on port 3306 is not used, altered or deleted by this stack.

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100 backend
```

The fresh Compose MySQL volume receives safe Docker-only copies of the schema and sample data, followed by the advanced SQL migration. The schema copy has no `DROP DATABASE`; init scripts run only when Docker's MySQL data directory is first initialized. Do not run `docker compose down -v`; that removes the persistent Compose data volumes. To stop while preserving data, use:

```powershell
docker compose down
```

To restart without rebuilding:

```powershell
docker compose up -d
```

The four services are frontend `localhost:3000`, backend `localhost:8000`, MySQL `localhost:3307`, and Redis `localhost:6379`. Container-internal backend addresses are `mysql:3306` and `redis:6379`. The browser uses `http://localhost:8000/api/v1`.

## URLs and API

- Frontend: `http://localhost:3000`
- MySQL-backed health and actual item count: `http://localhost:8000/health`
- MySQL + Redis readiness: `http://localhost:8000/ready`
- Swagger UI: `http://localhost:8000/docs`

Read API includes item search/category/location/status filters, pagination and sorting, item detail/reviews, categories, locations, public owner profiles, category statistics and overdue analytics. Protected routes include registration/login/profile, item management, borrowing requests, owner decisions, handover/return, participant reviews, borrowing history, request-linked messaging and admin statistics.

Listing `DELETE` is a soft deactivation to `UNAVAILABLE`; historical foreign-key relationships are preserved. All user values are parameterized in SQL. Redis outages fail `/ready` and messaging but item-list caching fails open to MySQL.

## Redis key design and persistence

The Compose Redis service enables AOF (`appendonly yes`, `appendfsync everysec`) and uses the persistent `redis_data` volume. Application keys are documented in `app/redis_store.py`. Streams retain up to the latest 10,000 messages per conversation. Item-list cache keys use a SHA-256 digest of normalized filters and expire after `CACHE_TTL_SECONDS`; item writes and availability transitions invalidate those keys. Message sends use a per-user fixed-window rate counter with expiry.

Redis inspection from the host (if `redis-cli` is installed):

```powershell
redis-cli -h localhost -p 6379 PING
redis-cli -h localhost -p 6379 INFO persistence
redis-cli -h localhost -p 6379 --scan --pattern "conversation:*"
```

From the Redis container, use `docker compose exec redis redis-cli`. Persistence across an actual container restart must be demonstrated on the user's Docker Desktop; AOF and the named volume are configured, but the current environment could not reach Docker Engine during implementation.

## SQL scripts and advanced features

The original schema, sample, verification and negative-test SQL files remain in Downloads and were not edited or run destructively. The negative tests are intended to fail; do not execute them wholesale against the live database. The live schema inspection found no custom `idx_*` secondary indexes, views, routines or triggers installed.

`backend/sql/05_borrownear_advanced_features.sql` is the manual DBA migration for an existing Workbench database. Inspect for object-name collisions and run once in Workbench only if you want those features installed there. The Compose copy is applied only to a new isolated Compose MySQL volume. The migration adds indexes, `v_borrownear_transaction_history`, `sp_borrownear_category_stats` and integrity triggers. App CRUD does not require DDL privileges.

The original project has no need for vector search. MySQL is the right store for constrained relational loan records; Redis is used for fast participant inboxes, append-only message streams and expiring cache/rate-limit values.

## Testing and verification

From the backend directory, install test dependencies with `pip install -r ..\requirements-dev.txt`, then run:

```powershell
python -m pytest -q
```

Frontend checks from `frontend`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Backend tests use mocked SQL and in-memory fakeredis so they never write to the Workbench sample database. Live MySQL and Redis checks are `/health` and `/ready`. Docker image builds, Redis AOF recovery and full Compose restart tests remain to be run after Docker Desktop starts successfully.

### Verified on 1 November 2026

- `python -m pytest -q`: **14 passed**, with one Starlette/httpx deprecation warning.
- Frontend `npm.cmd run lint`, `npm.cmd run typecheck` and `npm.cmd run build`: **passed**.
- Live `/health`: HTTP 200, actual `items_in_db: 10`.
- After the backend folder move, launching Uvicorn from `backend/` and requesting `/health` again returned HTTP 200 with `items_in_db: 10`.
- Live `/ready`: HTTP 503 with `mysql: ok`, `redis: unavailable` because the local Redis service is not running.
- Redis data operations: in-memory tests passed for conversation creation, participant sets, inbox ordering, stream messages, rate limit, TTL cache and invalidation.
- `docker compose config --quiet`: **passed**. `docker info` cannot reach the Docker Engine named pipe, so image builds and real container persistence checks could not be run.
- Existing MySQL object inspection found no custom indexes/views/routines/triggers from migration `05`; no schema or rows were modified.

## Admin account

New accounts choose **Lender** or **Borrower** at registration. Lenders manage their own listings and incoming requests; borrowers browse and request items. The API checks these roles on write operations as well as hiding unrelated dashboard actions. Existing `USER` accounts get a one-time role choice after sign-in, with their account data preserved.

Run `backend/sql/06_role_based_access.sql` once against an existing `borrownear` database before deploying the RBAC backend. Fresh Compose databases include the role values during initialization. Do not run the initialization schema on an existing database.

Admin accounts cannot be created through public registration. Register a separate account, then have a trusted DBA promote that exact account in Workbench:

```sql
UPDATE borrownear.users SET role='ADMIN' WHERE email='your-admin-email@example.com';
```

Use `/admin/login` for administrator sign-in. The regular login endpoint rejects admin accounts, and admin analytics endpoints require the ADMIN role. Seeded sample password hashes are placeholders and cannot be used to sign in. Keep user/team contribution records and instructor-specific submission details in your final course report.
#   B o r r o w e r N e a r  
 
