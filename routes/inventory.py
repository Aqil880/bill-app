from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.product import ProductModel
from models.supplier import SupplierModel
from services.inventory_service import InventoryService

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@inventory_bp.route('/', methods=['GET'])
def list_inventory():
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', '').strip()
    supplier_filter = request.args.get('supplier', '').strip()
    low_stock = request.args.get('low_stock', '') == '1'

    products = ProductModel.get_all(
        search_query=search if search else None,
        category_id=int(category_id) if category_id and category_id.isdigit() else None,
        supplier_id=int(supplier_filter) if supplier_filter and supplier_filter.isdigit() else None,
        low_stock_only=low_stock
    )
    categories = ProductModel.get_categories()
    suppliers = SupplierModel.get_all()
    low_stock_count = len(InventoryService.get_low_stock_alerts())
    supplier_payables = SupplierModel.get_total_payables()

    return render_template(
        'inventory.html',
        products=products,
        categories=categories,
        suppliers=suppliers,
        search=search,
        selected_category=int(category_id) if category_id and category_id.isdigit() else '',
        selected_supplier=int(supplier_filter) if supplier_filter and supplier_filter.isdigit() else '',
        low_stock_filter=low_stock,
        low_stock_count=low_stock_count,
        supplier_payables=supplier_payables
    )

@inventory_bp.route('/add', methods=['POST'])
def add_product():
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    supplier_id = request.form.get('supplier_id')
    description = request.form.get('description')
    sku = request.form.get('sku')
    purchase_price = request.form.get('purchase_price', 0)
    selling_price = request.form.get('selling_price', 0)
    gst_rate = request.form.get('gst_rate', 0)
    stock_quantity = request.form.get('stock_quantity', 0)
    min_stock_level = request.form.get('min_stock_level', 5)

    prod_id, errors = ProductModel.create(
        name=name, category_id=category_id, description=description, sku=sku,
        purchase_price=purchase_price, selling_price=selling_price, gst_rate=gst_rate,
        stock_quantity=stock_quantity, min_stock_level=min_stock_level,
        supplier_id=supplier_id
    )
    if errors:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Product added to inventory successfully!', 'success')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/edit/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    supplier_id = request.form.get('supplier_id')
    description = request.form.get('description')
    sku = request.form.get('sku')
    purchase_price = request.form.get('purchase_price')
    selling_price = request.form.get('selling_price')
    gst_rate = request.form.get('gst_rate')
    min_stock_level = request.form.get('min_stock_level')

    success, errors = ProductModel.update(
        product_id, name=name, category_id=category_id, description=description, sku=sku,
        purchase_price=purchase_price, selling_price=selling_price, gst_rate=gst_rate,
        min_stock_level=min_stock_level, supplier_id=supplier_id
    )
    if not success:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Product details updated successfully!', 'success')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    success, error = ProductModel.delete(product_id)
    if not success:
        flash(error, 'danger')
    else:
        flash('Product removed from inventory.', 'success')
    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/adjust-stock/<int:product_id>', methods=['POST'])
def adjust_stock(product_id):
    adjustment_type = request.form.get('adjustment_type') # 'set' or 'add'
    qty_val = request.form.get('quantity')
    reason = request.form.get('reason', 'Stock adjustment')
    supplier_id = request.form.get('supplier_id')
    unit_cost = request.form.get('unit_cost')
    paid_now = request.form.get('paid_now', 0)
    payment_method = request.form.get('payment_method', 'Cash')

    try:
        qty_int = int(qty_val)
        if adjustment_type == 'set':
            success, err = InventoryService.adjust_stock(product_id, qty_int, notes=reason)
        else: # 'add'
            if supplier_id and qty_int > 0:
                cost = float(unit_cost) if unit_cost else None
                success, err = InventoryService.record_stock_inward(
                    product_id=product_id,
                    quantity=qty_int,
                    supplier_id=supplier_id,
                    unit_price=cost,
                    paid_now=float(paid_now or 0),
                    payment_method=payment_method,
                    notes=reason or "Incoming Supplier Stock"
                )
            else:
                change_type = 'PURCHASE' if qty_int >= 0 else 'ADJUSTMENT'
                InventoryService.update_stock(product_id, qty_int, change_type=change_type, reference_id='MANUAL', notes=reason)
                success, err = True, None

        if not success:
            flash(err, 'danger')
        else:
            flash('Stock level updated successfully!', 'success')
    except Exception as e:
        flash(f"Stock update error: {str(e)}", 'danger')

    return redirect(url_for('inventory.list_inventory'))

@inventory_bp.route('/movements', methods=['GET'])
def stock_movements():
    product_id = request.args.get('product_id')
    pid = int(product_id) if product_id and product_id.isdigit() else None
    movements = InventoryService.get_stock_movements(product_id=pid, limit=100)
    return render_template('stock_movements.html', movements=movements)

@inventory_bp.route('/api/search', methods=['GET'])
def search_products_api():
    query = request.args.get('q', '').strip()
    results = ProductModel.get_all(search_query=query if query else None)
    return jsonify(results)

@inventory_bp.route('/api/<int:product_id>', methods=['GET'])
def get_product_api(product_id):
    prod = ProductModel.get_by_id(product_id)
    if not prod:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(prod)
