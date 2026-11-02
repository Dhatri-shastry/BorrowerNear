-- Apply manually in MySQL Workbench as a database administrator, after
-- 01 and 02. This file creates no data rows and does not alter/drop tables.
USE borrownear;

CREATE INDEX idx_items_category_status ON items(category_id, status);
CREATE INDEX idx_users_location ON users(location_id);
CREATE INDEX idx_requests_item_dates_status ON borrow_requests(item_id, status, start_date, end_date);
CREATE INDEX idx_requests_borrower_date ON borrow_requests(borrower_id, request_date);
CREATE INDEX idx_transactions_status_due ON borrow_transactions(status, due_date);
CREATE INDEX idx_reviews_reviewer ON reviews(reviewer_id);

CREATE OR REPLACE VIEW v_borrownear_transaction_history AS
SELECT t.transaction_id, t.status AS transaction_status, t.borrow_date, t.due_date,
       t.return_date, r.request_id, r.status AS request_status,
       i.item_id, i.item_name, c.category_name,
       o.user_id AS owner_id, o.name AS owner_name,
       b.user_id AS borrower_id, b.name AS borrower_name
FROM borrow_transactions t
JOIN borrow_requests r ON r.request_id=t.request_id
JOIN items i ON i.item_id=r.item_id
JOIN categories c ON c.category_id=i.category_id
JOIN users o ON o.user_id=i.owner_id
JOIN users b ON b.user_id=r.borrower_id;

DELIMITER $$
CREATE PROCEDURE sp_borrownear_category_stats()
BEGIN
  SELECT c.category_id, c.category_name,
         COUNT(DISTINCT i.item_id) AS item_count,
         COUNT(DISTINCT r.request_id) AS request_count,
         COUNT(DISTINCT t.transaction_id) AS transaction_count
  FROM categories c
  LEFT JOIN items i ON i.category_id=c.category_id
  LEFT JOIN borrow_requests r ON r.item_id=i.item_id
  LEFT JOIN borrow_transactions t ON t.request_id=r.request_id
  GROUP BY c.category_id,c.category_name
  HAVING COUNT(DISTINCT i.item_id) >= 0
  ORDER BY transaction_count DESC,request_count DESC;
END$$

CREATE TRIGGER trg_request_no_self_borrow
BEFORE INSERT ON borrow_requests FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM items WHERE item_id=NEW.item_id AND owner_id=NEW.borrower_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='An owner cannot request their own item';
  END IF;
END$$

CREATE TRIGGER trg_request_approval_guard
BEFORE UPDATE ON borrow_requests FOR EACH ROW
BEGIN
  IF NEW.status='APPROVED' AND OLD.status<>'APPROVED' THEN
    IF EXISTS (SELECT 1 FROM borrow_requests x WHERE x.item_id=NEW.item_id
      AND x.request_id<>NEW.request_id AND x.status='APPROVED'
      AND x.start_date<=NEW.end_date AND x.end_date>=NEW.start_date) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Approved borrowing dates overlap';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_transaction_insert_guard
BEFORE INSERT ON borrow_transactions FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_start DATE;
  DECLARE v_end DATE;
  SELECT status,start_date,end_date INTO v_status,v_start,v_end
    FROM borrow_requests WHERE request_id=NEW.request_id;
  IF v_status IS NULL OR v_status<>'APPROVED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Transaction requires an approved request';
  END IF;
  IF NEW.borrow_date<>v_start OR NEW.due_date<>v_end THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Transaction dates must match its request';
  END IF;
END$$

CREATE TRIGGER trg_review_participant_guard
BEFORE INSERT ON reviews FOR EACH ROW
BEGIN
  DECLARE v_borrower INT;
  DECLARE v_owner INT;
  DECLARE v_status VARCHAR(20);
  SELECT r.borrower_id,i.owner_id,t.status INTO v_borrower,v_owner,v_status
  FROM borrow_transactions t JOIN borrow_requests r ON r.request_id=t.request_id
  JOIN items i ON i.item_id=r.item_id WHERE t.transaction_id=NEW.transaction_id;
  IF v_status IS NULL OR v_status<>'RETURNED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reviews require a returned transaction';
  END IF;
  IF NEW.reviewer_id<>v_borrower AND NEW.reviewer_id<>v_owner THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Reviewer must be a transaction participant';
  END IF;
END$$

CREATE TRIGGER trg_transaction_item_status_insert
AFTER INSERT ON borrow_transactions FOR EACH ROW
BEGIN
  UPDATE items i JOIN borrow_requests r ON r.item_id=i.item_id
     SET i.status='BORROWED' WHERE r.request_id=NEW.request_id;
END$$

CREATE TRIGGER trg_transaction_item_status_update
AFTER UPDATE ON borrow_transactions FOR EACH ROW
BEGIN
  IF NEW.status='RETURNED' AND OLD.status<>'RETURNED' THEN
    UPDATE items i JOIN borrow_requests r ON r.item_id=i.item_id
       SET i.status='AVAILABLE' WHERE r.request_id=NEW.request_id;
  END IF;
END$$
DELIMITER ;

-- Inspect installed features:
-- SHOW FULL TABLES IN borrownear WHERE TABLE_TYPE='VIEW';
-- SHOW PROCEDURE STATUS WHERE Db='borrownear';
-- SHOW TRIGGERS FROM borrownear;
-- SHOW INDEX FROM items;
