from datetime import datetime
from database import get_db

class InvoiceModel:
    @staticmethod
    def generate_next_invoice_number(cursor):
        now = datetime.now()
        prefix = f"INV-{now.strftime('%Y%m')}-"
        cursor.execute("SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}%",))
        last = cursor.fetchone()
        if not last or not last['invoice_number']:
            return f"{prefix}0001"
        try:
            last_seq = int(last['invoice_number'].split('-')[-1])
            return f"{prefix}{last_seq + 1:04d}"
        except (IndexError, ValueError):
            return f"{prefix}0001"

    @classmethod
    def get_by_id(cls, invoice_id):
        db = get_db()
        inv = db.execute("""
            SELECT i.*, c.name as customer_name, c.phone as customer_phone,
                   c.email as customer_email, c.address as customer_address,
                   c.gstin as customer_gstin, c.customer_id as customer_code
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            WHERE i.id = ?
        """, (invoice_id,)).fetchone()
        if not inv:
            return None

        inv_dict = dict(inv)
        items = db.execute("""
            SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id ASC
        """, (invoice_id,)).fetchall()
        inv_dict['items'] = [dict(it) for it in items]

        payments = db.execute("""
            SELECT * FROM payments WHERE invoice_id = ? ORDER BY id ASC
        """, (invoice_id,)).fetchall()
        inv_dict['payments'] = [dict(p) for p in payments]

        return inv_dict

    @classmethod
    def get_by_number(cls, invoice_number):
        db = get_db()
        row = db.execute("SELECT id FROM invoices WHERE invoice_number = ?", (invoice_number,)).fetchone()
        return cls.get_by_id(row['id']) if row else None

    @classmethod
    def get_all(cls, search_query=None, start_date=None, end_date=None, status=None):
        db = get_db()
        query = """
            SELECT i.*, c.name as customer_name, c.phone as customer_phone, c.customer_id as customer_code
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            WHERE 1=1
        """
        params = []

        if search_query:
            q = f"%{search_query.strip()}%"
            query += " AND (i.invoice_number LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)"
            params.extend([q, q, q])

        if start_date:
            query += " AND i.invoice_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND i.invoice_date <= ?"
            params.append(end_date)

        if status:
            query += " AND i.status = ?"
            params.append(status)

        query += " ORDER BY i.id DESC"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]
