from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .errors import AwsBillInputError


@dataclass(frozen=True)
class AwsBillInput:
    client_name: str
    billing_period: str  # YYYY-MM
    account_id: str
    currency: str
    comparable_pre_tax_total_usd: Decimal
    source_document: str | None = None


def load_aws_bill_json(path: str | Path) -> AwsBillInput:
    """Load a manually prepared AWS bill summary JSON for local testing.

    Later this adapter can be replaced with AWS Invoicing/Cost Explorer API
    retrieval while keeping the workflow input model unchanged.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise AwsBillInputError(f"AWS bill JSON not found: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        total = Decimal(str(data["comparable_pre_tax_total_usd"]))
        result = AwsBillInput(
            client_name=str(data["client_name"]).strip(),
            billing_period=str(data["billing_period"]).strip(),
            account_id=str(data["account_id"]).strip(),
            currency=str(data.get("currency", "USD")).upper(),
            comparable_pre_tax_total_usd=total,
            source_document=data.get("source_document"),
        )
    except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
        raise AwsBillInputError(f"Invalid AWS bill JSON {file_path}: {exc}") from exc

    if result.currency != "USD":
        raise AwsBillInputError("Testing reconciliation currently requires USD amounts.")
    if result.comparable_pre_tax_total_usd < 0:
        raise AwsBillInputError("AWS bill total cannot be negative.")
    if not result.client_name or not result.billing_period or not result.account_id:
        raise AwsBillInputError("AWS bill JSON must include client_name, billing_period and account_id.")
    return result
