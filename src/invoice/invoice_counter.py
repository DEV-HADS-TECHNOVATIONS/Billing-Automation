from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv, set_key

from common.exceptions import ConfigurationError


def get_starting_invoice_number(env_path: Path) -> int:
    load_dotenv(env_path, override=True)
    raw_value = os.getenv("INVOICE_NUMBER")
    if raw_value is None or not raw_value.strip():
        raise ConfigurationError("INVOICE_NUMBER is missing from .env")
    try:
        counter = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError("INVOICE_NUMBER in .env must be a positive integer") from exc
    if counter <= 0:
        raise ConfigurationError("INVOICE_NUMBER in .env must be a positive integer")
    return counter


def build_invoice_number(counter: int, now: datetime | None = None) -> str:
    timestamp = now or datetime.now()
    return f"INV{counter}-{timestamp.strftime('%d%m')}-CY{timestamp.strftime('%y')}"


def get_invoice_date(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%d-%b-%Y")


def commit_next_invoice_number(next_counter: int, env_path: Path) -> None:
    """Persist the next counter only after a PDF was generated successfully."""
    env_path.touch(exist_ok=True)
    set_key(env_path, "INVOICE_NUMBER", str(next_counter))
    content = env_path.read_text(encoding="utf-8")
    env_path.write_text(content.replace(f"'{next_counter}'", str(next_counter)), encoding="utf-8")
