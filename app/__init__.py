from flask import Flask
import os

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    app.config.from_object('app.config.Config')

    from app.routes.main import bp as main_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.manager import bp as manager_bp
    from app.routes.shop import bp as shop_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(shop_bp)
    
    return app