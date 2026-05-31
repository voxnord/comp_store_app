"""
Модели данных для системы учета компьютерной техники
"""
from .utils import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime

class BaseModel:
    """Базовый класс для всех моделей"""
    
    @classmethod
    def _execute_query(cls, query, params=None, fetchone=False, fetchall=False, commit=True):
        """Выполняет SQL запрос и возвращает результат"""
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(query, params)
            result = None
            
            if fetchone and cur.description:
                result = cur.fetchone()
            elif fetchall and cur.description:
                result = cur.fetchall()
            
            if commit:
                conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

class User(BaseModel):
    """Модель пользователя"""
    def __init__(self, id=None, username=None, email=None, role_id=None,
                 employee_id=None, is_active=True, created_at=None, **kwargs):
        self.id = id
        self.username = username
        self.email = email
        self.role_id = role_id
        self.employee_id = employee_id
        self.is_active = is_active
        self.created_at = created_at

    @classmethod
    def get_by_username(cls, username):
        query = """
            SELECT u.*, r.name as role_name, r.permissions
            FROM "user" u
            JOIN role r ON u.role_id = r.id
            WHERE u.username = %s
        """
        result = cls._execute_query(query, (username,), fetchone=True)
        return cls(**dict(result)) if result else None

    @classmethod
    def get_all(cls):
        query = """
            SELECT u.id, u.username, u.email, u.is_active, u.created_at,
                   r.name as role_name,
                   e.last_name || ' ' || e.first_name as employee_name
            FROM "user" u
            JOIN role r ON u.role_id = r.id
            LEFT JOIN employee e ON u.employee_id = e.id
            ORDER BY u.created_at DESC
        """
        results = cls._execute_query(query, fetchall=True)
        return [cls(**dict(row)) for row in results] if results else []

class Employee(BaseModel):
    """Модель сотрудника"""
    def __init__(self, id=None, last_name=None, first_name=None, middle_name=None,
                 position=None, phone=None, email=None, hire_date=None, **kwargs):
        self.id = id
        self.last_name = last_name
        self.first_name = first_name
        self.middle_name = middle_name
        self.position = position
        self.phone = phone
        self.email = email
        self.hire_date = hire_date

    @classmethod
    def get_all(cls):
        query = "SELECT * FROM employee ORDER BY last_name, first_name"
        results = cls._execute_query(query, fetchall=True)
        return [cls(**dict(row)) for row in results] if results else []

class Category(BaseModel):
    """Модель категории товаров"""
    def __init__(self, id=None, name=None, parent_id=None, description=None, **kwargs):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.description = description

    @classmethod
    def get_all(cls):
        query = "SELECT * FROM category ORDER BY name"
        results = cls._execute_query(query, fetchall=True)
        return [cls(**dict(row)) for row in results] if results else []

class Product(BaseModel):
    """Модель товара"""
    def __init__(self, id=None, category_id=None, sku=None, name=None, brand=None, 
                 description=None, price=0, stock_quantity=0, min_stock_level=0,
                 is_available=True, **kwargs):
        self.id = id
        self.category_id = category_id
        self.sku = sku
        self.name = name
        self.brand = brand
        self.description = description
        self.price = price
        self.stock_quantity = stock_quantity
        self.min_stock_level = min_stock_level
        self.is_available = is_available
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def get_all(cls, search=None):
        query = """
            SELECT p.*, c.name as category_name
            FROM product p
            LEFT JOIN category c ON p.category_id = c.id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (p.name ILIKE %s OR p.sku ILIKE %s OR p.brand ILIKE %s)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        query += " ORDER BY p.name"
        results = cls._execute_query(query, params, fetchall=True)
        return [cls(**dict(row)) for row in results] if results else []

    @classmethod
    def create(cls, data):
        """Метод для создания из словаря (manager)"""
        query = """
            INSERT INTO product
            (category_id, sku, name, brand, description, price, stock_quantity, min_stock_level, is_available)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            data.get('category_id'), data.get('sku'), data.get('name'),
            data.get('brand'), data.get('description'), data.get('price'),
            data.get('stock_quantity'), data.get('min_stock_level', 0),
            data.get('is_available', True)
        )
        result = cls._execute_query(query, params, fetchone=True)
        return result['id'] if result else None

    @classmethod
    def update(cls, product_id, data):
        """Метод для обновления (manager.py)"""
        query = """
            UPDATE product
            SET category_id = %s, sku = %s, name = %s, brand = %s, 
                description = %s, price = %s, stock_quantity = %s, 
                min_stock_level = %s, is_available = %s
            WHERE id = %s
        """
        params = (
            data.get('category_id'), data.get('sku'), data.get('name'),
            data.get('brand'), data.get('description'), data.get('price'),
            data.get('stock_quantity'), data.get('min_stock_level'),
            data.get('is_available'), product_id
        )
        cls._execute_query(query, params)

class Customer(BaseModel):
    """Модель клиента"""
    def __init__(self, id=None, user_id=None, first_name=None, last_name=None,
                 phone=None, email=None, address=None, consent_pdn=False, **kwargs):
        self.id = id
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.email = email
        self.address = address
        self.consent_pdn = consent_pdn

    @classmethod
    def get_all(cls):
        query = "SELECT * FROM customer ORDER BY last_name, first_name"
        results = cls._execute_query(query, fetchall=True)
        return [cls(**dict(row)) for row in results] if results else []

class Sale(BaseModel):
    """Модель продажи (заказа)"""
    def __init__(self, id=None, sale_number=None, customer_id=None, employee_id=None,
                 sale_date=None, total_amount=0, status='новый', payment_method=None, **kwargs):
        self.id = id
        self.sale_number = sale_number
        self.customer_id = customer_id
        self.employee_id = employee_id
        self.sale_date = sale_date
        self.total_amount = total_amount
        self.status = status
        self.payment_method = payment_method

    @classmethod
    def create_transaction(cls, customer_id, employee_id, payment_method, items):
        """
        Создание заказа и позиций в рамках одной транзакции, 
        с автоматическим списанием остатков
        """
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            sale_num = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            total = sum(item['quantity'] * item['price'] for item in items)
            
            cur.execute("""
                INSERT INTO sale (sale_number, customer_id, employee_id, total_amount, payment_method)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (sale_num, customer_id, employee_id, total, payment_method))
            
            sale_id = cur.fetchone()['id']

            for item in items:
                cur.execute("""
                    INSERT INTO sale_item (sale_id, product_id, quantity, price_at_sale)
                    VALUES (%s, %s, %s, %s)
                """, (sale_id, item['product_id'], item['quantity'], item['price']))
                
                cur.execute("""
                    UPDATE product 
                    SET stock_quantity = stock_quantity - %s 
                    WHERE id = %s AND stock_quantity >= %s
                """, (item['quantity'], item['product_id'], item['quantity']))
                
                if cur.rowcount == 0:
                    raise ValueError(f"Недостаточно товара (ID: {item['product_id']}) на складе")

            conn.commit()
            return sale_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    @classmethod
    def get_by_id(cls, sale_id):
        query = """
            SELECT s.*, 
                   c.last_name || ' ' || c.first_name as customer_name,
                   e.last_name || ' ' || e.first_name as employee_name
            FROM sale s
            LEFT JOIN customer c ON s.customer_id = c.id
            LEFT JOIN employee e ON s.employee_id = e.id
            WHERE s.id = %s
        """
        result = cls._execute_query(query, (sale_id,), fetchone=True)
        return cls(**dict(result)) if result else None

    def get_items(self):
        query = """
            SELECT p.name, p.sku, si.quantity, si.price_at_sale as price, 
                   (si.quantity * si.price_at_sale) as total_line
            FROM sale_item si
            JOIN product p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """
        return self._execute_query(query, (self.id,), fetchall=True) or []