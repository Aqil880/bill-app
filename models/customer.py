import re
from datetime import datetime
from database import get_db, transaction

class CustomerModel:
    @staticmethod
    def validate(name, phone, email=None, gstin=None):
        """Validates customer input data."""
        errors = []
        name = name.strip() if name else ''
        phone = phone.strip() if phone else ''
        email = email.strip() if email else ''
        gstin = gstin.strip().upper() if gstin else ''

        if not name or len(name) < 2:
            errors.append("Customer name is required (at least 2 characters).")

        # Phone validation: digits only, 10 to 15 digits, optional leading +
        if not phone or not re.match(r'^\+?[0-9]{10,15}$', phone):
            errors.append("A valid phone number (10-15 digits) is required.")

        # Email validation if provided
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
            errors.append("Please provide a valid email address.")

        # GSTIN validation if provided (Standard Indian GSTIN format: 15 alphanumeric characters)
        if gstin and not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
            errors.append("GSTIN format is invalid. Must be 15 alphanumeric characters (e.g., 29ABCDE1234F1Z5).")

        return errors

    @staticmethod
    def generate_next_customer_id(cursor):
        """Generates next sequential customer ID like CUST-1001."""
        cursor.execute("SELECT customer_id FROM customers ORDER BY id DESC LIMIT 1")
        last = cursor.fetchone()
        if not last or not last['customer_id']:
            return "CUST-1001"
        try:
            last_num = int(last['customer_id'].split('-')[1])
            return f"CUST-{last_num + 1}"
        except (IndexError, ValueError):
            return f"CUST-1001"

    @classmethod
    def create(cls, name, phone, email=None, address=None, gstin=None):
        """Creates a new customer record."""
        errors = cls.validate(name, phone, email, gstin)
        if errors:
            return None, errors

        phone = phone.strip()
        email = email.strip() if email else None
        gstin = gstin.strip().upper() if gstin else None
        name = name.strip()
        address = address.strip() if address else None

        db = get_db()
        # Check duplicate phone
        existing = db.execute("SELECT id FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            return None, ["A customer with this phone number already exists."]

        if email:
            existing_email = db.execute("SELECT id FROM customers WHERE email = ?", (email,)).fetchone()
            if existing_email:
                return None, ["A customer with this email address already exists."]

        cursor = db.cursor()
        customer_id = cls.generate_next_customer_id(cursor)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO customers (customer_id, name, phone, email, address, gstin, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (customer_id, name, phone, email, address, gstin, now, now))
        db.commit()

        return cursor.lastrowid, []

    @classmethod
    def update(cls, customer_db_id, name, phone, email=None, address=None, gstin=None):
        """Updates an existing customer record."""
        errors = cls.validate(name, phone, email, gstin)
        if errors:
            return False, errors

        phone = phone.strip()
        email = email.strip() if email else None
        gstin = gstin.strip().upper() if gstin else None
        name = name.strip()
        address = address.strip() if address else None

        db = get_db()
        # Check duplicate phone for different customer
        existing = db.execute("SELECT id FROM customers WHERE phone = ? AND id != ?", (phone, customer_db_id)).fetchone()
        if existing:
            return False, ["Another customer already has this phone number."]

        if email:
            existing_email = db.execute("SELECT id FROM customers WHERE email = ? AND id != ?", (email, customer_db_id)).fetchone()
            if existing_email:
                return False, ["Another customer already has this email address."]

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("""
            UPDATE customers
            SET name = ?, phone = ?, email = ?, address = ?, gstin = ?, updated_at = ?
            WHERE id = ?
        """, (name, phone, email, address, gstin, now, customer_db_id))
        db.commit()
        return True, []

    @classmethod
    def delete(cls, customer_db_id):
        """Deletes customer only if no associated invoices exist."""
        db = get_db()
        # Check if customer has invoices
        inv = db.execute("SELECT COUNT(*) as count FROM invoices WHERE customer_id = ?", (customer_db_id,)).fetchone()
        if inv and inv['count'] > 0:
            return False, f"Cannot delete customer. There are {inv['count']} invoice(s) associated with this customer."

        db.execute("DELETE FROM customers WHERE id = ?", (customer_db_id,))
        db.commit()
        return True, None

    @classmethod
    def get_by_id(cls, customer_db_id):
        """Fetches single customer by primary key."""
        db = get_db()
        row = db.execute("SELECT * FROM customers WHERE id = ?", (customer_db_id,)).fetchone()
        return dict(row) if row else None

    @classmethod
    def get_all(cls, search_query=None):
        """Fetches customers with optional search filtering."""
        db = get_db()
        if search_query:
            q = f"%{search_query.strip()}%"
            rows = db.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM invoices WHERE customer_id = c.id) as total_invoices,
                       (SELECT COALESCE(SUM(grand_total), 0) FROM invoices WHERE customer_id = c.id AND status != 'cancelled') as total_spend
                FROM customers c
                WHERE c.name LIKE ? OR c.phone LIKE ? OR c.customer_id LIKE ? OR c.email LIKE ?
                ORDER BY c.id DESC
            """, (q, q, q, q)).fetchall()
        else:
            rows = db.execute("""
                SELECT c.*, 
                       (SELECT COUNT(*) FROM invoices WHERE customer_id = c.id) as total_invoices,
                       (SELECT COALESCE(SUM(grand_total), 0) FROM invoices WHERE customer_id = c.id AND status != 'cancelled') as total_spend
                FROM customers c
                ORDER BY c.id DESC
            """).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def get_purchase_history(cls, customer_db_id):
        """Returns all invoice records for a given customer."""
        db = get_db()
        rows = db.execute("""
            SELECT id, invoice_number, invoice_date, grand_total, paid_amount, balance_amount, payment_status, status
            FROM invoices
            WHERE customer_id = ?
            ORDER BY invoice_date DESC, id DESC
        """, (customer_db_id,)).fetchall()
        return [dict(r) for r in rows]
