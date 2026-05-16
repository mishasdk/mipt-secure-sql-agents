-- Убедимся, что работаем в схеме public
SET search_path TO public;
-- 1. Клиенты
CREATE TABLE IF NOT EXISTS customer (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    gender VARCHAR(10),
    DOB DATE,
    job_title VARCHAR(255),
    job_industry_category VARCHAR(100),
    wealth_segment VARCHAR(50),
    deceased_indicator CHAR(1),
    owns_car CHAR(3),
    address VARCHAR(255),
    postcode VARCHAR(10),
    state VARCHAR(50),
    country VARCHAR(50),
    property_valuation INTEGER
);
-- 2. Продукты
CREATE TABLE IF NOT EXISTS product (
    product_id INTEGER PRIMARY KEY,
    brand VARCHAR(100),
    product_line VARCHAR(100),
    product_class VARCHAR(50),
    product_size VARCHAR(20),
    list_price DECIMAL(10, 2),
    standard_cost DECIMAL(10, 2)
);
-- 3. Заказы 
-- Убрали REFERENCES customer(customer_id). Теперь это просто целое число.
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER, 
    order_date DATE,
    online_order BOOLEAN,
    order_status VARCHAR(20)
);
-- 4. Позиции заказов
-- Убрали REFERENCES orders(order_id) и REFERENCES product(product_id).
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER, 
    product_id INTEGER, 
    quantity INTEGER,
    item_list_price_at_sale DECIMAL(10, 2),
    item_standard_cost_at_sale DECIMAL(10, 2)
);