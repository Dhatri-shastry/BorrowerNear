-- =====================================================================
-- BorrowNear | Stage 1: Sample data
-- Run AFTER 01_borrownear_schema.sql.
-- Inserts are in dependency order (parents before children).
-- All people, emails and phone numbers are fictional.
-- password_hash values are dummy placeholders, NOT real hashes; the
-- authentication stage will generate real bcrypt hashes.
-- =====================================================================
USE borrownear;

START TRANSACTION;

-- locations (4) --------------------------------------------------------
INSERT INTO locations (location_id, locality, city, pincode) VALUES
(1, 'Banashankari', 'Bengaluru', '560070'),
(2, 'Jayanagar',    'Bengaluru', '560011'),
(3, 'Koramangala',  'Bengaluru', '560034'),
(4, 'Indiranagar',  'Bengaluru', '560038');

-- users (6: 1 admin, 5 regular) ----------------------------------------
-- trust_score is seeded to match the sample reviews below
-- (average rating received). A later stage will maintain it automatically.
INSERT INTO users (user_id, name, email, phone, password_hash, location_id, role, trust_score) VALUES
(1, 'Ananya Rao',     'ananya.rao@example.com',     '9876500001', '$2b$10$dummyhash.admin.placeholder.000000000000000000000000001', 3, 'ADMIN', 0.00),
(2, 'Rohan Mehta',    'rohan.mehta@example.com',    '9876500002', '$2b$10$dummyhash.rohan.placeholder.000000000000000000000000002', 1, 'USER',  4.50),
(3, 'Priya Nair',     'priya.nair@example.com',     '9876500003', '$2b$10$dummyhash.priya.placeholder.000000000000000000000000003', 1, 'USER',  5.00),
(4, 'Karthik Iyer',   'karthik.iyer@example.com',   '9876500004', '$2b$10$dummyhash.karthik.placeholder.0000000000000000000000004', 2, 'USER',  5.00),
(5, 'Sneha Reddy',    'sneha.reddy@example.com',    '9876500005', '$2b$10$dummyhash.sneha.placeholder.000000000000000000000000005', 3, 'USER',  3.00),
(6, 'Arjun Kulkarni', 'arjun.kulkarni@example.com', '9876500006', '$2b$10$dummyhash.arjun.placeholder.000000000000000000000000006', 4, 'USER',  0.00);

-- categories (5) -------------------------------------------------------
INSERT INTO categories (category_id, category_name, description) VALUES
(1, 'Tools',              'Power tools, hand tools and DIY equipment'),
(2, 'Electronics',        'Cameras, projectors, dev boards and gadgets'),
(3, 'Books',              'Textbooks and reference books'),
(4, 'Sports & Outdoors',  'Camping gear and sports equipment'),
(5, 'Kitchen Appliances', 'Small appliances for cooking');

-- items (10) -----------------------------------------------------------
-- Item status is consistent with the transactions/requests further down:
--   BORROWED    -> has an ACTIVE or OVERDUE transaction (items 1, 9)
--   RESERVED    -> has an APPROVED request not yet handed over (item 5)
--   UNAVAILABLE -> withdrawn by the owner (item 10)
INSERT INTO items (item_id, owner_id, category_id, item_name, description, `condition`, estimated_value, deposit_amount, status) VALUES
(1,  2, 1, 'Bosch Cordless Drill',            '18V drill with 2 batteries and a basic bit set',    'Good',      4500.00, 1000.00, 'BORROWED'),
(2,  2, 4, 'Camping Tent (3-person)',         'Waterproof dome tent with carry bag',               'Excellent', 6000.00, 1500.00, 'AVAILABLE'),
(3,  3, 2, 'Canon DSLR Camera',               'Includes 18-55mm lens, strap and one battery',      'Good',     35000.00, 8000.00, 'AVAILABLE'),
(4,  3, 3, 'Introduction to Algorithms (CLRS)', 'Hardcover, 3rd edition, light highlighting',      'Fair',      1800.00,  300.00, 'AVAILABLE'),
(5,  4, 5, 'Philips Air Fryer',               '4.1 L air fryer, basket and tray included',         'Good',      7500.00, 1500.00, 'RESERVED'),
(6,  4, 1, 'Aluminium Extension Ladder',      '12-foot extendable ladder',                         'Fair',      3500.00,  800.00, 'AVAILABLE'),
(7,  5, 2, 'Portable Projector',              'HD mini projector with HDMI cable and tripod',      'Excellent',12000.00, 3000.00, 'AVAILABLE'),
(8,  5, 4, 'Badminton Racket Set',            'Two rackets, shuttle tube and carry cover',         'Good',      2500.00,  500.00, 'AVAILABLE'),
(9,  6, 2, 'Raspberry Pi 4 Kit',              'Pi 4 (4 GB), case, power supply and 32 GB SD card', 'Excellent', 6500.00, 1500.00, 'BORROWED'),
(10, 6, 3, 'Database System Concepts',        'Silberschatz textbook, 7th edition',                'Good',      1500.00,  300.00, 'UNAVAILABLE');

-- borrow_requests (11) -------------------------------------------------
INSERT INTO borrow_requests (request_id, item_id, borrower_id, request_date, start_date, end_date, status) VALUES
(1,  1, 3, '2026-10-05 10:15:00', '2026-10-08', '2026-10-15', 'APPROVED'),  -- -> txn 1 (ACTIVE)
(2,  3, 2, '2026-09-07 18:40:00', '2026-09-10', '2026-09-14', 'APPROVED'),  -- -> txn 2 (RETURNED)
(3,  9, 4, '2026-09-25 09:05:00', '2026-09-28', '2026-10-05', 'APPROVED'),  -- -> txn 3 (OVERDUE)
(4,  5, 5, '2026-10-11 20:30:00', '2026-10-16', '2026-10-20', 'APPROVED'),  -- item 5 RESERVED, not yet handed over
(5,  2, 4, '2026-08-29 11:00:00', '2026-09-01', '2026-09-05', 'APPROVED'),  -- -> txn 4 (RETURNED)
(6,  7, 6, '2026-10-12 08:20:00', '2026-10-12', '2026-10-14', 'PENDING'),
(7,  6, 3, '2026-09-29 16:45:00', '2026-10-01', '2026-10-03', 'REJECTED'),
(8,  8, 2, '2026-10-10 13:10:00', '2026-10-18', '2026-10-22', 'CANCELLED'),
(9,  4, 5, '2026-09-18 12:00:00', '2026-09-20', '2026-09-27', 'APPROVED'),  -- -> txn 5 (RETURNED, late)
(10, 3, 6, '2026-10-12 19:25:00', '2026-10-20', '2026-10-25', 'PENDING'),
(11, 8, 6, '2026-09-13 15:30:00', '2026-09-15', '2026-09-18', 'APPROVED');  -- -> txn 6 (CANCELLED)

-- borrow_transactions (6) ----------------------------------------------
INSERT INTO borrow_transactions (transaction_id, request_id, borrow_date, due_date, return_date, status, condition_before, condition_after) VALUES
(1, 1,  '2026-10-08', '2026-10-15', NULL,         'ACTIVE',    'Good; minor scratches on casing; 2 batteries and charger handed over', NULL),
(2, 2,  '2026-09-10', '2026-09-14', '2026-09-13', 'RETURNED',  'Good; lens cap, strap and battery included; sensor clean',            'Returned in the same condition'),
(3, 3,  '2026-09-28', '2026-10-05', NULL,         'OVERDUE',   'Excellent; all accessories present',                                  NULL),
(4, 5,  '2026-09-01', '2026-09-05', '2026-09-05', 'RETURNED',  'Excellent; no tears, all pegs present',                               'Slightly muddy, cleaned before return'),
(5, 9,  '2026-09-20', '2026-09-27', '2026-09-29', 'RETURNED',  'Fair; spine slightly worn',                                           'Same as before; returned 2 days late'),
(6, 11, '2026-09-15', '2026-09-18', NULL,         'CANCELLED', NULL,                                                                  NULL);

-- reviews (6) ----------------------------------------------------------
-- Each completed (RETURNED) transaction is reviewed by both the owner
-- and the borrower.
INSERT INTO reviews (review_id, transaction_id, reviewer_id, rating, comment, review_date) VALUES
(1, 2, 2, 5, 'Camera was in great shape and Priya was easy to coordinate with.',  '2026-09-14 10:00:00'),
(2, 2, 3, 5, 'Rohan returned the camera a day early, very careful with it.',      '2026-09-14 12:30:00'),
(3, 4, 4, 4, 'Tent was clean and complete. Pickup timing was slightly flexible.', '2026-09-06 09:15:00'),
(4, 4, 2, 5, 'Karthik cleaned the tent before returning it. Perfect.',            '2026-09-06 11:45:00'),
(5, 5, 5, 5, 'Book in the condition described, very helpful owner.',              '2026-09-30 18:00:00'),
(6, 5, 3, 3, 'Book was fine but returned two days after the agreed date.',        '2026-09-30 19:10:00');

COMMIT;
