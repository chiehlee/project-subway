"""Aggregate POS export CSVs into clean transaction CSVs (bucketed per day).

Input: directory containing report-style POS CSV/XLSX files (8 columns, multiple transaction blocks separated by ',,,,,,,,').
Output: per-day CSVs named YYYY-MM-DD.csv with columns (Traditional Chinese):
時間,交易金額,折扣金額,種類,發票編號,客戶編號,品項
"""
from __future__ import annotations

import argparse
import csv
import io
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


SEPARATOR_LINE = ",,,,,,"
OUTPUT_HEADERS = ["時間", "交易金額", "折扣金額", "種類", "發票編號", "客戶編號", "品項"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate POS transaction CSV directory.")
    parser.add_argument(
        "input_dir",
        nargs="?",
        default="data/from_pos/transactions",
        help="Input directory containing POS CSV files (default: data/from_pos/transactions)",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="data/transactions",
        help="Output directory for aggregated per-day CSVs (default: data/transactions)",
    )
    parser.add_argument(
        "--delete-raw",
        action="store_true",
        help="Delete raw CSVs after successful aggregation (default: keep them)",
    )
    return parser.parse_args()


def normalize_cell(value: str) -> str:
    """Strip whitespace and full-width spaces."""
    return value.replace("\u3000", "").strip()


def looks_like_number(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", value))


def looks_like_time(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", value))


def pad_row(row: Sequence[str], target_len: int = 8) -> List[str]:
    if len(row) >= target_len:
        return list(row[:target_len])
    return list(row) + [""] * (target_len - len(row))


def to_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def decimal_to_str(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def normalize_date(date_str: str) -> str:
    """Normalize date to YYYY-MM-DD style; returns empty string if missing."""
    if not date_str:
        return ""
    return date_str.replace("/", "-")


def normalize_payment_method(method: str) -> str:
    """Strip trailing '付款' to keep payment type only."""
    if not method:
        return ""
    method = method.strip()
    if method.endswith("付款"):
        method = method[: -len("付款")]
    return method.strip()


def split_blocks(lines: Iterable[str]) -> List[List[str]]:
    """Split raw lines into blocks using the separator line."""
    blocks: List[List[str]] = []
    current: List[str] = []

    for raw in lines:
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        is_separator = stripped == SEPARATOR_LINE or (
            stripped and set(stripped) == {","} and len(stripped) >= len(SEPARATOR_LINE)
        )
        if is_separator:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(raw)

    if current:
        blocks.append(current)
    return blocks


def is_item_row(cells: Sequence[str]) -> bool:
    c1, c2, c3, c4, _, _, _, c8 = cells
    if "序" in c1 or c3 == "品名" or "品名" in c3:
        return False
    if c2 in ("交易日期：", "發票編號：", "合計", "TOTAL"):
        return False
    if not c3 or not c4:
        return False
    if not looks_like_number(c4):
        return False
    if c8 and not looks_like_time(c8):
        # Time is optional; if provided ensure it looks like a time.
        return False
    return True


def parse_block(block_lines: List[str]) -> Optional[List[str]]:
    # Quick check to skip pure metadata blocks.
    joined = "".join(block_lines)
    normalized_joined = re.sub(r"\s+", "", joined)
    if (
        "交易日期" not in normalized_joined
        and "序號" not in normalized_joined
        and "品名" not in normalized_joined
    ):
        return None

    info = {
        "txn_date": "",
        "first_item_time": "",
        "total_amount": "",
        "total_amount_sum": Decimal("0"),
        "discount_sum": Decimal("0"),
        "payment_method": "",
        "invoice_no": "",
        "customer_id": "",
        "items": [],  # type: List[str]
    }

    reader = csv.reader(io.StringIO("".join(block_lines)))
    for row in reader:
        if not row:
            continue
        cells = [normalize_cell(c) for c in pad_row(row)]
        if not any(cells):
            continue

        c1, c2, c3, c4, c5, c6, c7, c8 = cells

        if c2 == "交易日期：":
            info["txn_date"] = c3
            continue

        if c2 == "發票編號：":
            if c3:
                info["invoice_no"] = c3.split("～")[0].strip()
            info["customer_id"] = c8
            continue

        if c2 == "合計":
            info["total_amount"] = c6
            continue

        if c2 == "TOTAL":
            if not info["total_amount"]:
                info["total_amount"] = c6
            info["payment_method"] = c7
            continue

        if is_item_row(cells):
            if not info["first_item_time"] and c8:
                info["first_item_time"] = c8
            info["items"].append(f"{c3}({c4})")
            if c6:
                info["total_amount_sum"] += to_decimal(c6)
            if c5:
                info["discount_sum"] += to_decimal(c5)

    if not any(info.values()):
        return None
    return info


def merge_info(primary: dict, secondary: dict) -> dict:
    """Merge two block infos, preferring fields from primary when present."""
    merged = {
        "txn_date": primary.get("txn_date") or secondary.get("txn_date") or "",
        "first_item_time": primary.get("first_item_time") or secondary.get("first_item_time") or "",
        "total_amount": primary.get("total_amount") or secondary.get("total_amount") or "",
        "total_amount_sum": primary.get("total_amount_sum", Decimal("0"))
        + secondary.get("total_amount_sum", Decimal("0")),
        "discount_sum": primary.get("discount_sum", Decimal("0")) + secondary.get("discount_sum", Decimal("0")),
        "payment_method": primary.get("payment_method") or secondary.get("payment_method") or "",
        "invoice_no": primary.get("invoice_no") or secondary.get("invoice_no") or "",
        "customer_id": primary.get("customer_id") or secondary.get("customer_id") or "",
        "items": [],
    }
    merged["items"] = (primary.get("items") or []) + (secondary.get("items") or [])
    return merged


def info_to_row(info: dict) -> List[str]:
    txn_date = info.get("txn_date", "")
    first_item_time = info.get("first_item_time", "")
    time_field = ""
    if txn_date and first_item_time:
        time_field = f"{txn_date} {first_item_time}"
    else:
        time_field = txn_date

    items_field = "|".join(info.get("items") or [])

    # Prefer summed amounts from item rows; fall back to captured totals if missing.
    total_amount_sum = info.get("total_amount_sum", Decimal("0"))
    total_amount_field = (
        decimal_to_str(total_amount_sum) if total_amount_sum != Decimal("0") else info.get("total_amount", "")
    )
    discount_sum = info.get("discount_sum", Decimal("0"))
    discount_field = decimal_to_str(discount_sum) if discount_sum != Decimal("0") else "0"

    return [
        time_field,
        total_amount_field,
        discount_field,
        normalize_payment_method(info.get("payment_method", "")),
        info.get("invoice_no", ""),
        info.get("customer_id", ""),
        items_field,
    ]


def is_complete(info: dict) -> bool:
    """Consider a block complete if it has items plus some metadata."""
    return bool(info.get("items")) and bool(
        info.get("payment_method") or info.get("invoice_no") or info.get("txn_date")
    )


def aggregate(input_path: Path) -> List[List[str]]:
    lines = read_input_lines(input_path)
    blocks = split_blocks(lines)
    aggregated: List[List[str]] = []
    pending: Optional[dict] = None

    for block in blocks:
        info = parse_block(block)
        if info is None:
            continue

        if pending is None:
            if is_complete(info):
                aggregated.append(info_to_row(info))
            else:
                pending = info
            continue

        merged = merge_info(pending, info)
        if is_complete(merged):
            aggregated.append(info_to_row(merged))
            pending = None
        else:
            pending = merged

    if pending:
        aggregated.append(info_to_row(pending))

    return aggregated


def bucket_by_date(rows: List[List[str]]) -> dict:
    buckets: dict[str, List[List[str]]] = {}
    for row in rows:
        if not row:
            continue
        time_field = row[0]
        date_raw = time_field.split()[0] if time_field else ""
        date_norm = normalize_date(date_raw)
        if not date_norm:
            continue
        buckets.setdefault(date_norm, []).append(row)
    return buckets


def excel_to_csv_lines(input_path: Path) -> List[str]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Missing optional dependency 'openpyxl'. Install it to process .xlsx files.") from exc

    data_frame = pd.read_excel(input_path)
    buffer = io.StringIO()
    data_frame.to_csv(buffer, index=False, lineterminator="\n")
    buffer.seek(0)
    return buffer.read().splitlines(keepends=True)


def read_input_lines(input_path: Path) -> List[str]:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            return f.readlines()
    if suffix == ".xlsx":
        return excel_to_csv_lines(input_path)
    raise ValueError(f"Unsupported file type: {input_path.suffix}")


def process_directory(input_dir: Path) -> tuple[dict[str, List[List[str]]], List[Path]]:
    """Aggregate all CSV/XLSX files in a directory, grouped by transaction date."""
    daily_rows: dict[str, List[List[str]]] = {}
    processed: List[Path] = []

    for csv_path in sorted(input_dir.iterdir()):
        if not csv_path.is_file() or csv_path.suffix.lower() not in {".csv", ".xlsx"}:
            continue
        log_info(f"Processing file: {csv_path}")
        rows = aggregate(csv_path)
        if not rows:
            log_info(f"Skipped (no parsed rows): {csv_path}")
            continue
        processed.append(csv_path)
        per_file_bucket = bucket_by_date(rows)
        for date_key, date_rows in per_file_bucket.items():
            if date_key in daily_rows:
                log_info(f"Overwriting existing data for {date_key} with {csv_path.name}")
            daily_rows[date_key] = list(date_rows)

    return daily_rows, processed


def write_daily_outputs(daily_rows: dict[str, List[List[str]]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for date_key, rows in sorted(daily_rows.items()):
        output_path = output_dir / f"{date_key}.csv"
        log_info(f"Writing {output_path} ({len(rows)} rows)")
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_HEADERS)
            writer.writerows(rows)


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    log_info(f"Start aggregation. Input dir: {input_dir} -> Output dir: {output_dir}")
    log_info(f"Delete raw after aggregation: {args.delete_raw}")

    daily_rows, processed_files = process_directory(input_dir)
    write_daily_outputs(daily_rows, output_dir)

    if args.delete_raw:
        for path in processed_files:
            try:
                path.unlink()
            except OSError:
                # Best-effort; skip failures.
                pass
        log_info(f"Deleted {len(processed_files)} raw files.")

    log_info("Aggregation completed.")


if __name__ == "__main__":
    main()
