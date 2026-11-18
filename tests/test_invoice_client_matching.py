from invoice.invoice_generator import find_matching_client


def test_invoice_client_match_uses_legal_name_not_filename():
    clients = [
        {"name": "RODEO DIGITAL"},
        {"name": "ASTRAVUE TECHNOLOGIES PVT LTD"},
    ]

    assert find_matching_client("RODEO DIGITAL", clients) == {"name": "RODEO DIGITAL"}
    assert find_matching_client("Rodeo Digital - July'26.xlsx", clients) is None
