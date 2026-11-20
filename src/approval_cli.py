from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from automation.manual_review import record_local_decision
from automation.settings import PROJECT_ROOT, Settings


def _review_file(review_id: str, review_dir: Path) -> Path:
    matches = list(review_dir.glob(f"review_{review_id}.json"))
    if len(matches) != 1:
        raise ValueError(f"Review '{review_id}' was not found in {review_dir}")
    return matches[0]


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Local manual-review approval tool")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for action in ("approve", "reject"):
        command = sub.add_parser(action)
        command.add_argument("review_id")
        command.add_argument("--reviewer", required=True)
        command.add_argument("--comment", default="")
    args = parser.parse_args()
    directory = Settings.from_env().manual_review_dir
    if args.command == "list":
        for path in sorted(directory.glob("review_*.json")):
            print(path.read_text(encoding="utf-8"))
        return 0
    allowed = {item.strip().casefold() for item in os.getenv("AUTHORIZED_REVIEWERS", "").split(",") if item.strip()}
    if not allowed or args.reviewer.casefold() not in allowed:
        raise ValueError("Reviewer is not in AUTHORIZED_REVIEWERS.")
    decision = "APPROVED" if args.command == "approve" else "REJECTED"
    record_local_decision(_review_file(args.review_id, directory), decision, args.reviewer, args.comment)
    print(f"{args.command.title()}d {args.review_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
