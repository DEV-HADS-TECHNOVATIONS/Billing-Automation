# HADS TECHNOVATIONS Document and AWS Billing System

This integrated local application provides AWS Billing Automation, Tax Invoice generation, Proforma Invoice generation, and Credit Note generation.

## Installation and configuration

Install with the same Python used to run the application:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`. It contains local paths, tracker settings, reconciliation tolerance, authorised reviewers, and placeholder `AWS_<PROFILE>_*` credentials. Never commit a populated `.env` file.

`config/client.json` maps AWS linked account IDs to active status, credential profile, and billing mode. `config/clients.json` contains the recipient names, addresses, contacts, and GSTINs used by all manual documents. Add a client by updating these JSON files and the matching environment variables; source-code changes are not needed.

Required assets are `assets/Letter_Head.png` and `assets/Signature.png`. The local tracker is configured by `TRACKER_LOCAL_PATH` (normally `input/Invoice tracker.xlsx`). Credit-note numbering is stored in `data/document_counters.json` after a successful PDF and tracker update.

## Run

```bash
python src/main.py
```

The main menu offers AWS Billing Automation, Tax Invoice Generator, Proforma Invoice Generator, Credit Note Generator, and Exit.

### Tax Invoice

Choose a client, enter a date, enter multiline subject details (finish with a blank line), and enter the taxable value. GST is calculated automatically. The next tax invoice number comes from the existing tracker. The final PDF is saved below `output/tax_invoices/`, then its invoice values are recorded in the tracker.

### Proforma Invoice

Client, date, multiline subject details, and taxable value are collected in the same way. GST is calculated automatically. Proforma invoices do not allocate a tax invoice number and do not update the tax tracker. PDFs are saved below `output/proforma_invoices/`.

### Credit Note

Enter the client, credit-note date, original invoice number/date, multiline subject details, and taxable value. GST is calculated automatically. The credit-note sequence is persistent (`CR-1`, `CR-2`, and so on). PDFs are saved below `output/credit_notes/`. The original invoice row in the existing tracker receives the credit-note number in the `Credit Note Number` column. The supplied tracker had no such column, so this is added as the first unused column (R) only when needed. A retry reuses the existing PDF/number and records it safely instead of generating a duplicate.

### AWS Billing Automation

Select a consolidated consumption workbook in the file picker. The application identifies linked accounts, skips inactive accounts, extracts the billing period and exchange rate, retrieves Cost Explorer `UnblendedCost` data with client-specific credentials, reconciles the split invoice USD amount, creates pending local reviews when needed, and only then generates final AWS invoice PDFs and tracker updates. AWS evidence is stored under `output/aws_bills/`; drafts, reviews, invoices, and tracker proposals use their respective `output/` subdirectories. Use `python -m src.approval_cli list`, `approve`, or `reject` for local reviews.

For direct credentials set `"aws_billing_mode": "direct"`. For consolidated billing set `"aws_billing_mode": "payer"` and provide the payer identity in `aws_credential_owner_account_id`; Cost Explorer then filters to the configured linked account.

## Troubleshooting

- Missing AWS credentials: confirm the client profile in `config/client.json` matches `AWS_<PROFILE>_*` variables in `.env`.
- Tracker missing or invalid: confirm `TRACKER_LOCAL_PATH` and leave the worksheet structure intact.
- Existing output filename: documents are intentionally never overwritten; use a new valid number/date or repair the associated tracker entry.
- Pending AWS reconciliation: review the JSON under `output/manual_review/` with an authorised reviewer.

## Tests

```bash
python -m pytest -q
```
