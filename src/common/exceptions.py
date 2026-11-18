"""Application-specific exceptions."""


class BillingAutomationError(Exception):
    """Base exception for expected application failures."""


class WorkbookValidationError(BillingAutomationError):
    """Raised when a selected or exported workbook is invalid."""


class ConfigurationError(BillingAutomationError):
    """Raised when a required configuration value is missing or invalid."""


class PdfGenerationError(BillingAutomationError):
    """Raised when a PDF cannot be produced successfully."""
