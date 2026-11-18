from __future__ import annotations

import logging

import pandas as pd

from splitter.client_mapping import ClientMapping
from splitter.excel_splitter import ExcelSplitter
from common.exceptions import WorkbookValidationError


def test_split_validates_exports_and_uses_display_name(tmp_path):
    dataframe = pd.DataFrame({
        "BillingPeriodStartDate": ["2026-06-01"],
        "LinkedAccountId": ["115690512010"],
        "Actual Cost": [10],
    })
    mapping_path = tmp_path / "client.json"
    mapping_path.write_text('{"115690512010": {"legal_name": "RODEO DIGITAL", "display_name": "Rodeo Digital", "active": true}}', encoding="utf-8")
    logger = logging.getLogger("test_split")
    result = ExcelSplitter().split(dataframe, ClientMapping(mapping_path), tmp_path / "01_Excels", logger)

    assert result.billing_month == "June'26"
    assert result.skipped_clients == 0
    assert result.excel_files == [tmp_path / "01_Excels" / "Rodeo Digital - July'26.xlsx"]
    assert result.excel_files[0].exists()


def test_split_skips_inactive_client(tmp_path):
    dataframe = pd.DataFrame({"BillingPeriodStartDate": ["2026-06-01"], "LinkedAccountId": ["130677210002"]})
    mapping_path = tmp_path / "client.json"
    mapping_path.write_text('{"130677210002": {"legal_name": "HADS TECHNOVATIONS LLP", "display_name": "CloudOps", "active": false}}', encoding="utf-8")
    result = ExcelSplitter().split(dataframe, ClientMapping(mapping_path), tmp_path, logging.getLogger("test_skip"))

    assert result.excel_files == []
    assert result.skipped_clients == 1


def test_split_auto_adds_account_number_with_unknown_defaults(tmp_path):
    dataframe = pd.DataFrame({
        "BillingPeriodStartDate": ["2026-06-01"],
        "LinkedAccountId": [999999999999],
    })
    mapping_path = tmp_path / "client.json"
    result = ExcelSplitter().split(dataframe, ClientMapping(mapping_path), tmp_path, logging.getLogger("test_add"))
    mapping = ClientMapping(mapping_path)

    assert result.new_clients == ["999999999999"]
    assert mapping.clients["999999999999"] == {
        "legal_name": "Unknown",
        "display_name": "Unknown",
        "active": True,
    }


def test_split_rejects_payer_account_id_without_linked_account_id(tmp_path):
    dataframe = pd.DataFrame({"BillingPeriodStartDate": ["2026-06-01"], "PayerAccountId": ["130677210002"]})
    try:
        ExcelSplitter().split(dataframe, ClientMapping(tmp_path / "client.json"), tmp_path, logging.getLogger("test_no_fallback"))
    except WorkbookValidationError as exc:
        assert "LinkedAccountId" in str(exc)
    else:
        raise AssertionError("PayerAccountId must not be accepted as a client identifier")
