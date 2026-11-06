CREATE DATABASE borrownear;

USE borrownear;

CREATE TABLE locations (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    locality VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    pincode VARCHAR(10) NOT NULL
);

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    
    name VARCHAR(100) NOT NULL,
    
    email VARCHAR(150) NOT NULL UNIQUE,
    
    phone VARCHAR(20) NOT NULL UNIQUE,
    
    password_hash VARCHAR(255) NOT NULL,
    
    location_id INT NOT NULL,
    
    role ENUM('USER', 'ADMIN') NOT NULL DEFAULT 'USER',
    
    trust_score DECIMAL(3,2) DEFAULT 0.00,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_users_location
        FOREIGN KEY (location_id)
        REFERENCES locations(location_id)
);

CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    
    category_name VARCHAR(100) NOT NULL UNIQUE,
    
    description VARCHAR(500)
);

CREATE TABLE items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    
    owner_id INT NOT NULL,
    
    category_id INT NOT NULL,
    
    item_name VARCHAR(150) NOT NULL,
    
    description TEXT,
    
    `condition` VARCHAR(100),
    
    estimated_value DECIMAL(10,2) NOT NULL,
    
    deposit_amount DECIMAL(10,2) DEFAULT 0.00,
    
    status ENUM(
        'AVAILABLE',
        'RESERVED',
        'BORROWED',
        'UNAVAILABLE'
    ) NOT NULL DEFAULT 'AVAILABLE',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_items_owner
        FOREIGN KEY (owner_id)
        REFERENCES users(user_id),
    
    CONSTRAINT fk_items_category
        FOREIGN KEY (category_id)
        REFERENCES categories(category_id)
);

CREATE TABLE borrow_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    
    item_id INT NOT NULL,
    
    borrower_id INT NOT NULL,
    
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    start_date DATE NOT NULL,
    
    end_date DATE NOT NULL,
    
    status ENUM(
        'PENDING',
        'APPROVED',
        'REJECTED',
        'CANCELLED'
    ) NOT NULL DEFAULT 'PENDING',
    
    CONSTRAINT fk_requests_item
        FOREIGN KEY (item_id)
        REFERENCES items(item_id),
    
    CONSTRAINT fk_requests_borrower
        FOREIGN KEY (borrower_id)
        REFERENCES users(user_id),
    
    CONSTRAINT chk_request_dates
        CHECK (end_date > start_date)
);

CREATE TABLE borrow_transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    
    request_id INT NOT NULL UNIQUE,
    
    borrow_date DATE NOT NULL,
    
    due_date DATE NOT NULL,
    
    return_date DATE,
    
    status ENUM(
        'ACTIVE',
        'RETURNED',
        'OVERDUE',
        'CANCELLED'
    ) NOT NULL DEFAULT 'ACTIVE',
    
    condition_before TEXT,
    
    condition_after TEXT,
    
    CONSTRAINT fk_transactions_request
        FOREIGN KEY (request_id)
        REFERENCES borrow_requests(request_id),
    
    CONSTRAINT chk_due_date
        CHECK (due_date >= borrow_date)
);

CREATE TABLE reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    
    transaction_id INT NOT NULL,
    
    reviewer_id INT NOT NULL,
    
    rating INT NOT NULL,
    
    comment TEXT,
    
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_reviews_transaction
        FOREIGN KEY (transaction_id)
        REFERENCES borrow_transactions(transaction_id),
    
    CONSTRAINT fk_reviews_reviewer
        FOREIGN KEY (reviewer_id)
        REFERENCES users(user_id),
    
    CONSTRAINT chk_rating
        CHECK (rating BETWEEN 1 AND 5)
);


    
    
    