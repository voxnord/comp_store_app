# app/auth.py
import json
from werkzeug.security import check_password_hash
from .utils import get_db_connection

def authenticate_user(username, password, ip_address=None, user_agent=None):
    """Аутентификация пользователя"""
    try:
        print(username, password)
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            SELECT 
                u.id, u.username, u.password_hash, u.is_active,
                r.id as role_id, r.name as role_name, r.permissions,
                e.id as employee_id, e.first_name || ' ' || e.last_name as employee_name
            FROM "user" u
            JOIN role r ON u.role_id = r.id
            LEFT JOIN employee e ON u.employee_id = e.id
            WHERE u.username = %s
        """
        cur.execute(query, (username,))
        result = cur.fetchone()
        
        if result:
            user_id, uname, pwd_hash, is_active, r_id, r_name, perms, emp_id, emp_name = result
            
            if not is_active:
                raise Exception("Аккаунт деактивирован")

            if check_password_hash(pwd_hash, password):
                return {
                    'user_id': user_id,
                    'username': uname,
                    'role_id': r_id,
                    'role_name': r_name,
                    'employee_id': emp_id,
                    'employee_name': emp_name or uname,
                    'permissions': perms if isinstance(perms, dict) else {}
                }
        
        return None
        
    except Exception as e:
        raise Exception(f"Ошибка системы аутентификации: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def logout_user():
    return True
