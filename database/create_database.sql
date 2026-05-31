-- Таблица ролей
CREATE TABLE role (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB DEFAULT '{"read": true}'::jsonb
);

-- Таблица сотрудников
CREATE TABLE employee (
    id SERIAL PRIMARY KEY,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50),
    position VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    hire_date DATE DEFAULT CURRENT_DATE
);

-- Таблица учетных записей пользователей
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role_id INTEGER NOT NULL,
    employee_id INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (role_id) REFERENCES role(id),
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE SET NULL
);

-- Таблица категорий товаров
CREATE TABLE category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER,
    description TEXT,
    FOREIGN KEY (parent_id) REFERENCES category(id)
);

-- Таблица товаров
CREATE TABLE product (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(100),
    description TEXT,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    stock_quantity INTEGER DEFAULT 0 CHECK (stock_quantity >= 0),
    is_available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES category(id),
    min_stock_level INTEGER DEFAULT 0
);

-- Таблица клиентов
CREATE TABLE customer (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    consent_pdn BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE SET NULL
);

-- Таблица заказов (продаж)
CREATE TABLE sale (
    id SERIAL PRIMARY KEY,
    sale_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER,
    employee_id INTEGER,
    sale_date TIMESTAMP DEFAULT NOW(),
    total_amount NUMERIC(12,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'новый',
    payment_method VARCHAR(20) CHECK (payment_method IN ('наличные', 'карта', 'перевод')),
    FOREIGN KEY (customer_id) REFERENCES customer(id) ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES employee(id) ON DELETE SET NULL
);

-- Позиции заказа
CREATE TABLE sale_item (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price_at_sale NUMERIC(12,2) NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sale(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product(id)
);

-- 1. Индекс на JSONB для быстрого поиска по правам доступа
CREATE INDEX idx_role_permissions ON role USING GIN (permissions);

-- 2. Индексы для ускорения поиска в каталоге товаров
-- Поиск по названию
CREATE INDEX idx_product_name ON product (name);
-- Фильтрация по категории и бренду
CREATE INDEX idx_product_category_brand ON product (category_id, brand);
-- Быстрая сортировка по цене и проверка наличия
CREATE INDEX idx_product_price_stock ON product (price, stock_quantity) WHERE is_available = TRUE;

-- 3. Индексы для связей
CREATE INDEX idx_user_role ON "user" (role_id);
CREATE INDEX idx_user_employee ON "user" (employee_id);
CREATE INDEX idx_customer_user ON customer (user_id);

-- 4. Индексы для истории заказов
-- Поиск заказов конкретного клиента
CREATE INDEX idx_sale_customer ON sale (customer_id);
-- Фильтрация по дате и статусу
CREATE INDEX idx_sale_date_status ON sale (sale_date, status);

-- 5. Индекс для позиций заказа
CREATE INDEX idx_sale_item_order ON sale_item (sale_id);
CREATE INDEX idx_sale_item_product ON sale_item (product_id);

-- 6. Индексы для поиска сотрудников и клиентов по ФИО/телефону
CREATE INDEX idx_employee_names ON employee (last_name, first_name);
CREATE INDEX idx_customer_phone ON customer (phone);

-- Данные

-- 1. Добавляем основные роли
INSERT INTO role (name, description) VALUES 
('Администратор', 'Полный доступ'),
('Менеджер', 'Управление складом и ценами'),
('Кассир', 'Оформление продаж'),
('Кладовщик', 'Приемка и списание');

-- 2. Добавляем сотрудника
INSERT INTO employee (first_name, last_name, position) 
VALUES ('Иван', 'Иванов', 'Старший админ');

INSERT INTO "user" (username, password_hash, role_id, employee_id)
VALUES ('admin', 'admin123', 1, 1);

INSERT INTO category (name) VALUES ('Процессоры');

INSERT INTO product (name, sku, category_id, price, stock_quantity, is_available)
VALUES ('Intel Core i9-13900K', 'INT-13900', 1, 55000.00, 10, TRUE);