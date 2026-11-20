from __future__ import annotations

from datetime import date
from .tracker import InvoiceTracker


class InvoiceNumberAllocator:
    """In-memory sequential allocator seeded from the local tracker.

    Use one allocator for one sequential local test run. In production, replace
    this with an atomic DynamoDB counter for concurrent Lambda executions.
    """

    def __init__(self, last_used_number: int):
        if last_used_number < 0:
            raise ValueError("Last invoice number cannot be negative.")
        self._next = last_used_number + 1

    @classmethod
    def from_tracker(cls, tracker: InvoiceTracker | None = None):
        tracker = tracker or InvoiceTracker.from_settings()
        return cls(tracker.get_last_invoice_number())

    def allocate(self) -> int:
        value = self._next
        self._next += 1
        return value


def format_invoice_id(sequence: int, issue_date: date | None = None) -> str:
    """Format INV{sequence}-{DDMM}-CY{YY}; year follows issue date dynamically."""
    issue_date = issue_date or date.today()
    return (
        f"INV{int(sequence)}-"
        f"{issue_date.strftime('%d%m')}-"
        f"CY{issue_date.year % 100:02d}"
    )
