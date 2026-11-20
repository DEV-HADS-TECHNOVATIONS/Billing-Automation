from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from automation.aws_credentials import get_aws_credentials
from automation.consumption_period import consumption_period
from automation.exchange_rate import read_exchange_rate
from automation.invoice_number import InvoiceNumberAllocator, format_invoice_id
from automation.reconciliation import reconcile
from automation.settings import Settings
from automation.tracker import InvoiceTracker
from integrations.aws_cost_explorer import aggregate_unblended_cost, fetch_cost_explorer, save_cost_response
from invoice.invoice_calculator import calculate_totals, prepare_invoice_data
from pdf.pdf_generator import create_invoice_pdf
from splitter.client_mapping import ClientMapping
from splitter.excel_splitter import ExcelSplitter


def process_selected_report(report: Path, settings: Settings, allocator: InvoiceNumberAllocator, logger: logging.Logger) -> dict:
    from common.excel_io import load_consumption_workbook
    dataframe, _ = load_consumption_workbook(report)
    start, end = consumption_period(dataframe)
    rate = read_exchange_rate(report)
    folders = settings.output_dir / "drafts" / f"{start:%Y-%m}"
    folders.mkdir(parents=True, exist_ok=True)
    split = ExcelSplitter().split(dataframe, ClientMapping(settings.project_client_mapping), folders, logger)
    outcomes = {"generated": [], "pending": [], "failed": [], "inactive": split.skipped_clients}
    mapping = ClientMapping(settings.project_client_mapping)
    from invoice.invoice_generator import load_clients, find_matching_client
    clients = load_clients(settings.project_invoice_clients)
    for excel in sorted(split.excel_files):
        account = split.excel_account_numbers[excel]
        config = mapping.clients[account]
        if not config.get("active", True):
            outcomes["inactive"] += 1
            continue
        client = find_matching_client(str(config.get("legal_name", "")), clients)
        if not client:
            outcomes["failed"].append((account, "Invoice recipient missing in clients.json")); continue
        try:
            import pandas as pd
            split_data = pd.read_excel(excel)
            prepared, _ = prepare_invoice_data(split_data, logger)
            credentials = get_aws_credentials(account, config)
            response, owner_account = fetch_cost_explorer(credentials, start, end)
            raw = save_cost_response(response, settings.output_dir, start, credentials.profile, linked_account_id=account, credential_owner_account_id=owner_account)
            totals = calculate_totals(prepared, float(rate))
            result = reconcile(aggregate_unblended_cost(response), totals.usd, settings.reconciliation_tolerance_usd)
            if not result.passed:
                draft = folders / f"{excel.stem}_DRAFT.pdf"
                if draft.exists(): raise FileExistsError(f"Draft invoice already exists: {draft}")
                create_invoice_pdf(excel, draft, client, f"DRAFT-{account}", datetime.now().strftime("%d-%b-%Y"), float(rate), logger)
                from automation.manual_review import create_pending_review
                review = create_pending_review(review_dir=settings.manual_review_dir, client_name=client["name"], billing_period=f"{start:%Y-%m}", excel_filename=report.name, aws_source_document=str(raw), reconciliation=result.to_dict(), account_id=account, draft_invoice=str(draft))
                outcomes["pending"].append((account, str(review))); continue
            number = format_invoice_id(allocator.allocate())
            final = settings.output_dir / "invoices" / f"{start:%Y-%m}" / f"{excel.stem}_invoice.pdf"
            if final.exists(): raise FileExistsError(f"Final invoice already exists: {final}")
            create_invoice_pdf(excel, final, client, number, datetime.now().strftime("%d-%b-%Y"), float(rate), logger)
            try:
                tracker_row = InvoiceTracker.from_settings(settings).update_final_invoice(
                    client_name=str(config.get("display_name") or client["name"]), consumption_start=start,
                    invoice_number=number, exchange_rate=rate, invoice_date=datetime.now().date(),
                    before_gst=totals.before_tax_inr, gst=totals.gst_inr, total=totals.total_inr)
            except Exception as exc:
                outcomes["failed"].append((account, f"TRACKER_UPDATE after final PDF: {exc}")); continue
            outcomes["generated"].append((account, number, str(final), tracker_row))
        except Exception as exc:
            outcomes["failed"].append((account, str(exc)))
    return outcomes
