from datetime import datetime
from database import get_db

class ProductModel:
    @staticmethod
    def generate_next_product_id(cursor):
        cursor.execute("SELECT product_id FROM products ORDER BY id DESC LIMIT 1")
        last = cursor.fetchone()
        if not last or not last['product_id']:
            return "PROD-1001"
        try:
            last_num = int(last['product_id'].split('-')[1])
            return f"PROD-{last_num + 1}"
        except (IndexError, ValueError):
            return "PROD-1001"

    @classmethod
    def validate(cls, name, purchase_price, selling_price, gst_rate, stock_quantity, min_stock_level):
        errors = []
        name = name.strip() if name else ''
        if not name or len(name) < 2:
            errors.append("Product name is required (at least 2 characters).")
        try:
            pp = float(purchase_price)
            if pp < 0:
                errors.append("Purchase price cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Valid purchase price is required.")

        try:
            sp = float(selling_price)
            if sp < 0:
                errors.append("Selling price cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Valid selling price is required.")

        try:
            gst = float(gst_rate)
            if gst < 0 or gst > 100:
                errors.append("GST rate must be between 0% and 100%.")
        except (ValueError, TypeError):
            errors.append("Valid GST rate is required.")

        try:
            sq = int(stock_quantity)
            if sq < 0:
                errors.append("Stock quantity cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Valid stock quantity is required.")

        try:
            msl = int(min_stock_level)
            if msl < 0:
                errors.append("Minimum stock level cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Valid minimum stock level is required.")

        return errors

    @classmethod
    def create(cls, name, category_id, description, sku, purchase_price, selling_price, gst_rate, stock_quantity, min_stock_level, supplier_id=None):
        errors = cls.validate(name, purchase_price, selling_price, gst_rate, stock_quantity, min_stock_level)
        if errors:
            return None, errors

        db = get_db()
        name = name.strip()
        sku = sku.strip() if sku else None
        description = description.strip() if description else None
        category_id = int(category_id) if category_id else None
        supplier_id = int(supplier_id) if supplier_id else None

        if sku:
            existing_sku = db.execute("SELECT id FROM products WHERE sku = ?", (sku,)).fetchone()
            if existing_sku:
                return None, ["A product with this SKU / Barcode already exists."]

        cursor = db.cursor()
        prod_id = cls.generate_next_product_id(cursor)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO products (
                product_id, name, category_id, supplier_id, description, sku,
                purchase_price, selling_price, gst_rate, stock_quantity, min_stock_level,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prod_id, name, category_id, supplier_id, description, sku,
            float(purchase_price), float(selling_price), float(gst_rate),
            int(stock_quantity), int(min_stock_level), now, now
        ))
        new_id = cursor.lastrowid

        # Record initial stock movement
        sq = int(stock_quantity)
        if sq > 0:
            cursor.execute("""
                INSERT INTO stock_movements (product_id, change_type, quantity, balance_after, reference_id, notes, created_at)
                VALUES (?, 'PURCHASE', ?, ?, 'INITIAL', 'Initial stock entry', ?)
            """, (new_id, sq, sq, now))

            # If supplier is linked, record purchase so payable balance reflects initial stock
            if supplier_id:
                from models.supplier import SupplierModel
                SupplierModel.record_purchase(
                    supplier_id=supplier_id,
                    product_id=new_id,
                    quantity=sq,
                    unit_price=float(purchase_price),
                    notes="Initial product stock opening",
                    conn=db
                )

        db.commit()
        return new_id, []

    @classmethod
    def update(cls, product_db_id, name, category_id, description, sku, purchase_price, selling_price, gst_rate, min_stock_level, supplier_id=None):
        name = name.strip() if name else ''
        sku = sku.strip() if sku else None
        description = description.strip() if description else None
        category_id = int(category_id) if category_id else None
        supplier_id = int(supplier_id) if supplier_id else None

        errors = []
        if not name or len(name) < 2:
            errors.append("Product name is required (at least 2 characters).")
        try:
            pp = float(purchase_price)
            if pp < 0: errors.append("Purchase price cannot be negative.")
        except: errors.append("Valid purchase price required.")
        try:
            sp = float(selling_price)
            if sp < 0: errors.append("Selling price cannot be negative.")
        except: errors.append("Valid selling price required.")
        try:
            gst = float(gst_rate)
            if gst < 0 or gst > 100: errors.append("GST rate must be between 0% and 100%.")
        except: errors.append("Valid GST rate required.")
        try:
            msl = int(min_stock_level)
            if msl < 0: errors.append("Minimum stock level cannot be negative.")
        except: errors.append("Valid minimum stock level required.")

        if errors:
            return False, errors

        db = get_db()
        if sku:
            existing = db.execute("SELECT id FROM products WHERE sku = ? AND id != ?", (sku, product_db_id)).fetchone()
            if existing:
                return False, ["Another product already has this SKU / Barcode."]

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("""
            UPDATE products
            SET name = ?, category_id = ?, supplier_id = ?, description = ?, sku = ?,
                purchase_price = ?, selling_price = ?, gst_rate = ?, min_stock_level = ?,
                updated_at = ?
            WHERE id = ?
        """, (name, category_id, supplier_id, description, sku, float(purchase_price), float(selling_price), float(gst_rate), int(min_stock_level), now, product_db_id))
        db.commit()
        return True, []

    @classmethod
    def delete(cls, product_db_id):
        db = get_db()
        # Check if product is in invoice_items
        count = db.execute("SELECT COUNT(*) as cnt FROM invoice_items WHERE product_id = ?", (product_db_id,)).fetchone()['cnt']
        if count > 0:
            return False, f"Cannot delete product. It has been billed in {count} invoice line item(s). You can set its stock to 0 instead."

        db.execute("DELETE FROM products WHERE id = ?", (product_db_id,))
        db.commit()
        return True, None

    @classmethod
    def get_by_id(cls, product_db_id):
        db = get_db()
        row = db.execute("""
            SELECT p.*, c.name as category_name, s.name as supplier_name, s.supplier_id as supplier_code, s.phone as supplier_phone
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE p.id = ?
        """, (product_db_id,)).fetchone()
        return dict(row) if row else None

    @classmethod
    def get_all(cls, search_query=None, category_id=None, low_stock_only=False, supplier_id=None):
        db = get_db()
        query = """
            SELECT p.*, c.name as category_name, s.name as supplier_name, s.supplier_id as supplier_code, s.phone as supplier_phone
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE 1=1
        """
        params = []

        if search_query:
            q = f"%{search_query.strip()}%"
            query += " AND (p.name LIKE ? OR p.product_id LIKE ? OR p.sku LIKE ? OR p.description LIKE ? OR s.name LIKE ?)"
            params.extend([q, q, q, q, q])

        if category_id:
            query += " AND p.category_id = ?"
            params.append(category_id)

        if supplier_id:
            query += " AND p.supplier_id = ?"
            params.append(supplier_id)

        if low_stock_only:
            query += " AND p.stock_quantity <= p.min_stock_level"

        query += " ORDER BY p.id DESC"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def get_categories(cls):
        db = get_db()
        rows = db.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def add_category(cls, name, description=None):
        name = name.strip() if name else ''
        if not name:
            return None, "Category name is required."
        db = get_db()
        existing = db.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if existing:
            return existing['id'], None
        cursor = db.cursor()
        cursor.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, description))
        db.commit()
        return cursor.lastrowid, None

    @classmethod
    def delete_category(cls, category_id):
        db = get_db()
        # Set products category_id to NULL
        db.execute("UPDATE products SET category_id = NULL WHERE category_id = ?", (category_id,))
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()
        return True
