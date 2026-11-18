from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from common.models import InvoiceResult
from config.settings import ENV_PATH
from invoice.invoice_counter import build_invoice_number, commit_next_invoice_number, get_invoice_date, get_starting_invoice_number
from pdf.pdf_generator import create_invoice_pdf
from splitter.client_mapping import ClientMapping


def find_matching_client(legal_name: str, clients: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve an invoice recipient by client.json's LinkedAccountId-owned legal name."""
    normalized_legal_name = "".join(character for character in legal_name.lower() if character.isalnum())
    for client in clients:
        normalized_client_name = "".join(character for character in client.get("name", "").lower() if character.isalnum())
        if normalized_legal_name and normalized_legal_name == normalized_client_name:
            return client
    return None


def load_clients(clients_path: Path) -> list[dict[str, Any]]:
    try:
        with clients_path.open("r", encoding="utf-8") as handle:
            clients = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load clients.json: {exc}") from exc
    if not isinstance(clients, list) or not clients:
        raise ValueError("clients.json is empty or not a valid list")
    return clients


class InvoiceGenerator:
    def __init__(self, clients_path: Path, account_mapping: ClientMapping, logger: logging.Logger) -> None:
        self.clients = load_clients(clients_path)
        self.account_mapping = account_mapping
        self.logger = logger

    def generate(
        self,
        excel_files: list[Path],
        excel_account_numbers: dict[Path, str],
        pdf_output_dir: Path,
        exchange_rate: float,
    ) -> InvoiceResult:
        result = InvoiceResult()
        invoice_date = get_invoice_date()
        for excel_path in sorted(excel_files):
            account_number = excel_account_numbers.get(excel_path)
            account_config = self.account_mapping.clients.get(account_number or "", {})
            legal_name = str(account_config.get("legal_name", "")).strip()
            client = find_matching_client(legal_name, self.clients)
            if client is None:
                result.unmatched_files.append(excel_path)
                self.logger.warning(
                    "No clients.json record found for LinkedAccountId %s with legal_name %r; skipped",
                    account_number,
                    legal_name,
                )
                continue

            # The current counter is only committed after this specific PDF is verified.
            counter = get_starting_invoice_number(ENV_PATH)
            invoice_number = build_invoice_number(counter)
            output_path = pdf_output_dir / f"{excel_path.stem}_invoice.pdf"
            try:
                create_invoice_pdf(excel_path, output_path, client, invoice_number, invoice_date, exchange_rate, self.logger)
            except Exception:
                result.failed_files.append(excel_path)
                self.logger.exception("PDF generation failed for %s; invoice counter was not updated", excel_path.name)
                continue

            commit_next_invoice_number(counter + 1, ENV_PATH)
            result.pdf_files.append(output_path)
            self.logger.info("Created %s for account %s (%s) with invoice %s", output_path.name, account_number, client["name"], invoice_number)
        return result
