from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook, load_workbook

from common.exceptions import WorkbookValidationError

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def normalize_column_name(column_name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(column_name).strip().lower())


def find_normalized_column(dataframe: pd.DataFrame, expected_name: str) -> str:
    columns = {normalize_column_name(column): column for column in dataframe.columns}
    target = normalize_column_name(expected_name)
    if target not in columns:
        raise WorkbookValidationError(f"Missing {expected_name} column")
    return str(columns[target])


def find_linked_account_id_column(dataframe: pd.DataFrame) -> str:
    """Return the application's only supported client identifier column."""
    return find_normalized_column(dataframe, "LinkedAccountId")


def load_consumption_workbook(workbook_path: Path) -> tuple[pd.DataFrame, str]:
    """Return the first populated sheet containing a supported AWS account-number column."""
    engine = "xlrd" if workbook_path.suffix.lower() == ".xls" else "openpyxl"
    try:
        with pd.ExcelFile(workbook_path, engine=engine) as excel_file:
            for sheet_name in excel_file.sheet_names:
                dataframe = pd.read_excel(excel_file, sheet_name=sheet_name)
                if dataframe.empty:
                    continue
                try:
                    find_linked_account_id_column(dataframe)
                    return dataframe, str(sheet_name)
                except WorkbookValidationError:
                    continue
    except Exception as exc:
        raise WorkbookValidationError(f"Workbook could not be opened: {exc}") from exc

    raise WorkbookValidationError("Missing LinkedAccountId column")


def sanitize_filename(value: str) -> str:
    return INVALID_FILENAME_CHARS.sub("_", value.strip()) or "Unknown"


def write_dataframe_to_workbook(dataframe: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    try:
        worksheet = workbook.active
        for column_index, column_name in enumerate(dataframe.columns, start=1):
            worksheet.cell(row=1, column=column_index, value=column_name)
        for row_index, row_values in enumerate(dataframe.itertuples(index=False, name=None), start=2):
            for column_index, value in enumerate(row_values, start=1):
                worksheet.cell(row=row_index, column=column_index, value=value)
        workbook.save(output_path)
    finally:
        workbook.close()


def validate_exported_workbook(output_path: Path, expected_rows: int) -> int:
    """Reopen an export and ensure it has exactly the expected data rows."""
    try:
        workbook = load_workbook(output_path, read_only=True, data_only=False)
        try:
            row_count = sum(1 for _ in workbook.active.iter_rows(min_row=2, values_only=True))
        finally:
            workbook.close()
    except Exception as exc:
        raise WorkbookValidationError(f"Unable to validate {output_path.name}: {exc}") from exc

    if row_count != expected_rows:
        raise WorkbookValidationError(
            f"Export validation failed for {output_path.name}: expected {expected_rows} rows, found {row_count}"
        )
    return row_count
