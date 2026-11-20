class AutomationError(RuntimeError):
    """Base exception for automation helpers."""


class TrackerAccessError(AutomationError):
    """The invoice tracker cannot be accessed or parsed."""


class ClientMatchError(AutomationError):
    """No unique client could be identified from an Excel filename."""


class ExchangeRateError(AutomationError):
    """The Excel report does not contain one valid exchange rate."""


class AwsBillInputError(AutomationError):
    """AWS bill reference data is missing or does not match the job."""
