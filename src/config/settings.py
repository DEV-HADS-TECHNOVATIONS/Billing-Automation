from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from common.exceptions import ConfigurationError
from common.models import OutputFolders

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_DIR = PROJECT_ROOT / "config"
CLIENT_MAPPING_PATH = CONFIG_DIR / "client.json"
INVOICE_CLIENTS_PATH = CONFIG_DIR / "clients.json"
ENV_PATH = PROJECT_ROOT / ".env"
ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = PROJECT_ROOT / "fonts"
SUPPORTED_EXCEL_EXTENSIONS = {".xlsx", ".xls"}


def load_and_validate_environment() -> tuple[float, int]:
    """Load `.env` and validate the values required for a billing run."""
    load_dotenv(ENV_PATH, override=True)

    raw_rate = os.getenv("USD_TO_INR")
    if raw_rate is None or not raw_rate.strip():
        raise ConfigurationError("USD_TO_INR is missing from .env")
    try:
        exchange_rate = float(raw_rate)
    except ValueError as exc:
        raise ConfigurationError("USD_TO_INR in .env must be a positive number") from exc
    if exchange_rate <= 0:
        raise ConfigurationError("USD_TO_INR in .env must be a positive number")

    raw_counter = os.getenv("INVOICE_NUMBER")
    if raw_counter is None or not raw_counter.strip():
        raise ConfigurationError("INVOICE_NUMBER is missing from .env")
    try:
        invoice_number = int(raw_counter)
    except ValueError as exc:
        raise ConfigurationError("INVOICE_NUMBER in .env must be a positive integer") from exc
    if invoice_number <= 0:
        raise ConfigurationError("INVOICE_NUMBER in .env must be a positive integer")

    return exchange_rate, invoice_number


def create_output_folders(billing_month: str) -> OutputFolders:
    root = OUTPUT_DIR / billing_month
    folders = OutputFolders(
        billing_month=billing_month,
        root=root,
        excels=root / "01_Excels",
        pdfs=root / "02_PDFs",
        logs=root / "03_Logs",
    )
    for folder in (folders.excels, folders.pdfs, folders.logs):
        folder.mkdir(parents=True, exist_ok=True)
    return folders
