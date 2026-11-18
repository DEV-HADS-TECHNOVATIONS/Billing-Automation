from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from common.exceptions import WorkbookValidationError

REGION_MAP = {
    "us-east-1": "US East (N. Virginia)", "USE1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)", "USE2": "US East (Ohio)",
    "us-west-1": "US West (N. California)", "USW1": "US West (N. California)",
    "us-west-2": "US West (Oregon)", "USW2": "US West (Oregon)",
    "af-south-1": "Africa (Cape Town)", "AFS1": "Africa (Cape Town)",
    "ap-east-1": "Asia Pacific (Hong Kong)", "APE1": "Asia Pacific (Hong Kong)",
    "ap-south-1": "Asia Pacific (Mumbai)", "APS3": "Asia Pacific (Mumbai)",
    "ap-south-2": "Asia Pacific (Hyderabad)", "APS5": "Asia Pacific (Hyderabad)",
    "ap-southeast-1": "Asia Pacific (Singapore)", "APS1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)", "APS2": "Asia Pacific (Sydney)",
    "ap-southeast-3": "Asia Pacific (Jakarta)", "APS4": "Asia Pacific (Jakarta)",
    "ap-southeast-4": "Asia Pacific (Melbourne)", "APS6": "Asia Pacific (Melbourne)",
    "ap-southeast-5": "Asia Pacific (Malaysia)", "APS7": "Asia Pacific (Malaysia)",
    "ap-southeast-6": "Asia Pacific (New Zealand)", "APS8": "Asia Pacific (New Zealand)",
    "ap-southeast-7": "Asia Pacific (Thailand)", "APS9": "Asia Pacific (Thailand)",
    "ap-northeast-1": "Asia Pacific (Tokyo)", "APN1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)", "APN2": "Asia Pacific (Seoul)",
    "ap-northeast-3": "Asia Pacific (Osaka)", "APN3": "Asia Pacific (Osaka)",
    "ca-central-1": "Canada (Central)", "CAN1": "Canada (Central)",
    "eu-central-1": "Europe (Frankfurt)", "EUC1": "Europe (Frankfurt)",
    "eu-west-1": "Europe (Ireland)", "EU": "Europe (Ireland)",
    "eu-west-2": "Europe (London)", "EUW2": "Europe (London)",
    "eu-south-1": "Europe (Milan)", "EUS1": "Europe (Milan)",
    "eu-west-3": "Europe (Paris)", "EUW3": "Europe (Paris)",
    "eu-south-2": "Europe (Spain)", "EUS2": "Europe (Spain)",
    "eu-north-1": "Europe (Stockholm)", "EUN1": "Europe (Stockholm)",
    "me-south-1": "Middle East (Bahrain)", "MES1": "Middle East (Bahrain)",
    "me-central-1": "Middle East (UAE)", "MEC1": "Middle East (UAE)",
    "sa-east-1": "South America (São Paulo)", "SAE1": "South America (São Paulo)",
    "ZA": "Africa (Cape Town)", "IN": "Asia Pacific (Mumbai)", "AP": "Asia Pacific (Singapore)",
    "AU": "Asia Pacific (Sydney)", "JP": "Asia Pacific (Tokyo)", "CA": "Canada (Central)",
    "ME": "Middle East (Bahrain)", "SA": "South America (Sao Paulo)", "US": "US East (N. Virginia)",
}


@dataclass(frozen=True)
class InvoiceColumns:
    product: str
    usage_type: str
    item_description: str
    usage_quantity: str
    actual_cost: str
    linked_account_id: str
    billing_period_start: str
    billing_period_end: str
    credits: str | None


@dataclass(frozen=True)
class InvoiceTotals:
    usd: float
    before_tax_inr: float
    gst_inr: float
    total_inr: float


def normalize_column_name(value: object) -> str:
    """Normalize CUR headers while preserving the original dataframe column names."""
    return re.sub(r"\s+", "", str(value).strip()).lower()


def find_column_name(dataframe: pd.DataFrame, expected_name: str) -> str | None:
    normalized_columns = {normalize_column_name(column): str(column) for column in dataframe.columns}
    return normalized_columns.get(normalize_column_name(expected_name))


def get_region_from_usage_type(usage_type: object) -> str:
    if not isinstance(usage_type, str):
        return "Global"
    match = re.match(r"^([A-Z]{2,3})-", usage_type)
    if match and match.group(1) in REGION_MAP:
        return REGION_MAP[match.group(1)]
    match = re.search(r"([a-z]{2,3}-[a-z]+-\d)", usage_type)
    if match:
        return REGION_MAP.get(match.group(1), match.group(1))
    match = re.search(r"([A-Z]{2,3}\d)", usage_type)
    if match:
        return REGION_MAP.get(match.group(1), match.group(1))
    return "Global"


def calculate_due_date(invoice_date: datetime) -> str:
    year, month = (invoice_date.year + 1, 1) if invoice_date.month == 12 else (invoice_date.year, invoice_date.month + 1)
    return datetime(year, month, 10).strftime("%d-%b-%Y")


def truncate_toward_zero(value: float, decimals: int = 2) -> float:
    factor = 10 ** decimals
    return int(value * factor) / factor


def prepare_invoice_data(
    dataframe: pd.DataFrame,
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, InvoiceColumns]:
    if logger:
        logger.info("Detected Excel columns: %s", list(dataframe.columns))
    values = {
    "product": find_column_name(dataframe, "PRODUCTNAME"),
    "usage_type": find_column_name(dataframe, "USAGETYPE"),
    "item_description": find_column_name(dataframe, "ITEMDESCRIPTION"),
    "usage_quantity": find_column_name(dataframe, "USAGEQUANTITY"),
    "actual_cost": (
        find_column_name(dataframe, "ACTUAL COST")
        or find_column_name(dataframe, "ACTUALCUSTOMERCOST")
    ),
    "linked_account_id": find_column_name(dataframe, "LINKEDACCOUNTID"),
    "billing_period_start": find_column_name(dataframe, "BILLINGPERIODSTARTDATE"),
    "billing_period_end": find_column_name(dataframe, "BILLINGPERIODENDDATE"),
    "credits": find_column_name(dataframe, "CREDITS"),
}
    missing = [key for key, value in values.items() if value is None and key != "credits"]
    if missing:
        labels = {
            "product": "Product",
            "usage_type": "Usage Type",
            "item_description": "Item Description",
            "usage_quantity": "Usage Quantity",
            "actual_cost": "Actual Cost",
            "linked_account_id": "Linked Account Id",
            "billing_period_start": "Billing Period Start",
            "billing_period_end": "Billing Period End",
        }
        raise WorkbookValidationError(f"Missing invoice column: {labels[missing[0]]}")
    columns = InvoiceColumns(**values)  # type: ignore[arg-type]
    if logger:
        logger.info(
            "Resolved invoice column mapping:\n"
            "Product -> %s\nUsage Type -> %s\nItem Description -> %s\n"
            "Usage Quantity -> %s\nActual Cost -> %s\nLinked Account Id -> %s\n"
            "Billing Period Start -> %s\nBilling Period End -> %s",
            columns.product,
            columns.usage_type,
            columns.item_description,
            columns.usage_quantity,
            columns.actual_cost,
            columns.linked_account_id,
            columns.billing_period_start,
            columns.billing_period_end,
        )
    prepared = dataframe.copy()
    prepared[columns.actual_cost] = pd.to_numeric(prepared[columns.actual_cost], errors="coerce").fillna(0)
    prepared[columns.usage_quantity] = prepared[columns.usage_quantity].astype(str)
    if columns.credits:
        prepared[columns.credits] = pd.to_numeric(prepared[columns.credits], errors="coerce").fillna(0)
        prepared["Consolidated Cost"] = prepared[columns.actual_cost] + prepared[columns.credits]
    else:
        prepared["Consolidated Cost"] = prepared[columns.actual_cost]
    prepared["Region"] = prepared[columns.usage_type].apply(get_region_from_usage_type)
    return prepared, columns


def calculate_totals(dataframe: pd.DataFrame, exchange_rate: float) -> InvoiceTotals:
    usd = float(dataframe["Consolidated Cost"].sum())
    before_tax = usd * exchange_rate
    gst = before_tax * 0.18
    return InvoiceTotals(usd=usd, before_tax_inr=before_tax, gst_inr=gst, total_inr=before_tax + gst)
