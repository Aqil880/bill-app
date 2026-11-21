from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from models.product import ProductModel

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/', methods=['GET'])
def index():
    db = get_db()
    settings = db.execute("SELECT * FROM business_settings WHERE id = 1").fetchone()
    categories = ProductModel.get_categories()
    return render_template('settings.html', settings=dict(settings) if settings else {}, categories=categories)

@settings_bp.route('/update', methods=['POST'])
def update_settings():
    business_name = request.form.get('business_name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    email = request.form.get('email')
    gstin = request.form.get('gstin')
    currency_symbol = request.form.get('currency_symbol', '₹')
    terms_conditions = request.form.get('terms_conditions')

    db = get_db()
    db.execute("""
        UPDATE business_settings
        SET business_name = ?, address = ?, phone = ?, email = ?,
            gstin = ?, currency_symbol = ?, terms_conditions = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (business_name, address, phone, email, gstin, currency_symbol, terms_conditions))
    db.commit()

    flash('Business profile and invoice settings updated successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/category/add', methods=['POST'])
def add_category():
    name = request.form.get('category_name')
    desc = request.form.get('category_desc')
    new_id, err = ProductModel.add_category(name, desc)
    if err:
        flash(err, 'danger')
    else:
        flash('Product category added successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/category/delete/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    ProductModel.delete_category(category_id)
    flash('Category deleted.', 'success')
    return redirect(url_for('settings.index'))
