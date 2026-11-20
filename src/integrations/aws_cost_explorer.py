from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from automation.aws_credentials import AwsCredentials, create_session


def aggregate_unblended_cost(response: dict) -> Decimal:
    if not response.get("ResultsByTime"):
        raise ValueError("Cost Explorer returned no monthly billing data")
    total = Decimal("0")
    for period in response.get("ResultsByTime", []):
        for group in period.get("Groups", []):
            metric = group.get("Metrics", {}).get("UnblendedCost", {})
            if metric.get("Unit") not in {None, "USD"}:
                raise ValueError(f"Cost Explorer currency must be USD, got {metric.get('Unit')}")
            total += Decimal(str(metric["Amount"]))
    return total


def fetch_cost_explorer(credentials: AwsCredentials, start, end) -> dict:
    session = create_session(credentials)
    identity = session.client("sts", region_name=credentials.region).get_caller_identity()
    if str(identity.get("Account")) != credentials.expected_identity_account_id:
        raise ValueError(f"STS account mismatch for {credentials.profile}; configured credential owner {credentials.expected_identity_account_id}, received {identity.get('Account')}")
    request = dict(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()}, Granularity="MONTHLY",
        Metrics=["UnblendedCost"], GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])
    if credentials.billing_mode == "payer":
        request["Filter"] = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [credentials.linked_account_id]}}
    return session.client("ce", region_name=credentials.ce_region).get_cost_and_usage(**request), str(identity["Account"])


def save_cost_response(response: dict, output_dir: Path, start, profile: str, *, linked_account_id: str, credential_owner_account_id: str) -> Path:
    folder = output_dir / "aws_bills" / str(start.year) / start.strftime("%B") / profile
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / "aws_cost_explorer.json"
    if raw.exists():
        index = 2
        while (folder / f"aws_cost_explorer_{index}.json").exists(): index += 1
        raw = folder / f"aws_cost_explorer_{index}.json"
    raw.write_text(json.dumps(response, indent=2, default=str), encoding="utf-8")
    (raw.with_name(raw.stem + "_summary.json")).write_text(json.dumps({"linked_account_id": linked_account_id, "credential_owner_account_id": credential_owner_account_id, "billing_period": f"{start:%Y-%m}", "unblended_cost_usd": str(aggregate_unblended_cost(response)), "currency": "USD"}, indent=2), encoding="utf-8")
    return raw
