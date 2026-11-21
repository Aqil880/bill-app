import sqlite3
from contextlib import contextmanager
from flask import g
from config import Config

def get_db():
    """Returns a SQLite connection for the current Flask application context or standalone execution."""
    try:
        if 'db' not in g:
            g.db = sqlite3.connect(Config.DATABASE_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
            g.db.execute("PRAGMA journal_mode = WAL;")
        return g.db
    except RuntimeError:
        return get_standalone_db()

def close_db(e=None):
    """Closes the database connection if open."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_standalone_db():
    """Returns a standalone database connection outside of Flask request context."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def transaction(conn=None):
    """
    Context manager for atomic database transactions.
    Automatically commits on success or rolls back on exception.
    """
    close_when_done = False
    if conn is None:
        try:
            conn = get_db()
        except RuntimeError:
            conn = get_standalone_db()
            close_when_done = True
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        if close_when_done:
            conn.close()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    gstin TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    gstin TEXT,
    opening_balance REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    description TEXT,
    sku TEXT UNIQUE,
    purchase_price REAL NOT NULL DEFAULT 0.0,
    selling_price REAL NOT NULL DEFAULT 0.0,
    gst_rate REAL NOT NULL DEFAULT 0.0,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_level INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    invoice_date DATE NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0.0,
    discount_type TEXT DEFAULT 'fixed',
    discount_value REAL NOT NULL DEFAULT 0.0,
    discount_amount REAL NOT NULL DEFAULT 0.0,
    taxable_amount REAL NOT NULL DEFAULT 0.0,
    tax_type TEXT NOT NULL DEFAULT 'intra_state',
    cgst_amount REAL NOT NULL DEFAULT 0.0,
    sgst_amount REAL NOT NULL DEFAULT 0.0,
    igst_amount REAL NOT NULL DEFAULT 0.0,
    total_tax REAL NOT NULL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    paid_amount REAL NOT NULL DEFAULT 0.0,
    balance_amount REAL NOT NULL DEFAULT 0.0,
    payment_status TEXT NOT NULL DEFAULT 'Unpaid',
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    sku TEXT,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    gst_rate REAL NOT NULL DEFAULT 0.0,
    gst_amount REAL NOT NULL DEFAULT 0.0,
    total_amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quotation_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    quotation_date DATE NOT NULL,
    valid_until DATE,
    subtotal REAL NOT NULL DEFAULT 0.0,
    discount_type TEXT DEFAULT 'fixed',
    discount_value REAL NOT NULL DEFAULT 0.0,
    discount_amount REAL NOT NULL DEFAULT 0.0,
    taxable_amount REAL NOT NULL DEFAULT 0.0,
    tax_type TEXT NOT NULL DEFAULT 'intra_state',
    cgst_amount REAL NOT NULL DEFAULT 0.0,
    sgst_amount REAL NOT NULL DEFAULT 0.0,
    igst_amount REAL NOT NULL DEFAULT 0.0,
    total_tax REAL NOT NULL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'Draft',
    converted_invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quotation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    sku TEXT,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    gst_rate REAL NOT NULL DEFAULT 0.0,
    gst_amount REAL NOT NULL DEFAULT 0.0,
    total_amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    reference_number TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    purchase_date DATE NOT NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL,
    reference_number TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reference_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    business_name TEXT NOT NULL DEFAULT 'Billing Pro Enterprises',
    logo_path TEXT DEFAULT 'static/images/logo.png',
    address TEXT DEFAULT '123 Business Avenue, Suite 100, Tech City',
    phone TEXT DEFAULT '+91 98765 43210',
    email TEXT DEFAULT 'contact@billingpro.com',
    gstin TEXT DEFAULT '29ABCDE1234F1Z5',
    currency_symbol TEXT DEFAULT '₹',
    terms_conditions TEXT DEFAULT '1. Goods once sold will not be accepted back without invoice.\n2. Payment is due within 15 days.',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_phone ON suppliers(phone);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_stock_movements_prod ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_supplier_purchases_supp ON supplier_purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_payments_supp ON supplier_payments(supplier_id);
CREATE INDEX IF NOT EXISTS idx_quotations_customer ON quotations(customer_id);
CREATE INDEX IF NOT EXISTS idx_quotations_date ON quotations(quotation_date);
CREATE INDEX IF NOT EXISTS idx_quotations_status ON quotations(status);
"""

def init_db():
    """Initializes the database schema and default business settings."""
    conn = get_standalone_db()
    try:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)

        # Check if products table has supplier_id column (for migrations on existing databases)
        cursor.execute("PRAGMA table_info(products)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'supplier_id' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id)")
        
        # Ensure default business settings exist
        cursor.execute("SELECT id FROM business_settings WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO business_settings (id, business_name, address, phone, email, gstin, currency_symbol, terms_conditions)
                VALUES (1, 'Billing Pro Enterprises', '123 Business Avenue, Suite 100, Tech City', '+91 98765 43210', 'contact@billingpro.com', '29ABCDE1234F1Z5', '₹', '1. Goods once sold will not be accepted back without original invoice.\n2. Payment is due within 15 days from date of invoice.')
            """)

        # Ensure default product categories exist
        default_categories = ['General', 'Electronics', 'Apparel', 'Stationery', 'Hardware', 'Services']
        for cat in default_categories:
            cursor.execute("INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)", (cat, f'{cat} items'))
            
        conn.commit()
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at:", Config.DATABASE_PATH)
