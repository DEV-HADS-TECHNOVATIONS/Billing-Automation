from datetime import date
from decimal import Decimal

from document_generator.generator import generate_document
from document_generator.services import Totals, gst_totals, indian_words


def test_gst_and_indian_words():
    totals = gst_totals("101151.00")
    assert totals.cgst == Decimal("9103.59") and totals.total == Decimal("119358.18")
    assert "One Lakh" in indian_words(totals.total)


def test_all_document_types_generate_pdfs(tmp_path):
    client = {"name":"RODEO DIGITAL", "address":"Address", "contact_person":"Person", "mobile":"1", "gstin":"GST"}
    totals = Totals(Decimal("100"), Decimal("9"), Decimal("9"), Decimal("18"), Decimal("118"))
    for kind, kwargs in [("TAX INVOICE", {"number":"INV57-0101-CY26"}), ("PROFORMA INVOICE", {}), ("CREDIT NOTE", {"number":"CR-18", "original_invoice":"INV57-0101-CY26", "original_date":date(2026,1,1)})]:
        path = tmp_path / f"{kind}.pdf"
        generate_document(kind=kind, client=client, issue_date=date(2026,1,2), subject="Subject line", totals=totals, output=path, **kwargs)
        assert path.exists() and path.stat().st_size > 0
