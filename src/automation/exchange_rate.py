from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from openpyxl import load_workbook

from .errors import ExchangeRateError


def read_exchange_rate(excel_path: str | Path,
                       header_name: str = "EXCHANGERATE",
                       header_scan_rows: int = 30) -> Decimal:
    """Read the unique positive rate from the column headed EXCHANGERATE.

    Header is found by name rather than hardcoded column AA. All populated
    values below it must agree to 5 decimal places; otherwise fail safely.
    """
    path = Path(excel_path)
    if not path.is_file():
        raise ExchangeRateError(f"Excel report not found: {path}")

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ExchangeRateError(f"Cannot open Excel report: {exc}") from exc

    try:
        ws = wb.active
        target = header_name.strip().casefold()
        header_row = None
        rate_col = None

        for row_idx, row in enumerate(
            ws.iter_rows(min_row=1, max_row=min(header_scan_rows, ws.max_row),
                         values_only=True), start=1
        ):
            for col_idx, value in enumerate(row, start=1):
                if value is not None and str(value).strip().casefold() == target:
                    header_row, rate_col = row_idx, col_idx
                    break
            if rate_col:
                break

        if rate_col is None:
            raise ExchangeRateError(
                f"Column '{header_name}' was not found in the first "
                f"{header_scan_rows} rows of {path.name}."
            )

        rates: set[Decimal] = set()
        for row in ws.iter_rows(min_row=header_row + 1, min_col=rate_col,
                                max_col=rate_col, values_only=True):
            value = row[0]
            if value is None or str(value).strip() == "":
                continue
            try:
                rate = Decimal(str(value).strip()).quantize(Decimal("0.00001"))
            except (InvalidOperation, ValueError):
                raise ExchangeRateError(
                    f"Invalid exchange-rate value '{value}' in {path.name}."
                )
            if rate <= 0:
                raise ExchangeRateError("Exchange rate must be greater than zero.")
            rates.add(rate)

        if not rates:
            raise ExchangeRateError(f"No exchange-rate values found in {path.name}.")
        if len(rates) != 1:
            values = ", ".join(str(v) for v in sorted(rates))
            raise ExchangeRateError(
                f"Inconsistent EXCHANGERATE values in {path.name}: {values}. "
                "Manual validation is required."
            )
        return next(iter(rates))
    finally:
        wb.close()
