-- Run once against an existing BorrowNear database before deploying the RBAC backend.
-- This adds role values without deleting accounts, listings, or other rows.
USE borrownear;

ALTER TABLE users
    MODIFY COLUMN role ENUM('USER', 'LENDER', 'BORROWER', 'ADMIN') NOT NULL DEFAULT 'USER';
