"""Local AWS billing source interface for the testing phase."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from automation.aws_bill_input import AwsBillInput, load_aws_bill_json


class AwsBillingProvider(ABC):
    @abstractmethod
    def get_bill(self, client_name: str, billing_period: str) -> AwsBillInput: ...


class LocalAwsBillingProvider(AwsBillingProvider):
    def __init__(self, bills_dir: Path) -> None:
        self.bills_dir = bills_dir

    def get_bill(self, client_name: str, billing_period: str) -> AwsBillInput:
        candidates = sorted(self.bills_dir.rglob("aws_bill.json"))
        matches = []
        for candidate in candidates:
            bill = load_aws_bill_json(candidate)
            if bill.client_name.casefold() == client_name.casefold() and bill.billing_period == billing_period:
                matches.append(bill)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one AWS billing JSON for {client_name} / {billing_period}; found {len(matches)}")
        return matches[0]
