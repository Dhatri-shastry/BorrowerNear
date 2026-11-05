-- Role support. Preserves existing USER accounts for one-time role selection.
ALTER TABLE users
    MODIFY COLUMN role ENUM('USER', 'LENDER', 'BORROWER', 'ADMIN') NOT NULL DEFAULT 'USER';
