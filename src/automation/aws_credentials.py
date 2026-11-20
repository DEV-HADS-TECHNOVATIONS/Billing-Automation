from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AwsCredentials:
    profile: str
    linked_account_id: str
    expected_identity_account_id: str
    billing_mode: str
    access_key_id: str
    secret_access_key: str
    session_token: str | None
    region: str
    ce_region: str


def get_aws_credentials(account_id: str, client: dict) -> AwsCredentials:
    profile = str(client.get("aws_credential_profile", "")).strip().upper()
    if not profile:
        raise ValueError(f"Client {account_id} is missing aws_credential_profile")
    prefix = f"AWS_{profile}_"
    access_key, secret = os.getenv(prefix + "ACCESS_KEY_ID", "").strip(), os.getenv(prefix + "SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret:
        raise ValueError(f"AWS credentials are missing for profile {profile}; set {prefix}ACCESS_KEY_ID and {prefix}SECRET_ACCESS_KEY")
    mode = str(client.get("aws_billing_mode", "direct")).lower()
    if mode not in {"direct", "payer"}:
        raise ValueError(f"Client {account_id} has invalid aws_billing_mode; use direct or payer")
    expected = str(client.get("aws_credential_owner_account_id", "")).strip()
    if not expected:
        if mode == "payer":
            raise ValueError(f"Client {account_id} requires aws_credential_owner_account_id for payer credentials")
        expected = str(account_id)
    return AwsCredentials(profile, str(account_id), expected, mode, access_key, secret, os.getenv(prefix + "SESSION_TOKEN") or None,
                          os.getenv(prefix + "REGION", "ap-south-1"), os.getenv(prefix + "CE_REGION", "us-east-1"))


def create_session(credentials: AwsCredentials):
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for AWS Cost Explorer. Install requirements.txt.") from exc
    return boto3.Session(aws_access_key_id=credentials.access_key_id, aws_secret_access_key=credentials.secret_access_key,
                         aws_session_token=credentials.session_token, region_name=credentials.region)
