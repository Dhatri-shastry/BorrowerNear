# Requirement-to-implementation checklist

## Source review and scope

The pasted request mentions an official requirements PDF, but no matching PDF is available in the workspace or Downloads. The available `DBMS Level 3 Mini_Project Requirements draft.docx` was read completely and is the source used below. If the instructor has a newer PDF, compare it before submission.

The available course document is `C:\Users\dhatr\Downloads\DBMS Level 3 Mini_Project Requirements draft.docx`; it is a draft, not the official PDF referenced in the pasted request. The original stage SQL files are also in Downloads. The project migration is `backend/sql/05_borrownear_advanced_features.sql`. The previously inspected live database had seven base tables and sample counts (4 locations, 6 users, 5 categories, 10 items, 11 requests, 6 transactions, 6 reviews). Read-only inspection found no views, routines, triggers or named `idx_*` indexes installed in that live schema.

## Checklist

| Requirement from the available course brief | Current implementation | Status / follow-up |
|---|---|---|
| Meaningful project beyond basic CRUD | Item sharing with date-bounded requests, approval, loans, returns, ratings, inbox, cache and analytics | Implemented in application; demonstrate end-to-end workflow in presentation |
| SQL plus a second database paradigm | MySQL holds normalized transactional records; Redis will hold persistent conversation streams and ephemeral cache/rate-limit keys | Implemented in code/config; Docker/Redis runtime verification awaits Docker Engine |
| ER diagram and relational schema | `backend/docs/architecture.md`; original seven-table schema is preserved in `backend/sql/` | Implemented; add the actual diagram screenshot if the submission template requires an image |
| Keys, relationships, constraints and validation | Existing PK/FK/UNIQUE/CHECK/ENUM constraints plus Pydantic request validation and ownership checks | Implemented in base schema/application; verify CHECK enforcement on MySQL 8.0.16+ |
| CREATE, ALTER, DROP and DDL demonstration | Base schema and safe Docker initialization cover CREATE; original schema script documents DROP but is destructive; no ALTER migration is currently required | Partial; demonstrate DDL in a disposable schema or document safely; never run the DROP schema against the populated database |
| INSERT, UPDATE, DELETE, SELECT | Registration, listing creation/update/deactivation, requests, transaction, review flows and read endpoints | Implemented; DELETE listing is a soft deactivation to preserve foreign-key history |
| Joins, aggregates, GROUP BY, HAVING, ORDER BY, subqueries | Item/profile joins, category analytics and admin aggregates; SQL verification has EXISTS/NOT EXISTS | Implemented in source; database query exercises are safe to run read-only |
| Four or more advanced database concepts | Transactions and indexes are present in base/engine; `05` adds a view, procedure and triggers | Partial until DBA applies migration `05` to the intended database; live schema currently lacks those objects |
| Next.js web application | Responsive connected UI for browse, details, auth, dashboard, listing management, messaging, profiles and admin statistics | Implemented; lint/typecheck/build passed; manual browser demonstration remains |
| API integration and authentication | FastAPI, JWT, Argon2 hashes, USER/ADMIN checks and parameterized MySQL | Implemented; MySQL `/health` and read endpoints verified live |
| Security and secrets | Environment configuration, `.env` ignore rules, explicit CORS origins, request schemas, participant/owner checks | Implemented; user must keep local credentials private |
| Redis NoSQL feature | Hashes, participant Sets, inbox Sorted Sets, message Streams, request lookup Strings, TTL cache and expiring rate-limit counters | Implemented; live Redis writes/persistence and restart recovery await Docker Engine |
| Docker Compose delivery | Four services, health checks, internal network, persistent MySQL/Redis volumes and safe first-run SQL copies | Configuration prepared; cannot build/start while Docker Engine pipe is unavailable |
| Tests and demonstration results | Backend unit tests, frontend lint/typecheck/build and live database checks | Verified results in README; full Compose integration remains blocked by Docker Desktop not running |
| Documentation and team contribution | README and architecture/checklist docs | Technical docs implemented; team member contributions, screenshots, conclusion/future work and instructor submission details require student-specific completion |
| Two-member team and unique title | Not inferable from code | Confirm with instructor/team; not an application feature |

## Preservation notes

- `backend/sql/docker_init/001_schema.sql` is a separate Docker-only copy of the base schema with its `DROP DATABASE` line removed. It is mounted only into a fresh Compose MySQL volume and never targets the user's existing Workbench server.
- `backend/sql/docker_init/002_sample_data.sql` seeds only that new Docker volume on first initialization.
- `backend/sql/docker_init/003_advanced_features.sql` applies the existing advanced migration only inside that new Docker volume on first initialization.
- The former `conversations` and `messages` collections were count-checked and both contained zero documents before migration. No persisted messages needed migration, and no external data store was dropped or modified.
- The Redis data uses AOF plus a named Docker volume. AOF recovery across actual container restarts still needs to be demonstrated once Docker Desktop is running.
