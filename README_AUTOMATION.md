# AWS Invoice Generator – Testing Automation Package

This package adds a **testing-phase automation layer** to the project tree supplied by the user. It does not overwrite `src/main.py`, the existing invoice calculator, invoice generator, PDF generator, splitter, or client configuration.

## What is included

- Read invoice sequence from the local copy of the tracker workbook, column E.
- Identify a client from the Excel filename using `config/clients.json`.
- Read the unique positive `EXCHANGERATE` value from the Excel workbook by header name (the screenshot shows it in column AA).
- Format invoice IDs as `INV{sequence}-{DDMM}-CY{YY}`, with the CY year calculated dynamically from the invoice issue date.
- Reconcile comparable AWS and Excel pre-tax USD totals with a ±USD 5.00 threshold.
- Create a local JSON manual-review record when the threshold is exceeded.
- Provide one orchestration function to prepare/validate one invoice job.
- Provide a preview script to test the helpers.

## SharePoint link during this testing phase

The `.env` includes `TRACKER_SHAREPOINT_URL` as requested, but a private SharePoint sharing URL alone does not authenticate Python. Microsoft Graph integration is intentionally deferred.

For testing:
1. Sync the SharePoint invoice tracker using OneDrive or download a copy.
2. Set `TRACKER_LOCAL_PATH` to that local workbook.
3. Set `TRACKER_MODE=local`.
4. The tracker adapter reads column E from that local file.

When Graph is implemented later, replace the adapter behind `InvoiceTracker` with Graph download/update operations. The rest of the code can keep using the same interface.

## Install and configure

Merge `requirements-automation.txt` into the project's existing `requirements.txt`:

```text
openpyxl>=3.1.2
python-dotenv>=1.0.0
```

Copy `.env.example` to `.env`, then edit `TRACKER_LOCAL_PATH`. Add `.env` to `.gitignore`.

Load environment variables early in `src/main.py` if it does not already load them:

```python
from dotenv import load_dotenv
load_dotenv()
```

## AWS source input for local testing

This package does not call AWS APIs yet. Supply a test JSON file following `examples/aws_bill_summary.example.json`. Its `comparable_pre_tax_total_usd` must be the official AWS amount for the same customer/account, month, currency, and charge basis as the existing invoice calculator's `excel_pre_tax_total_usd`.

Do not compare an account-wide consolidated AWS total against one client's consumption total. Add the client's `aws_account_id` to the matching record in `config/clients.json`.

## Preview the automation helpers

```bash
python scripts/preview_automation.py \
  input/HADS-Consumption-Report.xlsx \
  2026-10 \
  2318.31 \
  input/aws_bills/hads-2026-10.json
```

PowerShell:

```powershell
python scripts/preview_automation.py "input/HADS Consumption Report OCT'26.xlsx" 2026-10 2318.31 "input/aws_bills/hads-2026-10.json"
```

The Excel total argument must come from the existing Python invoice calculator's comparable **pre-tax USD** total. Do not include INR conversion or GST.

## One integration point in the existing application

After the existing code has:
- identified the Excel file,
- calculated the client's comparable pre-tax USD total,
- located the corresponding AWS bill JSON,

create one `InvoiceNumberAllocator` per batch and call `prepare_invoice(...)`.

Example:

```python
from src.automation.workflow import create_allocator_from_tracker, prepare_invoice

allocator = create_allocator_from_tracker()

job = prepare_invoice(
    excel_path=excel_path,
    billing_period="2026-10",
    excel_pre_tax_total_usd=existing_calculator_pre_tax_usd,
    aws_bill_json_path=aws_bill_json_path,
    allocator=allocator,
)

if job.status == "AUTO_APPROVED":
    # Pass job.invoice_number and job.exchange_rate into the existing invoice generator.
    # Send/deliver only after the PDF and tracker update have succeeded.
    pass
else:
    # Do not send or finalize. The job.review_record must be reviewed.
    print("Manual review required:", job.review_record)
```

This is an integration seam, not a replacement `main.py`: the exact call site depends on the existing function signatures, which were not included in the supplied project tree.

## Testing-only manual approval

`output/manual_review/*.json` files are created with `status: PENDING`. An authorized tester may update the JSON to `APPROVED` or `REJECTED`, and record reviewer/time/comment.

This local JSON decision is only a testing mechanism. It is not a secure production approval channel. Production approval should use authenticated Outlook/Graph approval replies or an authenticated internal approval endpoint, with reviewer identity verification and an immutable audit trail.

## Safety notes

- The tracker adapter is read-only: it will not modify the SharePoint workbook or append invoice numbers. The tracker structure shown in the screenshots has other columns and row relationships; blindly appending values into column E could corrupt the register.
- The allocator is in-memory for sequential local testing. Concurrent production jobs require an atomic DynamoDB counter.
- The official AWS bill JSON is a manual test fixture in this phase. Replace it later with AWS Invoicing/Cost Explorer retrieval.
- This package does not send client emails.
- The package does not change existing invoice calculations or PDF layout.
- Test against copies of real files before connecting to production data.
