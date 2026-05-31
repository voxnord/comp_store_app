from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from ..utils import login_required, role_required, get_db_connection
from datetime import datetime
from werkzeug.security import generate_password_hash
from psycopg2.extras import RealDictCursor

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/users')
@login_required
@role_required('Администратор')
def users():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Запрос для сотрудников
    cur.execute("""
        SELECT 
            u.id, u.username, u.email, u.is_active, u.created_at, u.role_id, u.employee_id,
            r.name as role_name,
            e.last_name, e.first_name, e.middle_name, e.position, e.phone, e.hire_date
        FROM "user" u
        JOIN role r ON u.role_id = r.id
        JOIN employee e ON u.employee_id = e.id
        ORDER BY e.last_name ASC
    """)
    employees_list = cur.fetchall()

    # 2. Запрос для клиентов
    cur.execute("""
        SELECT 
            u.id as user_id, u.username, u.is_active, u.created_at,
            c.id as customer_id, c.last_name, c.first_name, c.phone, 
            c.email as customer_email, c.address, c.consent_pdn
        FROM "user" u
        JOIN customer c ON u.id = c.user_id
        ORDER BY c.last_name ASC
    """)
    customers_list = cur.fetchall()

    # Данные для модалок добавления/редактирования
    cur.execute("SELECT id, name FROM role ORDER BY name")
    roles = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('admin/users.html', 
                           employees=employees_list, 
                           customers=customers_list, 
                           roles=roles)

@bp.route('/users/add', methods=['POST'])
@login_required
@role_required('Администратор')
def add_user():
    data = request.form
    role_id = int(data.get('role_id'))
    password_hash = generate_password_hash(data.get('password'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if role_id == 4:  # КЛИЕНТ
            # 1. Сначала создаем запись в таблице user
            cur.execute("""
                INSERT INTO "user" (username, password_hash, email, role_id)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (data['username'], password_hash, data['email'], role_id))
            new_user_id = cur.fetchone()[0]
            
            # 2. Создаем запись в customer
            cur.execute("""
                INSERT INTO customer (user_id, last_name, first_name, phone, email, address, consent_pdn)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (new_user_id, data['last_name'], data['first_name'], 
                  data['phone'], data['email'], data['address'], 
                  'consent_pdn' in data))

        else:  # СОТРУДНИК (Админ, Менеджер, Кассир)
            # 1. Создаем запись в employee
            cur.execute("""
                INSERT INTO employee (last_name, first_name, middle_name, phone, email, position)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (data['last_name'], data['first_name'], data.get('middle_name'),
                  data['phone'], data['email'], "Сотрудник системы"))
            new_emp_id = cur.fetchone()[0]
            
            # 2. Создаем запись в user со ссылкой на employee_id
            cur.execute("""
                INSERT INTO "user" (username, password_hash, email, role_id, employee_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (data['username'], password_hash, data['email'], role_id, new_emp_id))

        conn.commit()
        flash('Пользователь успешно создан!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при создании: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('admin.users'))

@bp.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@role_required('Администратор')
def edit_user(user_id):
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Обновляем базовые данные в таблице user
        cur.execute("""
            UPDATE "user" SET username=%s, email=%s, role_id=%s
            WHERE id=%s RETURNING employee_id
        """, (data['username'], data['email'], data['role_id'], user_id))
        emp_id = cur.fetchone()[0]
        
        # 2. Если к юзеру привязан сотрудник, обновляем таблицу employee
        if emp_id:
            cur.execute("""
                UPDATE employee 
                SET last_name=%s, first_name=%s, middle_name=%s, phone=%s, email=%s, position=%s
                WHERE id=%s
            """, (data['last_name'], data['first_name'], data['middle_name'], 
                  data['phone'], data['email'], data['position'], emp_id))
        
        # 3. Если введен новый пароль — обновляем его
        password = data.get('password')
        if password and password.strip():
            cur.execute('UPDATE "user" SET password_hash=%s WHERE id=%s', 
                       (generate_password_hash(password), user_id))
        
        conn.commit()
        flash('Данные сотрудника и аккаунта обновлены', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.users'))

@bp.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
@role_required('Администратор')
def edit_customer(customer_id):
    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    consent_pdn = 'consent_pdn' in data
    try:
        # 1. Сначала находим user_id, связанный с этим клиентом
        cur.execute('SELECT user_id FROM customer WHERE id = %s', (customer_id,))
        u_id = cur.fetchone()[0]

        # 2. Обновляем таблицу customer
        cur.execute("""
            UPDATE customer 
            SET last_name = %s, first_name = %s, phone = %s, email = %s, address = %s, consent_pdn = %s
            WHERE id = %s
        """, (data['last_name'], data['first_name'], data['phone'], 
              data['email'], data['address'], consent_pdn, customer_id))
        
        # 3. Обновляем таблицу user (логин и email клиента)
        cur.execute('UPDATE "user" SET username=%s, email=%s WHERE id=%s', 
                   (data['username'], data['email'], u_id))
        
        conn.commit()
        flash('Данные клиента обновлены', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при обновлении: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.users'))

@bp.route('/users/toggle/<int:user_id>', methods=['POST'])
@login_required
@role_required('Администратор')
def toggle_user(user_id):
    """Этот маршрут лечит ошибку BuildError"""
    if user_id == session.get('user_id'):
        flash('Нельзя деактивировать себя', 'danger')
        return redirect(url_for('admin.users'))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE "user" SET is_active = NOT is_active WHERE id = %s', (user_id,))
        conn.commit()
        flash('Статус изменен', 'success')
    except Exception as e:
        conn.rollback()
        flash(str(e), 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.users'))

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('Администратор')
def delete_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('SELECT employee_id FROM "user" WHERE id = %s', (user_id,))
        user_data = cur.fetchone()
        
        if not user_data:
            flash('Пользователь не найден', 'warning')
            return redirect(url_for('admin.users'))

        emp_id = user_data['employee_id']

        cur.execute('SELECT id FROM customer WHERE user_id = %s', (user_id,))
        cust_data = cur.fetchone()

        if emp_id:
            cur.execute('DELETE FROM employee WHERE id = %s', (emp_id,))
        
        if cust_data:
            cur.execute('DELETE FROM customer WHERE id = %s', (cust_data['id'],))

        cur.execute('DELETE FROM "user" WHERE id = %s', (user_id,))
        
        conn.commit()
        flash('Пользователь и все связанные данные успешно удалены', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка удаления: Похоже, у этого пользователя есть активные операции (продажи/чеки) в системе.', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.users'))

# --- Категории (чтобы не ломались ссылки в шаблоне) ---

@bp.route('/categories')
@login_required
@role_required('Администратор')
def categories():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Используем LEFT JOIN, чтобы получить имя родительской категории
    cur.execute("""
        SELECT c1.*, c2.name as parent_name
        FROM category c1
        LEFT JOIN category c2 ON c1.parent_id = c2.id
        ORDER BY c1.id
    """)
    categories_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/categories.html', categories=categories_list)

@bp.route('/categories/add', methods=['POST'])
@login_required
@role_required('Администратор')
def add_category():
    name = request.form.get('name')
    description = request.form.get('description')
    parent_id = request.form.get('parent_id')
    if not parent_id:
        parent_id = None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO category (name, description, parent_id)
            VALUES (%s, %s, %s)
        """, (name, description, parent_id))
        conn.commit()
        flash('Категория добавлена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при добавлении: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.categories'))

@bp.route('/suppliers')
@login_required
@role_required('Администратор')
def suppliers():
    """Заглушка для поставщиков, чтобы не вылетала ошибка BuildError"""
    return render_template('admin/suppliers.html', suppliers=[])

@bp.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
@role_required('Администратор')
def edit_category(id):
    name = request.form.get('name')
    description = request.form.get('description')
    parent_id = request.form.get('parent_id')
    if not parent_id:
        parent_id = None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE category 
            SET name = %s, description = %s, parent_id = %s
            WHERE id = %s
        """, (name, description, parent_id, id))
        conn.commit()
        flash('Категория обновлена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при обновлении: {e}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.categories'))

@bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
@role_required('Администратор')
def delete_category(id):
    """Исправляет BuildError для delete_category"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM category WHERE id = %s", (id,))
        conn.commit()
        flash('Категория удалена', 'success')
    except Exception as e:
        conn.rollback()
        flash('Ошибка: Нельзя удалить категорию, в которой есть товары', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin.categories'))

# --- Остальное ---

@bp.route('/customers')
@login_required
@role_required('Администратор', 'Менеджер')
def customers():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM customer")
    customers_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manager/customers.html', customers=customers_list)

@bp.route('/sales')
@login_required
@role_required('Администратор', 'Менеджер')
def sales_history():
    # Получаем параметры из URL
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    payment_method = request.args.get('payment_method', '')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT s.*, 
               c.id as customer_id,
               COALESCE(c.last_name || ' ' || c.first_name, 'Розничный покупатель') as customer_name,
               c.first_name as c_fname,
               c.last_name as c_lname,
               e.id as employee_id,
               e.last_name as employee_name
        FROM sale s
        LEFT JOIN customer c ON s.customer_id = c.id
        LEFT JOIN employee e ON s.employee_id = e.id
        WHERE 1=1
    """
    params = []

    # Фильтр по датам
    if start_date:
        query += " AND s.sale_date >= %s"
        params.append(f"{start_date} 00:00:00")
    if end_date:
        query += " AND s.sale_date <= %s"
        params.append(f"{end_date} 23:59:59")

    # if search:
    #     search_param = f"%{search}%"
    #     query += """ AND (
    #         s.sale_number ILIKE %s 
    #         OR CAST(c.id AS TEXT) ILIKE %s 
    #         OR c.first_name ILIKE %s 
    #         OR c.last_name ILIKE %s
    #     )"""
    #     params.extend([search_param, search_param, search_param, search_param])

    if search:
        query += """ AND (
            s.sale_number = %s 
            OR CAST(c.id AS TEXT) = %s 
            OR c.first_name ILIKE %s 
            OR c.last_name ILIKE %s
        )"""
        params.extend([search, search, search, search])

    # Фильтр по статусу
    if status:
        query += " AND s.status = %s"
        params.append(status)

    # Фильтр по типу оплаты
    if payment_method:
        query += " AND s.payment_method = %s"
        params.append(payment_method)

    query += " ORDER BY s.sale_date DESC"
    
    cur.execute(query, params)
    sales_list = cur.fetchall()
    
    cur.close()
    conn.close()

    return render_template('admin/sales_history.html', 
                           sales=sales_list, 
                           start_date=start_date, 
                           end_date=end_date, 
                           search=search,
                           current_status=status,
                           current_payment=payment_method)

@bp.route('/api/sale-details/<int:sale_id>')
@login_required
def get_sale_details(sale_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Берем цену напрямую из таблицы product (p.price)
        cur.execute("""
            SELECT 
                si.quantity, 
                p.price, 
                p.name as product_name 
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (sale_id,))
        items = cur.fetchall()
        
        cur.execute("SELECT sale_number, total_amount FROM sale WHERE id = %s", (sale_id,))
        sale_info = cur.fetchone()
        
        return jsonify({
            'sale_number': sale_info['sale_number'] if sale_info else '',
            'total_amount': float(sale_info['total_amount']) if sale_info else 0,
            'items': items
        })
    except Exception as e:
        print(f"Ошибка API деталей: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
@bp.route('/api/update-sale-status/<int:sale_id>', methods=['POST'])
@login_required
@role_required('Администратор', 'Менеджер')
def update_sale_status(sale_id):
    data = request.json
    field = data.get('field')  # 'status' или 'payment_method'
    value = data.get('value')
    
    if field not in ['status', 'payment_method']:
        return jsonify({'success': False, 'error': 'Некорректное поле'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Динамически обновляем нужное поле
        cur.execute(f"UPDATE sale SET {field} = %s WHERE id = %s", (value, sale_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
@bp.route('/sale/<int:sale_id>/receipt-full')
@login_required
@role_required('Администратор')
def print_full_receipt(sale_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT s.*, c.first_name || ' ' || c.last_name as customer_name FROM sale s LEFT JOIN customer c ON s.customer_id = c.id WHERE s.id = %s", (sale_id,))
        sale = cur.fetchone()
        cur.execute("SELECT si.*, p.name as product_name FROM sale_item si JOIN product p ON si.product_id = p.id WHERE si.sale_id = %s", (sale_id,))
        items = cur.fetchall()
        
        return render_template('admin/receiptadmin.html', sale=sale, items=items)
    finally:
        cur.close()
        conn.close()