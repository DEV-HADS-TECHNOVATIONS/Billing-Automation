from __future__ import annotations

import sys
import time
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog

import pandas as pd
from dotenv import load_dotenv

from common.excel_io import load_consumption_workbook
from common.exceptions import BillingAutomationError, WorkbookValidationError
from common.logging_setup import setup_logger
from config.settings import (
    CLIENT_MAPPING_PATH,
    INPUT_DIR,
    INVOICE_CLIENTS_PATH,
    SUPPORTED_EXCEL_EXTENSIONS,
    create_output_folders,
    load_and_validate_environment,
)
from automation.client_matcher import identify_client
from automation.exchange_rate import read_exchange_rate
from automation.invoice_number import InvoiceNumberAllocator, format_invoice_id
from automation.manual_review import create_pending_review
from automation.reconciliation import reconcile
from automation.settings import PROJECT_ROOT, Settings
from automation.tracker import InvoiceTracker
from integrations.aws_billing import LocalAwsBillingProvider
from invoice.invoice_calculator import calculate_totals, prepare_invoice_data
from pdf.pdf_generator import create_invoice_pdf
from splitter.client_mapping import ClientMapping
from splitter.excel_splitter import ExcelSplitter
from automation.multi_client import process_selected_report
from document_generator.menu import document_menu


def prompt_for_workbook() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selection = filedialog.askopenfilename(
            title="Select AWS Billing Consumption Report",
            initialdir=str(INPUT_DIR),
            filetypes=[("Excel Files", "*.xlsx *.xls")],
        )
    finally:
        root.destroy()
    return Path(selection) if selection else None


def print_summary(billing_month: str, excel_count: int, pdf_count: int, skipped_clients: int, elapsed: float, output_dir: Path) -> None:
    print("\n========================================")
    print("AWS Billing Automation Summary")
    print("========================================")
    print(f"Billing Month: {billing_month}")
    print(f"Excel Files Created: {excel_count}")
    print(f"PDF Files Created: {pdf_count}")
    print(f"Skipped Clients: {skipped_clients}")
    print(f"Execution Time: {elapsed:.2f}s")
    print(f"Output Folder: {output_dir}")


def _billing_period(dataframe: pd.DataFrame) -> str:
    _, columns = prepare_invoice_data(dataframe)
    return pd.to_datetime(dataframe[columns.billing_period_start].dropna().iloc[0], errors="raise").strftime("%Y-%m")


def _account_id(dataframe: pd.DataFrame) -> str:
    _, columns = prepare_invoice_data(dataframe)
    value = str(dataframe[columns.linked_account_id].dropna().iloc[0]).strip()
    return value[:-2] if value.endswith(".0") and value[:-2].isdigit() else value


def _tracker_proposal(output_dir: Path, client_name: str, billing_period: str, invoice_number: str) -> None:
    folder = output_dir / "tracker_update_proposals"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{invoice_number}.json").write_text(json.dumps({"client_name": client_name, "billing_period": billing_period, "invoice_number": invoice_number, "status": "PROPOSED_MANUAL_TRACKER_UPDATE"}, indent=2), encoding="utf-8")


def _approved_review_exists(settings: Settings, report: Path, period: str) -> bool:
    for path in settings.manual_review_dir.glob("review_*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "APPROVED" and record.get("excel_filename") == report.name and record.get("billing_period") == period:
                return True
        except (OSError, ValueError):
            continue
    return False


def _highest_proposed_sequence(output_dir: Path) -> int:
    maximum = 0
    for path in (output_dir / "tracker_update_proposals").glob("INV*.json"):
        match = re.match(r"INV(\d+)-", path.name)
        if match:
            maximum = max(maximum, int(match.group(1)))
    return maximum


def aws_billing_main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    settings = Settings.from_env()
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    print("Opening Excel file selection dialog...")
    report = prompt_for_workbook()
    if report is None:
        print("No workbook selected. Application closed.")
        return 0
    try:
        allocator = InvoiceNumberAllocator(InvoiceTracker.from_settings(settings).get_last_invoice_number())
        outcome = process_selected_report(report, settings, allocator, logging.getLogger("aws_invoice_automation"))
    except Exception as exc:
        print(f"Processing failed: {exc}")
        return 1
    print("AWS BILLING AUTOMATION")
    print(f"Invoices Generated: {len(outcome['generated'])}")
    print(f"Manual Reviews Required: {len(outcome['pending'])}")
    print(f"Inactive Clients Skipped: {outcome['inactive']}")
    print(f"Failed Clients: {len(outcome['failed'])}")
    for account, reason in outcome["failed"]:
        print(f"{account}: FAILED — {type(reason).__name__ if isinstance(reason, Exception) else 'PROCESSING'}: {reason}")
    for account, review in outcome["pending"]:
        print(f"{account}: MANUAL REVIEW REQUIRED — {review}")
    for account, invoice, path, tracker_row in outcome["generated"]:
        print(f"{account}: FINAL INVOICE {invoice} — {path}; tracker row {tracker_row} verified")
    return 1 if outcome["failed"] else 0

    # Legacy single-report local-file flow retained below for reference.
    summary = {"generated": [], "pending": [], "failed": []}
    try:
        allocator = InvoiceNumberAllocator(max(InvoiceTracker.from_settings(settings).get_last_invoice_number(), _highest_proposed_sequence(settings.output_dir)))
    except Exception as exc:
        print(f"Configuration error: {exc}")
        return 1
    provider, logger = LocalAwsBillingProvider(settings.aws_bills_dir), logging.getLogger("aws_invoice_automation")
    files = sorted(path for path in settings.input_dir.glob("*.*") if path.suffix.lower() in SUPPORTED_EXCEL_EXTENSIONS and path.resolve() != settings.tracker_local_path.resolve())
    for report in files:
        try:
            client = identify_client(report.name)
            dataframe, _ = load_consumption_workbook(report)
            period, account_id, rate = _billing_period(dataframe), _account_id(dataframe), read_exchange_rate(report)
            prepared, _ = prepare_invoice_data(dataframe, logger)
            aws_bill = provider.get_bill(str(client["name"]), period)
            if aws_bill.account_id != account_id:
                raise ValueError(f"AWS account mismatch: report={account_id}, bill={aws_bill.account_id}")
            result = reconcile(aws_bill.comparable_pre_tax_total_usd, calculate_totals(prepared, float(rate)).usd, settings.reconciliation_tolerance_usd)
            if not result.passed and not _approved_review_exists(settings, report, period):
                review = create_pending_review(review_dir=settings.manual_review_dir, client_name=str(client["name"]), billing_period=period, excel_filename=report.name, aws_source_document=aws_bill.source_document, reconciliation=result.to_dict())
                summary["pending"].append((report.name, str(review)))
                continue
            invoice_number = format_invoice_id(allocator.allocate())
            destination = settings.output_dir / "invoices" / period / f"{report.stem}_invoice.pdf"
            if destination.exists():
                raise ValueError(f"Invoice output already exists for {report.name}; refusing to overwrite it")
            create_invoice_pdf(report, destination, client, invoice_number, datetime.now().strftime("%d-%b-%Y"), float(rate), logger)
            _tracker_proposal(settings.output_dir, str(client["name"]), period, invoice_number)
            summary["generated"].append((report.name, invoice_number, str(rate)))
        except Exception as exc:
            logger.exception("Failed processing %s", report.name)
            summary["failed"].append((report.name, str(exc)))
    print("AWS INVOICE GENERATOR – PROCESSING SUMMARY")
    print(f"Total Excel Files: {sum(len(entries) for entries in summary.values())}")
    print(f"Successfully Generated: {len(summary['generated'])}")
    print(f"Pending Manual Review: {len(summary['pending'])}")
    print(f"Failed Files: {len(summary['failed'])}")
    for name, invoice, rate in summary["generated"]:
        print(f"{name}: {invoice} (rate {rate})")
    for name, review in summary["pending"]:
        print(f"{name}: MANUAL REVIEW REQUIRED ({review})")
    for name, reason in summary["failed"]:
        print(f"{name}: FAILED ({reason})")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    while True:
        action = document_menu()
        if action == "EXIT":
            sys.exit(0)
        if action == "AWS":
            aws_billing_main()
