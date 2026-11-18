# AWS Billing Automation

One Windows application that splits an AWS Consumption Report by `LinkedAccountId`, then creates invoices for the successfully validated client workbooks.

## Run

```powershell
pip install -r requirements.txt


```

Copy `.env.example` to `.env` and set a positive `USD_TO_INR` and `INVOICE_NUMBER`. The application opens a Windows file picker, then writes results to:

```text
output/<Billing Month>/
├── 01_Excels/
├── 02_PDFs/
└── 03_Logs/
```

`config/client.json` is keyed by `LinkedAccountId` and controls `legal_name`, display names, and active flags. `config/clients.json` contains invoice recipient details matched by `legal_name`.

The invoice number is committed to `.env` only after a PDF is successfully rendered and verified on disk.



 **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Add Billing Files:**
    -   Place one or more AWS billing reports in Excel format (`.xlsx` or `.xls`) inside the `data/input/` folder.

2.  **Run the script:**
    ```bash
    python src/main.py
    ```