from datetime import datetime
from database import get_db, transaction

class InventoryService:
    @staticmethod
    def update_stock(product_id, quantity_change, change_type, reference_id="MANUAL", notes="", conn=None):
        """
        Updates stock quantity and records an immutable stock movement.
        quantity_change can be positive (PURCHASE, RETURN, CANCELLATION) or negative (SALE).
        Can participate in an existing external transaction when conn is passed.
        """
        db = conn if conn is not None else get_db()
        cursor = db.cursor()

        row = cursor.execute("SELECT stock_quantity, name FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            raise ValueError(f"Product with ID {product_id} not found.")

        current_stock = row['stock_quantity']
        new_balance = current_stock + quantity_change

        if new_balance < 0:
            raise ValueError(f"Insufficient stock for '{row['name']}'. Requested reduction: {abs(quantity_change)}, Available: {current_stock}.")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update product stock
        cursor.execute("UPDATE products SET stock_quantity = ?, updated_at = ? WHERE id = ?", (new_balance, now, product_id))

        # Record movement
        cursor.execute("""
            INSERT INTO stock_movements (product_id, change_type, quantity, balance_after, reference_id, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (product_id, change_type, quantity_change, new_balance, reference_id, notes, now))

        if conn is None:
            db.commit()

        return new_balance

    @staticmethod
    def adjust_stock(product_id, new_quantity, notes="Manual adjustment"):
        """Sets stock to an absolute new quantity and computes difference."""
        db = get_db()
        row = db.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return False, "Product not found."
        
        current = row['stock_quantity']
        diff = int(new_quantity) - current
        if diff == 0:
            return True, "Stock unchanged."

        change_type = 'ADJUSTMENT'
        try:
            InventoryService.update_stock(product_id, diff, change_type, reference_id='ADJUSTMENT', notes=notes)
            return True, None
        except ValueError as e:
            return False, str(e)

    @staticmethod
    def validate_items_stock(items):
        """
        Validates whether all requested items can be fulfilled from existing stock.
        items: list of dicts with 'product_id' and 'quantity'
        """
        db = get_db()
        for item in items:
            pid = item.get('product_id')
            qty = int(item.get('quantity', 0))
            if qty <= 0:
                return False, "Quantity must be greater than zero for all items."

            row = db.execute("SELECT name, stock_quantity FROM products WHERE id = ?", (pid,)).fetchone()
            if not row:
                return False, f"Product ID {pid} does not exist."
            if row['stock_quantity'] < qty:
                return False, f"Insufficient stock for '{row['name']}'. Requested: {qty}, Available: {row['stock_quantity']}."
        return True, None

    @staticmethod
    def record_stock_inward(product_id, quantity, supplier_id=None, unit_price=None, paid_now=0.0, payment_method='Cash', notes="Incoming Stock"):
        """
        Receives new stock into inventory and creates supplier purchase & payment records.
        """
        db = get_db()
        qty = int(quantity)
        if qty <= 0:
            return False, "Quantity must be greater than zero."

        prod_row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not prod_row:
            return False, "Product not found."

        price = float(unit_price) if unit_price is not None else float(prod_row['purchase_price'])
        
        # Link to supplier if passed or fallback to product's current supplier
        supp_id = int(supplier_id) if supplier_id else prod_row['supplier_id']

        ref_id = "MANUAL"
        if supp_id:
            from models.supplier import SupplierModel
            p_id, p_num = SupplierModel.record_purchase(
                supplier_id=supp_id,
                product_id=product_id,
                quantity=qty,
                unit_price=price,
                notes=notes,
                paid_now=paid_now,
                payment_method=payment_method,
                conn=db
            )
            ref_id = p_num

            # Update product's supplier if not set
            if not prod_row['supplier_id']:
                db.execute("UPDATE products SET supplier_id = ? WHERE id = ?", (supp_id, product_id))

        # Update physical stock
        InventoryService.update_stock(product_id, qty, change_type='PURCHASE', reference_id=ref_id, notes=notes, conn=db)
        db.commit()
        return True, None

    @staticmethod
    def get_low_stock_alerts():
        """Returns list of products currently at or below minimum stock level."""
        db = get_db()
        rows = db.execute("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.stock_quantity <= p.min_stock_level
            ORDER BY p.stock_quantity ASC
        """).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_stock_movements(product_id=None, limit=100):
        """Returns stock movement ledger."""
        db = get_db()
        if product_id:
            rows = db.execute("""
                SELECT sm.*, p.name as product_name, p.product_id as prod_code
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                WHERE sm.product_id = ?
                ORDER BY sm.id DESC LIMIT ?
            """, (product_id, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT sm.*, p.name as product_name, p.product_id as prod_code
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                ORDER BY sm.id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
