from datetime import datetime
from flask import Blueprint, render_template
from database import get_db
from models.supplier import SupplierModel

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/', methods=['GET'])
def index():
    db = get_db()
    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')

    # Total Customers
    cust_count = db.execute("SELECT COUNT(*) as count FROM customers").fetchone()['count']

    # Total Products
    prod_count = db.execute("SELECT COUNT(*) as count FROM products").fetchone()['count']

    # Today's Sales
    today_sales_row = db.execute("""
        SELECT COALESCE(SUM(grand_total), 0) as total, COUNT(*) as count
        FROM invoices
        WHERE invoice_date = ? AND status != 'cancelled'
    """, (today_str,)).fetchone()
    today_sales = float(today_sales_row['total'])
    today_invoices = int(today_sales_row['count'])

    # Monthly Sales
    month_sales_row = db.execute("""
        SELECT COALESCE(SUM(grand_total), 0) as total, COUNT(*) as count
        FROM invoices
        WHERE strftime('%Y-%m', invoice_date) = ? AND status != 'cancelled'
    """, (month_str,)).fetchone()
    month_sales = float(month_sales_row['total'])
    month_invoices = int(month_sales_row['count'])

    # Total Invoices (All time active)
    total_invoices = db.execute("SELECT COUNT(*) as count FROM invoices WHERE status != 'cancelled'").fetchone()['count']

    # Pending Payments (Outstanding balance)
    pending_row = db.execute("""
        SELECT COALESCE(SUM(balance_amount), 0) as total
        FROM invoices
        WHERE status != 'cancelled' AND payment_status != 'Paid'
    """, ()).fetchone()
    pending_payments = float(pending_row['total'])

    # Low Stock Products count
    low_stock_rows = db.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.stock_quantity <= p.min_stock_level
        ORDER BY p.stock_quantity ASC
    """).fetchall()
    low_stock_products = [dict(r) for r in low_stock_rows]
    low_stock_count = len(low_stock_products)

    # Recent Invoices
    recent_invoices_rows = db.execute("""
        SELECT i.*, c.name as customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        ORDER BY i.id DESC LIMIT 6
    """).fetchall()
    recent_invoices = [dict(r) for r in recent_invoices_rows]

    # Recent Customers
    recent_cust_rows = db.execute("""
        SELECT * FROM customers ORDER BY id DESC LIMIT 5
    """).fetchall()
    recent_customers = [dict(r) for r in recent_cust_rows]

    # Supplier Payables (Payment needed to give to suppliers)
    supplier_payables = SupplierModel.get_total_payables()
    supplier_count = db.execute("SELECT COUNT(*) as count FROM suppliers").fetchone()['count']

    return render_template(
        'dashboard.html',
        cust_count=cust_count,
        prod_count=prod_count,
        supplier_count=supplier_count,
        supplier_payables=supplier_payables,
        today_sales=today_sales,
        today_invoices=today_invoices,
        month_sales=month_sales,
        month_invoices=month_invoices,
        total_invoices=total_invoices,
        pending_payments=pending_payments,
        low_stock_count=low_stock_count,
        low_stock_products=low_stock_products[:5],
        recent_invoices=recent_invoices,
        recent_customers=recent_customers
    )
