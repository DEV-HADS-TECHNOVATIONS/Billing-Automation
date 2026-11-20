from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def create_pending_review(*, review_dir: str | Path, client_name: str,
                          billing_period: str, excel_filename: str,
                          aws_source_document: str | None,
                          reconciliation: dict, account_id: str | None = None,
                          draft_invoice: str | None = None) -> Path:
    folder = Path(review_dir)
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "review_id": str(uuid4()),
        "status": "PENDING",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_name": client_name,
        "linked_aws_account_id": account_id,
        "billing_period": billing_period,
        "excel_filename": excel_filename,
        "aws_source_document": aws_source_document,
        "draft_invoice": draft_invoice,
        "reconciliation": reconciliation,
        "reviewed_by": None,
        "reviewed_at_utc": None,
        "review_comment": None
    }
    path = folder / f"review_{record['review_id']}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def record_local_decision(review_path: str | Path, decision: str,
                          reviewer: str, comment: str = "") -> None:
    """Testing-only approval. Not an authenticated production approval channel."""
    path = Path(review_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    decision = decision.strip().upper()
    if record.get("status") != "PENDING":
        raise ValueError("Only PENDING review records can be decided.")
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("Decision must be APPROVED or REJECTED.")
    if not reviewer.strip():
        raise ValueError("Reviewer identity is required.")
    record.update({
        "status": decision,
        "reviewed_by": reviewer.strip(),
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_comment": comment.strip()
    })
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
