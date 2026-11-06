-- =====================================================================
-- BorrowNear | Stage 1: Negative tests
-- Every statement below is EXPECTED TO FAIL. That is the test passing.
-- Run them ONE AT A TIME (Ctrl+Enter), not as a whole script, because
-- Workbench stops a script at the first error.
-- If any statement succeeds, the constraint it targets is not working;
-- run the cleanup block at the bottom to remove the stray row.
-- =====================================================================
USE borrownear;

-- N1. Request end date not after start date            -> Error 3819 (chk_request_dates)
INSERT INTO borrow_requests (item_id, borrower_id, start_date, end_date)
VALUES (2, 3, '2026-11-10', '2026-11-10');

-- N2. Rating outside 1-5                               -> Error 3819 (chk_rating)
INSERT INTO reviews (transaction_id, reviewer_id, rating, comment)
VALUES (1, 2, 6, 'rating out of range');

-- N3. Same person reviews the same transaction twice   -> Error 1062 (uq_review_per_reviewer)
INSERT INTO reviews (transaction_id, reviewer_id, rating, comment)
VALUES (2, 2, 4, 'duplicate review');

-- N4. Duplicate email                                  -> Error 1062 (users.email)
INSERT INTO users (name, email, phone, password_hash, location_id)
VALUES ('Dup Email', 'rohan.mehta@example.com', '9876500099', 'x', 1);

-- N5. Malformed phone number                           -> Error 3819 (chk_user_phone)
INSERT INTO users (name, email, phone, password_hash, location_id)
VALUES ('Bad Phone', 'bad.phone@example.com', '12345', 'x', 1);

-- N6. Foreign key violation: item with non-existent owner -> Error 1452
INSERT INTO items (owner_id, category_id, item_name, estimated_value)
VALUES (999, 1, 'Ghost item', 100.00);

-- N7. Deposit larger than item value                   -> Error 3819 (chk_item_deposit)
INSERT INTO items (owner_id, category_id, item_name, estimated_value, deposit_amount)
VALUES (2, 1, 'Over-deposit item', 100.00, 500.00);

-- N8. Second PENDING request, same borrower and item   -> Error 1062 (uq_one_pending_request)
--     (request 6 is already PENDING for item 7 by user 6)
INSERT INTO borrow_requests (item_id, borrower_id, start_date, end_date)
VALUES (7, 6, '2026-11-01', '2026-11-03');

-- N9. Second transaction for the same request          -> Error 1062 (borrow_transactions.request_id)
INSERT INTO borrow_transactions (request_id, borrow_date, due_date)
VALUES (1, '2026-10-08', '2026-10-15');

-- N10. RETURNED transaction without a return date      -> Error 3819 (chk_status_vs_return)
INSERT INTO borrow_transactions (request_id, borrow_date, due_date, status)
VALUES (4, '2026-10-16', '2026-10-20', 'RETURNED');

-- N11. Return date before borrow date                  -> Error 3819 (chk_return_date)
UPDATE borrow_transactions
SET return_date = '2026-09-01', status = 'RETURNED'
WHERE transaction_id = 3;

-- N12. Deleting a user that other rows depend on       -> Error 1451 (RESTRICT)
DELETE FROM users WHERE user_id = 2;

-- N13. Invalid enum value                              -> Error 1265 (Data truncated) in strict mode
UPDATE items SET status = 'LOST' WHERE item_id = 2;

-- N14. Invalid trust score                             -> Error 3819 (chk_trust_score)
UPDATE users SET trust_score = 7.50 WHERE user_id = 2;

-- ---------------------------------------------------------------------
-- Known gaps (these statements WOULD currently succeed; they need
-- triggers/procedures in a later stage, so they are not listed above):
--   * an owner requesting their own item
--   * approving two overlapping requests for the same item
--   * a review written by someone who was not part of the transaction
--   * item status drifting out of sync with transaction status
-- Re-run V8 in 03_borrownear_verification.sql to detect such rows.
-- ---------------------------------------------------------------------
