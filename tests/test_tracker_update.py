from datetime import date
from openpyxl import Workbook, load_workbook

from automation.tracker import InvoiceTracker


def test_tracker_update_preserves_payment_columns_and_verifies(tmp_path):
    path = tmp_path / "tracker.xlsx"
    wb = Workbook(); ws = wb.active
    headers = ["Billing Month", "Consumption Month", "End Customer", "Invoice Number", "USD", "Invoice Date", "Amount", "GST (18%)", "Inovice Total", "Payment Received"]
    for col, value in enumerate(headers, 1): ws.cell(7, col, value)
    ws.cell(8, 10, "Received")
    wb.save(path)
    row = InvoiceTracker(path).update_final_invoice(client_name="HADS", consumption_start=date(2026, 10, 1), invoice_number="INV57-1911-CY26", exchange_rate="94.93592", invoice_date=date(2026, 11, 19), before_gst=100, gst=18, total=118)
    book = load_workbook(path, data_only=False); sheet = book.active
    assert row == 9 and sheet.cell(row, 4).value == "INV57-1911-CY26" and sheet.cell(8, 10).value == "Received"
    assert sheet.cell(row, 7).value == 100 and (tmp_path / "tracker.backup.xlsx").exists()
