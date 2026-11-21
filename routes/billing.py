import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.customer import CustomerModel
from models.product import ProductModel
from models.invoice import InvoiceModel
from services.billing_service import BillingService
from services.pdf_service import PDFService
from database import get_db


billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

@billing_bp.route('/new', methods=['GET'])
def create_bill():
    customers = CustomerModel.get_all()
    products = ProductModel.get_all()
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template('billing.html', customers=customers, products=products, today_date=today_date)

@billing_bp.route('/create', methods=['POST'])
def save_bill():
    try:
        # Retrieve manual customer details from form
        cust_name = request.form.get('customer_name')
        cust_phone = request.form.get('customer_phone')
        cust_email = request.form.get('customer_email')
        cust_gstin = request.form.get('customer_gstin')
        cust_address = request.form.get('customer_address')
        # Validate required fields
        if not cust_name or not cust_phone:
            flash('Customer name and phone are required.', 'danger')
            return redirect(url_for('billing.create_bill'))
        # Create new customer record
        new_cust_id, err = CustomerModel.create(
            name=cust_name.strip(),
            phone=cust_phone.strip(),
            email=cust_email.strip() if cust_email else None,
            address=cust_address.strip() if cust_address else None,
            gstin=cust_gstin.strip() if cust_gstin else None,
        )
        if err:
            flash('Failed to create customer: ' + '; '.join(err), 'danger')
            return redirect(url_for('billing.create_bill'))
        customer_id = new_cust_id
        invoice_date = request.form.get('invoice_date')
        discount_type = request.form.get('discount_type', 'fixed')
        discount_value = float(request.form.get('discount_value') or 0.0)
        tax_type = request.form.get('tax_type', 'intra_state')
        paid_amount = float(request.form.get('paid_amount') or 0.0)
        payment_method = request.form.get('payment_method', 'Cash')
        notes = request.form.get('notes', '')


        # Parse items from form
        # We support either JSON payload or multi-field form submission
        items_json = request.form.get('items_json')
        if items_json:
            items = json.loads(items_json)
        else:
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            gst_rates = request.form.getlist('gst_rate[]')
            product_names = request.form.getlist('product_name[]')

            items = []
            for i in range(len(product_ids)):
                if not product_ids[i]:
                    continue
                items.append({
                    'product_id': int(product_ids[i]),
                    'product_name': product_names[i],
                    'quantity': int(quantities[i]),
                    'unit_price': float(unit_prices[i]),
                    'gst_rate': float(gst_rates[i]) if i < len(gst_rates) else 0.0
                })

        invoice_id, invoice_num, error = BillingService.create_invoice(
            customer_id=int(customer_id) if customer_id else None,
            invoice_date=invoice_date,
            items=items,
            discount_type=discount_type,
            discount_value=discount_value,
            tax_type=tax_type,
            paid_amount=paid_amount,
            payment_method=payment_method,
            notes=notes
        )

        if error:
            flash(error, 'danger')
            return redirect(url_for('billing.create_bill'))

        # Generate PDF automatically
        inv_data = InvoiceModel.get_by_id(invoice_id)
        if inv_data:
            PDFService.generate_invoice_pdf(inv_data)

        flash(f'Invoice #{invoice_num} generated successfully with stock updated!', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

    except Exception as e:
        flash(f"Error creating invoice: {str(e)}", 'danger')
        return redirect(url_for('billing.create_bill'))

@billing_bp.route('/api/calculate', methods=['POST'])
def api_calculate():
    """Live JSON endpoint for real-time calculation in invoice builder."""
    data = request.get_json() or {}
    items = data.get('items', [])
    discount_type = data.get('discount_type', 'fixed')
    discount_value = float(data.get('discount_value') or 0.0)
    tax_type = data.get('tax_type', 'intra_state')

    calc = BillingService.calculate_bill(items, discount_type, discount_value, tax_type)
    return jsonify(calc)
