import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from src.automation.exchange_rate import read_exchange_rate
from src.automation.invoice_number import format_invoice_id, InvoiceNumberAllocator
from src.automation.reconciliation import reconcile
from src.automation.exchange_rate import ExchangeRateError


def test_exchange_rate_detects_header_not_fixed_column(tmp_path):
    path = tmp_path / "consumption.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["AA1"] = "EXCHANGERATE"
    ws["AA2"] = 94.93592
    ws["AA3"] = 94.93592
    wb.save(path)
    assert read_exchange_rate(path) == Decimal("94.93592")


def test_dynamic_year_invoice_format():
    assert format_invoice_id(57, date(2027, 1, 5)) == "INV57-0501-CY27"


def test_allocator_increments():
    allocator = InvoiceNumberAllocator(56)
    assert allocator.allocate() == 57
    assert allocator.allocate() == 58


def test_reconciliation_plus_minus_five():
    assert reconcile("100", "105", "5").passed
    assert reconcile("105", "100", "5").passed
    assert not reconcile("100", "105.01", "5").passed
    assert not reconcile("105.01", "100", "5").passed


def test_exchange_rate_rejects_inconsistent_values(tmp_path):
    path = tmp_path / "consumption.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["B1"] = "EXCHANGERATE"
    ws["B2"] = 94.93592
    ws["B3"] = 95
    wb.save(path)
    try:
        read_exchange_rate(path)
    except ExchangeRateError as exc:
        assert "Inconsistent" in str(exc)
    else:
        raise AssertionError("inconsistent exchange rates must be blocked")
