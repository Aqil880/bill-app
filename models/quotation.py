from datetime import datetime
from database import get_db, transaction
from services.billing_service import BillingService

class QuotationModel:
    STATUSES = ['Draft', 'Sent', 'Accepted', 'Declined', 'Converted']

    @staticmethod
    def generate_next_quotation_number(cursor):
        now = datetime.now()
        prefix = f"QTN-{now.strftime('%Y%m')}-"
        cursor.execute("SELECT quotation_number FROM quotations WHERE quotation_number LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}%",))
        last = cursor.fetchone()
        if not last or not last['quotation_number']:
            return f"{prefix}0001"
        try:
            last_seq = int(last['quotation_number'].split('-')[-1])
            return f"{prefix}{last_seq + 1:04d}"
        except (IndexError, ValueError):
            return f"{prefix}0001"

    @classmethod
    def create(cls, customer_id, quotation_date, valid_until=None, items=None,
               discount_type='fixed', discount_value=0.0, tax_type='intra_state', notes=''):
        """Creates a quotation/estimate with line items."""
        if not customer_id:
            return None, None, "Please select a customer for the quotation."
        if not items or len(items) == 0:
            return None, None, "A quotation must contain at least one product."

        calc = BillingService.calculate_bill(items, discount_type, discount_value, tax_type)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        qtn_date = quotation_date or datetime.now().strftime('%Y-%m-%d')

        with transaction() as db:
            cursor = db.cursor()

            # Ensure customer exists
            cust = cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not cust:
                return None, None, "Selected customer does not exist."

            quotation_number = cls.generate_next_quotation_number(cursor)

            cursor.execute("""
                INSERT INTO quotations (
                    quotation_number, customer_id, quotation_date, valid_until, subtotal,
                    discount_type, discount_value, discount_amount, taxable_amount,
                    tax_type, cgst_amount, sgst_amount, igst_amount, total_tax,
                    grand_total, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?, ?)
            """, (
                quotation_number, customer_id, qtn_date, valid_until, calc['subtotal'],
                calc['discount_type'], calc['discount_value'], calc['discount_amount'], calc['taxable_amount'],
                calc['tax_type'], calc['cgst_amount'], calc['sgst_amount'], calc['igst_amount'],
                calc['total_tax'], calc['grand_total'], notes, now_str, now_str
            ))
            quotation_id = cursor.lastrowid

            # Insert quotation line items
            for item in calc['items']:
                cursor.execute("""
                    INSERT INTO quotation_items (
                        quotation_id, product_id, product_name, sku, quantity,
                        unit_price, gst_rate, gst_amount, total_amount, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    quotation_id, item['product_id'], item['product_name'], item['sku'],
                    item['quantity'], item['unit_price'], item['gst_rate'],
                    item['gst_amount'], item['total_amount'], now_str
                ))

        return quotation_id, quotation_number, None

    @classmethod
    def update(cls, quotation_id, customer_id, quotation_date, valid_until=None, items=None,
               discount_type='fixed', discount_value=0.0, tax_type='intra_state', notes=''):
        """Updates an existing quotation if not yet converted."""
        db = get_db()
        existing = db.execute("SELECT * FROM quotations WHERE id = ?", (quotation_id,)).fetchone()
        if not existing:
            return False, "Quotation not found."
        if existing['status'] == 'Converted':
            return False, "Cannot edit a quotation that has already been converted to an invoice."

        if not customer_id:
            return False, "Please select a customer."
        if not items or len(items) == 0:
            return False, "A quotation must contain at least one product."

        calc = BillingService.calculate_bill(items, discount_type, discount_value, tax_type)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE quotations
                SET customer_id = ?, quotation_date = ?, valid_until = ?, subtotal = ?,
                    discount_type = ?, discount_value = ?, discount_amount = ?, taxable_amount = ?,
                    tax_type = ?, cgst_amount = ?, sgst_amount = ?, igst_amount = ?, total_tax = ?,
                    grand_total = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (
                customer_id, quotation_date, valid_until, calc['subtotal'],
                calc['discount_type'], calc['discount_value'], calc['discount_amount'], calc['taxable_amount'],
                calc['tax_type'], calc['cgst_amount'], calc['sgst_amount'], calc['igst_amount'],
                calc['total_tax'], calc['grand_total'], notes, now_str, quotation_id
            ))

            # Delete old items and re-insert
            cursor.execute("DELETE FROM quotation_items WHERE quotation_id = ?", (quotation_id,))
            for item in calc['items']:
                cursor.execute("""
                    INSERT INTO quotation_items (
                        quotation_id, product_id, product_name, sku, quantity,
                        unit_price, gst_rate, gst_amount, total_amount, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    quotation_id, item['product_id'], item['product_name'], item['sku'],
                    item['quantity'], item['unit_price'], item['gst_rate'],
                    item['gst_amount'], item['total_amount'], now_str
                ))

        return True, None

    @classmethod
    def update_status(cls, quotation_id, new_status):
        """Updates quotation status."""
        if new_status not in cls.STATUSES:
            return False, "Invalid status."
        db = get_db()
        q = db.execute("SELECT status FROM quotations WHERE id = ?", (quotation_id,)).fetchone()
        if not q:
            return False, "Quotation not found."
        if q['status'] == 'Converted' and new_status != 'Converted':
            return False, "Quotation is already converted to an invoice."

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE quotations SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, quotation_id))
        db.commit()
        return True, None

    @classmethod
    def convert_to_invoice(cls, quotation_id, paid_amount=0.0, payment_method='Cash', notes=None):
        """
        Converts an accepted quotation into an active bill/invoice,
        deducts physical stock atomically, records payments, and links records.
        """
        qtn = cls.get_by_id(quotation_id)
        if not qtn:
            return None, None, "Quotation not found."
        if qtn['status'] == 'Converted':
            return None, None, f"Quotation is already converted to Invoice #{qtn.get('invoice_number')}."

        # Prepare items for create_invoice
        items = []
        for it in qtn['items']:
            items.append({
                'product_id': it['product_id'],
                'product_name': it['product_name'],
                'sku': it['sku'],
                'quantity': it['quantity'],
                'unit_price': it['unit_price'],
                'gst_rate': it['gst_rate']
            })

        inv_notes = f"Converted from Quotation #{qtn['quotation_number']}."
        if notes:
            inv_notes += f" {notes}"

        # Call billing service
        invoice_id, invoice_num, error = BillingService.create_invoice(
            customer_id=qtn['customer_id'],
            invoice_date=datetime.now().strftime('%Y-%m-%d'),
            items=items,
            discount_type=qtn['discount_type'],
            discount_value=qtn['discount_value'],
            tax_type=qtn['tax_type'],
            paid_amount=paid_amount,
            payment_method=payment_method,
            notes=inv_notes
        )

        if error:
            return None, None, error

        # Mark quotation as converted
        db = get_db()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("""
            UPDATE quotations
            SET status = 'Converted', converted_invoice_id = ?, updated_at = ?
            WHERE id = ?
        """, (invoice_id, now_str, quotation_id))
        db.commit()

        return invoice_id, invoice_num, None

    @classmethod
    def get_by_id(cls, quotation_id):
        """Fetches complete quotation by ID with line items and customer info."""
        db = get_db()
        row = db.execute("""
            SELECT q.*, c.name as customer_name, c.phone as customer_phone,
                   c.email as customer_email, c.address as customer_address,
                   c.gstin as customer_gstin, c.customer_id as customer_code,
                   i.invoice_number as converted_invoice_number
            FROM quotations q
            JOIN customers c ON q.customer_id = c.id
            LEFT JOIN invoices i ON q.converted_invoice_id = i.id
            WHERE q.id = ?
        """, (quotation_id,)).fetchone()

        if not row:
            return None

        qtn_dict = dict(row)
        items = db.execute("""
            SELECT * FROM quotation_items WHERE quotation_id = ? ORDER BY id ASC
        """, (quotation_id,)).fetchall()
        qtn_dict['items'] = [dict(it) for it in items]

        return qtn_dict

    @classmethod
    def get_all(cls, search_query=None, status=None, start_date=None, end_date=None):
        """Fetches all quotations with filtering."""
        db = get_db()
        query = """
            SELECT q.*, c.name as customer_name, c.phone as customer_phone, c.customer_id as customer_code,
                   i.invoice_number as converted_invoice_number
            FROM quotations q
            JOIN customers c ON q.customer_id = c.id
            LEFT JOIN invoices i ON q.converted_invoice_id = i.id
            WHERE 1=1
        """
        params = []

        if search_query:
            q = f"%{search_query.strip()}%"
            query += " AND (q.quotation_number LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)"
            params.extend([q, q, q])

        if status:
            query += " AND q.status = ?"
            params.append(status)

        if start_date:
            query += " AND q.quotation_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND q.quotation_date <= ?"
            params.append(end_date)

        query += " ORDER BY q.id DESC"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def delete(cls, quotation_id):
        """Deletes a quotation and its line items."""
        db = get_db()
        q = db.execute("SELECT status FROM quotations WHERE id = ?", (quotation_id,)).fetchone()
        if not q:
            return False, "Quotation not found."
        if q['status'] == 'Converted':
            return False, "Cannot delete a quotation that has already been converted to an invoice."

        db.execute("DELETE FROM quotation_items WHERE quotation_id = ?", (quotation_id,))
        db.execute("DELETE FROM quotations WHERE id = ?", (quotation_id,))
        db.commit()
        return True, None
