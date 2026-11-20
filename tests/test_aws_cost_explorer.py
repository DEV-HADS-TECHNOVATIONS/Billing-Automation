from datetime import date
from decimal import Decimal

import pytest

from automation.aws_credentials import AwsCredentials, get_aws_credentials
from integrations.aws_cost_explorer import aggregate_unblended_cost, fetch_cost_explorer, save_cost_response


def test_profile_specific_credentials_and_blank_token(monkeypatch):
    monkeypatch.setenv("AWS_HADS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_HADS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_HADS_SESSION_TOKEN", "")
    credentials = get_aws_credentials("130", {"aws_credential_profile": "HADS", "aws_billing_mode": "direct"})
    assert credentials.profile == "HADS" and credentials.session_token is None


def test_payer_request_uses_linked_account_filter(monkeypatch):
    calls = {}
    class Client:
        def __init__(self, name): self.name = name
        def get_caller_identity(self): return {"Account": "999"}
        def get_cost_and_usage(self, **kwargs): calls.update(kwargs); return {"ResultsByTime": [{"Groups": [{"Metrics": {"UnblendedCost": {"Amount": "2.50", "Unit": "USD"}}}]}]}
    class Session:
        def client(self, name, **kwargs): return Client(name)
    monkeypatch.setattr("integrations.aws_cost_explorer.create_session", lambda _: Session())
    credentials = AwsCredentials("HADS", "130", "999", "payer", "id", "secret", None, "ap-south-1", "us-east-1")
    response, owner = fetch_cost_explorer(credentials, date(2026, 12, 1), date(2027, 1, 1))
    assert owner == "999" and calls["Filter"]["Dimensions"]["Values"] == ["130"]
    assert aggregate_unblended_cost(response) == Decimal("2.50")


def test_empty_response_and_json_collision_are_safe(tmp_path):
    with pytest.raises(ValueError): aggregate_unblended_cost({})
    response = {"ResultsByTime": [{"Groups": [{"Metrics": {"UnblendedCost": {"Amount": "1", "Unit": "USD"}}}]}]}
    first = save_cost_response(response, tmp_path, date(2026, 10, 1), "HADS", linked_account_id="130", credential_owner_account_id="999")
    second = save_cost_response(response, tmp_path, date(2026, 10, 1), "HADS", linked_account_id="130", credential_owner_account_id="999")
    assert first != second and first.exists() and second.exists()
