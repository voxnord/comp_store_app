from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils import get_db_connection
from ..queries import PRODUCT_QUERIES
from psycopg2.extras import RealDictCursor

bp = Blueprint('shop', __name__, url_prefix='/shop')

CUSTOMER_ROLE_ID = 4


def get_cart():
    """Получить корзину из сессии (list словарей)."""
    return session.get('cart', [])


def save_cart(cart):
    """Сохранить корзину в сессии."""
    session['cart'] = cart
    session.modified = True


@bp.route('/')
def index():
    """Главная витрина магазина /shop"""
    search = (request.args.get('q') or '').strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if search:
            # Если запрос в queries.py не возвращает категорию, 
            # мы добавим JOIN прямо здесь или используем тот же SQL, что в блоке else
            cur.execute("""
                SELECT p.id, p.name, p.sku, p.price, p.stock_quantity, c.name as category_name
                FROM product p
                LEFT JOIN category c ON p.category_id = c.id
                WHERE (p.name ILIKE %s OR p.sku ILIKE %s)
                AND p.is_available = TRUE
            """, (f'%{search}%', f'%{search}%'))
        else:
            cur.execute("""
                SELECT p.id, p.name, p.sku, p.price, p.stock_quantity, c.name as category_name
                FROM product p
                LEFT JOIN category c ON p.category_id = c.id
                WHERE p.is_available = TRUE
                ORDER BY p.name
            """)
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    products = []
    for row in rows:
        products.append({
            'id': row[0],
            'name': row[1],
            'vendor_code': row[2],
            'price': float(row[3]),
            'stock': row[4],
            'category_name': row[5]
        })

    cart = get_cart()
    cart_count = sum(item['quantity'] for item in cart)

    return render_template(
        'shop/index.html',
        products=products,
        search=search,
        cart_count=cart_count
    )


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        consent_pdn = True if request.form.get('consent_pdn') else False
        
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute('SELECT 1 FROM "user" WHERE username = %s', (username,))
            if cur.fetchone():
                flash('Пользователь с таким логином уже существует', 'danger')
                return redirect(url_for('shop.register'))

            hashed_password = generate_password_hash(password)

            cur.execute("""
                INSERT INTO "user" (username, email, password_hash, role_id, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
            """, (username, email, hashed_password, CUSTOMER_ROLE_ID))
            
            new_user_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO customer (first_name, last_name, email, phone, user_id, address, consent_pdn)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                first_name,
                last_name,
                email,
                phone,
                new_user_id,
                address,
                consent_pdn 
            ))

            conn.commit()
            flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
            return redirect(url_for('shop.login'))

        except Exception as e:
            conn.rollback()
            print(f"SQL Error details: {e}")
            flash(f'Ошибка регистрации: {e}', 'danger')
        finally:
            cur.close()
            conn.close()

    return render_template('shop/register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT 
                    u.id, u.username, u.password_hash, u.role_id, 
                    c.first_name || ' ' || c.last_name as customer_name
                FROM "user" u
                LEFT JOIN customer c ON c.email = u.email
                WHERE u.username = %s AND u.role_id = %s
            """, (username, CUSTOMER_ROLE_ID))
            
            user = cur.fetchone()

            if user and check_password_hash(user[2], password):
                session['shop_user_id'] = user[0]
                session['shop_customer_name'] = user[4]
                flash(f'Добро пожаловать, {user[4]}!', 'success')
                return redirect(url_for('shop.index'))
            else:
                flash('Неверный логин или пароль', 'danger')

        except Exception as e:
            flash(f'Ошибка входа: {e}', 'danger')
        finally:
            cur.close()
            conn.close()

    return render_template('shop/login.html')


@bp.route('/logout')
def logout():
    """Выход покупателя"""
    session.pop('shop_user_id', None)
    session.pop('shop_customer_id', None)
    session.pop('shop_customer_name', None)
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('shop.index'))


# ------------------- КОРЗИНА -------------------


@bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """Добавить товар в корзину с учетом выбранного количества."""
    product_id = request.form.get('product_id', type=int)
    # Считываем введенное пользователем количество, по умолчанию 1
    quantity_to_add = request.form.get('quantity', default=1, type=int)
    
    if not product_id:
        flash('Некорректный идентификатор товара', 'danger')
        return redirect(url_for('shop.index'))

    if quantity_to_add < 1:
        flash('Количество должно быть не менее 1', 'warning')
        return redirect(url_for('shop.index'))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                p.id, p.name, p.price, p.stock_quantity, p.is_available
            FROM product p
            WHERE p.id = %s
        """, (product_id,))
        
        product = cur.fetchone()

        if product:
            product_id_val, name, price, stock, is_available = product
            
            if not is_available or (stock is not None and stock <= 0):
                flash('Товара нет в наличии', 'warning')
                return redirect(url_for('shop.index'))

            # Проверка, не запрашивает ли пользователь больше, чем есть на складе
            if stock is not None and quantity_to_add > stock:
                flash(f'Недостаточно товара (доступно: {stock})', 'warning')
                return redirect(url_for('shop.index'))

            cart = get_cart()
            found = False
            
            for item in cart:
                if item['product_id'] == product_id_val:
                    new_quantity = item['quantity'] + quantity_to_add
                    # Проверка лимита склада при обновлении существующей позиции
                    if stock is None or new_quantity <= stock:
                        item['quantity'] = new_quantity
                        found = True
                    else:
                        flash(f'Нельзя добавить больше {stock} шт.', 'info')
                        return redirect(url_for('shop.index'))
            
            if not found:
                cart.append({
                    'product_id': product_id_val,
                    'name': name,
                    'price': float(price),
                    'quantity': quantity_to_add # Используем переданное количество
                })
            
            save_cart(cart)
            flash(f'Добавлено {quantity_to_add} шт. товара "{name}"', 'success')
        else:
            flash('Товар не найден', 'danger')

    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('shop.index'))


@bp.route('/cart', methods=['GET', 'POST'])
def cart_view():
    """Страница корзины и оформление заказа."""
    cart = get_cart()
    total_amount = sum(item['price'] * item['quantity'] for item in cart)

    if request.method == 'POST':
        if not cart:
            flash('Корзина пуста', 'warning')
            return redirect(url_for('shop.cart_view'))

        user_id = session.get('shop_user_id')
        if not user_id:
            flash('Для оформления заказа нужно войти или зарегистрироваться', 'warning')
            return redirect(url_for('shop.login'))

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # 1. Получаем customer_id, связанный с этим пользователем
            # В вашей схеме в sale должен быть именно customer_id, а не user_id
            cur.execute('SELECT id FROM customer WHERE email = (SELECT email FROM "user" WHERE id = %s)', (user_id,))
            customer_row = cur.fetchone()
            customer_id = customer_row[0] if customer_row else None

            # 2. Оформляем заказ в соответствии со схемой таблицы sale
            # Поля payment_status, warehouse_id, notes удалены, так как их нет в схеме
            cur.execute("""
                INSERT INTO sale (
                    sale_number,
                    customer_id,
                    employee_id,
                    total_amount,
                    status,
                    payment_method
                )
                VALUES (
                    CONCAT('WEB-', TO_CHAR(NOW(), 'YYYYMMDDHH24MISS')),
                    %s,
                    NULL, -- В онлайн-заказе сотрудник может быть не назначен сразу
                    %s,
                    'новый',
                    'карта' -- Значение по умолчанию из разрешенных CHECK (наличные, карта, перевод)
                )
                RETURNING id
            """, (
                customer_id,
                total_amount
            ))
            sale_id = cur.fetchone()[0]

            # 3. Добавляем товары (в схеме таблица называется sale_item, а не sale_items)
            for item in cart:
                cur.execute("""
                    INSERT INTO sale_item (
                        sale_id,
                        product_id,
                        quantity,
                        price_at_sale
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    sale_id,
                    item['product_id'],
                    item['quantity'],
                    item['price']
                ))

                # Уменьшаем остаток на складе
                cur.execute("""
                    UPDATE product 
                    SET stock_quantity = stock_quantity - %s 
                    WHERE id = %s
                """, (item['quantity'], item['product_id']))

            conn.commit()
            save_cart([])
            flash('Заказ успешно оформлен! Наш менеджер свяжется с вами.', 'success')
            return f'''
                <script>
                    window.open("{url_for('manager.print_receipt', sale_id=sale_id)}", "_blank");
                    window.location.href = "{url_for('shop.index')}";
                </script>
            '''

        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при оформлении заказа: {e}', 'danger')
            return redirect(url_for('shop.cart_view'))
        finally:
            cur.close()
            conn.close()

    return render_template(
        'shop/cart.html',
        cart=cart,
        total_amount=total_amount
    )

@bp.route('/cart/remove/<int:product_id>')
def cart_remove(product_id):
    """Удалить товар из корзины."""
    cart = get_cart()
    cart = [item for item in cart if item['product_id'] != product_id]
    save_cart(cart)
    flash('Товар удалён из корзины', 'info')
    return redirect(url_for('shop.cart_view'))
