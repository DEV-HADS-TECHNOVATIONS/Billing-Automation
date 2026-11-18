from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(log_file: Path) -> logging.Logger:
    """Configure the application logger for the selected billing-month run."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("aws_billing_automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
