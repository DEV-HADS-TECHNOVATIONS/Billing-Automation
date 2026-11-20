from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True)
class Settings:
    input_dir: Path
    output_dir: Path
    aws_bills_dir: Path
    tracker_sharepoint_url: str
    tracker_mode: str
    tracker_local_path: Path
    tracker_sheet_name: str | None
    tracker_invoice_column: str
    reconciliation_tolerance_usd: str
    manual_review_dir: Path

    @property
    def project_client_mapping(self) -> Path:
        return PROJECT_ROOT / "config" / "client.json"

    @property
    def project_invoice_clients(self) -> Path:
        return PROJECT_ROOT / "config" / "clients.json"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            input_dir=resolve_project_path(os.getenv("INPUT_DIR", "./input")),
            output_dir=resolve_project_path(os.getenv("OUTPUT_DIR", "./output")),
            aws_bills_dir=resolve_project_path(os.getenv("AWS_BILLS_DIR", "./input/aws_bills")),
            tracker_sharepoint_url=os.getenv("TRACKER_SHAREPOINT_URL", "").strip(),
            tracker_mode=os.getenv("TRACKER_MODE", "local").strip().lower(),
            tracker_local_path=resolve_project_path(
                os.getenv("TRACKER_LOCAL_PATH", "./input/Invoice tracker.xlsx")
            ),
            tracker_sheet_name=os.getenv("TRACKER_SHEET_NAME", "").strip() or None,
            tracker_invoice_column=os.getenv("TRACKER_INVOICE_COLUMN", "E").strip().upper(),
            reconciliation_tolerance_usd=os.getenv(
                "RECONCILIATION_TOLERANCE_USD", "5.00"
            ).strip(),
            manual_review_dir=resolve_project_path(
                os.getenv("MANUAL_REVIEW_DIR", "./output/manual_review")
            ),
        )
