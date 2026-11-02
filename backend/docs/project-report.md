# BorrowNear — DBMS Level 3 project report

## Problem statement

Neighbourhood households often buy equipment and household items that are used only occasionally, while nearby people need temporary access to the same items. BorrowNear provides a local listing and borrowing workflow with clear dates, owner approval, handover/return records and participant reviews.

## Objectives and scope

- Let members discover items by text, category, location and availability.
- Record borrowing intent and decisions with relational constraints and transaction history.
- Protect listings and private borrowing records with authentication and ownership checks.
- Provide participant-only messaging without moving transactional lending records out of MySQL.
- Demonstrate relational SQL and a complementary Redis key-value NoSQL model in a working web application.

Out of scope: payments, delivery logistics, public phone/email exposure, and vector/semantic search.

## Functional requirements

Registration/login; user profiles; listing create/edit/deactivate; category/locality browse and search; request, approve/reject/cancel, handover and return; post-return reviews; borrow history; request-participant conversations; admin aggregates. See the API endpoint list in [README.md](../../README.md).

## Non-functional requirements

Parameterized SQL, Argon2 password hashes, expiring JWTs, validated inputs, minimum-privilege service accounts, explicit CORS allowlist, safe errors, transaction rollback, bounded pagination, Redis cache expiry, message-rate limiting, Redis AOF persistence and persistent Compose volumes.

## Database choice and design

MySQL is appropriate for structured entities and cross-row lending rules requiring foreign keys, uniqueness, checks and atomic state transitions. Redis is appropriate for fast key lookup, participant membership, ordered inboxes, append-only chat streams and expiring cache/rate-limit state. Redis does not replace MySQL as the source of truth for lending.

ER diagram and service flow: [architecture.md](architecture.md).

### Relational data dictionary

| Table | Key attributes and relationships |
|---|---|
| `locations` | `location_id` PK; locality, city, six-digit pincode; unique locality/city/pincode |
| `users` | `user_id` PK; unique email/phone; Argon2 `password_hash`; FK `location_id`; role enum; trust score |
| `categories` | `category_id` PK; unique category name, optional description |
| `items` | `item_id` PK; FKs `owner_id`, `category_id`; value/deposit checks; availability enum |
| `borrow_requests` | `request_id` PK; FKs `item_id`, `borrower_id`; start/end date check; request status; generated pending uniqueness flag |
| `borrow_transactions` | `transaction_id` PK; unique FK `request_id`; borrow/due/return dates; status/return consistency check |
| `reviews` | `review_id` PK; FKs `transaction_id`, `reviewer_id`; 1–5 rating check; unique reviewer per transaction |

### Redis data dictionary

Conversation hashes, participant sets, message streams, request-to-conversation string keys, user inbox sorted sets, TTL item-list JSON cache keys and TTL message-rate counters are documented with exact patterns in [architecture.md](architecture.md).

## SQL features and important operations

- Multi-table item reads join owner, category and location; owner history joins requests and transactions.
- Category analytics use `LEFT JOIN`, `COUNT(DISTINCT ...)`, `GROUP BY`, `HAVING` and ordering.
- Overdue reporting uses date comparison and `DATEDIFF`; admin counts use scalar subqueries.
- Item/request rows are selected `FOR UPDATE` before concurrency-sensitive transitions; multi-row writes commit together and roll back on exceptions.
- The base schema provides PK/FK/UNIQUE/CHECK constraints. The live Workbench schema was inspected and currently has no named secondary `idx_*` indexes, views, routines or triggers.
- The one-time migration `backend/sql/05_borrownear_advanced_features.sql` adds secondary indexes, a history view, category procedure and cross-table triggers. It is included in first-run Docker initialization, but it has not been applied to the existing Workbench database.

## System architecture

```text
Browser (Next.js) -> FastAPI -> MySQL (relational source of truth)
                              -> Redis (conversations, cache, rate limits)
Docker Compose: frontend, backend, mysql, redis
```

The browser API URL is public/local (`http://localhost:8000/api/v1`). Docker-internal hostnames are used only by the backend. Detailed Compose networking and persistence are in [README.md](../../README.md).

## Testing results

As of 1 November 2026:

- Backend: 14 pytest tests passed; 1 Starlette/httpx deprecation warning.
- Redis structures: fakeredis tests passed for atomic conversation mapping, participant sets, inbox ordering, message stream read/write, rate limiting and cache invalidation/TTL.
- Frontend: ESLint, TypeScript typecheck and Next.js production build passed.
- Live MySQL: `/health` returned HTTP 200 and actual count 10; sample list/category/location reads returned data.
- Re-tested after moving the Python application into `backend/`: Uvicorn started from that directory and `/health` returned HTTP 200 with `items_in_db: 10`.
- Redis readiness: local host Redis is unavailable without Docker; `/ready` returned 503 with MySQL `ok`, Redis `unavailable`.
- Compose YAML: `docker compose config --quiet` passed. Docker image builds, actual Compose health, Redis AOF recovery and container restart checks could not run because Docker Engine was not running (the Docker named pipe was absent).

## Screenshots and team contribution

Capture the running frontend pages locally after bringing up Compose and add screenshots of browse, item detail, dashboard, messaging and admin views if required by the submission rubric. Fill this section with actual team member names, responsibilities and contribution evidence; that information cannot be inferred from the code.

## Conclusion and future enhancements

BorrowNear now connects a Next.js application to a FastAPI service that separates normalized transactional records from Redis conversation/cache workloads. Future work could add a dedicated isolated integration-test environment, audit trails for admin actions, item image storage and instructor-approved payments or reservation policies. Apply and demonstrate the advanced SQL migration on a disposable or approved schema before the final viva.
