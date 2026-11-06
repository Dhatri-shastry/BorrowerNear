-- =====================================================================
-- BorrowNear | Stage 1: Verification queries (all should run without error)
-- Run AFTER 01 and 02. Execute the whole file, or one query at a time
-- (Ctrl+Enter runs the statement under the cursor in MySQL Workbench).
-- =====================================================================
USE borrownear;

-- ---------------------------------------------------------------------
-- V1. Tables exist (expect 7 rows)
-- ---------------------------------------------------------------------
SHOW TABLES;

-- ---------------------------------------------------------------------
-- V2. Row counts (expect: 4, 6, 5, 10, 11, 6, 6)
-- ---------------------------------------------------------------------
SELECT 'locations' AS table_name, COUNT(*) AS row_count FROM locations
UNION ALL SELECT 'users',               COUNT(*) FROM users
UNION ALL SELECT 'categories',          COUNT(*) FROM categories
UNION ALL SELECT 'items',               COUNT(*) FROM items
UNION ALL SELECT 'borrow_requests',     COUNT(*) FROM borrow_requests
UNION ALL SELECT 'borrow_transactions', COUNT(*) FROM borrow_transactions
UNION ALL SELECT 'reviews',             COUNT(*) FROM reviews;

-- ---------------------------------------------------------------------
-- V3. Foreign keys (expect 8 rows)
-- ---------------------------------------------------------------------
SELECT k.TABLE_NAME, k.COLUMN_NAME, k.CONSTRAINT_NAME,
       k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME,
       r.DELETE_RULE, r.UPDATE_RULE
FROM information_schema.KEY_COLUMN_USAGE k
JOIN information_schema.REFERENTIAL_CONSTRAINTS r
  ON r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA
 AND r.CONSTRAINT_NAME   = k.CONSTRAINT_NAME
WHERE k.TABLE_SCHEMA = 'borrownear'
  AND k.REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME;

-- ---------------------------------------------------------------------
-- V4. CHECK constraints (expect 13 rows)
-- ---------------------------------------------------------------------
SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE
FROM information_schema.CHECK_CONSTRAINTS cc
JOIN information_schema.TABLE_CONSTRAINTS tc
  ON tc.CONSTRAINT_SCHEMA = cc.CONSTRAINT_SCHEMA
 AND tc.CONSTRAINT_NAME   = cc.CONSTRAINT_NAME
WHERE cc.CONSTRAINT_SCHEMA = 'borrownear'
ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME;

-- ---------------------------------------------------------------------
-- V5. UNIQUE constraints and primary keys
-- ---------------------------------------------------------------------
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'borrownear'
  AND CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')
ORDER BY TABLE_NAME, CONSTRAINT_TYPE, CONSTRAINT_NAME;

-- ---------------------------------------------------------------------
-- V6. Full relationship chain: item -> owner, borrower, request,
--     transaction (expect 6 rows)
-- ---------------------------------------------------------------------
SELECT t.transaction_id,
       i.item_name,
       c.category_name,
       o.name  AS owner,
       b.name  AS borrower,
       r.status AS request_status,
       t.status AS txn_status,
       i.status AS item_status,
       t.borrow_date, t.due_date, t.return_date
FROM borrow_transactions t
JOIN borrow_requests r ON r.request_id  = t.request_id
JOIN items           i ON i.item_id     = r.item_id
JOIN categories      c ON c.category_id = i.category_id
JOIN users           o ON o.user_id     = i.owner_id
JOIN users           b ON b.user_id     = r.borrower_id
ORDER BY t.transaction_id;

-- ---------------------------------------------------------------------
-- V7. Reviews with reviewer, and the person being reviewed
--     (reviewee is derived: if the reviewer is the borrower, the
--     reviewee is the owner, and vice versa). Expect 6 rows.
-- ---------------------------------------------------------------------
SELECT rv.review_id, rv.transaction_id, i.item_name,
       rer.name AS reviewer,
       IF(rv.reviewer_id = r.borrower_id, o.name, bw.name) AS reviewee,
       rv.rating, rv.comment
FROM reviews rv
JOIN borrow_transactions t ON t.transaction_id = rv.transaction_id
JOIN borrow_requests     r ON r.request_id     = t.request_id
JOIN items               i ON i.item_id        = r.item_id
JOIN users             rer ON rer.user_id      = rv.reviewer_id
JOIN users               o ON o.user_id        = i.owner_id
JOIN users              bw ON bw.user_id       = r.borrower_id
ORDER BY rv.review_id;

-- ---------------------------------------------------------------------
-- V8. Consistency audit. EXPECT ZERO ROWS.
--     These rules cannot be expressed as CHECK constraints (they span
--     several tables), so the schema alone does not stop violations;
--     triggers/procedures in a later stage will. This query detects them.
-- ---------------------------------------------------------------------
SELECT 'owner borrowing own item' AS violation, r.request_id AS record_id
FROM borrow_requests r
JOIN items i ON i.item_id = r.item_id
WHERE i.owner_id = r.borrower_id

UNION ALL
SELECT 'overlapping APPROVED requests for same item', a.request_id
FROM borrow_requests a
JOIN borrow_requests b
  ON a.item_id = b.item_id
 AND a.request_id < b.request_id
 AND a.status = 'APPROVED' AND b.status = 'APPROVED'
 AND a.start_date <= b.end_date AND b.start_date <= a.end_date

UNION ALL
SELECT 'transaction for a request that is not APPROVED', t.transaction_id
FROM borrow_transactions t
JOIN borrow_requests r ON r.request_id = t.request_id
WHERE r.status <> 'APPROVED'

UNION ALL
SELECT 'item BORROWED but no ACTIVE/OVERDUE transaction', i.item_id
FROM items i
WHERE i.status = 'BORROWED'
  AND NOT EXISTS (
        SELECT 1 FROM borrow_requests r
        JOIN borrow_transactions t ON t.request_id = r.request_id
        WHERE r.item_id = i.item_id AND t.status IN ('ACTIVE', 'OVERDUE'))

UNION ALL
SELECT 'ACTIVE/OVERDUE transaction but item not BORROWED', i.item_id
FROM items i
WHERE i.status <> 'BORROWED'
  AND EXISTS (
        SELECT 1 FROM borrow_requests r
        JOIN borrow_transactions t ON t.request_id = r.request_id
        WHERE r.item_id = i.item_id AND t.status IN ('ACTIVE', 'OVERDUE'))

UNION ALL
SELECT 'item RESERVED but no APPROVED request awaiting handover', i.item_id
FROM items i
WHERE i.status = 'RESERVED'
  AND NOT EXISTS (
        SELECT 1 FROM borrow_requests r
        LEFT JOIN borrow_transactions t ON t.request_id = r.request_id
        WHERE r.item_id = i.item_id AND r.status = 'APPROVED'
          AND t.transaction_id IS NULL)

UNION ALL
SELECT 'review by someone not part of the transaction', rv.review_id
FROM reviews rv
JOIN borrow_transactions t ON t.transaction_id = rv.transaction_id
JOIN borrow_requests     r ON r.request_id     = t.request_id
JOIN items               i ON i.item_id        = r.item_id
WHERE rv.reviewer_id NOT IN (r.borrower_id, i.owner_id)

UNION ALL
SELECT 'review on a transaction that is not RETURNED', rv.review_id
FROM reviews rv
JOIN borrow_transactions t ON t.transaction_id = rv.transaction_id
WHERE t.status <> 'RETURNED';

-- ---------------------------------------------------------------------
-- V9. trust_score vs. average rating received. Expect stored_score = computed_score
--     for every user.
-- ---------------------------------------------------------------------
SELECT u.user_id, u.name, u.trust_score AS stored_score,
       ROUND(COALESCE(x.avg_rating, 0), 2) AS computed_score
FROM users u
LEFT JOIN (
    SELECT IF(rv.reviewer_id = r.borrower_id, i.owner_id, r.borrower_id) AS reviewee_id,
           AVG(rv.rating) AS avg_rating
    FROM reviews rv
    JOIN borrow_transactions t ON t.transaction_id = rv.transaction_id
    JOIN borrow_requests     r ON r.request_id     = t.request_id
    JOIN items               i ON i.item_id        = r.item_id
    GROUP BY reviewee_id
) x ON x.reviewee_id = u.user_id
ORDER BY u.user_id;

-- ---------------------------------------------------------------------
-- V10. Generated column check: pending_flag is 1 only for PENDING rows
-- ---------------------------------------------------------------------
SELECT request_id, status, pending_flag FROM borrow_requests ORDER BY request_id;
