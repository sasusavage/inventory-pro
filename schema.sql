-- ============================================================================
-- INVENTORY MANAGEMENT SYSTEM - DATABASE SCHEMA
-- PostgreSQL Schema (for reference - automatically created by SQLAlchemy)
-- ============================================================================

-- Drop existing tables if they exist (careful with this in production!)
DROP TABLE IF EXISTS supplier_payments CASCADE;
DROP TABLE IF EXISTS sale_items CASCADE;
DROP TABLE IF EXISTS sales CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS products CASCADE;

-- ============================================================================
-- PRODUCTS TABLE
-- ============================================================================
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    cost_price NUMERIC(10, 2) NOT NULL,
    selling_price NUMERIC(10, 2) NOT NULL,
    quantity_in_stock INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster SKU lookups
CREATE INDEX idx_products_sku ON products(sku);

-- ============================================================================
-- CUSTOMERS TABLE
-- ============================================================================
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for customer name searches
CREATE INDEX idx_customers_name ON customers(full_name);

-- ============================================================================
-- SUPPLIERS TABLE
-- ============================================================================
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for supplier name searches
CREATE INDEX idx_suppliers_name ON suppliers(name);

-- ============================================================================
-- SALES TABLE
-- ============================================================================
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    total_amount NUMERIC(10, 2) NOT NULL,
    amount_paid NUMERIC(10, 2) DEFAULT 0 NOT NULL,
    balance_due NUMERIC(10, 2) NOT NULL,
    payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('PAID', 'PARTIAL', 'UNPAID')),
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX idx_sales_customer ON sales(customer_id);
CREATE INDEX idx_sales_status ON sales(payment_status);
CREATE INDEX idx_sales_date ON sales(sale_date);

-- ============================================================================
-- SALE_ITEMS TABLE
-- ============================================================================
CREATE TABLE sale_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price_at_sale NUMERIC(10, 2) NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL
);

-- Indexes for sale item lookups
CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX idx_sale_items_product ON sale_items(product_id);

-- ============================================================================
-- SUPPLIER_PAYMENTS TABLE
-- ============================================================================
CREATE TABLE supplier_payments (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    amount_paid NUMERIC(10, 2) NOT NULL,
    description TEXT,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for supplier payment lookups
CREATE INDEX idx_supplier_payments_supplier ON supplier_payments(supplier_id);
CREATE INDEX idx_supplier_payments_date ON supplier_payments(payment_date);

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Insert sample products
INSERT INTO products (name, sku, cost_price, selling_price, quantity_in_stock) VALUES
    ('Laptop Dell XPS 13', 'TECH-001', 800.00, 1200.00, 15),
    ('Wireless Mouse', 'ACC-001', 15.00, 25.00, 50),
    ('USB-C Cable', 'ACC-002', 5.00, 10.00, 100),
    ('Office Chair', 'FURN-001', 150.00, 250.00, 8),
    ('Desk Lamp', 'FURN-002', 20.00, 35.00, 25);

-- Insert sample customers
INSERT INTO customers (full_name, phone, email) VALUES
    ('John Smith', '+1234567890', 'john@example.com'),
    ('Sarah Johnson', '+1234567891', 'sarah@example.com'),
    ('Michael Brown', '+1234567892', NULL);

-- Insert sample suppliers
INSERT INTO suppliers (name, phone) VALUES
    ('Tech Wholesale Inc.', '+1111111111'),
    ('Office Supplies Co.', '+2222222222');

-- ============================================================================
-- USEFUL QUERIES
-- ============================================================================

-- Get all products with low stock (< 10)
-- SELECT * FROM products WHERE quantity_in_stock < 10;

-- Get all customers with outstanding balances
-- SELECT c.id, c.full_name, c.phone, SUM(s.balance_due) as total_debt
-- FROM customers c
-- JOIN sales s ON c.id = s.customer_id
-- WHERE s.balance_due > 0
-- GROUP BY c.id;

-- Get total sales for today
-- SELECT SUM(total_amount) as today_sales 
-- FROM sales 
-- WHERE DATE(sale_date) = CURRENT_DATE;

-- Get profit calculation
-- SELECT 
--     SUM(si.price_at_sale * si.quantity) as total_revenue,
--     SUM(p.cost_price * si.quantity) as total_cost,
--     SUM((si.price_at_sale - p.cost_price) * si.quantity) as total_profit
-- FROM sale_items si
-- JOIN products p ON si.product_id = p.id;

-- Get supplier expenses
-- SELECT s.name, SUM(sp.amount_paid) as total_paid
-- FROM suppliers s
-- JOIN supplier_payments sp ON s.id = sp.supplier_id
-- GROUP BY s.id;
