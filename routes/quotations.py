import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from models.customer import CustomerModel
from models.product import ProductModel
from models.quotation import QuotationModel
from models.payment import PaymentModel
from services.pdf_service import PDFService
from config import Config

quotations_bp = Blueprint('quotations', __name__, url_prefix='/quotations')

@quotations_bp.route('/', methods=['GET'])
def list_quotations():
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    status = request.args.get('status', '').strip()

    quotations = QuotationModel.get_all(
        search_query=search if search else None,
        status=status if status else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )

    # Calculate status counts for quick chips
    all_quotes = QuotationModel.get_all()
    count_total = len(all_quotes)
    count_draft = sum(1 for q in all_quotes if q['status'] == 'Draft')
    count_sent = sum(1 for q in all_quotes if q['status'] == 'Sent')
    count_accepted = sum(1 for q in all_quotes if q['status'] == 'Accepted')
    count_converted = sum(1 for q in all_quotes if q['status'] == 'Converted')
    total_value = sum(q['grand_total'] for q in all_quotes)

    return render_template(
        'quotations.html',
        quotations=quotations,
        search=search,
        start_date=start_date,
        end_date=end_date,
        status=status,
        count_total=count_total,
        count_draft=count_draft,
        count_sent=count_sent,
        count_accepted=count_accepted,
        count_converted=count_converted,
        total_value=total_value
    )

@quotations_bp.route('/new', methods=['GET'])
def create_quotation():
    customers = CustomerModel.get_all()
    products = ProductModel.get_all()
    today_date = datetime.now().strftime('%Y-%m-%d')
    valid_until = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template(
        'quotation_form.html',
        customers=customers,
        products=products,
        today_date=today_date,
        valid_until=valid_until,
        quotation=None
    )

@quotations_bp.route('/create', methods=['POST'])
def save_quotation():
    try:
        customer_id = request.form.get('customer_id')
        quotation_date = request.form.get('quotation_date')
        valid_until = request.form.get('valid_until')
        discount_type = request.form.get('discount_type', 'fixed')
        discount_value = float(request.form.get('discount_value') or 0.0)
        tax_type = request.form.get('tax_type', 'intra_state')
        notes = request.form.get('notes', '')

        # Parse items from form
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

        qtn_id, qtn_num, error = QuotationModel.create(
            customer_id=int(customer_id) if customer_id else None,
            quotation_date=quotation_date,
            valid_until=valid_until,
            items=items,
            discount_type=discount_type,
            discount_value=discount_value,
            tax_type=tax_type,
            notes=notes
        )

        if error:
            flash(error, 'danger')
            return redirect(url_for('quotations.create_quotation'))

        # Generate quotation PDF automatically
        qtn_data = QuotationModel.get_by_id(qtn_id)
        if qtn_data:
            PDFService.generate_quotation_pdf(qtn_data)

        flash(f'Quotation #{qtn_num} created successfully!', 'success')
        return redirect(url_for('quotations.view_quotation', quotation_id=qtn_id))

    except Exception as e:
        flash(f"Error creating quotation: {str(e)}", 'danger')
        return redirect(url_for('quotations.create_quotation'))

@quotations_bp.route('/<int:quotation_id>', methods=['GET'])
def view_quotation(quotation_id):
    qtn = QuotationModel.get_by_id(quotation_id)
    if not qtn:
        flash('Quotation not found.', 'danger')
        return redirect(url_for('quotations.list_quotations'))

    settings = PDFService.get_business_settings()
    return render_template(
        'quotation_detail.html',
        quotation=qtn,
        settings=settings,
        statuses=QuotationModel.STATUSES,
        payment_methods=PaymentModel.PAYMENT_METHODS
    )

@quotations_bp.route('/edit/<int:quotation_id>', methods=['GET', 'POST'])
def edit_quotation(quotation_id):
    qtn = QuotationModel.get_by_id(quotation_id)
    if not qtn:
        flash('Quotation not found.', 'danger')
        return redirect(url_for('quotations.list_quotations'))

    if qtn['status'] == 'Converted':
        flash('Cannot edit a quotation that has already been converted to an invoice.', 'warning')
        return redirect(url_for('quotations.view_quotation', quotation_id=quotation_id))

    if request.method == 'POST':
        try:
            customer_id = request.form.get('customer_id')
            quotation_date = request.form.get('quotation_date')
            valid_until = request.form.get('valid_until')
            discount_type = request.form.get('discount_type', 'fixed')
            discount_value = float(request.form.get('discount_value') or 0.0)
            tax_type = request.form.get('tax_type', 'intra_state')
            notes = request.form.get('notes', '')

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

            success, error = QuotationModel.update(
                quotation_id=quotation_id,
                customer_id=int(customer_id) if customer_id else None,
                quotation_date=quotation_date,
                valid_until=valid_until,
                items=items,
                discount_type=discount_type,
                discount_value=discount_value,
                tax_type=tax_type,
                notes=notes
            )

            if not success:
                flash(error, 'danger')
                return redirect(url_for('quotations.edit_quotation', quotation_id=quotation_id))

            # Regenerate PDF
            updated_data = QuotationModel.get_by_id(quotation_id)
            if updated_data:
                PDFService.generate_quotation_pdf(updated_data)

            flash('Quotation updated successfully!', 'success')
            return redirect(url_for('quotations.view_quotation', quotation_id=quotation_id))

        except Exception as e:
            flash(f"Error updating quotation: {str(e)}", 'danger')
            return redirect(url_for('quotations.edit_quotation', quotation_id=quotation_id))

    customers = CustomerModel.get_all()
    products = ProductModel.get_all()
    return render_template(
        'quotation_form.html',
        customers=customers,
        products=products,
        today_date=qtn['quotation_date'],
        valid_until=qtn['valid_until'] or '',
        quotation=qtn
    )

@quotations_bp.route('/status/<int:quotation_id>', methods=['POST'])
def update_status(quotation_id):
    status = request.form.get('status')
    success, error = QuotationModel.update_status(quotation_id, status)
    if not success:
        flash(error, 'danger')
    else:
        # Regenerate PDF with updated status
        qtn_data = QuotationModel.get_by_id(quotation_id)
        if qtn_data:
            PDFService.generate_quotation_pdf(qtn_data)
        flash(f'Quotation status updated to {status}.', 'success')
    return redirect(url_for('quotations.view_quotation', quotation_id=quotation_id))

@quotations_bp.route('/convert/<int:quotation_id>', methods=['POST'])
def convert_to_invoice(quotation_id):
    paid_amount = float(request.form.get('paid_amount') or 0.0)
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', '')

    inv_id, inv_num, error = QuotationModel.convert_to_invoice(
        quotation_id=quotation_id,
        paid_amount=paid_amount,
        payment_method=payment_method,
        notes=notes
    )

    if error:
        flash(f"Failed to convert quotation: {error}", 'danger')
        return redirect(url_for('quotations.view_quotation', quotation_id=quotation_id))

    # Generate invoice PDF
    from models.invoice import InvoiceModel
    inv_data = InvoiceModel.get_by_id(inv_id)
    if inv_data:
        PDFService.generate_invoice_pdf(inv_data)

    # Regenerate quotation PDF to reflect 'CONVERTED'
    qtn_data = QuotationModel.get_by_id(quotation_id)
    if qtn_data:
        PDFService.generate_quotation_pdf(qtn_data)

    flash(f"Quotation successfully converted to Invoice #{inv_num}! Inventory stock has been updated.", 'success')
    return redirect(url_for('invoices.view_invoice', invoice_id=inv_id))

@quotations_bp.route('/pdf/<int:quotation_id>', methods=['GET'])
def download_pdf(quotation_id):
    qtn = QuotationModel.get_by_id(quotation_id)
    if not qtn:
        abort(404)

    pdf_path = Config.PDF_DIR / f"Quotation_{qtn['quotation_number']}.pdf"
    if not pdf_path.exists():
        PDFService.generate_quotation_pdf(qtn)

    return send_file(
        str(pdf_path),
        as_attachment=True,
        download_name=f"Quotation_{qtn['quotation_number']}.pdf",
        mimetype='application/pdf'
    )

@quotations_bp.route('/print/<int:quotation_id>', methods=['GET'])
def print_pdf(quotation_id):
    qtn = QuotationModel.get_by_id(quotation_id)
    if not qtn:
        abort(404)

    pdf_path = Config.PDF_DIR / f"Quotation_{qtn['quotation_number']}.pdf"
    if not pdf_path.exists():
        PDFService.generate_quotation_pdf(qtn)

    return send_file(
        str(pdf_path),
        as_attachment=False,
        mimetype='application/pdf'
    )

@quotations_bp.route('/delete/<int:quotation_id>', methods=['POST'])
def delete_quotation(quotation_id):
    success, error = QuotationModel.delete(quotation_id)
    if not success:
        flash(error, 'danger')
    else:
        flash('Quotation deleted successfully.', 'success')
    return redirect(url_for('quotations.list_quotations'))
