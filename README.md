# BorrowNear

BorrowNear is a neighbourhood item-sharing application for the DBMS Level 3 mini project. Members can publish useful belongings, request date-bounded loans, approve handovers, record returns, review completed exchanges and message the other participant.

## Architecture

- **Next.js, React, TypeScript and Tailwind CSS** provide the responsive web interface.
- **FastAPI** validates requests, applies authorization, runs MySQL transactions and coordinates Redis messaging/cache operations.
- **MySQL** is authoritative for users, locations, categories, items, borrow requests, transactions and reviews. Foreign keys, unique/check constraints and transaction boundaries protect relational integrity.
- **Redis** is the NoSQL key-value store. It uses:
  - Hashes for conversation metadata.
  - Sets for participant membership.
  - Sorted sets for each user's recent conversations.
  - Streams for message history.
  - Strings for request-to-conversation mapping.
  - Short-lived strings for item-list cache and message rate limits.

The browser communicates only with FastAPI. MySQL and Redis credentials stay in the backend environment.

Refer to the following documentation:

- [Architecture Documentation](backend/docs/architecture.md) – Key names, ER diagrams and service diagrams.
- [Requirements Checklist](backend/docs/requirements-checklist.md) – Requirement implementation status.
- [Project Report](backend/docs/project-report.md) – Data dictionary and evaluation write-up.

## Existing MySQL Schema

The seven base tables are:

1. `locations`
2. `users`
3. `categories`
4. `items`
5. `borrow_requests`
6. `borrow_transactions`
7. `reviews`

The original schema includes primary keys, foreign keys, UNIQUE and CHECK constraints, status enums and a generated pending-request uniqueness guard.

**Important:** The supplied original schema script includes a `DROP DATABASE` statement. Do not run it against your existing Workbench database.

The available course requirements file is a draft DOCX, not the PDF mentioned in the pasted request. It was read fully. No matching official PDF was available in the workspace or Downloads at audit time. Compare against the instructor's final PDF if one exists.

## Prerequisites

- Python 3.10+
- VS Code
- Node.js 20.9+
- npm
- Docker Desktop with Docker Engine running (Docker CLI alone is not enough)
- MySQL Workbench for inspecting the existing local database

Docker Compose also runs a separate MySQL 8.4 service and never mounts or replaces the Workbench server.

## Local Development (PowerShell)

The repository keeps the API under `backend/` and the web application under `frontend/`.

**Important:** `npm run dev` is only for the frontend. The `backend/` directory has no `package.json` and must be started using Uvicorn.

Run these commands in separate PowerShell terminals from the project root.

### 1. Backend Environment Setup

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r ..\requirements-dev.txt
Set-Location ..
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

### 2. Environment Configuration

Edit `.env` locally.

Configure the following:

- A strong `JWT_SECRET`.
- Existing MySQL connection fields if running FastAPI outside Docker.
- `REDIS_URL`.
- Docker-only `MYSQL_ROOT_PASSWORD`.

Never commit `.env` or share its contents.

Generate a JWT secret locally using:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Local Service Defaults

| Service | Host | Port |
|---|---|---|
| MySQL | localhost | 3306 |
| Redis | localhost | 6379 |

The Compose MySQL instance is published at `localhost:3307` by default to avoid colliding with an existing Workbench server on port 3306.

### 4. Start the Backend

After starting MySQL and Redis locally, start the backend from its folder.

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

The parent `.env` file is automatically discovered.

### 5. Start the Frontend

Open another terminal from the project root.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

The browser calls the same-origin `/api/v1` path. Next.js proxies those requests to FastAPI, avoiding browser CORS and host-name mismatches.

- In Docker, the proxy target is `backend:8000`.
- For local `npm run dev`, it defaults to `127.0.0.1:8000`.

## Docker Compose (Recommended Complete Stack)

Docker Desktop must be running before executing these commands.

Add a fresh local `MYSQL_ROOT_PASSWORD` to `.env` if it is absent.

Compose uses:

- A separate named MySQL volume.
- A separate MySQL application account.
- MySQL published on port `3307` by default.

The pre-existing Workbench database on port `3306` is not used, altered or deleted by this stack.

### Start the Complete Application

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100 backend
```

The fresh Compose MySQL volume receives safe Docker-only copies of the schema and sample data, followed by the advanced SQL migration.

The schema copy has no `DROP DATABASE` statement. Initialization scripts run only when Docker's MySQL data directory is first initialized.

**Warning:** Do not execute `docker compose down -v`. This removes the persistent Compose data volumes.

### Stop the Application Without Deleting Data

```powershell
docker compose down
```

### Restart Without Rebuilding

```powershell
docker compose up -d
```

### Service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| MySQL | localhost:3307 |
| Redis | localhost:6379 |

Container-internal backend addresses:

- MySQL: `mysql:3306`
- Redis: `redis:6379`

The browser uses:

`http://localhost:8000/api/v1`

## URLs and API

| Endpoint | Description |
|---|---|
| `http://localhost:3000` | Frontend application |
| `http://localhost:8000/health` | MySQL-backed health check and actual item count |
| `http://localhost:8000/ready` | MySQL and Redis readiness check |
| `http://localhost:8000/docs` | Swagger UI |

### API Features

**Public/read API:**

- Item search with category, location and status filters.
- Pagination and sorting.
- Item details and reviews.
- Categories and locations.
- Public owner profiles.
- Category statistics.
- Overdue analytics.

**Protected API:**

- Registration, login and profile management.
- Item management.
- Borrowing requests.
- Owner decisions.
- Handover and return operations.
- Participant reviews.
- Borrowing history.
- Request-linked messaging.
- Admin statistics.

Listing `DELETE` is implemented as a soft deactivation to `UNAVAILABLE`, preserving historical foreign-key relationships.

All user values are parameterized in SQL.

Redis outages cause `/ready` and messaging to fail, while item-list caching fails open to MySQL.

## Redis Key Design and Persistence

The Compose Redis service enables AOF persistence:

- `appendonly yes`
- `appendfsync everysec`

It also uses the persistent `redis_data` volume.

Application keys are documented in `backend/app/redis_store.py`.

### Redis Implementation

- Streams retain up to the latest 10,000 messages per conversation.
- Item-list cache keys use a SHA-256 digest of normalized filters.
- Cache entries expire after `CACHE_TTL_SECONDS`.
- Item writes and availability transitions invalidate relevant cache keys.
- Message sends use a per-user fixed-window rate counter with expiry.

### Redis Inspection from PowerShell

If `redis-cli` is installed locally:

```powershell
redis-cli -h localhost -p 6379 PING
redis-cli -h localhost -p 6379 INFO persistence
redis-cli -h localhost -p 6379 --scan --pattern "conversation:*"
```

Alternatively, inspect Redis from its container:

```powershell
docker compose exec redis redis-cli
```

Persistence across an actual container restart must be demonstrated on the user's Docker Desktop.

AOF and the named volume are configured, but the current environment could not reach Docker Engine during implementation.

## SQL Scripts and Advanced Features

The original schema, sample, verification and negative-test SQL files remain in Downloads and were not edited or run destructively.

The live schema inspection found no custom `idx_*` secondary indexes, views, routines or triggers installed.

### Advanced SQL Migration

The following file contains the manual DBA migration for an existing Workbench database:

`backend/sql/05_borrownear_advanced_features.sql`

Before running it in Workbench:

1. Inspect the database for existing object-name collisions.
2. Review the migration statements.
3. Run it only once if you want the advanced features installed in that database.

The Docker copy is applied only to a new, isolated Compose MySQL volume.

The migration adds:

- Secondary indexes.
- `v_borrownear_transaction_history` view.
- `sp_borrownear_category_stats` stored procedure.
- Integrity triggers.

Application CRUD operations do not require DDL privileges.

### Database Technology Choice

The original project has no need for vector search.

MySQL is the appropriate store for constrained relational loan records, while Redis is used for:

- Fast participant inboxes.
- Append-only message streams.
- Expiring cache values.
- Rate-limit counters.

## Testing and Verification

### Backend Tests

From the backend directory, install the test dependencies:

```powershell
pip install -r ..\requirements-dev.txt
```

Run the test suite:

```powershell
python -m pytest -q
```

### Frontend Checks

From the `frontend/` directory:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Backend tests use mocked SQL and in-memory fakeredis, ensuring that they never write to the Workbench sample database.

Live MySQL and Redis checks are available through:

- `/health`
- `/ready`

Docker image builds, Redis AOF recovery and full Compose restart tests remain to be run after Docker Desktop starts successfully.



## Verified on 1 November 2026

| Verification | Result |
|---|---|
| Backend `python -m pytest -q` | **14 passed** |
| Frontend lint | **Passed** |
| Frontend typecheck | **Passed** |
| Frontend build | **Passed** |
| Live `/health` | **HTTP 200** |
| Actual items in database | **10** |
| Live `/ready` | **HTTP 503** |
| MySQL connectivity | **OK** |
| Redis connectivity | **Unavailable** |
| `docker compose config --quiet` | **Passed** |

### Additional Observations

- Backend tests passed with one Starlette/httpx deprecation warning.
- After moving the backend folder, launching Uvicorn from `backend/` and requesting `/health` again returned HTTP 200 with `items_in_db: 10`.
- `/ready` returned HTTP 503 because the local Redis service was not running, although MySQL connectivity was successful.
- In-memory Redis tests passed for conversation creation, participant sets, inbox ordering, stream messages, rate limiting, TTL cache and invalidation.
- `docker info` could not reach the Docker Engine named pipe. Therefore, Docker image builds and real container persistence checks could not be completed.
- Existing MySQL object inspection found no custom indexes, views, routines or triggers from migration `05`.
- No existing MySQL schema or rows were modified.

## Admin Account

Seeded sample password hashes are placeholders.

To create an actual admin account:

1. Register a real account through the application.
2. Ask a trusted DBA to promote exactly that user through MySQL Workbench.
3. Do not expose admin promotion through a public API route.

Keep user/team contribution records and instructor-specific submission details in the final course report.
