"""Taiwan e-invoice (電子發票) QR-code parsing helpers.

This is a best-effort parser for the two QR codes printed on Taiwan e-invoice paper.
The payload format has multiple variants; this module focuses on extracting:
- invoice number
- ROC date (YYYMMDD) -> Gregorian date
- total amount (hex)
- seller tax id
- item list (best-effort from the 2nd QR code)

If you need authoritative invoice details (e.g., exact time, seller name), you'll
usually need to query an external service (e.g., the official platform / vendor).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional


_INVOICE_NO_RE = re.compile(r"^[A-Z]{2}\d{8}$")
_ROC_DATE_RE = re.compile(r"^\d{7}$")
_RANDOM_RE = re.compile(r"^[0-9A-Za-z]{4}$")
_EINV_KEY_ANYWHERE_RE = re.compile(r"([A-Z]{2}\d{8}\d{7}[0-9A-Za-z]{4})")


def _clean_qr_text(value: str) -> str:
    """Normalize decoded QR text.

    Some decoders occasionally include leading BOM/control characters.
    This keeps only printable characters and strips whitespace.
    """
    s = value or ""
    # Remove common BOM explicitly, then drop other control chars.
    s = s.replace("\ufeff", "")
    s = "".join(ch for ch in s if ch.isprintable())
    return s.strip()


def _find_invoice_key(value: str) -> tuple[str, int] | tuple[None, None]:
    """Return (key, start_index) if an e-invoice key pattern is found."""
    s = _clean_qr_text(value)
    if len(s) < 21:
        return None, None

    # Fast path: expected to start at position 0.
    prefix = s[:21]
    inv_no = prefix[:10].upper()
    roc_date = prefix[10:17]
    rnd = prefix[17:21]
    if _INVOICE_NO_RE.fullmatch(inv_no) and _ROC_DATE_RE.fullmatch(roc_date) and _RANDOM_RE.fullmatch(rnd):
        return inv_no + roc_date + rnd, 0

    m = _EINV_KEY_ANYWHERE_RE.search(s)
    if not m:
        return None, None

    raw = m.group(1)
    inv_no = raw[:10].upper()
    roc_date = raw[10:17]
    rnd = raw[17:21]
    if _INVOICE_NO_RE.fullmatch(inv_no) and _ROC_DATE_RE.fullmatch(roc_date) and _RANDOM_RE.fullmatch(rnd):
        return inv_no + roc_date + rnd, m.start(1)

    return None, None


def _to_decimal(value: str) -> Optional[Decimal]:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _looks_like_number(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", (value or "").strip()))


def _score_readability(text: str) -> tuple[int, int, int]:
    """Score a string for 'looks like human-readable Traditional Chinese'.

    Higher is better.
    Returns (cjk_count, ascii_count, weird_count).
    """
    s = text or ""
    cjk = 0
    ascii_printable = 0
    weird = 0
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:  # CJK Unified Ideographs
            cjk += 1
        elif 0x20 <= o <= 0x7E:
            ascii_printable += 1
        elif 0xFF61 <= o <= 0xFF9F:  # Halfwidth Katakana (common in mojibake)
            weird += 2
        else:
            weird += 1
    return cjk, ascii_printable, weird


def _fix_mojibake_text_best_effort(text: str) -> str:
    """Try to repair common mojibake for item names.

    In practice, some decoders yield a Unicode string that is actually CP950/Big5 bytes
    mis-decoded as CP932/Shift-JIS (showing characters like '､' or halfwidth katakana).

    Strategy:
    - If the string already looks fine, return as-is.
    - Otherwise, try: encode with the *wrong* codec -> decode with the likely *right* codec.
    - Pick the candidate that increases CJK characters and reduces weird symbols.
    """
    s = (text or "").strip()
    if not s:
        return ""

    base_score = _score_readability(s)
    # If it already contains CJK, don't aggressively rewrite.
    if base_score[0] >= 2 and base_score[2] == 0:
        return s

    candidates: list[str] = [s]

    # Most common: CP932 mojibake -> CP950/Big5.
    for wrong in ("cp932", "shift_jis"):
        for right in ("cp950", "big5"):
            try:
                repaired = s.encode(wrong, errors="strict").decode(right, errors="strict")
                candidates.append(repaired)
            except Exception:
                pass

    # Fallback: Latin-1 roundtrip (some libs effectively do this).
    for right in ("cp950", "big5", "utf-8"):
        try:
            repaired = s.encode("latin1", errors="strict").decode(right, errors="strict")
            candidates.append(repaired)
        except Exception:
            pass

    def _key(x: str) -> tuple[int, int, int, int]:
        cjk, ascii_printable, weird = _score_readability(x)
        # Sort by: more CJK, less weird, then more ASCII, then shorter (avoid garbage expansions)
        return (cjk, -weird, ascii_printable, -len(x))

    best = max(candidates, key=_key)

    # Only accept if it actually improves readability.
    best_score = _score_readability(best)
    if best_score[0] > base_score[0] and best_score[2] <= base_score[2]:
        return best
    return s


def roc_yyyymmdd_to_date(roc_yyyymmdd: str) -> date:
    """Convert ROC date string (YYYMMDD) into Gregorian date."""
    s = (roc_yyyymmdd or "").strip()
    if not re.fullmatch(r"\d{7}", s):
        raise ValueError(f"Invalid ROC date (expected 7 digits YYYMMDD): {roc_yyyymmdd!r}")

    roc_year = int(s[0:3])
    month = int(s[3:5])
    day = int(s[5:7])
    return date(roc_year + 1911, month, day)


def format_invoice_number(invoice_number: str) -> str:
    """Format as 'AB-12345678' when possible."""
    s = (invoice_number or "").strip().upper()
    if _INVOICE_NO_RE.fullmatch(s):
        return f"{s[:2]}-{s[2:]}"
    return s


def invoice_key_from_qr(qr_text: str) -> Optional[str]:
    """Return a stable key for grouping the two QR codes of the same invoice.

    Expected prefix:
      invoiceNumber(10) + rocDate(7) + random(4)

    Returns the 21-char prefix if it looks valid, else None.
    """
    key, _pos = _find_invoice_key(qr_text)
    return key


@dataclass(frozen=True)
class InvoiceItem:
    name: str
    unit_price: Decimal
    quantity: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class ParsedTaiwanEInvoice:
    invoice_number: str
    invoice_date: date
    total_amount: int
    seller_identifier: str
    buyer_identifier: str = ""
    random_number: str = ""
    items: tuple[InvoiceItem, ...] = ()

    seller_name: str = ""
    category: str = ""
    invoice_type: str = "電子發票"

    def timestamp_str(self) -> str:
        # QR payload may not include time; default to midnight.
        return self.invoice_date.strftime("%Y/%m/%d 00:00:00")

    def amount_str(self) -> str:
        return f"${int(self.total_amount)}"

    def invoice_number_str(self) -> str:
        return format_invoice_number(self.invoice_number)

    def items_str(self) -> str:
        if not self.items:
            return ""

        def _fmt_decimal(x: Decimal) -> str:
            # avoid trailing zeros
            text = format(x.normalize(), "f")
            return text.rstrip("0").rstrip(".") if "." in text else text

        parts: list[str] = []
        for it in self.items:
            qty = _fmt_decimal(it.quantity)
            unit = _fmt_decimal(it.unit_price)
            sub = _fmt_decimal(it.subtotal)
            parts.append(f"{it.name} : {qty} * {unit} = {sub}")
        return "； ".join(parts)


def enrich_from_mof_best_effort(
    inv: ParsedTaiwanEInvoice,
    *,
    qr_a: str,
    qr_b: str,
    endpoint: str,
    app_id: str,
    api_key: str,
    timeout_seconds: int = 15,
    version: str = "0.5",
    action: str = "qryInvDetail",
) -> tuple[ParsedTaiwanEInvoice, dict[str, Any]]:
    """Try to enrich invoice details by calling the official e-invoice API.

    This is intentionally *best-effort* because the platform has multiple API
    generations and parameter schemas. We try a few common request shapes and
    return:
      (possibly_enriched_invoice, raw_response_json)

    If the call fails or response schema is unfamiliar, the returned invoice may
    be unchanged.
    """

    import json

    import requests

    url = (endpoint or "").strip()
    if not url:
        raise ValueError("MOF endpoint is empty")

    # Some APIs use ROC date, some Gregorian date.
    roc_date_yyyymmdd = f"{inv.invoice_date.year - 1911:03d}{inv.invoice_date.month:02d}{inv.invoice_date.day:02d}"
    greg_date_yyyymmdd = inv.invoice_date.strftime("%Y%m%d")

    # Try multiple payload variants. We keep the pair QR raw strings too.
    candidates: list[dict[str, Any]] = [
        {
            "version": version,
            "action": action,
            "appID": app_id,
            "apiKey": api_key,
            "invNum": inv.invoice_number,
            "invDate": roc_date_yyyymmdd,
            "randomNumber": inv.random_number,
            "sellerID": inv.seller_identifier,
            "totalAmount": str(inv.total_amount),
        },
        {
            "version": version,
            "action": action,
            "appID": app_id,
            "apiKey": api_key,
            "invoiceNumber": inv.invoice_number,
            "invoiceDate": roc_date_yyyymmdd,
            "randomNumber": inv.random_number,
            "sellerID": inv.seller_identifier,
            "totalAmount": str(inv.total_amount),
        },
        {
            "version": version,
            "action": action,
            "appID": app_id,
            "apiKey": api_key,
            "invoiceNumber": inv.invoice_number,
            "invoiceDate": greg_date_yyyymmdd,
            "randomNumber": inv.random_number,
            "sellerID": inv.seller_identifier,
            "totalAmount": str(inv.total_amount),
        },
        {
            "version": version,
            "action": action,
            "appID": app_id,
            "apiKey": api_key,
            "qrcode1": qr_a,
            "qrcode2": qr_b,
        },
    ]

    last_json: dict[str, Any] = {}
    for payload in candidates:
        try:
            resp = requests.post(url, data=payload, timeout=timeout_seconds)
            resp.raise_for_status()
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else json.loads(resp.text)
            last_json = data if isinstance(data, dict) else {"_raw": data}
        except Exception:
            continue

        # Heuristic: if response has non-error code, try to extract fields.
        code = str(last_json.get("code", ""))
        msg = str(last_json.get("msg", ""))
        is_ok = code in ("200", "0", "") and "錯誤" not in msg

        # Try to locate a detail object.
        detail = None
        for k in ("details", "detail", "result", "data"):
            v = last_json.get(k)
            if isinstance(v, dict):
                detail = v
                break

        if detail is None and is_ok:
            detail = last_json

        if not isinstance(detail, dict):
            return inv, last_json

        # Seller name
        seller_name = ""
        for k in ("sellerName", "seller_name", "SellerName"):
            if isinstance(detail.get(k), str):
                seller_name = detail[k]
                break
        if not seller_name:
            seller = detail.get("seller")
            if isinstance(seller, dict) and isinstance(seller.get("name"), str):
                seller_name = seller["name"]

        # Items
        items: list[InvoiceItem] = list(inv.items)
        raw_items = detail.get("items") or detail.get("details") or detail.get("invDetails")
        if isinstance(raw_items, list):
            parsed_items: list[InvoiceItem] = []
            for it in raw_items:
                if not isinstance(it, dict):
                    continue
                name = str(it.get("name") or it.get("description") or it.get("itemName") or "").strip()
                qty_s = str(it.get("quantity") or it.get("qty") or it.get("amount") or "").strip()
                unit_s = str(it.get("unitPrice") or it.get("price") or it.get("unit_price") or "").strip()
                if not name or not _looks_like_number(qty_s) or not _looks_like_number(unit_s):
                    continue
                qty = _to_decimal(qty_s)
                unit = _to_decimal(unit_s)
                if qty is None or unit is None:
                    continue
                parsed_items.append(InvoiceItem(name=name, unit_price=unit, quantity=qty))
            if parsed_items:
                items = parsed_items

        enriched = replace(inv, seller_name=seller_name or inv.seller_name, items=tuple(items))
        return enriched, last_json

    return inv, last_json


def _parse_amount_hex(hex_str: str) -> int:
    s = (hex_str or "").strip()
    if not re.fullmatch(r"[0-9A-Fa-f]{8}", s):
        raise ValueError(f"Invalid amount hex: {hex_str!r}")
    return int(s, 16)


def _extract_items_best_effort(qr_text: str) -> tuple[InvoiceItem, ...]:
    """Try to extract items from a QR code by scanning colon-separated segments.

    Many e-invoice QR payloads embed a sequence like:
      ...:<itemName>:<qty>:<unitPrice>:<itemName>:<qty>:<unitPrice>:...

    Since there may be metadata segments, this tries all possible offsets and
    takes the parse that yields the most items.
    """
    if ":" not in (qr_text or ""):
        return ()

    segments = [s.strip() for s in qr_text.split(":") if s.strip()]
    if len(segments) < 3:
        return ()

    def parse_from(start: int) -> list[InvoiceItem]:
        items: list[InvoiceItem] = []
        i = start
        while i + 2 < len(segments):
            name = _fix_mojibake_text_best_effort(segments[i])
            qty_s = segments[i + 1]
            unit_s = segments[i + 2]

            # Reject obvious non-names (common when we start at a wrong offset)
            if not name:
                i += 1
                continue
            if set(name) <= {"*"}:
                i += 1
                continue
            # Must contain at least one CJK character or ASCII letter.
            # Purely-numeric names (e.g. "1") are almost always false positives.
            if not re.search(r"[A-Za-z\u4e00-\u9fff]", name):
                i += 1
                continue

            if name and _looks_like_number(qty_s) and _looks_like_number(unit_s):
                qty = _to_decimal(qty_s)
                unit = _to_decimal(unit_s)
                if qty is not None and unit is not None:
                    items.append(InvoiceItem(name=name, unit_price=unit, quantity=qty))
                    i += 3
                    continue
            i += 1
        return items

    best: list[InvoiceItem] = []
    for start in range(0, min(len(segments), 12)):
        cand = parse_from(start)
        if len(cand) > len(best):
            best = cand

    return tuple(best)


def parse_taiwan_einvoice_qr_pair(qr_a: str, qr_b: str) -> ParsedTaiwanEInvoice:
    """Parse the two QR codes from a Taiwan e-invoice paper.

    This assumes both payloads share the same leading 21 chars:
      invoiceNumber(10) + invoiceDate(7, ROC) + random(4)

    Then attempts to parse amounts and identifiers from fixed positions.
    """
    a0 = _clean_qr_text(qr_a)
    b0 = _clean_qr_text(qr_b)
    a = a0
    b = b0
    if not a or not b:
        raise ValueError("Need 2 non-empty QR payloads")

    # If the invoice key appears later in the decoded string, align to it.
    key_a, pos_a = _find_invoice_key(a)
    key_b, pos_b = _find_invoice_key(b)
    if key_a and key_b and key_a == key_b:
        a = a[pos_a:]
        b = b[pos_b:]

    if len(a) < 53 and len(b) < 53:
        raise ValueError("QR payload too short; not a Taiwan e-invoice QR")

    # Both QR codes should start with the same 21 chars.
    prefix = a[:21] if len(a) >= 21 else ""
    if not prefix or (len(b) < 21 or b[:21] != prefix):
        # fallback: longest common prefix
        common = []
        for ca, cb in zip(a, b):
            if ca != cb:
                break
            common.append(ca)
        prefix = "".join(common)
        if len(prefix) < 21:
            raise ValueError("QR pair does not look like the same invoice (prefix mismatch)")

    invoice_number = prefix[:10]
    invoice_date = roc_yyyymmdd_to_date(prefix[10:17])
    random_number = prefix[17:21]

    # Try fixed-position header parsing from whichever payload is long enough.
    base = a if len(a) >= 53 else b
    total_hex = base[29:37]
    buyer_id = base[37:45]
    seller_id = base[45:53]

    total_amount = _parse_amount_hex(total_hex)

    # Items usually live in the QR that contains more ':' segments.
    items_source = a if a.count(":") >= b.count(":") else b
    items = _extract_items_best_effort(items_source)

    return ParsedTaiwanEInvoice(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        total_amount=total_amount,
        seller_identifier=(seller_id or "").strip(),
        buyer_identifier=(buyer_id or "").strip(),
        random_number=(random_number or "").strip(),
        items=items,
    )


def _is_no_continuation_marker(qr_text: str) -> bool:
    """Return True if the given QR payload indicates 'no continuation'.

    Per common e-invoice paper behavior, the right QR may be:
    - blank/whitespace, or
    - '**' (possibly with padding)

    This does NOT mean decode failure; it can mean all items fit in the left QR.
    """
    s = (qr_text or "")
    trimmed = s.strip()
    return trimmed == "" or trimmed == "**"


def parse_taiwan_einvoice_qr_best_effort(qr_a: str, qr_b: str = "") -> ParsedTaiwanEInvoice:
    """Best-effort parser for Taiwan e-invoice paper QR.

    - If qr_b is missing or is a no-continuation marker ('**'/blank), parse using qr_a only.
    - Otherwise, parse as a strict pair.
    """
    a = _clean_qr_text(qr_a)
    if not a:
        raise ValueError("QR payload is empty")

    b_raw = qr_b or ""
    if _is_no_continuation_marker(b_raw):
        # Single-QR parse: use the same fixed-position header logic on qr_a.
        key_a, pos_a = _find_invoice_key(a)
        if key_a:
            a = a[pos_a:]
        if len(a) < 53:
            raise ValueError("QR payload too short; not a Taiwan e-invoice QR")

        prefix = a[:21]
        if len(prefix) < 21:
            raise ValueError("QR payload too short; missing invoice prefix")

        invoice_number = prefix[:10]
        invoice_date = roc_yyyymmdd_to_date(prefix[10:17])
        random_number = prefix[17:21]

        total_hex = a[29:37]
        buyer_id = a[37:45]
        seller_id = a[45:53]
        total_amount = _parse_amount_hex(total_hex)

        items = _extract_items_best_effort(a)

        return ParsedTaiwanEInvoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            total_amount=total_amount,
            seller_identifier=(seller_id or "").strip(),
            buyer_identifier=(buyer_id or "").strip(),
            random_number=(random_number or "").strip(),
            items=items,
        )

    return parse_taiwan_einvoice_qr_pair(qr_a, qr_b)


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = (v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
