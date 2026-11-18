from datetime import datetime

import pandas as pd

from invoice.invoice_calculator import calculate_due_date, calculate_totals, get_region_from_usage_type, prepare_invoice_data


def test_due_date_is_tenth_of_next_month():
    assert calculate_due_date(datetime(2026, 12, 31)) == "10-Jan-2027"


def test_credit_is_consolidated_before_usd_and_gst_calculation():
    dataframe = pd.DataFrame({
        "ProductName": ["Amazon EC2"], "UsageType": ["APS3-BoxUsage"], "ItemDescription": ["EC2"],
        "UsageQuantity": [1], "Actual Cost": [100], "Credits": [-10], "LinkedAccountId": ["123"],
        "BillingPeriodStartDate": ["2026-06-01"], "BillingPeriodEndDate": ["2026-06-30"],
    })
    prepared, _ = prepare_invoice_data(dataframe)
    totals = calculate_totals(prepared, 90)

    assert totals.usd == 90
    assert totals.before_tax_inr == 8100
    assert totals.gst_inr == 1458
    assert get_region_from_usage_type("APS3-BoxUsage") == "Asia Pacific (Mumbai)"


def test_prepare_invoice_data_resolves_actual_uppercase_cur_columns():
    dataframe = pd.DataFrame({
        " PRODUCTNAME ": ["Amazon EC2"],
        "USAGETYPE": ["APS3-BoxUsage"],
        "ITEMDESCRIPTION": ["EC2"],
        "USAGEQUANTITY": [1],
        "ACTUAL COST": [100],
        "LINKEDACCOUNTID": ["115690512010"],
        "BILLINGPERIODSTARTDATE": ["2026-07-01"],
        "BILLINGPERIODENDDATE": ["2026-07-31"],
        "CREDITS": [-10],
    })

    _, columns = prepare_invoice_data(dataframe)

    assert columns.product == " PRODUCTNAME "
    assert columns.usage_type == "USAGETYPE"
    assert columns.item_description == "ITEMDESCRIPTION"
    assert columns.usage_quantity == "USAGEQUANTITY"
    assert columns.actual_cost == "ACTUAL COST"
    assert columns.linked_account_id == "LINKEDACCOUNTID"
    assert columns.billing_period_start == "BILLINGPERIODSTARTDATE"
    assert columns.billing_period_end == "BILLINGPERIODENDDATE"
    assert columns.credits == "CREDITS"
