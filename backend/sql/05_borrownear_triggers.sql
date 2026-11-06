-- ============================================================
-- BorrowNear: Database Triggers
-- File: 05_borrownear_triggers.sql
--
-- IMPORTANT:
-- Run this only after the borrownear schema exists.
-- Do NOT rerun 01_borrownear_schema.sql to install these triggers:
-- that file contains DROP DATABASE IF EXISTS.
-- ============================================================

USE borrownear;

DELIMITER $$

-- 1. Prevent an owner from requesting their own item.
-- Runs before each INSERT into borrow_requests.
CREATE TRIGGER trg_prevent_own_item_request
BEFORE INSERT ON borrow_requests
FOR EACH ROW
BEGIN
    DECLARE item_owner INT DEFAULT NULL;

    SELECT owner_id INTO item_owner
    FROM items
    WHERE item_id = NEW.item_id;

    IF item_owner = NEW.borrower_id THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Owners cannot request their own items';
    END IF;
END$$


-- 2. Prevent overlapping APPROVED requests when a request is inserted.
CREATE TRIGGER trg_prevent_overlapping_insert
BEFORE INSERT ON borrow_requests
FOR EACH ROW
BEGIN
    DECLARE overlapping_count INT DEFAULT 0;

    IF NEW.status = 'APPROVED' THEN
        SELECT COUNT(*) INTO overlapping_count
        FROM borrow_requests existing_request
        WHERE existing_request.item_id = NEW.item_id
          AND existing_request.status = 'APPROVED'
          AND existing_request.start_date <= NEW.end_date
          AND existing_request.end_date >= NEW.start_date;

        IF overlapping_count > 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'This item already has an overlapping approved request';
        END IF;
    END IF;
END$$


-- 3. Prevent overlapping APPROVED requests when a request is updated.
CREATE TRIGGER trg_prevent_overlapping_update
BEFORE UPDATE ON borrow_requests
FOR EACH ROW
BEGIN
    DECLARE overlapping_count INT DEFAULT 0;

    IF NEW.status = 'APPROVED' THEN
        SELECT COUNT(*) INTO overlapping_count
        FROM borrow_requests existing_request
        WHERE existing_request.item_id = NEW.item_id
          AND existing_request.request_id <> OLD.request_id
          AND existing_request.status = 'APPROVED'
          AND existing_request.start_date <= NEW.end_date
          AND existing_request.end_date >= NEW.start_date;

        IF overlapping_count > 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'This item already has an overlapping approved request';
        END IF;
    END IF;
END$$


-- 4. Allow a review only between the owner and borrower,
--    and only after the transaction has been RETURNED.
-- Assumes reviews.transaction_id, reviewer_id and reviewee_id
-- are the column names in the BorrowNear schema.
CREATE TRIGGER trg_validate_review_participant
BEFORE INSERT ON reviews
FOR EACH ROW
BEGIN
    DECLARE valid_review_count INT DEFAULT 0;

    SELECT COUNT(*) INTO valid_review_count
    FROM borrow_transactions bt
    JOIN borrow_requests br
      ON br.request_id = bt.request_id
    JOIN items i
      ON i.item_id = br.item_id
    WHERE bt.transaction_id = NEW.transaction_id
      AND bt.status = 'RETURNED'
      AND (
          (NEW.reviewer_id = br.borrower_id
           AND NEW.reviewee_id = i.owner_id)
          OR
          (NEW.reviewer_id = i.owner_id
           AND NEW.reviewee_id = br.borrower_id)
      );

    IF valid_review_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only the owner or borrower can review the other participant after the item is returned';
    END IF;
END$$

DELIMITER ;

-- Verify that the triggers were created:
SHOW TRIGGERS;
