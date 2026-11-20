from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from num2words import num2words

from automation.settings import PROJECT_ROOT
from automation.tracker import InvoiceTracker
from invoice.invoice_counter import build_invoice_number

MONEY = Decimal("0.01")
SENDER = {"name": "HADS TECHNOVATIONS LLP", "address": "111, Rajiv Gandhi Road, Old Mahabalipuram Road, OMR, Ring Road, Chennai, Tamil Nadu 600096.", "contact_person": "Dinesh", "mobile": "8122015654", "gstin": "33AASFH0108G1ZP"}

@dataclass(frozen=True)
class Totals:
    taxable: Decimal; cgst: Decimal; sgst: Decimal; total_gst: Decimal; total: Decimal

def clients() -> list[dict]:
    data = json.loads((PROJECT_ROOT / "config" / "clients.json").read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data: raise ValueError("clients.json is empty or invalid")
    return data

def gst_totals(value: str, cgst_rate: Decimal = Decimal("9"), sgst_rate: Decimal = Decimal("9")) -> Totals:
    taxable = Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
    if taxable < 0: raise ValueError("Taxable value cannot be negative")
    cgst = (taxable * cgst_rate / 100).quantize(MONEY, rounding=ROUND_HALF_UP); sgst = (taxable * sgst_rate / 100).quantize(MONEY, rounding=ROUND_HALF_UP)
    return Totals(taxable, cgst, sgst, cgst + sgst, taxable + cgst + sgst)

def indian_words(amount: Decimal) -> str:
    rupees, paise = int(amount), int((amount % 1 * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{num2words(rupees, lang='en_IN').title()} Rupees and {num2words(paise, lang='en_IN').title()} Paise Only"

def next_tax_invoice_number(issue_date) -> str: return build_invoice_number(InvoiceTracker.from_settings().get_next_invoice_number(), issue_date)
def credit_number_path() -> Path: return PROJECT_ROOT / "data" / "document_counters.json"
def next_credit_note_number() -> int: return int(json.loads(credit_number_path().read_text()).get("last_credit_note_number", 0)) + 1 if credit_number_path().exists() else 1
def commit_credit_note_number(number: int) -> None:
    path = credit_number_path(); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({"last_credit_note_number": number}, indent=2) + "\n", encoding="utf-8")
