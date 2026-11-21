import os
import html
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from config import Config
from database import get_db

class PDFService:
    @staticmethod
    def get_business_settings():
        db = get_db()
        row = db.execute("SELECT * FROM business_settings WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return {
            'business_name': 'Billing Pro Enterprises',
            'address': '123 Business Avenue, Suite 100, Tech City',
            'phone': '+91 98765 43210',
            'email': 'contact@billingpro.com',
            'gstin': '29ABCDE1234F1Z5',
            'currency_symbol': '₹',
            'terms_conditions': '1. Goods once sold will not be accepted back without original invoice.\n2. Payment is due within 15 days from date of invoice.'
        }

    @classmethod
    def generate_invoice_pdf(cls, invoice_data):
        """
        Generates a clean, professional, high-contrast monochrome A4 PDF invoice.
        Uses pure black text only (no colors).
        Removes unnecessary boilerplate text.
        Anchors Terms & Conditions and Authorized Signatory strictly at the bottom of the page.
        """
        inv_num = invoice_data['invoice_number']
        filename = f"{inv_num}.pdf"
        filepath = Config.PDF_DIR / filename

        Config.PDF_DIR.mkdir(parents=True, exist_ok=True)

        settings = cls.get_business_settings()
        currency = settings.get('currency_symbol', 'Rs. ')
        if currency == '₹':
            currency_display = 'Rs. '
        else:
            currency_display = currency + ' '

        # Setup document: A4 with 15mm margins and 42mm bottom margin reserved for footer
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=42 * mm
        )

        styles = getSampleStyleSheet()

        # Pure Black Typography Styles
        title_style = ParagraphStyle(
            'BwTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.black
        )
        biz_title = ParagraphStyle(
            'BwBizTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.black
        )
        body_style = ParagraphStyle(
            'BwBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black
        )
        body_bold = ParagraphStyle(
            'BwBodyBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=12,
            textColor=colors.black
        )
        meta_style = ParagraphStyle(
            'BwMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.black,
            alignment=2 # Right aligned
        )
        th_style = ParagraphStyle(
            'BwTH',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black
        )
        th_right = ParagraphStyle(
            'BwTHRight',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
            alignment=2
        )
        th_center = ParagraphStyle(
            'BwTHCenter',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
            alignment=1
        )
        body_center = ParagraphStyle(
            'BwBodyCenter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black,
            alignment=1
        )
        body_right = ParagraphStyle(
            'BwBodyRight',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black,
            alignment=2
        )

        elements = []

        # ---------------- 1. HEADER SECTION (Business info & Invoice metadata) ----------------
        biz_name = html.escape(settings.get('business_name') or 'Billing Pro Enterprises')
        biz_addr = html.escape(settings.get('address') or '').replace('\n', '<br/>')
        biz_phone = html.escape(settings.get('phone') or '')
        biz_email = html.escape(settings.get('email') or '')
        biz_gstin = html.escape(settings.get('gstin') or '')

        biz_lines = [f"<b><font size='13'>{biz_name}</font></b>"]
        if biz_addr:
            biz_lines.append(biz_addr)
        contact_line = []
        if biz_phone: contact_line.append(f"Phone: {biz_phone}")
        if biz_email: contact_line.append(f"Email: {biz_email}")
        if contact_line:
            biz_lines.append(" | ".join(contact_line))
        if biz_gstin:
            biz_lines.append(f"<b>GSTIN: {biz_gstin}</b>")

        biz_p = Paragraph("<br/>".join(biz_lines), body_style)

        status_text = 'CANCELLED' if invoice_data.get('status') == 'cancelled' else invoice_data['payment_status'].upper()
        meta_p = Paragraph(f"""
            <b><font size="18">TAX INVOICE</font></b><br/><br/>
            <b>Invoice No:</b> {html.escape(invoice_data['invoice_number'])}<br/>
            <b>Date:</b> {invoice_data['invoice_date']}<br/>
            <b>Status:</b> {status_text}
        """, meta_style)

        header_table = Table([[biz_p, meta_p]], colWidths=[110 * mm, 70 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.2, color=colors.black, spaceAfter=10))

        # ---------------- 2. BILLED TO (Clean & Concise, No clutter) ----------------
        cust_name = html.escape(invoice_data.get('customer_name') or 'Customer')
        cust_phone = invoice_data.get('customer_phone')
        cust_email = invoice_data.get('customer_email')
        cust_addr = invoice_data.get('customer_address')
        cust_gstin = invoice_data.get('customer_gstin')

        cust_lines = [
            "<b>BILLED TO:</b>",
            f"<b><font size='10'>{cust_name}</font></b>"
        ]
        if cust_phone and cust_phone != '—':
            cust_lines.append(f"Phone: {html.escape(cust_phone)}")
        if cust_email and cust_email != '—':
            cust_lines.append(f"Email: {html.escape(cust_email)}")
        if cust_addr and cust_addr != '—':
            cust_lines.append(f"Address: {html.escape(cust_addr).replace(chr(10), '<br/>')}")
        if cust_gstin and cust_gstin != '—':
            cust_lines.append(f"<b>GSTIN:</b> {html.escape(cust_gstin)}")

        bill_to_p = Paragraph("<br/>".join(cust_lines), body_style)

        billed_table = Table([[bill_to_p]], colWidths=[180 * mm])
        billed_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(billed_table)
        elements.append(Spacer(1, 12))

        # ---------------- 3. PRODUCT ITEMS TABLE (Black & White) ----------------
        table_data = [
            [
                Paragraph("<b>#</b>", th_center),
                Paragraph("<b>Product Description</b>", th_style),
                Paragraph("<b>Qty</b>", th_center),
                Paragraph("<b>Unit Price</b>", th_right),
                Paragraph("<b>GST Rate</b>", th_right),
                Paragraph("<b>Total Amount</b>", th_right),
            ]
        ]

        items = invoice_data.get('items', [])
        for idx, it in enumerate(items, 1):
            p_name = html.escape(it.get('product_name', 'Item'))
            p_sku = html.escape(it.get('sku', '') or '')
            desc_text = f"<b>{p_name}</b>" + (f"<br/><font size='7'>SKU: {p_sku}</font>" if p_sku else "")

            qty = str(it.get('quantity', 1))
            unit_price = f"{currency_display}{it.get('unit_price', 0.0):.2f}"
            gst_str = f"{it.get('gst_rate', 0.0)}%"
            total_amt = f"{currency_display}{it.get('total_amount', 0.0):.2f}"

            table_data.append([
                Paragraph(str(idx), body_center),
                Paragraph(desc_text, body_style),
                Paragraph(qty, body_center),
                Paragraph(unit_price, body_right),
                Paragraph(gst_str, body_right),
                Paragraph(f"<b>{total_amt}</b>", body_right),
            ])

        prod_table = Table(
            table_data,
            colWidths=[10 * mm, 75 * mm, 18 * mm, 25 * mm, 22 * mm, 30 * mm]
        )
        prod_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.black),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(prod_table)
        elements.append(Spacer(1, 10))

        # ---------------- 4. FINANCIAL SUMMARY TABLE ----------------
        subtotal = invoice_data.get('subtotal', 0.0)
        discount_amt = invoice_data.get('discount_amount', 0.0)
        taxable_amt = invoice_data.get('taxable_amount', 0.0)
        cgst_amt = invoice_data.get('cgst_amount', 0.0)
        sgst_amt = invoice_data.get('sgst_amount', 0.0)
        igst_amt = invoice_data.get('igst_amount', 0.0)
        grand_total = invoice_data.get('grand_total', 0.0)
        paid_amt = invoice_data.get('paid_amount', 0.0)
        balance_amt = invoice_data.get('balance_amount', 0.0)

        summary_rows = [
            [Paragraph("Subtotal:", body_style), Paragraph(f"{currency_display}{subtotal:.2f}", body_right)],
        ]

        if discount_amt > 0:
            summary_rows.append([
                Paragraph(f"Discount ({invoice_data.get('discount_type', 'fixed')}):", body_style),
                Paragraph(f"- {currency_display}{discount_amt:.2f}", body_right)
            ])

        summary_rows.append([
            Paragraph("<b>Taxable Amount:</b>", body_style),
            Paragraph(f"<b>{currency_display}{taxable_amt:.2f}</b>", body_right)
        ])

        if invoice_data.get('tax_type') == 'intra_state':
            summary_rows.append([Paragraph("CGST:", body_style), Paragraph(f"{currency_display}{cgst_amt:.2f}", body_right)])
            summary_rows.append([Paragraph("SGST:", body_style), Paragraph(f"{currency_display}{sgst_amt:.2f}", body_right)])
        elif invoice_data.get('tax_type') == 'inter_state':
            summary_rows.append([Paragraph("IGST:", body_style), Paragraph(f"{currency_display}{igst_amt:.2f}", body_right)])

        summary_rows.extend([
            [Paragraph("<b>Grand Total:</b>", body_bold), Paragraph(f"<b><font size='11'>{currency_display}{grand_total:.2f}</font></b>", body_right)],
            [Paragraph("Amount Paid:", body_style), Paragraph(f"{currency_display}{paid_amt:.2f}", body_right)],
            [Paragraph("<b>Outstanding Balance:</b>", body_style), Paragraph(f"<b>{currency_display}{balance_amt:.2f}</b>", body_right)],
        ])

        summary_table = Table(summary_rows, colWidths=[45 * mm, 35 * mm])
        summary_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 2 if discount_amt > 0 else 1), (-1, 2 if discount_amt > 0 else 1), 0.5, colors.black),
            ('LINEABOVE', (0, -3), (-1, -3), 1.2, colors.black),
            ('LINEBELOW', (0, -3), (-1, -3), 1.2, colors.black),
        ]))

        # Optional customer/invoice notes on left (only if actual notes exist)
        raw_notes = invoice_data.get('notes', '')
        if raw_notes and raw_notes.strip():
            notes_p = Paragraph(f"<b>Note:</b><br/>{html.escape(raw_notes.strip())}", body_style)
        else:
            notes_p = Paragraph("", body_style)

        bottom_split = Table([[notes_p, summary_table]], colWidths=[100 * mm, 80 * mm])
        bottom_split.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(bottom_split)

        # ---------------- 5. FIXED BOTTOM FOOTER CANVAS CALLBACK ----------------
        terms_raw = settings.get('terms_conditions', '1. Goods once sold will not be accepted back without original invoice.\n2. Payment is due within 15 days from date of invoice.')
        terms_html = html.escape(terms_raw).replace('\n', '<br/>')

        def draw_bottom_footer(canvas, doc_obj):
            canvas.saveState()
            # Draw crisp horizontal divider line
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.line(15 * mm, 38 * mm, A4[0] - 15 * mm, 38 * mm)

            # Terms & conditions on bottom left
            terms_style = ParagraphStyle(
                'FooterTerms',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=7.5,
                leading=10,
                textColor=colors.black
            )
            p_terms = Paragraph(f"<b>Terms & Conditions:</b><br/>{terms_html}", terms_style)

            # Signature block on bottom right
            sig_style = ParagraphStyle(
                'FooterSig',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=8.5,
                leading=11,
                textColor=colors.black,
                alignment=1 # Center aligned
            )
            p_sig = Paragraph(f"For <b>{biz_name}</b><br/><br/><br/>___________________________<br/><b>Authorized Signatory</b>", sig_style)

            footer_tbl = Table([[p_terms, p_sig]], colWidths=[110 * mm, 70 * mm])
            footer_tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            footer_tbl.wrapOn(canvas, doc_obj.width, 32 * mm)
            footer_tbl.drawOn(canvas, 15 * mm, 8 * mm)

            canvas.restoreState()

        # Build document with fixed bottom footer on every page
        doc.build(elements, onFirstPage=draw_bottom_footer, onLaterPages=draw_bottom_footer)
        return str(filepath)

    @classmethod
    def generate_quotation_pdf(cls, quotation_data):
        """
        Generates a clean, professional, monochrome A4 PDF Quotation / Estimate.
        """
        qtn_num = quotation_data['quotation_number']
        filename = f"Quotation_{qtn_num}.pdf"
        filepath = Config.PDF_DIR / filename

        Config.PDF_DIR.mkdir(parents=True, exist_ok=True)

        settings = cls.get_business_settings()
        currency = settings.get('currency_symbol', 'Rs. ')
        currency_display = 'Rs. ' if currency == '₹' else currency + ' '

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=15 * mm,
            bottomMargin=42 * mm
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'QtnTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.black
        )
        biz_title = ParagraphStyle(
            'QtnBizTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.black
        )
        body_style = ParagraphStyle(
            'QtnBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black
        )
        body_bold = ParagraphStyle(
            'QtnBodyBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=12,
            textColor=colors.black
        )
        meta_style = ParagraphStyle(
            'QtnMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.black,
            alignment=2
        )
        th_style = ParagraphStyle(
            'QtnTH',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black
        )
        th_right = ParagraphStyle(
            'QtnTHRight',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
            alignment=2
        )
        th_center = ParagraphStyle(
            'QtnTHCenter',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
            alignment=1
        )
        body_center = ParagraphStyle(
            'QtnBodyCenter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black,
            alignment=1
        )
        body_right = ParagraphStyle(
            'QtnBodyRight',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.black,
            alignment=2
        )

        elements = []

        # 1. Header: Business info & Quotation title
        biz_name = html.escape(settings.get('business_name', 'Billing Pro Enterprises'))
        biz_addr = html.escape(settings.get('address', '')).replace('\n', '<br/>')
        biz_phone = html.escape(settings.get('phone', ''))
        biz_email = html.escape(settings.get('email', ''))
        biz_gstin = html.escape(settings.get('gstin', ''))

        left_biz = [
            f"<b>{biz_name}</b>",
            biz_addr,
            f"Phone: {biz_phone} | Email: {biz_email}"
        ]
        if biz_gstin:
            left_biz.append(f"<b>GSTIN:</b> {biz_gstin}")
        biz_p = Paragraph("<br/>".join(left_biz), body_style)

        qtn_date = quotation_data.get('quotation_date', '')
        valid_until = quotation_data.get('valid_until', '')
        status = quotation_data.get('status', 'Draft')

        right_meta = [
            "<b>QUOTATION / ESTIMATE</b>",
            f"<b>Quote #:</b> {html.escape(qtn_num)}",
            f"<b>Date:</b> {qtn_date}"
        ]
        if valid_until:
            right_meta.append(f"<b>Valid Until:</b> {valid_until}")
        right_meta.append(f"<b>Status:</b> {status.upper()}")
        meta_p = Paragraph("<br/>".join(right_meta), meta_style)

        header_tbl = Table([[biz_p, meta_p]], colWidths=[110 * mm, 70 * mm])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_tbl)
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceBefore=0, spaceAfter=10))

        # 2. Quotation Prepared For (Customer)
        cust_name = html.escape(quotation_data.get('customer_name', 'Valued Customer'))
        cust_phone = quotation_data.get('customer_phone') or ''
        cust_email = quotation_data.get('customer_email') or ''
        cust_addr = quotation_data.get('customer_address') or ''
        cust_gstin = quotation_data.get('customer_gstin') or ''

        cust_lines = [
            "<b>PREPARED FOR:</b>",
            f"<b><font size='10'>{cust_name}</font></b>"
        ]
        if cust_phone and cust_phone != '—':
            cust_lines.append(f"Phone: {html.escape(cust_phone)}")
        if cust_email and cust_email != '—':
            cust_lines.append(f"Email: {html.escape(cust_email)}")
        if cust_addr and cust_addr != '—':
            cust_lines.append(f"Address: {html.escape(cust_addr).replace(chr(10), '<br/>')}")
        if cust_gstin and cust_gstin != '—':
            cust_lines.append(f"<b>GSTIN:</b> {html.escape(cust_gstin)}")

        billed_table = Table([[Paragraph("<br/>".join(cust_lines), body_style)]], colWidths=[180 * mm])
        billed_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(billed_table)
        elements.append(Spacer(1, 12))

        # 3. Product items table
        table_data = [
            [
                Paragraph("<b>#</b>", th_center),
                Paragraph("<b>Product Description</b>", th_style),
                Paragraph("<b>Qty</b>", th_center),
                Paragraph("<b>Unit Price</b>", th_right),
                Paragraph("<b>GST Rate</b>", th_right),
                Paragraph("<b>Total Amount</b>", th_right),
            ]
        ]

        items = quotation_data.get('items', [])
        for idx, it in enumerate(items, 1):
            p_name = html.escape(it.get('product_name', 'Item'))
            p_sku = html.escape(it.get('sku', '') or '')
            desc_text = f"<b>{p_name}</b>" + (f"<br/><font size='7'>SKU: {p_sku}</font>" if p_sku else "")

            qty = str(it.get('quantity', 1))
            unit_price = f"{currency_display}{it.get('unit_price', 0.0):.2f}"
            gst_str = f"{it.get('gst_rate', 0.0)}%"
            total_amt = f"{currency_display}{it.get('total_amount', 0.0):.2f}"

            table_data.append([
                Paragraph(str(idx), body_center),
                Paragraph(desc_text, body_style),
                Paragraph(qty, body_center),
                Paragraph(unit_price, body_right),
                Paragraph(gst_str, body_right),
                Paragraph(f"<b>{total_amt}</b>", body_right),
            ])

        prod_table = Table(
            table_data,
            colWidths=[10 * mm, 75 * mm, 18 * mm, 25 * mm, 22 * mm, 30 * mm]
        )
        prod_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1.2, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.black),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(prod_table)
        elements.append(Spacer(1, 10))

        # 4. Financial Summary Table
        subtotal = quotation_data.get('subtotal', 0.0)
        discount_amt = quotation_data.get('discount_amount', 0.0)
        taxable_amt = quotation_data.get('taxable_amount', 0.0)
        cgst_amt = quotation_data.get('cgst_amount', 0.0)
        sgst_amt = quotation_data.get('sgst_amount', 0.0)
        igst_amt = quotation_data.get('igst_amount', 0.0)
        grand_total = quotation_data.get('grand_total', 0.0)

        sum_rows = [
            [Paragraph("Subtotal:", body_style), Paragraph(f"{currency_display}{subtotal:.2f}", body_right)]
        ]
        if discount_amt > 0:
            sum_rows.append([Paragraph("Discount:", body_style), Paragraph(f"- {currency_display}{discount_amt:.2f}", body_right)])
            sum_rows.append([Paragraph("Taxable Amount:", body_style), Paragraph(f"{currency_display}{taxable_amt:.2f}", body_right)])

        if cgst_amt > 0 or sgst_amt > 0:
            sum_rows.append([Paragraph("CGST:", body_style), Paragraph(f"{currency_display}{cgst_amt:.2f}", body_right)])
            sum_rows.append([Paragraph("SGST:", body_style), Paragraph(f"{currency_display}{sgst_amt:.2f}", body_right)])
        elif igst_amt > 0:
            sum_rows.append([Paragraph("IGST:", body_style), Paragraph(f"{currency_display}{igst_amt:.2f}", body_right)])

        sum_rows.append([
            Paragraph("<b>Estimated Total:</b>", body_bold),
            Paragraph(f"<b><font size='10'>{currency_display}{grand_total:.2f}</font></b>", body_right)
        ])

        summary_table = Table(sum_rows, colWidths=[40 * mm, 45 * mm])
        summary_table.setStyle(TableStyle([
            ('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 1.2, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))

        notes_text = quotation_data.get('notes', '')
        if notes_text:
            notes_p = Paragraph(f"<b>Quotation Notes:</b><br/>{html.escape(notes_text).replace(chr(10), '<br/>')}", body_style)
        else:
            notes_p = Paragraph("<i>This is an estimate/quotation subject to final confirmation and stock availability.</i>", body_style)

        notes_box = Table([[notes_p]], colWidths=[90 * mm])
        notes_box.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        lower_tbl = Table([[notes_box, summary_table]], colWidths=[95 * mm, 85 * mm])
        lower_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(lower_tbl)

        # Footer callback
        def draw_qtn_footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.line(15 * mm, 38 * mm, A4[0] - 15 * mm, 38 * mm)

            terms_style = ParagraphStyle(
                'QtnFooterTerms',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=7.5,
                leading=10,
                textColor=colors.black
            )
            p_terms = Paragraph(f"<b>Terms & Validity:</b><br/>1. Quote valid for 30 days from date of issue.<br/>2. Prices subject to market and tax rate revisions.", terms_style)

            sig_style = ParagraphStyle(
                'QtnFooterSig',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=8.5,
                leading=11,
                textColor=colors.black,
                alignment=1
            )
            p_sig = Paragraph(f"For <b>{biz_name}</b><br/><br/><br/>___________________________<br/><b>Authorized Representative</b>", sig_style)

            footer_tbl = Table([[p_terms, p_sig]], colWidths=[110 * mm, 70 * mm])
            footer_tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            footer_tbl.wrapOn(canvas, doc_obj.width, 32 * mm)
            footer_tbl.drawOn(canvas, 15 * mm, 8 * mm)
            canvas.restoreState()

        doc.build(elements, onFirstPage=draw_qtn_footer, onLaterPages=draw_qtn_footer)
        return str(filepath)
