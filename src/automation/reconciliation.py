from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")


def _money(value) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid USD amount: {value!r}") from exc
    return result


@dataclass(frozen=True)
class ReconciliationResult:
    aws_amount_usd: Decimal
    excel_amount_usd: Decimal
    difference_usd: Decimal
    tolerance_usd: Decimal
    status: str

    @property
    def passed(self) -> bool:
        return self.status == "AUTO_APPROVED"

    def to_dict(self):
        return {k: str(v) for k, v in asdict(self).items()} | {"passed": self.passed}


def reconcile(aws_amount_usd, excel_amount_usd, tolerance_usd="5.00"):
    aws_amount = _money(aws_amount_usd)
    excel_amount = _money(excel_amount_usd)
    tolerance = _money(tolerance_usd)
    if tolerance < 0:
        raise ValueError("Reconciliation tolerance cannot be negative.")
    difference = (aws_amount - excel_amount).quantize(CENT)
    status = "AUTO_APPROVED" if abs(difference) <= tolerance else "MANUAL_REVIEW_REQUIRED"
    return ReconciliationResult(
        aws_amount, excel_amount, difference, tolerance, status
    )
