from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash
from ..utils import login_required, role_required, get_db_connection
from ..models import Product, Category, Customer, Sale
from ..queries import PRODUCT_QUERIES, SALES_QUERIES
import json

bp = Blueprint('manager', __name__, url_prefix='/manager')

# --- Управление товарами ---

@bp.route('/products')
@login_required
@role_required('Менеджер', 'Администратор')
def products():
    search = request.args.get('search', '')
    raw_products = Product.get_all(search=search)
    products_list = [dict(p.__dict__) if hasattr(p, '__dict__') else p for p in raw_products]
    
    categories = Category.get_all()
    return render_template('manager/products.html', 
                           products=products_list, 
                           categories=categories,
                           search=search)

@bp.route('/products/add', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def add_product():
    try:
        data = {
            'category_id': request.form.get('category_id'),
            'sku': request.form.get('sku'),
            'name': request.form.get('name'),
            'brand': request.form.get('brand'),
            'description': request.form.get('description'),
            'price': request.form.get('price'),
            'stock_quantity': request.form.get('stock_quantity'),
            'min_stock_level': request.form.get('min_stock_level', 0),
            'is_available': 'is_available' in request.form
        }
        
        if not data['category_id']:
            data['category_id'] = None

        Product.create(data)
        flash('Товар успешно добавлен', 'success')
    except Exception as e:
        flash(f'Ошибка при добавлении: {e}', 'danger')
    return redirect(url_for('manager.products'))

@bp.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def edit_product(product_id):
    try:
        data = {
            'category_id': request.form.get('category_id'),
            'sku': request.form.get('sku'),
            'name': request.form.get('name'),
            'brand': request.form.get('brand'),
            'description': request.form.get('description'),
            'price': request.form.get('price'),
            'stock_quantity': request.form.get('stock_quantity'),
            'min_stock_level': request.form.get('min_stock_level'),
            'is_available': 'is_available' in request.form
        }
        Product.update(product_id, data)
        flash('Товар обновлен', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении: {e}', 'danger')
    return redirect(url_for('manager.products'))

@bp.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def delete_product(product_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM product WHERE id = %s", (product_id,))
        conn.commit()
        flash('Товар удален', 'success')
    except Exception as e:
        flash(f'Не удалось удалить товар (возможно, он участвует в сделках): {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manager.products'))

@bp.route('/products/update_stock/<int:product_id>', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def update_stock(product_id):
    """Исправляет BuildError и обновляет остатки"""
    new_qty = request.form.get('stock_quantity') or request.form.get('quantity')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE product SET stock_quantity = %s WHERE id = %s', (new_qty, product_id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Остатки обновлены', 'success')
    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    return redirect(url_for('manager.products'))

# --- POS-терминал ---

@bp.route('/pos')
@login_required
@role_required('Менеджер', 'Администратор')
def pos():
    """Страница оформления заказа менеджером (Point of Sale)"""
    products = Product.get_all()
    customers = Customer.get_all()
    return render_template('manager/pos.html', 
                           products=products, 
                           customers=customers)

@bp.route('/api/create-order', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def create_order():
    data = request.json
    if not data:
        return jsonify({'error': 'Данные не получены'}), 400
        
    customer_id = data.get('customer_id')
    items = data.get('items')
    payment_method = data.get('payment_method', 'карта')

    if not items:
        return jsonify({'error': 'Корзина пуста'}), 400

    try:
        for item in items:
            if 'product_id' not in item or 'quantity' not in item:
                return jsonify({'error': 'Некорректные данные товаров'}), 400
            if 'price' not in item:
                return jsonify({'error': f'Отсутствует цена для товара ID {item.get("product_id")}'}), 400

        sale_id = Sale.create_transaction(
            customer_id=customer_id,
            employee_id=session.get('employee_id'),
            payment_method=payment_method,
            items=items
        )
        return jsonify({'success': True, 'sale_id': sale_id})
        
    except Exception as e:
        print(f"Ошибка при создании заказа: {e}") 
        return jsonify({'error': str(e)}), 500

# --- Управление клиентами ---

@bp.route('/customers')
@login_required
@role_required('Менеджер', 'Администратор')
def customers():
    customers_list = Customer.get_all()
    return render_template('manager/customers.html', customers=customers_list)

@bp.route('/customers/add', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def add_customer():
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        CUSTOMER_ROLE_ID = 4 
        default_password = generate_password_hash('123456')
        
        username = data.get('username') or data.get('phone')
        email = data.get('email') if data.get('email') else None
        
        cur.execute("""
            INSERT INTO "user" (username, password_hash, email, role_id, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            RETURNING id
        """, (username, default_password, email, CUSTOMER_ROLE_ID))
        
        user_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO customer (user_id, first_name, last_name, phone, email, address, consent_pdn)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, 
            data['first_name'], 
            data['last_name'], 
            data.get('phone'), 
            email,
            data.get('address'),
            'consent_pdn' in data
        ))
        
        conn.commit()
        flash('Клиент успешно зарегистрирован. Доступ на витрину открыт.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при регистрации: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('manager.customers'))

@bp.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
@role_required('Менеджер', 'Администратор')
def edit_customer(customer_id):
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        email = data.get('email') if data.get('email') else None
        
        cur.execute("""
            UPDATE customer 
            SET first_name = %s, last_name = %s, phone = %s, email = %s, address = %s, consent_pdn = %s
            WHERE id = %s
        """, (
            data['first_name'], 
            data['last_name'], 
            data.get('phone'), 
            email,
            data.get('address'),
            'consent_pdn' in data,
            customer_id
        ))

        cur.execute("SELECT user_id FROM customer WHERE id = %s", (customer_id,))
        user_id_row = cur.fetchone()
        if user_id_row and user_id_row[0]:
            cur.execute('UPDATE "user" SET email = %s WHERE id = %s', (email, user_id_row[0]))

        conn.commit()
        flash('Данные обновлены', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manager.customers'))

from datetime import datetime
from psycopg2.extras import RealDictCursor

@bp.route('/sale/<int:sale_id>/receipt')
@login_required
def print_receipt(sale_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT s.*, c.first_name || ' ' || c.last_name as customer_name, c.phone as customer_phone
            FROM sale s
            LEFT JOIN customer c ON s.customer_id = c.id
            WHERE s.id = %s
        """, (sale_id,))
        sale = cur.fetchone()
        
        cur.execute("""
            SELECT si.*, p.name as product_name
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (sale_id,))
        items = cur.fetchall()
        
        return render_template('manager/receipt.html', sale=sale, items=items, now=datetime.now())
    finally:
        cur.close()
        conn.close()