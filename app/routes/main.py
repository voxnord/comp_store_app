from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from ..utils import login_required
from ..utils import get_stats
from ..auth import authenticate_user

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            user_data = authenticate_user(username, password)

            if user_data:
                for key, value in user_data.items():
                    session[key] = value

                flash(f'Добро пожаловать, {user_data["employee_name"]}!', 'success')

                if user_data['role_name'] == 'Администратор':
                    return redirect(url_for('admin.users'))
                else:
                    return redirect(url_for('manager.pos'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('main.index'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Единая точка входа для всех ролей"""
    role = session.get('role_name')
    stats = get_stats()

    role_templates = {
        'Администратор': 'dashboard/admin.html',
        'Менеджер': 'dashboard/manager.html',
        'Кассир': 'dashboard/cashier.html',
        'Кладовщик': 'dashboard/storeman.html'
    }

    template = role_templates.get(role)
    
    if not template:
        flash("Роль не распознана, доступ к дашборду ограничен", "danger")
        return redirect(url_for('main.index'))

    return render_template(template, stats=stats)

@bp.route('/api/product/<int:product_id>')
@login_required
def get_product_json(product_id):
    from ..utils import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, sku, price, stock_quantity 
        FROM product 
        WHERE id = %s AND is_available = TRUE
    """, (product_id,))

    product = cur.fetchone()
    cur.close()
    conn.close()

    if product:
        return jsonify({
            'id': product[0],
            'name': product[1],
            'sku': product[2],
            'price': float(product[3]),
            'stock': product[4]
        })
    return jsonify({'error': 'Товар не найден'}), 404