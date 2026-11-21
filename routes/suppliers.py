from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.supplier import SupplierModel

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')

@suppliers_bp.route('/', methods=['GET'])
def list_suppliers():
    search = request.args.get('search', '').strip()
    suppliers = SupplierModel.get_all(search_query=search if search else None)

    total_suppliers = len(suppliers)
    total_purchases = sum(s['total_purchases'] for s in suppliers)
    total_paid = sum(s['total_paid'] for s in suppliers)
    total_payables = sum(max(0.0, s['balance_due']) for s in suppliers)

    return render_template(
        'suppliers.html',
        suppliers=suppliers,
        search=search,
        total_suppliers=total_suppliers,
        total_purchases=total_purchases,
        total_paid=total_paid,
        total_payables=total_payables
    )

@suppliers_bp.route('/add', methods=['POST'])
def add_supplier():
    name = request.form.get('name')
    phone = request.form.get('phone')
    contact_person = request.form.get('contact_person')
    email = request.form.get('email')
    address = request.form.get('address')
    gstin = request.form.get('gstin')
    opening_balance = request.form.get('opening_balance', 0.0)

    supp_id, errors = SupplierModel.create(
        name=name, phone=phone, contact_person=contact_person,
        email=email, address=address, gstin=gstin, opening_balance=opening_balance
    )

    if errors:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Supplier registered successfully!', 'success')

    return redirect(url_for('suppliers.list_suppliers'))

@suppliers_bp.route('/edit/<int:supplier_id>', methods=['POST'])
def edit_supplier(supplier_id):
    name = request.form.get('name')
    phone = request.form.get('phone')
    contact_person = request.form.get('contact_person')
    email = request.form.get('email')
    address = request.form.get('address')
    gstin = request.form.get('gstin')
    opening_balance = request.form.get('opening_balance', 0.0)

    success, errors = SupplierModel.update(
        supplier_id, name=name, phone=phone, contact_person=contact_person,
        email=email, address=address, gstin=gstin, opening_balance=opening_balance
    )

    if not success:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Supplier details updated successfully!', 'success')

    return redirect(url_for('suppliers.list_suppliers'))

@suppliers_bp.route('/delete/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    success, error = SupplierModel.delete(supplier_id)
    if not success:
        flash(error, 'danger')
    else:
        flash('Supplier removed successfully.', 'success')
    return redirect(url_for('suppliers.list_suppliers'))

@suppliers_bp.route('/pay/<int:supplier_id>', methods=['POST'])
def record_payment(supplier_id):
    amount = request.form.get('amount')
    payment_date = request.form.get('payment_date')
    payment_method = request.form.get('payment_method', 'Cash')
    reference_number = request.form.get('reference_number')
    notes = request.form.get('notes')

    pay_id, errors = SupplierModel.record_payment(
        supplier_id=supplier_id,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        reference_number=reference_number,
        notes=notes
    )

    if errors:
        for err in errors:
            flash(err, 'danger')
    else:
        flash(f'Payment of ₹{float(amount):.2f} to supplier recorded successfully!', 'success')

    return redirect(url_for('suppliers.list_suppliers'))

@suppliers_bp.route('/api/<int:supplier_id>', methods=['GET'])
def get_supplier_api(supplier_id):
    supp = SupplierModel.get_by_id(supplier_id)
    if not supp:
        return jsonify({'error': 'Supplier not found'}), 404

    ledger = SupplierModel.get_ledger(supplier_id)
    products = SupplierModel.get_supplied_products(supplier_id)

    return jsonify({
        'supplier': supp,
        'ledger': ledger,
        'products': products
    })
