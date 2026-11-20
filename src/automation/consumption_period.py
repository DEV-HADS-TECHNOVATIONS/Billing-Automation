from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
import pandas as pd

from invoice.invoice_calculator import prepare_invoice_data


def consumption_period(dataframe: pd.DataFrame) -> tuple[date, date]:
    _, columns = prepare_invoice_data(dataframe)
    values = pd.to_datetime(dataframe[columns.billing_period_start].dropna(), errors="coerce").dropna()
    if values.empty:
        raise ValueError("Consumption billing period is missing")
    start = values.iloc[0].date().replace(day=1)
    end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
    return start, end
