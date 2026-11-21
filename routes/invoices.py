import os
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from models.invoice import InvoiceModel
from models.payment import PaymentModel
from services.billing_service import BillingService
from services.pdf_service import PDFService
from config import Config

invoices_bp = Blueprint('invoices', __name__, url_prefix='/invoices')

@invoices_bp.route('/', methods=['GET'])
def list_invoices():
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    status = request.args.get('status', '').strip()

    invoices = InvoiceModel.get_all(
        search_query=search if search else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        status=status if status else None
    )

    return render_template(
        'invoices.html',
        invoices=invoices,
        search=search,
        start_date=start_date,
        end_date=end_date,
        status=status,
        payment_methods=PaymentModel.PAYMENT_METHODS
    )

@invoices_bp.route('/<int:invoice_id>', methods=['GET'])
def view_invoice(invoice_id):
    invoice = InvoiceModel.get_by_id(invoice_id)
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices.list_invoices'))

    settings = PDFService.get_business_settings()
    return render_template('invoice_detail.html', invoice=invoice, settings=settings, payment_methods=PaymentModel.PAYMENT_METHODS)

@invoices_bp.route('/pdf/<int:invoice_id>', methods=['GET'])
def download_pdf(invoice_id):
    invoice = InvoiceModel.get_by_id(invoice_id)
    if not invoice:
        abort(404)

    pdf_path = Config.PDF_DIR / f"{invoice['invoice_number']}.pdf"
    if not pdf_path.exists():
        PDFService.generate_invoice_pdf(invoice)

    return send_file(
        str(pdf_path),
        as_attachment=True,
        download_name=f"Invoice_{invoice['invoice_number']}.pdf",
        mimetype='application/pdf'
    )

@invoices_bp.route('/print/<int:invoice_id>', methods=['GET'])
def print_pdf(invoice_id):
    invoice = InvoiceModel.get_by_id(invoice_id)
    if not invoice:
        abort(404)

    pdf_path = Config.PDF_DIR / f"{invoice['invoice_number']}.pdf"
    if not pdf_path.exists():
        PDFService.generate_invoice_pdf(invoice)

    return send_file(
        str(pdf_path),
        as_attachment=False,
        mimetype='application/pdf'
    )

@invoices_bp.route('/payment/<int:invoice_id>', methods=['POST'])
def add_payment(invoice_id):
    amount = request.form.get('amount')
    payment_method = request.form.get('payment_method')
    reference_number = request.form.get('reference_number')
    notes = request.form.get('notes')

    success, error = PaymentModel.record_payment(
        invoice_id=invoice_id,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        notes=notes
    )

    if not success:
        flash(error, 'danger')
    else:
        # Regenerate PDF with updated payment info
        inv_data = InvoiceModel.get_by_id(invoice_id)
        if inv_data:
            PDFService.generate_invoice_pdf(inv_data)
        flash('Payment recorded successfully and invoice balance updated!', 'success')

    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

@invoices_bp.route('/cancel/<int:invoice_id>', methods=['POST'])
def cancel_invoice(invoice_id):
    reason = request.form.get('reason', 'Customer requested cancellation')
    success, error = BillingService.cancel_invoice(invoice_id, reason=reason)

    if not success:
        flash(error, 'danger')
    else:
        # Regenerate PDF to show cancelled watermark
        inv_data = InvoiceModel.get_by_id(invoice_id)
        if inv_data:
            PDFService.generate_invoice_pdf(inv_data)
        flash('Invoice cancelled and all inventory product quantities successfully restored!', 'warning')

    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
