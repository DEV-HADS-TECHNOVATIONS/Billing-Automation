from __future__ import annotations

import re
import shutil
from copy import copy
from datetime import date
from pathlib import Path
from openpyxl import load_workbook

from .errors import TrackerAccessError
from .settings import Settings

INVOICE_NUMBER_PATTERN = re.compile(
    r"(?i)(?:^|[^A-Z0-9])INV\s*0*(\d+)(?:-|$)"
)


class InvoiceTracker:
    """Read-only local tracker adapter for the testing phase.

    Uses a locally synced/downloaded .xlsx copy. Microsoft Graph will replace
    this adapter later while preserving its public interface.
    """

    def __init__(self, path: Path, sheet_name: str | None = None, column: str = "E"):
        self.path = Path(path)
        self.sheet_name = sheet_name
        self.column = column.upper()

    @classmethod
    def from_settings(cls, settings: Settings | None = None):
        settings = settings or Settings.from_env()
        if settings.tracker_mode != "local":
            raise TrackerAccessError(
                "Only TRACKER_MODE=local is available in this testing package. "
                "Microsoft Graph access will be implemented in the next phase."
            )
        return cls(settings.tracker_local_path, settings.tracker_sheet_name,
                   settings.tracker_invoice_column)

    def _open_sheet(self):
        if not self.path.is_file():
            raise TrackerAccessError(
                f"Local tracker workbook not found: {self.path}. "
                "Sync/download the SharePoint workbook and set TRACKER_LOCAL_PATH."
            )
        try:
            wb = load_workbook(self.path, read_only=True, data_only=True)
        except Exception as exc:
            raise TrackerAccessError(f"Unable to open tracker workbook: {exc}") from exc
        if self.sheet_name:
            if self.sheet_name not in wb.sheetnames:
                wb.close()
                raise TrackerAccessError(f"Worksheet '{self.sheet_name}' does not exist.")
            ws = wb[self.sheet_name]
        else:
            ws = wb.active
        return wb, ws

    def get_last_invoice_number(self) -> int:
        wb, ws = self._open_sheet()
        try:
            col_index = ws[f"{self.column}1"].column
            found: list[int] = []
            for row in ws.iter_rows(
                min_row=1, min_col=col_index, max_col=col_index, values_only=True
            ):
                value = row[0]
                if value is None:
                    continue
                match = INVOICE_NUMBER_PATTERN.search(str(value).strip())
                if match:
                    found.append(int(match.group(1)))
            if not found:
                raise TrackerAccessError(
                    f"No invoice numbers were found in tracker column {self.column}."
                )
            return max(found)
        finally:
            wb.close()

    def get_next_invoice_number(self) -> int:
        return self.get_last_invoice_number() + 1

    def update_final_invoice(self, *, client_name: str, consumption_start: date,
                             invoice_number: str, exchange_rate, invoice_date: date,
                             before_gst, gst, total) -> int:
        """Safely write final invoice values while preserving accounting columns."""
        if not self.path.is_file():
            raise TrackerAccessError(f"Local tracker workbook not found: {self.path}")
        workbook = load_workbook(self.path, data_only=False)
        worksheet = workbook[self.sheet_name] if self.sheet_name else workbook.active
        header_row, headers = self._headers(worksheet)
        required = {"billingmonth", "consumptionmonth", "endcustomer", "invoicenumber", "usd", "invoicedate", "amount", "gst18", "inovicetotal"}
        missing = required - set(headers)
        if missing:
            raise TrackerAccessError(f"Tracker is missing required headers: {sorted(missing)}")
        consumption = consumption_start.strftime("%B")
        billing = (date(consumption_start.year + (consumption_start.month == 12), 1 if consumption_start.month == 12 else consumption_start.month + 1, 1)).strftime("%B").upper()
        row = self._find_row(worksheet, header_row, headers, client_name, consumption, invoice_number)
        if row is None:
            row = worksheet.max_row + 1
            template = worksheet.max_row
            for col in range(1, worksheet.max_column + 1):
                source, target = worksheet.cell(template, col), worksheet.cell(row, col)
                if source.has_style:
                    target._style = copy(source._style)
                    target.number_format = source.number_format
        backup = self.path.with_name(self.path.stem + ".backup.xlsx")
        if not backup.exists(): shutil.copy2(self.path, backup)
        values = {"billingmonth": billing, "consumptionmonth": consumption, "endcustomer": client_name,
                  "invoicenumber": invoice_number, "invoicedate": invoice_date,
                  "amount": float(before_gst), "gst18": float(gst), "inovicetotal": float(total)}
        if exchange_rate not in (None, ""):
            values["usd"] = float(exchange_rate)
        for key, value in values.items(): worksheet.cell(row, headers[key], value)
        workbook.save(self.path)
        workbook.close()
        verify = load_workbook(self.path, read_only=True, data_only=False)
        try:
            sheet = verify[self.sheet_name] if self.sheet_name else verify.active
            if str(sheet.cell(row, headers["invoicenumber"]).value).strip() != invoice_number:
                raise TrackerAccessError("Tracker verification failed: invoice number was not saved")
        finally:
            verify.close()
        return row

    def record_credit_note(self, *, client_name: str, original_invoice_number: str,
                           credit_note_number: str) -> int:
        """Record one credit note against its existing original-invoice row.

        The supplied tracker has no credit-note field, so the first unused
        column (R) is labelled once as ``Credit Note Number``.  Existing rows,
        formulas and payment columns are untouched.
        """
        if not self.path.is_file():
            raise TrackerAccessError(f"Local tracker workbook not found: {self.path}")
        workbook = load_workbook(self.path, data_only=False)
        worksheet = workbook[self.sheet_name] if self.sheet_name else workbook.active
        header_row, headers = self._headers(worksheet)
        invoice_col, client_col = headers["invoicenumber"], headers["endcustomer"]
        credit_col = headers.get("creditnotenumber")
        if credit_col is None:
            # Use the first column after the real header set.  The shipped
            # tracker has an empty R column even though openpyxl reports it in
            # max_column, so worksheet.max_column + 1 would wrongly skip R.
            credit_col = max(headers.values()) + 1
            worksheet.cell(header_row, credit_col, "Credit Note Number")
            source = worksheet.cell(header_row, invoice_col)
            if source.has_style:
                worksheet.cell(header_row, credit_col)._style = copy(source._style)
        matched_row = None
        for row in range(header_row + 1, worksheet.max_row + 1):
            if self._normal(worksheet.cell(row, invoice_col).value) == self._normal(original_invoice_number):
                if self._normal(worksheet.cell(row, client_col).value) != self._normal(client_name):
                    raise TrackerAccessError("Original invoice belongs to a different tracker client")
                matched_row = row
                break
        if matched_row is None:
            raise TrackerAccessError(f"Original invoice {original_invoice_number} was not found in the tracker")
        existing = str(worksheet.cell(matched_row, credit_col).value or "").strip()
        if existing and self._normal(existing) != self._normal(credit_note_number):
            raise TrackerAccessError(f"Tracker row {matched_row} already records credit note {existing}")
        backup = self.path.with_name(self.path.stem + ".backup.xlsx")
        if not backup.exists(): shutil.copy2(self.path, backup)
        worksheet.cell(matched_row, credit_col, credit_note_number)
        workbook.save(self.path); workbook.close()
        verify = load_workbook(self.path, read_only=True, data_only=False)
        try:
            sheet = verify[self.sheet_name] if self.sheet_name else verify.active
            if str(sheet.cell(matched_row, credit_col).value).strip() != credit_note_number:
                raise TrackerAccessError("Credit note tracker verification failed")
        finally:
            verify.close()
        return matched_row

    @staticmethod
    def _normal(value) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def _headers(self, worksheet):
        for row in range(1, min(worksheet.max_row, 30) + 1):
            found = {}
            for col in range(1, worksheet.max_column + 1):
                key = self._normal(worksheet.cell(row, col).value)
                if key and key not in found:
                    found[key] = col
            if {"billingmonth", "consumptionmonth", "endcustomer", "invoicenumber"} <= set(found): return row, found
        raise TrackerAccessError("Tracker header row could not be identified")

    def _find_row(self, worksheet, header_row, headers, client_name, consumption, invoice_number):
        client = self._normal(client_name)
        for row in range(header_row + 1, worksheet.max_row + 1):
            if self._normal(worksheet.cell(row, headers["invoicenumber"]).value) == self._normal(invoice_number): return row
            if self._normal(worksheet.cell(row, headers["endcustomer"]).value) == client and self._normal(worksheet.cell(row, headers["consumptionmonth"]).value) == self._normal(consumption): return row
        return None
