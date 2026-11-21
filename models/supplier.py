import re
from datetime import datetime
from database import get_db, transaction

class SupplierModel:
    @staticmethod
    def validate(name, phone, email=None, gstin=None, opening_balance=0.0):
        """Validates supplier input data."""
        errors = []
        name = name.strip() if name else ''
        phone = phone.strip() if phone else ''
        email = email.strip() if email else ''
        gstin = gstin.strip().upper() if gstin else ''

        if not name or len(name) < 2:
            errors.append("Supplier / Company name is required (at least 2 characters).")

        # Phone validation: digits only, 10 to 15 digits, optional leading +
        if not phone or not re.match(r'^\+?[0-9]{10,15}$', phone):
            errors.append("A valid phone number (10-15 digits) is required.")

        # Email validation if provided
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
            errors.append("Please provide a valid email address.")

        # GSTIN validation if provided (15 alphanumeric characters)
        if gstin and not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
            errors.append("GSTIN format is invalid. Must be 15 alphanumeric characters (e.g., 29ABCDE1234F1Z5).")

        try:
            ob = float(opening_balance)
            if ob < 0:
                errors.append("Opening balance cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Opening balance must be a valid number.")

        return errors

    @staticmethod
    def generate_next_supplier_id(cursor):
        """Generates next sequential supplier ID like SUP-1001."""
        cursor.execute("SELECT supplier_id FROM suppliers ORDER BY id DESC LIMIT 1")
        last = cursor.fetchone()
        if not last or not last['supplier_id']:
            return "SUP-1001"
        try:
            last_num = int(last['supplier_id'].split('-')[1])
            return f"SUP-{last_num + 1}"
        except (IndexError, ValueError):
            return "SUP-1001"

    @classmethod
    def create(cls, name, phone, contact_person=None, email=None, address=None, gstin=None, opening_balance=0.0):
        """Creates a new supplier record."""
        errors = cls.validate(name, phone, email, gstin, opening_balance)
        if errors:
            return None, errors

        name = name.strip()
        phone = phone.strip()
        contact_person = contact_person.strip() if contact_person else None
        email = email.strip() if email else None
        address = address.strip() if address else None
        gstin = gstin.strip().upper() if gstin else None
        opening_balance = float(opening_balance or 0.0)

        db = get_db()
        existing = db.execute("SELECT id FROM suppliers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            return None, ["A supplier with this phone number already exists."]

        cursor = db.cursor()
        supplier_id = cls.generate_next_supplier_id(cursor)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO suppliers (supplier_id, name, contact_person, phone, email, address, gstin, opening_balance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (supplier_id, name, contact_person, phone, email, address, gstin, opening_balance, now, now))
        new_id = cursor.lastrowid
        db.commit()

        return new_id, []

    @classmethod
    def update(cls, supplier_db_id, name, phone, contact_person=None, email=None, address=None, gstin=None, opening_balance=0.0):
        """Updates an existing supplier record."""
        errors = cls.validate(name, phone, email, gstin, opening_balance)
        if errors:
            return False, errors

        name = name.strip()
        phone = phone.strip()
        contact_person = contact_person.strip() if contact_person else None
        email = email.strip() if email else None
        address = address.strip() if address else None
        gstin = gstin.strip().upper() if gstin else None
        opening_balance = float(opening_balance or 0.0)

        db = get_db()
        existing = db.execute("SELECT id FROM suppliers WHERE phone = ? AND id != ?", (phone, supplier_db_id)).fetchone()
        if existing:
            return False, ["Another supplier already has this phone number."]

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("""
            UPDATE suppliers
            SET name = ?, contact_person = ?, phone = ?, email = ?, address = ?, gstin = ?, opening_balance = ?, updated_at = ?
            WHERE id = ?
        """, (name, contact_person, phone, email, address, gstin, opening_balance, now, supplier_db_id))
        db.commit()
        return True, []

    @classmethod
    def delete(cls, supplier_db_id):
        """Deletes a supplier if they have no active purchases."""
        db = get_db()
        purchases_cnt = db.execute("SELECT COUNT(*) as cnt FROM supplier_purchases WHERE supplier_id = ?", (supplier_db_id,)).fetchone()['cnt']
        if purchases_cnt > 0:
            return False, f"Cannot delete supplier. {purchases_cnt} stock purchase order(s) are recorded for this supplier."

        # Unlink from products
        db.execute("UPDATE products SET supplier_id = NULL WHERE supplier_id = ?", (supplier_db_id,))
        # Delete payments and supplier
        db.execute("DELETE FROM supplier_payments WHERE supplier_id = ?", (supplier_db_id,))
        db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_db_id,))
        db.commit()
        return True, None

    @classmethod
    def get_by_id(cls, supplier_db_id):
        """Fetches a single supplier with live financial summary."""
        db = get_db()
        row = db.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_db_id,)).fetchone()
        if not row:
            return None
        supp = dict(row)

        # Financial calculations:
        purchases_row = db.execute("""
            SELECT COALESCE(SUM(total_amount), 0.0) as total_purchases, COUNT(*) as count
            FROM supplier_purchases
            WHERE supplier_id = ?
        """, (supplier_db_id,)).fetchone()
        purchases_amount = float(purchases_row['total_purchases'])
        purchases_count = int(purchases_row['count'])

        payments_row = db.execute("""
            SELECT COALESCE(SUM(amount), 0.0) as total_paid
            FROM supplier_payments
            WHERE supplier_id = ?
        """, (supplier_db_id,)).fetchone()
        paid_amount = float(payments_row['total_paid'])

        opening_balance = float(supp.get('opening_balance', 0.0))
        total_payable = opening_balance + purchases_amount
        balance_due = total_payable - paid_amount

        supp['total_purchases'] = total_payable
        supp['purchases_count'] = purchases_count
        supp['total_paid'] = paid_amount
        supp['balance_due'] = round(balance_due, 2)

        # Count supplied products
        prod_count = db.execute("SELECT COUNT(*) as cnt FROM products WHERE supplier_id = ?", (supplier_db_id,)).fetchone()['cnt']
        supp['supplied_products_count'] = prod_count

        return supp

    @classmethod
    def get_all(cls, search_query=None):
        """Fetches all suppliers along with their current balance to pay."""
        db = get_db()
        query = "SELECT * FROM suppliers WHERE 1=1"
        params = []

        if search_query:
            q = f"%{search_query.strip()}%"
            query += " AND (name LIKE ? OR supplier_id LIKE ? OR phone LIKE ? OR contact_person LIKE ? OR email LIKE ?)"
            params.extend([q, q, q, q, q])

        query += " ORDER BY id DESC"
        rows = db.execute(query, params).fetchall()

        results = []
        for r in rows:
            supp = dict(r)
            s_id = supp['id']

            # Purchases total
            p_row = db.execute("SELECT COALESCE(SUM(total_amount), 0.0) as total FROM supplier_purchases WHERE supplier_id = ?", (s_id,)).fetchone()
            purchases_amount = float(p_row['total'])

            # Payments total
            pay_row = db.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM supplier_payments WHERE supplier_id = ?", (s_id,)).fetchone()
            paid_amount = float(pay_row['total'])

            opening = float(supp.get('opening_balance', 0.0))
            total_bill = opening + purchases_amount
            balance_due = total_bill - paid_amount

            # Product count
            p_cnt = db.execute("SELECT COUNT(*) as cnt FROM products WHERE supplier_id = ?", (s_id,)).fetchone()['cnt']

            supp['total_purchases'] = total_bill
            supp['total_paid'] = paid_amount
            supp['balance_due'] = round(balance_due, 2)
            supp['products_count'] = p_cnt
            results.append(supp)

        return results

    @classmethod
    def record_purchase(cls, supplier_id, product_id, quantity, unit_price, purchase_date=None, notes=None, paid_now=0.0, payment_method='Cash', reference_number=None, conn=None):
        """
        Records a stock purchase from a supplier.
        Generates unique purchase number like PUR-202611-0001.
        """
        db = conn if conn is not None else get_db()
        cursor = db.cursor()

        if not purchase_date:
            purchase_date = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        month_prefix = f"PUR-{datetime.now().strftime('%Y%m')}"

        cursor.execute("SELECT purchase_number FROM supplier_purchases WHERE purchase_number LIKE ? ORDER BY id DESC LIMIT 1", (f"{month_prefix}-%",))
        last = cursor.fetchone()
        if last and last['purchase_number']:
            last_seq = int(last['purchase_number'].split('-')[-1])
            next_seq = f"{last_seq + 1:04d}"
        else:
            next_seq = "0001"
        purchase_number = f"{month_prefix}-{next_seq}"

        qty = int(quantity)
        price = float(unit_price)
        total = round(qty * price, 2)

        cursor.execute("""
            INSERT INTO supplier_purchases (
                purchase_number, supplier_id, purchase_date, product_id, quantity, unit_price, total_amount, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (purchase_number, supplier_id, purchase_date, product_id, qty, price, total, notes, now))
        purchase_id = cursor.lastrowid

        # If partial or full payment made at time of purchase
        if float(paid_now) > 0:
            cursor.execute("""
                INSERT INTO supplier_payments (
                    supplier_id, payment_date, amount, payment_method, reference_number, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (supplier_id, purchase_date, float(paid_now), payment_method, reference_number or purchase_number, f"Payment for purchase {purchase_number}", now))

        if conn is None:
            db.commit()

        return purchase_id, purchase_number

    @classmethod
    def record_payment(cls, supplier_id, amount, payment_date, payment_method, reference_number=None, notes=None):
        """Records a payment given to the supplier."""
        try:
            amt = float(amount)
            if amt <= 0:
                return None, ["Payment amount must be greater than zero."]
        except (ValueError, TypeError):
            return None, ["Valid payment amount is required."]

        if not payment_date:
            payment_date = datetime.now().strftime('%Y-%m-%d')

        valid_methods = ['Cash', 'UPI', 'Bank Transfer', 'Debit/Credit Card', 'Cheque']
        if payment_method not in valid_methods:
            payment_method = 'Cash'

        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO supplier_payments (
                supplier_id, payment_date, amount, payment_method, reference_number, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (supplier_id, payment_date, amt, payment_method, reference_number, notes, now))
        pay_id = cursor.lastrowid
        db.commit()
        return pay_id, []

    @classmethod
    def get_ledger(cls, supplier_id):
        """
        Returns unified chronological statement of all transactions (Purchases & Payments)
        along with the running balance owed to the supplier.
        """
        db = get_db()
        supp_row = db.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not supp_row:
            return None

        supp = dict(supp_row)
        opening_bal = float(supp.get('opening_balance', 0.0))

        # Purchases
        purchases = db.execute("""
            SELECT sp.*, p.name as product_name, p.product_id as prod_code
            FROM supplier_purchases sp
            LEFT JOIN products p ON sp.product_id = p.id
            WHERE sp.supplier_id = ?
            ORDER BY sp.purchase_date ASC, sp.id ASC
        """, (supplier_id,)).fetchall()

        # Payments
        payments = db.execute("""
            SELECT * FROM supplier_payments
            WHERE supplier_id = ?
            ORDER BY payment_date ASC, id ASC
        """, (supplier_id,)).fetchall()

        events = []
        if opening_bal > 0:
            events.append({
                'date': supp['created_at'][:10] if supp.get('created_at') else '—',
                'type': 'OPENING',
                'ref': 'Opening Balance',
                'description': 'Initial balance payable',
                'debit': opening_bal, # money we owe increases
                'credit': 0.0,
                'created_at': supp.get('created_at', '')
            })

        for p in purchases:
            events.append({
                'date': p['purchase_date'],
                'type': 'PURCHASE',
                'ref': p['purchase_number'],
                'description': f"Stock Inward: {p['quantity']}x {p['product_name'] or 'Product'} @ ₹{p['unit_price']:.2f}",
                'debit': float(p['total_amount']),
                'credit': 0.0,
                'created_at': p['created_at']
            })

        for py in payments:
            events.append({
                'date': py['payment_date'],
                'type': 'PAYMENT',
                'ref': py['reference_number'] or f"PAY-{py['id']}",
                'description': f"Payment via {py['payment_method']}{(' - ' + py['notes']) if py['notes'] else ''}",
                'debit': 0.0,
                'credit': float(py['amount']), # payment reduces what we owe
                'created_at': py['created_at']
            })

        # Sort chronologically
        events.sort(key=lambda x: (x['date'], x.get('created_at', '')))

        running_balance = 0.0
        for ev in events:
            running_balance += (ev['debit'] - ev['credit'])
            ev['balance'] = round(running_balance, 2)

        return {
            'supplier': supp,
            'events': events,
            'total_debit': sum(e['debit'] for e in events),
            'total_credit': sum(e['credit'] for e in events),
            'final_balance': round(running_balance, 2)
        }

    @classmethod
    def get_supplied_products(cls, supplier_id):
        """Fetches products currently linked to this supplier."""
        db = get_db()
        rows = db.execute("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.supplier_id = ?
            ORDER BY p.name ASC
        """, (supplier_id,)).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def get_total_payables(cls):
        """Calculates total pending amount that needs to be paid across all suppliers."""
        db = get_db()
        open_row = db.execute("SELECT COALESCE(SUM(opening_balance), 0.0) as total FROM suppliers").fetchone()
        pur_row = db.execute("SELECT COALESCE(SUM(total_amount), 0.0) as total FROM supplier_purchases").fetchone()
        pay_row = db.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM supplier_payments").fetchone()

        total_due = float(open_row['total']) + float(pur_row['total']) - float(pay_row['total'])
        return max(0.0, round(total_due, 2))
