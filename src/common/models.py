from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class OutputFolders:
    billing_month: str
    root: Path
    excels: Path
    pdfs: Path
    logs: Path


@dataclass
class SplitResult:
    billing_month: str
    excel_files: list[Path] = field(default_factory=list)
    excel_account_numbers: dict[Path, str] = field(default_factory=dict)
    skipped_clients: int = 0
    new_clients: list[str] = field(default_factory=list)
    total_rows: int = 0


@dataclass
class InvoiceResult:
    pdf_files: list[Path] = field(default_factory=list)
    unmatched_files: list[Path] = field(default_factory=list)
    failed_files: list[Path] = field(default_factory=list)
