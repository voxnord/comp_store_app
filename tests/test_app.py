import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, session
from werkzeug.security import generate_password_hash
from app.auth import authenticate_user
from app.routes.shop import get_cart, save_cart
from app.models import Sale, User, BaseModel

# --- Фикстуры ---

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test_secret'
    app.config['SERVER_NAME'] = 'localhost'

    @app.route('/dashboard', endpoint='main.dashboard')
    def dashboard(): return "OK"

    from app.utils import role_required
    @app.route('/admin-only')
    @role_required('Администратор')
    def admin_route(): return "OK"

    return app

@pytest.fixture
def mock_db():
    """Мок для psycopg2, который возвращает фейк соединение и курсор"""
    with patch('app.utils.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn
        mock_cur.__enter__.return_value = mock_cur
        yield mock_conn, mock_cur

# --- Тесты ---

# 1. Тест аутентификации
def test_authenticate_user_success(app, mock_db):
    mock_conn, mock_cur = mock_db
    pwd_hash = generate_password_hash("123")
    mock_cur.fetchone.return_value = (1, 'admin', pwd_hash, True, 1, 'Администратор', {}, 1, 'Иван')

    with app.app_context():
        result = authenticate_user('admin', '123')
        assert result is not None
        assert result['role_name'] == 'Администратор'

# 2. Тест корзины
def test_cart_operations(app):
    test_cart = [{'product_id': 1, 'quantity': 2}]
    with app.test_request_context():
        save_cart(test_cart)
        assert get_cart() == test_cart

# 3. Тест защиты ролей
def test_role_required_access_denied(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_name'] = 'Кассир'
        response = client.get('/admin-only')
        assert response.status_code == 302
        assert '/dashboard' in response.headers['Location']

# 4. Тест валидации остатков
def test_create_sale_insufficient_stock(app, mock_db):
    mock_conn, mock_cur = mock_db
    mock_cur.rowcount = 0 
    mock_cur.description = None 

    items = [{'product_id': 1, 'quantity': 999, 'price': 10.0}]
    
    with patch('app.models.get_db_connection', return_value=mock_conn):
        with pytest.raises(ValueError) as excinfo:
            Sale.create_transaction(
                customer_id=1, 
                employee_id=1, 
                items=items,
                payment_method='Наличные'
            )
        
        assert "Недостаточно товара" in str(excinfo.value)
        assert mock_conn.rollback.called

# 5. Тест закрытия соединений
def test_base_model_logic(app, mock_db):
    mock_conn, mock_cur = mock_db
    mock_cur.execute.side_effect = Exception("DB Error")
    
    with patch('app.models.get_db_connection', return_value=mock_conn):
        with pytest.raises(Exception):
            User._execute_query("SELECT 1")
            
    assert mock_cur.close.called
    assert mock_conn.close.called

# 6. Тест мапинга данных
def test_user_get_by_id(app, mock_db):
    mock_conn, mock_cur = mock_db
    mock_cur.fetchone.return_value = {
        'id': 10, 'username': 'test_user', 'role_id': 1, 'email': 't@t.ru'
    }
    mock_cur.description = True

    with patch('app.models.get_db_connection', return_value=mock_conn):
        query = "SELECT * FROM user WHERE id = %s"
        result = User._execute_query(query, (10,), fetchone=True)
        user = User(**dict(result))
        
        assert user.id == 10
        assert user.username == 'test_user'


# 7. Тест получения всех товаров (Product.get_all)
def test_product_get_all(app, mock_db):
    mock_conn, mock_cur = mock_db
    mock_cur.fetchall.return_value = [
        {'id': 1, 'name': 'Laptop', 'sku': 'LT01', 'price': 500, 'stock_quantity': 10, 'is_available': True, 'category_id': 1, 'brand': 'BrandX'}
    ]
    with patch('app.models.get_db_connection', return_value=mock_conn):
        products = Product.get_all()
        assert len(products) == 1
        assert products[0].name == 'Laptop'

# 8. Тест поиска товаров (Product.get_all с параметром search)
def test_product_search_logic(app, mock_db):
    mock_conn, mock_cur = mock_db
    with patch('app.models.get_db_connection', return_value=mock_conn):
        Product.get_all(search="Ryzen")
        args, _ = mock_cur.execute.call_args
        assert '%Ryzen%' in args[1]

# 9. Тест модели Категории (Category.get_all)
def test_category_get_all(app, mock_db):
    mock_conn, mock_cur = mock_db
    # Эмулируем возврат RealDictCursor
    mock_cur.fetchall.return_value = [{'id': 1, 'name': 'Процессоры', 'parent_id': None}]
    with patch('app.models.get_db_connection', return_value=mock_conn):
        categories = Category.get_all()
        # ТАК КАК get_all возвращает список объектов класса Category
        assert categories[0].name == 'Процессоры'

# 10. Тест создания клиента (Customer)
def test_customer_initialization():
    customer = Customer(id=1, first_name="Aleksey", last_name="Petrov", phone="123456")
    assert customer.first_name == "Aleksey"
    assert customer.phone == "123456"
    
