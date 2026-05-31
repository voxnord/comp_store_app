import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask import session, flash, redirect, url_for

def get_db_connection():
    """Устанавливает соединение с базой данных"""
    from .config import Config
    config = Config()
    conn = psycopg2.connect(**config.DB_CONFIG)
    return conn

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Требуется авторизация', 'warning')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Декоратор для проверки роли"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Требуется авторизация', 'warning')
                return redirect(url_for('main.login'))
            
            if session.get('role_name') not in roles:
                flash('Доступ запрещен', 'danger')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_stats():
    """Сбор статистики для дашбордов"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    stats = {
        'today': {},
        'low_stock': [],
        'top_products': [],
        'leader': None
    }
    
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as sales_today,
                COALESCE(SUM(total_amount), 0) as revenue_today,
                COALESCE(AVG(total_amount), 0) as avg_sale_today
            FROM sale
            WHERE DATE(sale_date) = CURRENT_DATE
        """)
        stats['today'] = cur.fetchone()

        cur.execute("""
            SELECT 
                p.name,
                SUM(si.quantity) as total_sold
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            GROUP BY p.name
            ORDER BY total_sold DESC
            LIMIT 5
        """)
        top_list = cur.fetchall()
        stats['top_products'] = top_list
        if top_list:
            stats['leader'] = top_list[0]

        cur.execute("""
            SELECT p.id, p.sku as vendor_code, p.name, c.name as category_name, 
                   p.stock_quantity as total_stock, p.min_stock_level
            FROM product p
            LEFT JOIN category c ON p.category_id = c.id
            WHERE p.is_available = TRUE
            AND p.stock_quantity <= p.min_stock_level
            ORDER BY p.stock_quantity ASC
            LIMIT 10
        """)
        stats['low_stock'] = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM category")
        stats['categories_count'] = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM customer")
        stats['customers_count'] = cur.fetchone()['count']
        stats['suppliers_count'] = 0
        
        cur.execute("SELECT COUNT(*) FROM sale")
        stats['total_sales_count'] = cur.fetchone()['count']
        
        cur.execute("SELECT COALESCE(SUM(stock_quantity), 0) as count FROM product")
        stats['total_items'] = cur.fetchone()['count']

    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()
    return stats