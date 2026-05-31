USER_QUERIES = {
    'get_all_users': """
        SELECT 
            u.id, u.username, u.email, u.is_active, u.created_at,
            r.name as role_name,
            e.last_name || ' ' || e.first_name as employee_name
        FROM "user" u
        JOIN role r ON u.role_id = r.id
        LEFT JOIN employee e ON u.employee_id = e.id
        ORDER BY u.created_at DESC
    """,
    'get_roles': "SELECT id, name FROM role",
    'get_employees': "SELECT id, last_name || ' ' || first_name as name FROM employee"
}

PRODUCT_QUERIES = {
    'get_products': """
        SELECT
            p.id, p.name, p.sku, p.price,
            p.stock_quantity, p.is_available,
            p.category_id, p.brand,
            c.name as category_name
        FROM product p
        JOIN category c ON p.category_id = c.id
        ORDER BY p.name
    """,
    'search_products': """
        SELECT 
            p.id, 
            p.name, 
            p.sku, 
            p.price, 
            p.stock_quantity, 
            p.is_available,
            p.category_id, 
            p.brand,
            c.name as category_name
        FROM product p
        JOIN category c ON p.category_id = c.id
        WHERE p.name ILIKE %s OR p.sku ILIKE %s OR p.brand ILIKE %s
        ORDER BY p.name
    """
}

SALES_QUERIES = {
    'history': """
        SELECT 
            s.id, s.sale_number, s.sale_date, s.total_amount, s.status,
            s.payment_method,
            c.last_name || ' ' || c.first_name as customer_name,
            e.last_name || ' ' || e.first_name as employee_name
        FROM sale s
        LEFT JOIN customer c ON s.customer_id = c.id
        LEFT JOIN employee e ON s.employee_id = e.id
        ORDER BY s.sale_date DESC
    """,
    'stats_today': """
        SELECT 
            COUNT(*) as count,
            COALESCE(SUM(total_amount), 0) as revenue
        FROM sale
        WHERE DATE(sale_date) = CURRENT_DATE
    """
}

CATEGORY_QUERIES = {
    'get_all': "SELECT * FROM category ORDER BY name",
    'get_with_parent': """
        SELECT c1.*, c2.name as parent_name 
        FROM category c1 
        LEFT JOIN category c2 ON c1.parent_id = c2.id
    """
}