from __future__ import annotations

import sys
import time
from pathlib import Path
from tkinter import Tk, filedialog

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
from invoice.invoice_generator import InvoiceGenerator
from splitter.client_mapping import ClientMapping
from splitter.excel_splitter import ExcelSplitter


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


def main() -> int:
    started_at = time.perf_counter()
    try:
        exchange_rate, _ = load_and_validate_environment()
    except BillingAutomationError as exc:
        print(f"Configuration error: {exc}")
        return 1

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Opening File Picker...")
    workbook_path = prompt_for_workbook()
    if workbook_path is None:
        print("No workbook selected. Application closed.")
        return 0
    if not workbook_path.exists() or workbook_path.suffix.lower() not in SUPPORTED_EXCEL_EXTENSIONS:
        print("Select an accessible .xlsx or .xls workbook.")
        return 1

    try:
        dataframe, worksheet_name = load_consumption_workbook(workbook_path)
        splitter = ExcelSplitter()
        billing_month = splitter.billing_month(dataframe)
        folders = create_output_folders(billing_month)
        logger = setup_logger(folders.logs / "processing.log")
        logger.info("Starting run for %s using worksheet %s", workbook_path.name, worksheet_name)
        mapping = ClientMapping(CLIENT_MAPPING_PATH)
        split_result = splitter.split(dataframe, mapping, folders.excels, logger)
        # `split()` validates every file before it returns. Any validation exception prevents this line.
        invoice_result = InvoiceGenerator(INVOICE_CLIENTS_PATH, mapping, logger).generate(
            split_result.excel_files, split_result.excel_account_numbers, folders.pdfs, exchange_rate
        )
    except WorkbookValidationError as exc:
        print(f"Workbook validation failed; invoice generation was aborted: {exc}")
        return 1
    except (BillingAutomationError, ValueError) as exc:
        print(f"Processing failed: {exc}")
        return 1
    except Exception as exc:
        print(f"Unexpected processing error: {exc}")
        return 1

    elapsed = time.perf_counter() - started_at
    skipped = split_result.skipped_clients + len(invoice_result.unmatched_files)
    print_summary(split_result.billing_month, len(split_result.excel_files), len(invoice_result.pdf_files), skipped, elapsed, folders.root)
    logger.info("Run completed: %s Excel files, %s PDFs, %s skipped clients", len(split_result.excel_files), len(invoice_result.pdf_files), skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
