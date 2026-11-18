from datetime import datetime

from invoice.invoice_counter import build_invoice_number, commit_next_invoice_number, get_starting_invoice_number


def test_counter_is_only_changed_when_commit_is_called(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("INVOICE_NUMBER=1\n", encoding="utf-8")

    assert build_invoice_number(get_starting_invoice_number(env_path), datetime(2026, 8, 4)) == "INV1-0408-CY26"
    assert "INVOICE_NUMBER=1" in env_path.read_text(encoding="utf-8")
    commit_next_invoice_number(2, env_path)
    assert "INVOICE_NUMBER=2" in env_path.read_text(encoding="utf-8")
