python scripts/aggregate_transaction_from_pos.py data/from_pos/transactions
mv ~/Downloads/G18_*.xlsx ./data/from_pos/transactions 
poetry run python scripts/aggregate_transaction_from_pos.py data/from_pos/transactions --delete-raw

cd /Users/chieh/Library/CloudStorage/Dropbox/subway/project-subway
export CWA_API_KEY="CWA-4A3DCED3-6032-48F5-89A8-DC0A76F578DB"
export CWA_COUNTY="臺北市"
export CWA_TOWN="北投區"
export CWA_DAYS=20
poetry run python scripts/fetch_weather_info.py


# Scan Taiwan e-invoice paper (2 QR codes) via webcam, append to TSV
# Prereq (macOS): brew install zbar
poetry run python scripts/scan_invoice_qr.py --output data/invoices/invoices.csv
poetry run python scripts/scan_invoice_qr.py --input-dir data/invoices/captures --output data/invoices/invoices.csv --debug-decode

python - <<'PY'
import csv
from pathlib import Path
src_dir = Path("data/transactions")
out = Path("data/transactions_all.csv")
files = sorted(p for p in src_dir.glob("*.csv") if p.is_file())
with out.open("w", encoding="utf-8-sig", newline="") as f_out:
    writer = None
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as f_in:
            reader = csv.reader(f_in)
            header = next(reader, None)
            if header is None:
                continue
            if writer is None:
                writer = csv.writer(f_out); writer.writerow(header)
            for row in reader:
                if row: writer.writerow(row)
PY


poetry run python scripts/generate_working_hours_gantt.py \
  --csv data/working_hours/2026-01-googlesheet.csv \
  --out data/working_hours/2026-01-gantt \
  --year 2026
