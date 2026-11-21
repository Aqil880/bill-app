from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.customer import CustomerModel

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/', methods=['GET'])
def list_customers():
    search = request.args.get('search', '').strip()
    customers = CustomerModel.get_all(search_query=search if search else None)
    return render_template('customers.html', customers=customers, search=search)

@customers_bp.route('/add', methods=['POST'])
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    gstin = request.form.get('gstin')

    cust_id, errors = CustomerModel.create(name=name, phone=phone, email=email, address=address, gstin=gstin)
    if errors:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Customer registered successfully!', 'success')
    return redirect(url_for('customers.list_customers'))

@customers_bp.route('/edit/<int:customer_id>', methods=['POST'])
def edit_customer(customer_id):
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    gstin = request.form.get('gstin')

    success, errors = CustomerModel.update(customer_id, name=name, phone=phone, email=email, address=address, gstin=gstin)
    if not success:
        for err in errors:
            flash(err, 'danger')
    else:
        flash('Customer details updated successfully!', 'success')
    return redirect(url_for('customers.list_customers'))

@customers_bp.route('/delete/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    success, error = CustomerModel.delete(customer_id)
    if not success:
        flash(error, 'danger')
    else:
        flash('Customer deleted successfully.', 'success')
    return redirect(url_for('customers.list_customers'))

@customers_bp.route('/api/<int:customer_id>', methods=['GET'])
def get_customer_api(customer_id):
    customer = CustomerModel.get_by_id(customer_id)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    history = CustomerModel.get_purchase_history(customer_id)
    return jsonify({'customer': customer, 'history': history})

@customers_bp.route('/api/search', methods=['GET'])
def search_customers_api():
    query = request.args.get('q', '').strip()
    results = CustomerModel.get_all(search_query=query if query else None)
    return jsonify(results)
