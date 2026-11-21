import random
from datetime import datetime, timedelta
from database import init_db, get_db
from models.customer import CustomerModel
from models.product import ProductModel
from models.supplier import SupplierModel
from models.invoice import InvoiceModel
from models.quotation import QuotationModel
from services.billing_service import BillingService
from services.pdf_service import PDFService

def seed_data():
    init_db()
    db = get_db()

    print("Seeding demo data...")

    # 1. Suppliers
    suppliers_data = [
        ("Zenith Tech Distribution Ltd", "9870011223", "Vikram Malhotra", "sales@zenithtech.com", "Plot 12, Electronic City Phase 1, Bangalore", "29AABCZ1234F1Z1", 5000.0),
        ("Global Paper & Stationery Wholesale", "9812233445", "Anita Roy", "info@globalstationery.com", "Industrial Estate, Market Road, Pune", "27AABCG9876M1Z2", 1200.0),
        ("Prime Hardware & Peripherals Co", "9833344556", "Karan Johar", "orders@primehardware.in", "B-88, Commerce Hub, Hyderabad", "36AAACP4567H1Z3", 0.0)
    ]

    supp_ids = []
    for name, phone, contact, email, addr, gstin, opening in suppliers_data:
        sid, errs = SupplierModel.create(name=name, phone=phone, contact_person=contact, email=email, address=addr, gstin=gstin, opening_balance=opening)
        if sid:
            supp_ids.append(sid)
        else:
            row = db.execute("SELECT id FROM suppliers WHERE phone = ?", (phone,)).fetchone()
            if row:
                supp_ids.append(row['id'])

    # 2. Customers
    customers_data = [
        ("Apex Infotech Solutions", "9876543210", "accounts@apexinfo.com", "Building 4, Tech Zone, Electronic City, Bangalore", "29ABCDE1234F1Z5"),
        ("Greenfield Supermarket", "9823456789", "orders@greenfield.in", "Shop 12-14, Commercial Complex, Pune", "27AABCG5555M1Z9"),
        ("Rahul Verma (Retail)", "9911223344", "rahul.v@gmail.com", "Flat 302, Palm Heights, Indiranagar, Bangalore", None),
        ("Skyline Engineering Corp", "9845012345", "finance@skyline.org", "Plot 88, Industrial Area, Hyderabad", "36AAACS1234H1Z1")
    ]

    cust_ids = []
    for name, phone, email, addr, gstin in customers_data:
        cid, errs = CustomerModel.create(name=name, phone=phone, email=email, address=addr, gstin=gstin)
        if cid:
            cust_ids.append(cid)
        else:
            # Maybe already exists
            row = db.execute("SELECT id FROM customers WHERE phone = ?", (phone,)).fetchone()
            if row: cust_ids.append(row['id'])

    # 2. Categories & Products
    cat_rows = ProductModel.get_categories()
    cat_map = {c['name']: c['id'] for c in cat_rows}

    products_data = [
        ("Wireless Ergonomic Mouse", cat_map.get("Electronics"), "2.4GHz wireless optical mouse with USB dongle", "MOU-WL-01", 600.0, 1250.0, 18.0, 35, 8, supp_ids[0] if len(supp_ids) > 0 else None),
        ("Mechanical Gaming Keyboard", cat_map.get("Electronics"), "RGB backlit mechanical keyboard with blue switches", "KB-MECH-02", 1800.0, 3200.0, 18.0, 14, 5, supp_ids[0] if len(supp_ids) > 0 else None),
        ("USB-C Fast Charging Hub", cat_map.get("Electronics"), "7-in-1 multi-port adapter with 100W PD", "HUB-USBC-07", 1200.0, 2499.0, 18.0, 3, 5, supp_ids[0] if len(supp_ids) > 0 else None), # Low stock!
        ("Executive Ergonomic Chair", cat_map.get("General"), "Breathable mesh chair with lumbar support", "CHR-EXEC-01", 5500.0, 9999.0, 18.0, 6, 2, None),
        ("A4 Copier Paper (500 Sheets)", cat_map.get("Stationery"), "75 GSM bright white copier paper ream", "PPR-A4-75", 180.0, 280.0, 12.0, 4, 10, supp_ids[1] if len(supp_ids) > 1 else None), # Low stock!
        ("Heavy Duty Thermal Receipt Printer", cat_map.get("Hardware"), "80mm auto-cutter POS billing thermal printer", "PRN-POS-80", 3500.0, 5999.0, 18.0, 8, 3, supp_ids[2] if len(supp_ids) > 2 else None),
        ("Office IT Maintenance Annual Contract", cat_map.get("Services"), "Quarterly preventive maintenance and on-call support", "SRV-AMC-YR", 12000.0, 24000.0, 18.0, 50, 5, None)
    ]

    prod_ids = []
    for name, cid, desc, sku, pp, sp, gst, qty, min_s, s_id in products_data:
        pid, errs = ProductModel.create(name, cid, desc, sku, pp, sp, gst, qty, min_s, supplier_id=s_id)
        if pid:
            prod_ids.append(pid)
        else:
            row = db.execute("SELECT id FROM products WHERE sku = ?", (sku,)).fetchone()
            if row:
                prod_ids.append(row['id'])
                # Update supplier_id if missing
                if s_id:
                    db.execute("UPDATE products SET supplier_id = ? WHERE id = ?", (s_id, row['id']))
    db.commit()

    # Record sample supplier payment to show partial clearance
    if len(supp_ids) > 0:
        pay_count = db.execute("SELECT COUNT(*) as cnt FROM supplier_payments").fetchone()['cnt']
        if pay_count == 0:
            SupplierModel.record_payment(
                supplier_id=supp_ids[0],
                amount=3000.0,
                payment_date=datetime.now().strftime('%Y-%m-%d'),
                payment_method='Bank Transfer',
                reference_number='UTR882910029',
                notes='Partial payment towards batch delivery'
            )

    # 3. Create Sample Invoices if none exist
    inv_count = db.execute("SELECT COUNT(*) as cnt FROM invoices").fetchone()['cnt']
    if inv_count == 0 and len(cust_ids) > 0 and len(prod_ids) >= 2:
        today = datetime.now()
        dates = [
            (today - timedelta(days=2)).strftime('%Y-%m-%d'),
            (today - timedelta(days=1)).strftime('%Y-%m-%d'),
            today.strftime('%Y-%m-%d')
        ]

        # Invoice 1: Full paid intra-state
        p1 = ProductModel.get_by_id(prod_ids[0])
        p2 = ProductModel.get_by_id(prod_ids[1])
        items_1 = [
            {'product_id': p1['id'], 'product_name': p1['name'], 'sku': p1['sku'], 'quantity': 2, 'unit_price': p1['selling_price'], 'gst_rate': p1['gst_rate']},
            {'product_id': p2['id'], 'product_name': p2['name'], 'sku': p2['sku'], 'quantity': 1, 'unit_price': p2['selling_price'], 'gst_rate': p2['gst_rate']}
        ]
        calc1 = BillingService.calculate_bill(items_1, discount_type='percentage', discount_value=5.0, tax_type='intra_state')
        inv_id1, inv_num1, _ = BillingService.create_invoice(
            customer_id=cust_ids[0],
            invoice_date=dates[0],
            items=items_1,
            discount_type='percentage',
            discount_value=5.0,
            tax_type='intra_state',
            paid_amount=calc1['grand_total'],
            payment_method='Bank Transfer',
            notes='Paid via NEFT Transaction #NEFT202611001'
        )
        inv_data1 = InvoiceModel.get_by_id(inv_id1)
        PDFService.generate_invoice_pdf(inv_data1)

        # Invoice 2: Partially paid
        p3 = ProductModel.get_by_id(prod_ids[3])
        items_2 = [
            {'product_id': p3['id'], 'product_name': p3['name'], 'sku': p3['sku'], 'quantity': 1, 'unit_price': p3['selling_price'], 'gst_rate': p3['gst_rate']}
        ]
        calc2 = BillingService.calculate_bill(items_2, discount_type='fixed', discount_value=500.0, tax_type='intra_state')
        inv_id2, inv_num2, _ = BillingService.create_invoice(
            customer_id=cust_ids[1],
            invoice_date=dates[1],
            items=items_2,
            discount_type='fixed',
            discount_value=500.0,
            tax_type='intra_state',
            paid_amount=5000.0,
            payment_method='UPI',
            notes='Advance payment received via GooglePay'
        )
        inv_data2 = InvoiceModel.get_by_id(inv_id2)
        PDFService.generate_invoice_pdf(inv_data2)

        # Invoice 3: Today's sale
        p4 = ProductModel.get_by_id(prod_ids[5])
        items_3 = [
            {'product_id': p4['id'], 'product_name': p4['name'], 'sku': p4['sku'], 'quantity': 1, 'unit_price': p4['selling_price'], 'gst_rate': p4['gst_rate']}
        ]
        calc3 = BillingService.calculate_bill(items_3, discount_type='fixed', discount_value=0.0, tax_type='intra_state')
        inv_id3, inv_num3, _ = BillingService.create_invoice(
            customer_id=cust_ids[2],
            invoice_date=dates[2],
            items=items_3,
            paid_amount=calc3['grand_total'],
            payment_method='Cash',
            notes='Over the counter retail purchase'
        )
        inv_data3 = InvoiceModel.get_by_id(inv_id3)
        PDFService.generate_invoice_pdf(inv_data3)

    # 4. Create Sample Quotations if none exist
    qtn_count = db.execute("SELECT COUNT(*) as cnt FROM quotations").fetchone()['cnt']
    if qtn_count == 0 and len(cust_ids) > 0 and len(prod_ids) >= 2:
        today = datetime.now()
        p_q1 = ProductModel.get_by_id(prod_ids[0])
        p_q2 = ProductModel.get_by_id(prod_ids[6]) # IT Maintenance contract

        q_items_1 = [
            {'product_id': p_q1['id'], 'product_name': p_q1['name'], 'sku': p_q1['sku'], 'quantity': 10, 'unit_price': p_q1['selling_price'], 'gst_rate': p_q1['gst_rate']},
            {'product_id': p_q2['id'], 'product_name': p_q2['name'], 'sku': p_q2['sku'], 'quantity': 1, 'unit_price': p_q2['selling_price'], 'gst_rate': p_q2['gst_rate']}
        ]
        q_id1, q_num1, _ = QuotationModel.create(
            customer_id=cust_ids[3] if len(cust_ids) > 3 else cust_ids[0],
            quotation_date=today.strftime('%Y-%m-%d'),
            valid_until=(today + timedelta(days=30)).strftime('%Y-%m-%d'),
            items=q_items_1,
            discount_type='percentage',
            discount_value=10.0,
            tax_type='intra_state',
            notes='Includes 1 year comprehensive onsite maintenance and priority support.'
        )
        QuotationModel.update_status(q_id1, 'Sent')
        q_data1 = QuotationModel.get_by_id(q_id1)
        PDFService.generate_quotation_pdf(q_data1)

    print("Demo data seeded successfully!")

if __name__ == '__main__':
    seed_data()
