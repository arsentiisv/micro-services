-- Добавляем FK в orders
ALTER TABLE orders ADD CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id);

-- Добавляем FK в products (seller_id)
ALTER TABLE products ADD COLUMN IF NOT EXISTS seller_id UUID;
ALTER TABLE products ADD CONSTRAINT fk_products_seller FOREIGN KEY (seller_id) REFERENCES users(id);

-- Добавляем FK в user_operations
ALTER TABLE user_operations ADD CONSTRAINT fk_user_operations_user FOREIGN KEY (user_id) REFERENCES users(id);
