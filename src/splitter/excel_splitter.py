from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta

from common.excel_io import (
    find_linked_account_id_column,
    find_normalized_column,
    sanitize_filename,
    validate_exported_workbook,
    write_dataframe_to_workbook,
)
from common.exceptions import WorkbookValidationError
from common.models import SplitResult
from splitter.client_mapping import ClientMapping


class ExcelSplitter:
    """Split one AWS consumption report by AWS account number."""

    @staticmethod
    def find_linked_account_id_column(dataframe: pd.DataFrame) -> str:
        return find_linked_account_id_column(dataframe)

    @staticmethod
    def find_billing_period_column(dataframe: pd.DataFrame) -> str:
        return find_normalized_column(dataframe, "BillingPeriodStartDate")

    def infer_billing_period_start(self, dataframe: pd.DataFrame) -> pd.Timestamp:
        billing_column = self.find_billing_period_column(dataframe)
        for value in dataframe[billing_column].dropna():
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return pd.Timestamp(parsed)
        raise WorkbookValidationError("Billing Period could not be determined")

    def billing_month(self, dataframe: pd.DataFrame) -> str:
        return self.infer_billing_period_start(dataframe).strftime("%B'%y")

    def filename_month(self, dataframe: pd.DataFrame) -> str:
        return (self.infer_billing_period_start(dataframe) + relativedelta(months=1)).strftime("%B'%y")

    @staticmethod
    def clean_linked_account_id(value: Any) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    def discover_accounts(self, dataframe: pd.DataFrame) -> list[str]:
        account_column = self.find_linked_account_id_column(dataframe)
        return sorted({self.clean_linked_account_id(value) for value in dataframe[account_column] if self.clean_linked_account_id(value)})

    def split(
        self,
        dataframe: pd.DataFrame,
        mapping: ClientMapping,
        excel_output_dir: Path,
        logger: logging.Logger,
    ) -> SplitResult:
        account_column = self.find_linked_account_id_column(dataframe)
        dataframe = dataframe.copy()
        dataframe[account_column] = dataframe[account_column].apply(self.clean_linked_account_id)
        accounts = self.discover_accounts(dataframe)
        new_clients = mapping.ensure_clients(accounts)
        filename_month = self.filename_month(dataframe)

        result = SplitResult(
            billing_month=self.billing_month(dataframe),
            new_clients=new_clients,
            total_rows=len(dataframe),
        )
        logger.info("AWS account numbers found: %s", len(accounts))
        for account_number in accounts:
            client_config = mapping.clients.get(account_number, {})
            if not client_config.get("active", True):
                result.skipped_clients += 1
                logger.info("Skipped account %s because active=false", account_number)
                continue

            display_name = str(client_config.get("display_name", account_number)).strip()
            output_path = excel_output_dir / f"{sanitize_filename(display_name)} - {filename_month}.xlsx"
            client_rows = dataframe.loc[dataframe[account_column] == account_number].copy()
            if client_rows.empty:
                continue

            write_dataframe_to_workbook(client_rows, output_path)
            validate_exported_workbook(output_path, len(client_rows))
            result.excel_files.append(output_path)
            result.excel_account_numbers[output_path] = account_number
            logger.info("Validated %s rows in %s", len(client_rows), output_path.name)

        return result
