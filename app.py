from flask import Flask
from config import Config
from database import close_db, init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Teardown database connection
    app.teardown_appcontext(close_db)

    # Register blueprints
    from routes.dashboard import dashboard_bp
    from routes.customers import customers_bp
    from routes.inventory import inventory_bp
    from routes.suppliers import suppliers_bp
    from routes.billing import billing_bp
    from routes.invoices import invoices_bp
    from routes.quotations import quotations_bp
    from routes.settings import settings_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(quotations_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(settings_bp)

    return app

if __name__ == '__main__':
    init_db()
    app = create_app()
    print("Billing Application started successfully at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
