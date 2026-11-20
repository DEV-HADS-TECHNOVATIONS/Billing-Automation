from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .aws_bill_input import AwsBillInput, load_aws_bill_json
from .client_matcher import identify_client
from .errors import AwsBillInputError
from .exchange_rate import read_exchange_rate
from .invoice_number import InvoiceNumberAllocator, format_invoice_id
from .manual_review import create_pending_review
from .reconciliation import reconcile
from .settings import Settings
from .tracker import InvoiceTracker


@dataclass
class PreparedInvoice:
    client: dict
    billing_period: str
    exchange_rate: str
    invoice_number: str | None
    reconciliation: dict
    status: str
    dispatch_allowed: bool
    review_record: str | None


def prepare_invoice(
    *,
    excel_path: str | Path,
    billing_period: str,
    excel_pre_tax_total_usd,
    aws_bill_json_path: str | Path,
    allocator: InvoiceNumberAllocator,
    clients_json_path: str | Path = "./config/clients.json",
    settings: Settings | None = None,
) -> PreparedInvoice:
    """Validate one Excel report against its matching AWS bill JSON.

    `excel_pre_tax_total_usd` must be the USD pre-tax amount produced by the
    existing invoice calculator, before INR conversion and GST.
    """
    settings = settings or Settings.from_env()
    excel_path = Path(excel_path)

    client = identify_client(excel_path.name, clients_json_path)
    rate = read_exchange_rate(excel_path)
    aws_bill = load_aws_bill_json(aws_bill_json_path)

    if aws_bill.client_name.casefold() != str(client["name"]).casefold():
        raise AwsBillInputError(
            f"AWS bill client '{aws_bill.client_name}' does not match "
            f"Excel filename client '{client['name']}'."
        )
    if aws_bill.billing_period != billing_period:
        raise AwsBillInputError(
            f"AWS bill period {aws_bill.billing_period} does not match "
            f"requested period {billing_period}."
        )

    expected_account = str(client.get("aws_account_id", "")).strip()
    if expected_account and aws_bill.account_id != expected_account:
        raise AwsBillInputError(
            f"AWS account mismatch. Expected {expected_account}, got {aws_bill.account_id}."
        )
    if not expected_account:
        raise AwsBillInputError(
            f"Client '{client['name']}' has no aws_account_id in clients.json. "
            "Add the correct AWS account mapping before reconciliation."
        )

    result = reconcile(
        aws_bill.comparable_pre_tax_total_usd,
        excel_pre_tax_total_usd,
        settings.reconciliation_tolerance_usd,
    )

    if result.passed:
        sequence = allocator.allocate()
        invoice_number = format_invoice_id(sequence)
        return PreparedInvoice(
            client=client,
            billing_period=billing_period,
            exchange_rate=str(rate),
            invoice_number=invoice_number,
            reconciliation=result.to_dict(),
            status="AUTO_APPROVED",
            dispatch_allowed=True,
            review_record=None,
        )

    review_path = create_pending_review(
        review_dir=settings.manual_review_dir,
        client_name=str(client["name"]),
        billing_period=billing_period,
        excel_filename=excel_path.name,
        aws_source_document=aws_bill.source_document,
        reconciliation=result.to_dict(),
    )
    return PreparedInvoice(
        client=client,
        billing_period=billing_period,
        exchange_rate=str(rate),
        invoice_number=None,  # allocate only after approval
        reconciliation=result.to_dict(),
        status="MANUAL_REVIEW_REQUIRED",
        dispatch_allowed=False,
        review_record=str(review_path),
    )


def create_allocator_from_tracker(settings: Settings | None = None) -> InvoiceNumberAllocator:
    settings = settings or Settings.from_env()
    tracker = InvoiceTracker.from_settings(settings)
    return InvoiceNumberAllocator(tracker.get_last_invoice_number())
