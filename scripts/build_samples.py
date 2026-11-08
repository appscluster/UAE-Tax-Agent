"""Write the longer synthetic PDFs in sample/.

Run from the repo root: python scripts/build_samples.py
"""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("freeze_fixtures", Path(__file__).with_name("freeze_fixtures.py"))
_freeze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_freeze)
pdf_bytes = _freeze.pdf_bytes

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample"

SUPPLIER = {
    "supplier_name": "Desert Ledger Trading LLC",
    "supplier_trn": "SYNTHETIC_TRN_NOT_VALID",
    "supplier_address": "Warehouse 14, Street 8, Al Quoz Industrial 3, Dubai",
    "supplier_po_box": "PO Box 94021, Dubai",
    "supplier_phone": "+971 4 000 1400",
    "supplier_email": "accounts@desert-ledger.example",
}


def money(value: float) -> str:
    return f"AED {value:,.2f}"


def line(description: str, qty: float, unit: str, unit_price: float, vat_rate: float) -> dict:
    net = round(qty * unit_price, 2)
    vat = round(net * vat_rate, 2)
    return {
        "description": description,
        "qty": qty,
        "unit": unit,
        "unit_price": unit_price,
        "net": net,
        "vat_rate": vat_rate,
        "vat": vat,
    }


def totals(lines: list[dict]) -> tuple[float, float, float]:
    net = round(sum(item["net"] for item in lines), 2)
    vat = round(sum(item["vat"] for item in lines), 2)
    return net, vat, round(net + vat, 2)


def invoice(invoice_id: str, lines: list[dict], **extra) -> dict:
    net, vat, gross = totals(lines)
    body = {
        "kind": "invoice",
        "invoice_id": invoice_id,
        "synthetic": True,
        **SUPPLIER,
        "currency": "AED",
        "lines": lines,
        "net_total": net,
        "vat_total": vat,
        "gross_total": extra.pop("gross_total", gross),
        "notes": "Synthetic invoice. Not a tax record and not an eInvoice.",
        "seed_classifier_error": "",
    }
    body.update(extra)
    return body


def render(name: str, visible: str, body: dict) -> None:
    encoded = base64.b64encode(json.dumps(body).encode()).decode()
    wrapped = "\n".join(encoded[index : index + 80] for index in range(0, len(encoded), 80))
    text = f"{visible.rstrip()}\n---JSON---\n{wrapped}\n"
    (SAMPLE / name).write_bytes(pdf_bytes(text))


def face(body: dict, rows: list[tuple[str, str]]) -> str:
    lines = body["lines"]
    head = [
        "SYNTHETIC SAMPLE - NOT A TAX RECORD AND NOT AN EINVOICE",
        body["supplier_name"],
        body["supplier_address"],
        f"{body['supplier_po_box']}    Tel {body['supplier_phone']}",
        body["supplier_email"],
        f"TRN {body['supplier_trn']}",
        "",
        f"Document          {body['invoice_id']}.pdf",
        f"Invoice ID        {body['invoice_id']}",
        f"Issue date        {body['issue_date']}",
        f"Supply date       {body.get('supply_date', body['issue_date'])}",
        f"Due date          {body.get('due_date', '')}",
        f"Currency          {body['currency']}",
        f"Payment terms     {body.get('payment_terms', '')}",
        f"Purchase order    {body.get('purchase_order', '')}",
        f"Delivery note     {body.get('delivery_note', '')}",
        "",
        "Buyer",
        f"  Name            {body['buyer_name']}",
        f"  Address         {body.get('buyer_address', '')}",
        f"  TRN             {body.get('buyer_trn') or '(not on the document)'}",
        "",
        "Description                              Qty  Unit         Net          VAT",
    ]
    for item in lines:
        rate = f"{item['vat_rate'] * 100:.0f}%"
        description = item["description"][:40].ljust(40)
        qty = f"{item['qty']:g} {item['unit']}"
        head.append(f"{description} {qty:>10}  {money(item['net']):>12}  {rate:>4} {money(item['vat']):>12}")
    head.extend(
        [
            "",
            f"Net total         {money(body['net_total'])}",
            f"VAT total         {money(body['vat_total'])}",
            f"Gross total       {money(body['gross_total'])}",
            "",
            "Notes",
            body["notes"],
            "",
        ]
    )
    for label, value in rows:
        head.append(f"{label:<18}{value}")
    head.append("")
    head.append("This PDF is a synthetic desk sample. It is not a filing.")
    return "\n".join(head)


def main() -> None:
    SAMPLE.mkdir(exist_ok=True)
    cable = invoice(
        "DL-INV-2001",
        [
            line("Copper cable 4mm, 100m drum", 120, "drum", 18.50, 0.05),
            line("PVC conduit 25mm, 3m length", 80, "length", 6.75, 0.05),
            line("Distribution board, 12-way", 4, "each", 640.00, 0.05),
            line("MCB 32A type C", 24, "each", 22.00, 0.05),
            line("Earthing rod 1.5m", 10, "each", 45.00, 0.05),
            line("Delivery to Jebel Ali warehouse", 1, "job", 180.00, 0.05),
        ],
        buyer_name="Harbor Glass Trading LLC",
        buyer_trn="SYNTHETIC_BUYER_NOT_VALID",
        buyer_address="Unit 22, Ras Al Khor Industrial 2, Dubai",
        issue_date="2026-09-18",
        supply_date="2026-09-17",
        due_date="2026-10-18",
        payment_terms="30 days from the invoice date",
        purchase_order="HG-PO-4418",
        delivery_note="DL-DN-7781",
        notes="Goods delivered to the buyer's Ras Al Khor store. Synthetic invoice. Not a tax record.",
    )
    render("DL-INV-2001.pdf", face(cable, [("Bank", "Synthetic Bank, IBAN AE00 SYNTH 0000 0000 0001")]), cable)

    coffee = invoice(
        "DL-INV-2002",
        [
            line("Green coffee, 60kg sack", 40, "sack", 85.00, 0.05),
            line("Printed export sack", 200, "each", 1.25, 0.05),
            line("Roasted coffee, designated-zone movement", 15, "sack", 90.00, 0.00),
        ],
        buyer_name="Mina Lantern LLC",
        buyer_trn="SYNTHETIC_BUYER_TWO_NOT_VALID",
        buyer_address="Warehouse B, Al Sajaa Industrial, Sharjah",
        issue_date="2026-09-21",
        supply_date="2026-09-21",
        due_date="2026-10-05",
        payment_terms="14 days from the invoice date",
        purchase_order="ML-PO-190",
        delivery_note="DL-DN-7794",
        notes="One line is stated at 0% VAT. Whether that rate fits the supply stays to verify. Synthetic invoice. Not a tax record.",
    )
    render("DL-INV-2002.pdf", face(coffee, [("Bank", "Synthetic Bank, IBAN AE00 SYNTH 0000 0000 0001")]), coffee)

    install = invoice(
        "DL-INV-2003",
        [
            line("Site survey, Al Quoz shop", 1, "visit", 1500.00, 0.05),
            line("Cable tray installation", 36, "metre", 85.00, 0.05),
            line("After-hours callout", 3, "hour", 420.00, 0.05),
        ],
        buyer_name="Creek Joinery LLC",
        buyer_trn="",
        buyer_address="Shop 4, Al Khawaneej Road, Dubai",
        issue_date="2026-09-24",
        supply_date="2026-09-23",
        due_date="2026-10-24",
        payment_terms="30 days from the invoice date",
        purchase_order="CJ-WO-55",
        delivery_note="",
        notes="The buyer tax number was not on the work order. Synthetic invoice. Not a tax record.",
    )
    render("DL-INV-2003.pdf", face(install, []), install)

    panels = invoice(
        "DL-INV-2004",
        [
            line("LED panel 60x60, 40W", 20, "each", 80.00, 0.05),
            line("Driver, constant current", 10, "each", 150.00, 0.05),
            line("Suspension kit", 5, "set", 120.00, 0.05),
            line("Commissioning visit", 8, "hour", 50.00, 0.05),
        ],
        gross_total=4218.90,
        buyer_name="Harbor Glass Trading LLC",
        buyer_trn="SYNTHETIC_BUYER_NOT_VALID",
        buyer_address="Unit 22, Ras Al Khor Industrial 2, Dubai",
        issue_date="2026-09-26",
        supply_date="2026-09-26",
        due_date="2026-10-26",
        payment_terms="30 days, less a 2% settlement if paid within 7 days",
        purchase_order="HG-PO-4460",
        delivery_note="DL-DN-7810",
        notes="The face shows a settlement discount in the gross total. The lines do not carry that discount. Synthetic invoice. Not a tax record.",
    )
    render("DL-INV-2004.pdf", face(panels, [("Settlement", "2% if paid by 2026-10-03, shown in the gross total only")]), panels)

    fitout = invoice(
        "DL-INV-2005",
        [
            line("Gypsum board 12.5mm", 90, "sheet", 28.00, 0.05),
            line("Metal stud 70mm", 140, "length", 11.40, 0.05),
            line("Insulation roll 50mm", 30, "roll", 46.00, 0.05),
            line("Joint compound 25kg", 18, "bag", 32.50, 0.05),
            line("Drywall screws, box of 1000", 40, "box", 14.00, 0.05),
            line("Access panel 600x600", 8, "each", 175.00, 0.05),
            line("Fixing labour", 24, "hour", 95.00, 0.05),
            line("Site protection and waste removal", 1, "job", 350.00, 0.05),
        ],
        buyer_name="Amber Dunes Fit-Out LLC",
        buyer_trn="SYNTHETIC_BUYER_THREE_NOT_VALID",
        buyer_address="Office 906, Business Bay, Dubai",
        issue_date="2026-09-28",
        supply_date="2026-09-15",
        due_date="2026-10-28",
        payment_terms="30 days from the invoice date",
        purchase_order="AD-PO-318",
        delivery_note="DL-DN-7844",
        notes="Materials delivered across 15 to 27 September 2026. Synthetic invoice. Not a tax record.",
    )
    render(
        "DL-INV-2005.pdf",
        face(fitout, [("Site", "Level 12, tower B, Business Bay"), ("Bank", "Synthetic Bank, IBAN AE00 SYNTH 0000 0000 0001")]),
        fitout,
    )

    contract = {
        "kind": "contract",
        "contract_id": "CTR-DL-03",
        "synthetic": True,
        "title": "Framework supply of electrical goods",
        "supplier_name": SUPPLIER["supplier_name"],
        "supplier_trn": SUPPLIER["supplier_trn"],
        "buyer_name": "Harbor Glass Trading LLC",
        "buyer_trn": "SYNTHETIC_BUYER_NOT_VALID",
        "currency": "AED",
        "start_date": "2026-07-01",
        "end_date": "2027-06-30",
        "payment_terms": "30 days from each invoice date",
        "notes": "Customer assertion of annual revenue AED 62000000. This contract is evidence, not an invoice and not a verified filing.",
    }
    visible = "\n".join(
        [
            "SYNTHETIC SAMPLE - NOT A TAX RECORD AND NOT AN EINVOICE",
            "Framework supply agreement",
            "CTR-DL-03",
            "",
            "Supplier  Desert Ledger Trading LLC",
            "Address   Warehouse 14, Street 8, Al Quoz Industrial 3, Dubai",
            "TRN       SYNTHETIC_TRN_NOT_VALID",
            "",
            "Buyer     Harbor Glass Trading LLC",
            "Address   Unit 22, Ras Al Khor Industrial 2, Dubai",
            "TRN       SYNTHETIC_BUYER_NOT_VALID",
            "",
            "Term      2026-07-01 to 2027-06-30",
            "Currency  AED",
            "Payment   30 days from each invoice date",
            "Delivery  Buyer's Ras Al Khor store, or Jebel Ali when the order says so",
            "",
            "Schedule",
            "Copper cable 4mm          AED 18.50 per drum, VAT extra",
            "Distribution board 12-way AED 640.00 each, VAT extra",
            "Callout, working hours    AED 180.00 per visit, VAT extra",
            "Callout, after hours      AED 420.00 per hour, VAT extra",
            "",
            "The buyer asserts annual revenue of AED 62,000,000. That figure is not a filing.",
            "Nothing in this agreement appoints an accredited service provider.",
            "",
            contract["notes"],
            "",
            "This PDF is a synthetic desk sample. It is not a filing.",
        ]
    )
    render("CTR-DL-03.pdf", visible, contract)
    print("wrote 6 sample files")


if __name__ == "__main__":
    main()
