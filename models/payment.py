from datetime import datetime
from database import get_db, transaction

class PaymentModel:
    PAYMENT_METHODS = ['Cash', 'UPI', 'Debit/Credit Card', 'Bank Transfer']

    @classmethod
    def record_payment(cls, invoice_id, amount, payment_method, reference_number=None, notes=None, payment_date=None):
        try:
            amt = float(amount)
            if amt <= 0:
                return False, "Payment amount must be greater than zero."
        except (ValueError, TypeError):
            return False, "Invalid payment amount."

        if payment_method not in cls.PAYMENT_METHODS:
            return False, f"Invalid payment method. Choose from: {', '.join(cls.PAYMENT_METHODS)}"

        date_str = payment_date or datetime.now().strftime('%Y-%m-%d')
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with transaction() as db:
            cursor = db.cursor()
            inv = cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv:
                return False, "Invoice not found."
            if inv['status'] == 'cancelled':
                return False, "Cannot record payment on a cancelled invoice."

            current_balance = float(inv['balance_amount'])
            if amt > current_balance + 0.01: # Small rounding tolerance
                return False, f"Payment amount (₹{amt:.2f}) exceeds outstanding balance (₹{current_balance:.2f})."

            # Insert payment log
            cursor.execute("""
                INSERT INTO payments (invoice_id, payment_date, amount, payment_method, reference_number, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (invoice_id, date_str, amt, payment_method, reference_number, notes, now_str))

            # Recalculate totals
            new_paid = float(inv['paid_amount']) + amt
            new_balance = max(0.0, float(inv['grand_total']) - new_paid)

            new_status = 'Paid' if new_balance <= 0.01 else 'Partially Paid'

            cursor.execute("""
                UPDATE invoices
                SET paid_amount = ?, balance_amount = ?, payment_status = ?, updated_at = ?
                WHERE id = ?
            """, (round(new_paid, 2), round(new_balance, 2), new_status, now_str, invoice_id))

        return True, None
