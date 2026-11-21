from datetime import datetime
from database import get_db, transaction
from models.invoice import InvoiceModel
from services.inventory_service import InventoryService

class BillingService:
    @staticmethod
    def calculate_bill(items, discount_type='fixed', discount_value=0.0, tax_type='intra_state'):
        """
        Calculates all billing amounts, line item amounts, discounts, GST breakdown, and grand total.
        tax_type: 'intra_state' (CGST + SGST), 'inter_state' (IGST), 'exempt' (0% tax)
        """
        try:
            discount_val = float(discount_value or 0.0)
        except (ValueError, TypeError):
            discount_val = 0.0

        subtotal = 0.0
        processed_items = []

        # 1. Calculate raw line amounts
        for item in items:
            qty = int(item['quantity'])
            price = float(item['unit_price'])
            gst_r = float(item.get('gst_rate', 0.0))
            line_amt = round(qty * price, 2)
            subtotal += line_amt

            processed_items.append({
                'product_id': item.get('product_id'),
                'product_name': item['product_name'],
                'sku': item.get('sku'),
                'quantity': qty,
                'unit_price': price,
                'gst_rate': gst_r,
                'line_amount': line_amt
            })

        subtotal = round(subtotal, 2)

        # 2. Calculate discount
        if discount_type == 'percentage':
            discount_pct = min(100.0, max(0.0, discount_val))
            discount_amount = round((subtotal * discount_pct) / 100.0, 2)
        else: # 'fixed'
            discount_amount = round(min(subtotal, max(0.0, discount_val)), 2)

        taxable_amount = round(max(0.0, subtotal - discount_amount), 2)

        # 3. Calculate GST across items proportionally after discount
        total_gst = 0.0
        discount_ratio = (discount_amount / subtotal) if subtotal > 0 else 0.0

        for it in processed_items:
            # Proportionate taxable portion for this item
            item_taxable = it['line_amount'] * (1.0 - discount_ratio)
            if tax_type == 'exempt':
                it_gst = 0.0
            else:
                it_gst = round((item_taxable * it['gst_rate']) / 100.0, 2)

            it['gst_amount'] = it_gst
            it['total_amount'] = round(it['line_amount'] + it_gst, 2)
            total_gst += it_gst

        total_gst = round(total_gst, 2)

        # 4. Tax splits based on tax_type
        if tax_type == 'intra_state':
            cgst_amount = round(total_gst / 2.0, 2)
            sgst_amount = round(total_gst - cgst_amount, 2) # preserve exact penny
            igst_amount = 0.0
        elif tax_type == 'inter_state':
            cgst_amount = 0.0
            sgst_amount = 0.0
            igst_amount = total_gst
        else: # exempt
            cgst_amount = 0.0
            sgst_amount = 0.0
            igst_amount = 0.0
            total_gst = 0.0

        grand_total = round(taxable_amount + total_gst, 2)

        return {
            'items': processed_items,
            'subtotal': subtotal,
            'discount_type': discount_type,
            'discount_value': discount_val,
            'discount_amount': discount_amount,
            'taxable_amount': taxable_amount,
            'tax_type': tax_type,
            'cgst_amount': cgst_amount,
            'sgst_amount': sgst_amount,
            'igst_amount': igst_amount,
            'total_tax': total_gst,
            'grand_total': grand_total
        }

    @classmethod
    def create_invoice(cls, customer_id, invoice_date, items, discount_type='fixed',
                       discount_value=0.0, tax_type='intra_state', paid_amount=0.0,
                       payment_method='Cash', notes=''):
        """
        Atomically creates invoice, adds snapshot line items, deducts inventory stock,
        records stock movements, and logs initial payment.
        """
        if not customer_id:
            return None, None, "Please select a customer."
        if not items or len(items) == 0:
            return None, None, "An invoice must contain at least one product."

        try:
            paid_amt = float(paid_amount or 0.0)
            if paid_amt < 0:
                return None, None, "Paid amount cannot be negative."
        except (ValueError, TypeError):
            return None, None, "Invalid paid amount."

        # Validate stock availability first
        valid, stock_err = InventoryService.validate_items_stock(items)
        if not valid:
            return None, None, stock_err

        # Compute accurate figures
        calc = cls.calculate_bill(items, discount_type, discount_value, tax_type)
        grand_total = calc['grand_total']

        if paid_amt > grand_total + 0.01:
            return None, None, f"Paid amount (₹{paid_amt:.2f}) cannot exceed Grand Total (₹{grand_total:.2f})."

        balance_amount = max(0.0, round(grand_total - paid_amt, 2))
        payment_status = 'Paid' if balance_amount <= 0.01 else ('Partially Paid' if paid_amt > 0 else 'Unpaid')

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        inv_date = invoice_date or datetime.now().strftime('%Y-%m-%d')

        with transaction() as db:
            cursor = db.cursor()

            # Ensure customer exists
            cust = cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
            if not cust:
                return None, None, "Selected customer does not exist."

            # Generate invoice number
            invoice_num = InvoiceModel.generate_next_invoice_number(cursor)

            # Insert invoice
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, customer_id, invoice_date, subtotal,
                    discount_type, discount_value, discount_amount, taxable_amount,
                    tax_type, cgst_amount, sgst_amount, igst_amount, total_tax,
                    grand_total, paid_amount, balance_amount, payment_status,
                    status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """, (
                invoice_num, customer_id, inv_date, calc['subtotal'],
                calc['discount_type'], calc['discount_value'], calc['discount_amount'], calc['taxable_amount'],
                calc['tax_type'], calc['cgst_amount'], calc['sgst_amount'], calc['igst_amount'], calc['total_tax'],
                calc['grand_total'], paid_amt, balance_amount, payment_status,
                notes, now_str, now_str
            ))
            invoice_id = cursor.lastrowid

            # Insert invoice items & update stock
            for it in calc['items']:
                cursor.execute("""
                    INSERT INTO invoice_items (
                        invoice_id, product_id, product_name, sku,
                        quantity, unit_price, gst_rate, gst_amount, total_amount, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_id, it['product_id'], it['product_name'], it['sku'],
                    it['quantity'], it['unit_price'], it['gst_rate'], it['gst_amount'], it['total_amount'], now_str
                ))

                # Deduct inventory stock and record movement
                if it['product_id']:
                    InventoryService.update_stock(
                        product_id=it['product_id'],
                        quantity_change=-it['quantity'],
                        change_type='SALE',
                        reference_id=invoice_num,
                        notes=f"Sold in Invoice #{invoice_num}",
                        conn=db
                    )

            # Record payment if paid_amount > 0
            if paid_amt > 0:
                cursor.execute("""
                    INSERT INTO payments (
                        invoice_id, payment_date, amount, payment_method,
                        reference_number, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_id, inv_date, paid_amt, payment_method or 'Cash',
                    f"INIT-{invoice_num}", "Initial payment upon invoice creation", now_str
                ))

        return invoice_id, invoice_num, None

    @classmethod
    def cancel_invoice(cls, invoice_id, reason="Customer cancelled invoice"):
        """
        Cancels invoice, restores inventory quantities for all products, and records audit trail.
        """
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as db:
            cursor = db.cursor()
            inv = cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv:
                return False, "Invoice not found."
            if inv['status'] == 'cancelled':
                return False, "Invoice is already cancelled."

            # Fetch line items
            items = cursor.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,)).fetchall()

            # Restore stock for each item
            for item in items:
                if item['product_id']:
                    # Check product still exists
                    p = cursor.execute("SELECT id FROM products WHERE id = ?", (item['product_id'],)).fetchone()
                    if p:
                        InventoryService.update_stock(
                            product_id=item['product_id'],
                            quantity_change=item['quantity'],
                            change_type='CANCELLATION',
                            reference_id=inv['invoice_number'],
                            notes=f"Stock restored: {reason}",
                            conn=db
                        )

            # Mark invoice as cancelled
            cursor.execute("""
                UPDATE invoices
                SET status = 'cancelled', notes = COALESCE(notes || ' | ', '') || ?, updated_at = ?
                WHERE id = ?
            """, (f"Cancelled: {reason}", now_str, invoice_id))

        return True, None
