-- =====================================================================
-- BorrowNear | Stage 1: Database foundation (schema)
-- Target: MySQL 8.0.16 or later (CHECK constraints are only enforced
-- from 8.0.16; on older 8.0.x they are parsed but silently ignored).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS borrownear
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE borrownear;

-- ---------------------------------------------------------------------
-- 1. locations
-- ---------------------------------------------------------------------
CREATE TABLE locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    locality    VARCHAR(100) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    pincode     VARCHAR(10)  NOT NULL,

    -- the same neighbourhood must not be stored twice
    CONSTRAINT uq_location UNIQUE (locality, city, pincode),
    -- assumption: Indian 6-digit PIN codes
    CONSTRAINT chk_pincode CHECK (pincode REGEXP '^[0-9]{6}$')
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. users
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(20)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,   -- never store a plain-text password
    location_id   INT NOT NULL,
    role          ENUM('USER', 'LENDER', 'BORROWER', 'ADMIN') NOT NULL DEFAULT 'USER',
    trust_score   DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_users_location
        FOREIGN KEY (location_id) REFERENCES locations(location_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT chk_user_name  CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_user_email CHECK (email REGEXP '^[^@ ]+@[^@ ]+\\.[^@ ]+$'),
    CONSTRAINT chk_user_phone CHECK (phone REGEXP '^[+]?[0-9]{10,15}$'),
    -- trust score is an average of 1-5 star ratings (0 = no reviews yet)
    CONSTRAINT chk_trust_score CHECK (trust_score BETWEEN 0 AND 5)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. categories
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description   VARCHAR(500)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. items
-- ---------------------------------------------------------------------
CREATE TABLE items (
    item_id          INT AUTO_INCREMENT PRIMARY KEY,
    owner_id         INT NOT NULL,
    category_id      INT NOT NULL,
    item_name        VARCHAR(150) NOT NULL,
    description      TEXT,
    `condition`      VARCHAR(100),          -- reserved word: always use backticks
    estimated_value  DECIMAL(10,2) NOT NULL,
    deposit_amount   DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status           ENUM('AVAILABLE', 'RESERVED', 'BORROWED', 'UNAVAILABLE')
                     NOT NULL DEFAULT 'AVAILABLE',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_items_owner
        FOREIGN KEY (owner_id) REFERENCES users(user_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_items_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT chk_item_name     CHECK (CHAR_LENGTH(TRIM(item_name)) > 0),
    CONSTRAINT chk_item_value    CHECK (estimated_value > 0),
    -- assumption: a deposit never exceeds what the item is worth
    CONSTRAINT chk_item_deposit  CHECK (deposit_amount >= 0
                                        AND deposit_amount <= estimated_value)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. borrow_requests
-- ---------------------------------------------------------------------
CREATE TABLE borrow_requests (
    request_id   INT AUTO_INCREMENT PRIMARY KEY,
    item_id      INT NOT NULL,
    borrower_id  INT NOT NULL,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    status       ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')
                 NOT NULL DEFAULT 'PENDING',

    -- helper column: 1 while the request is PENDING, otherwise NULL.
    -- MySQL has no partial unique index, and UNIQUE ignores NULLs, so
    -- this lets us say "one PENDING request per borrower per item"
    -- while still allowing repeat borrowing after earlier requests close.
    pending_flag TINYINT GENERATED ALWAYS AS
                 (CASE WHEN status = 'PENDING' THEN 1 ELSE NULL END) STORED,

    CONSTRAINT fk_requests_item
        FOREIGN KEY (item_id) REFERENCES items(item_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_borrower
        FOREIGN KEY (borrower_id) REFERENCES users(user_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT chk_request_dates CHECK (end_date > start_date),
    CONSTRAINT uq_one_pending_request UNIQUE (item_id, borrower_id, pending_flag)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. borrow_transactions
-- ---------------------------------------------------------------------
CREATE TABLE borrow_transactions (
    transaction_id   INT AUTO_INCREMENT PRIMARY KEY,
    request_id       INT NOT NULL UNIQUE,   -- one transaction per request
    borrow_date      DATE NOT NULL,
    due_date         DATE NOT NULL,
    return_date      DATE,
    status           ENUM('ACTIVE', 'RETURNED', 'OVERDUE', 'CANCELLED')
                     NOT NULL DEFAULT 'ACTIVE',
    condition_before TEXT,
    condition_after  TEXT,

    CONSTRAINT fk_transactions_request
        FOREIGN KEY (request_id) REFERENCES borrow_requests(request_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT chk_due_date    CHECK (due_date >= borrow_date),
    CONSTRAINT chk_return_date CHECK (return_date IS NULL OR return_date >= borrow_date),
    -- a transaction has a return date if and only if it is RETURNED
    CONSTRAINT chk_status_vs_return CHECK (
        (status = 'RETURNED' AND return_date IS NOT NULL)
        OR (status <> 'RETURNED' AND return_date IS NULL)
    )
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. reviews
-- ---------------------------------------------------------------------
CREATE TABLE reviews (
    review_id      INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT NOT NULL,
    reviewer_id    INT NOT NULL,
    rating         INT NOT NULL,
    comment        TEXT,
    review_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_reviews_transaction
        FOREIGN KEY (transaction_id) REFERENCES borrow_transactions(transaction_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_reviews_reviewer
        FOREIGN KEY (reviewer_id) REFERENCES users(user_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5),
    -- each person can review a given transaction only once
    CONSTRAINT uq_review_per_reviewer UNIQUE (transaction_id, reviewer_id)
) ENGINE=InnoDB;
