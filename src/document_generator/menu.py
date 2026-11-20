from __future__ import annotations
from datetime import datetime
from pathlib import Path
from common.excel_io import sanitize_filename
from .generator import generate_document
from .services import clients, commit_credit_note_number, gst_totals, next_credit_note_number, next_tax_invoice_number
from automation.tracker import InvoiceTracker

ROOT = Path(__file__).resolve().parents[2]

def _date(label: str):
    return datetime.strptime(input(f"{label} (DD-MM-YYYY): ").strip(), "%d-%m-%Y").date()
def _subject() -> str:
    print("\n----------------------------------------\nSUBJECT DETAILS\n----------------------------------------\nEnter Subject Details (blank line to finish):")
    lines=[]
    while True:
        line=input()
        if not line: break
        lines.append(line)
    if not lines: raise ValueError("Subject details cannot be empty")
    return "\n".join(lines)
def _client() -> dict:
    records=clients()
    for i, client in enumerate(records,1): print(f"{i}. {client['name']}")
    selected=int(input("Select client: "))
    if not 1 <= selected <= len(records): raise ValueError("Invalid client selection")
    return records[selected-1]
def _safe_name(value: str) -> str: return sanitize_filename(value).replace(" ", "_")
def _value(): return gst_totals(input("Taxable Value: ").strip())

def run_document(kind: str) -> None:
    client, issue_date, subject, totals = _client(), _date("Document date"), _subject(), _value()
    output_root={"TAX INVOICE":"tax_invoices","PROFORMA INVOICE":"proforma_invoices","CREDIT NOTE":"credit_notes"}[kind]
    if kind == "TAX INVOICE":
        number=next_tax_invoice_number(issue_date); output=ROOT / "output" / output_root / f"TAX_INVOICE_{number}_{_safe_name(client['name'])}.pdf"
        generate_document(kind=kind,client=client,issue_date=issue_date,subject=subject,totals=totals,output=output,number=number)
        row = InvoiceTracker.from_settings().update_final_invoice(client_name=client["name"], consumption_start=issue_date, invoice_number=number, exchange_rate=None, invoice_date=issue_date, before_gst=totals.taxable, gst=totals.total_gst, total=totals.total)
        print(f"Tracker row {row} updated and verified.")
    elif kind == "PROFORMA INVOICE":
        output=ROOT / "output" / output_root / f"PROFORMA_INVOICE_{_safe_name(client['name'])}_{issue_date:%Y%m%d}.pdf"
        generate_document(kind=kind,client=client,issue_date=issue_date,subject=subject,totals=totals,output=output)
    else:
        original=input("Original Invoice Number: ").strip()
        if not original: raise ValueError("Original Invoice Number is required")
        original_date=_date("Original Invoice Date"); seq=next_credit_note_number(); number=f"CR-{seq}"
        output=ROOT / "output" / output_root / f"CREDIT_NOTE_{number}_{_safe_name(client['name'])}.pdf"
        if not output.exists():
            generate_document(kind=kind,client=client,issue_date=issue_date,subject=subject,totals=totals,output=output,number=number,original_invoice=original,original_date=original_date)
        row = InvoiceTracker.from_settings().record_credit_note(client_name=client["name"], original_invoice_number=original, credit_note_number=number)
        commit_credit_note_number(seq)
        print(f"Tracker row {row} updated and verified with {number}.")
    print(f"Generated: {output}")

def document_menu() -> None:
    while True:
        print("\n========================================\n       HADS TECHNOVATIONS LLP\n          DOCUMENT SYSTEM\n========================================\n\nSelect an option:\n\n1. AWS Billing Automation\n2. Tax Invoice Generator\n3. Proforma Invoice Generator\n4. Credit Note Generator\n5. Exit")
        choice=input("\nEnter your choice: ").strip()
        if choice == "1": return "AWS"
        if choice == "5": return "EXIT"
        labels={"2":"TAX INVOICE","3":"PROFORMA INVOICE","4":"CREDIT NOTE"}
        if choice not in labels: print("Invalid selection. Please choose 1 to 5."); continue
        try: run_document(labels[choice])
        except (ValueError, FileExistsError) as exc: print(f"Document not generated: {exc}")
