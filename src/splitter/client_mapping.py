from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ClientMapping:
    """Manages AWS account-number configuration and invoice identity metadata."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.clients: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            self.clients = {}
            return
        with self.config_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        self.clients = value if isinstance(value, dict) else {}

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(self.clients, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    def ensure_clients(self, account_numbers: list[str]) -> list[str]:
        self.load()
        new_clients: list[str] = []
        for account_number in account_numbers:
            if account_number not in self.clients:
                self.clients[account_number] = {
                    "display_name": "Unknown",
                    "legal_name": "Unknown",
                    "active": True,
                }
                new_clients.append(account_number)
        self.save()
        return new_clients
