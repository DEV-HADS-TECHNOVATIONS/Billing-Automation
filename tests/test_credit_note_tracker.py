from openpyxl import Workbook, load_workbook
import pytest

from automation.errors import TrackerAccessError
from automation.tracker import InvoiceTracker


def test_credit_note_is_recorded_without_changing_tax_data(tmp_path):
    path = tmp_path / "Invoice tracker.xlsx"; wb = Workbook(); ws = wb.active
    for col, header in enumerate(["Billing Month", "Consumption Month", "End Customer", "Invoice Number", "Amount", "Total Payment"], 1): ws.cell(7, col, header)
    ws.cell(8, 3, "RODEO DIGITAL"); ws.cell(8, 4, "INV57-0101-CY26"); ws.cell(8, 5, 100); ws.cell(8, 6, "=E8")
    wb.save(path)
    tracker = InvoiceTracker(path)
    assert tracker.record_credit_note(client_name="RODEO DIGITAL", original_invoice_number="INV57-0101-CY26", credit_note_number="CR-18") == 8
    sheet = load_workbook(path, data_only=False).active
    assert sheet.cell(7, 7).value == "Credit Note Number" and sheet.cell(8, 7).value == "CR-18"
    assert sheet.cell(8, 5).value == 100 and sheet.cell(8, 6).value == "=E8"
    assert tracker.record_credit_note(client_name="RODEO DIGITAL", original_invoice_number="INV57-0101-CY26", credit_note_number="CR-18") == 8
    with pytest.raises(TrackerAccessError):
        tracker.record_credit_note(client_name="RODEO DIGITAL", original_invoice_number="INV57-0101-CY26", credit_note_number="CR-19")
