import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


# Ensure repo root is on sys.path so we can import `utilities.*`
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from utilities.tw_einvoice_qr import (  # noqa: E402
    InvoiceItem,
    ParsedTaiwanEInvoice,
    enrich_from_mof_best_effort,
    format_invoice_number,
    invoice_key_from_qr,
    parse_taiwan_einvoice_qr_best_effort,
    parse_taiwan_einvoice_qr_pair,
    roc_yyyymmdd_to_date,
)


def _make_prefix(*, inv_no: str = "AB12345678", roc_date: str = "1140103", rnd: str = "1A2b") -> str:
    # invoiceNumber(10) + ROC date(7) + random(4) = 21 chars
    return f"{inv_no}{roc_date}{rnd}"


def _make_base_payload(
    *,
    prefix: str,
    total_hex: str = "00000064",  # 100
    buyer_id: str = "00000000",
    seller_id: str = "12345678",
    filler8: str = "00000000",
) -> str:
    # Header fields are parsed from fixed positions:
    # total_hex = [29:37], buyer_id = [37:45], seller_id = [45:53]
    assert len(prefix) == 21
    assert len(filler8) == 8
    assert len(total_hex) == 8
    assert len(buyer_id) == 8
    assert len(seller_id) == 8
    return prefix + filler8 + total_hex + buyer_id + seller_id


def _make_items_payload(prefix: str) -> str:
    # Make sure this QR is also valid for fixed-position header parsing,
    # then append colon-separated items.
    base = _make_base_payload(prefix=prefix)
    return base + ":Milk:2:30:Egg:1:40"


class TestRocDate(unittest.TestCase):
    def test_roc_yyyymmdd_to_date_ok(self) -> None:
        self.assertEqual(roc_yyyymmdd_to_date("1140103"), date(2025, 1, 3))

    def test_roc_yyyymmdd_to_date_invalid(self) -> None:
        with self.assertRaises(ValueError):
            roc_yyyymmdd_to_date("20260103")
        with self.assertRaises(ValueError):
            roc_yyyymmdd_to_date("114013")


class TestInvoiceKey(unittest.TestCase):
    def test_invoice_key_from_qr_ok(self) -> None:
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        self.assertEqual(invoice_key_from_qr(prefix + "ZZZ"), prefix)

    def test_invoice_key_from_qr_tolerates_bom_and_offset(self) -> None:
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        self.assertEqual(invoice_key_from_qr("\ufeff" + prefix + "ZZZ"), prefix)
        self.assertEqual(invoice_key_from_qr("xx" + prefix + "ZZZ"), prefix)

    def test_invoice_key_from_qr_rejects_invalid(self) -> None:
        self.assertIsNone(invoice_key_from_qr(""))
        self.assertIsNone(invoice_key_from_qr("A" * 20))  # too short

        bad_inv = _make_prefix(inv_no="A123456789")  # not 2 letters + 8 digits
        self.assertIsNone(invoice_key_from_qr(bad_inv))

        bad_date = _make_prefix(roc_date="ABC0103")
        self.assertIsNone(invoice_key_from_qr(bad_date))

        bad_rnd = _make_prefix(rnd="!!!!")
        self.assertIsNone(invoice_key_from_qr(bad_rnd))


class TestFormatting(unittest.TestCase):
    def test_format_invoice_number(self) -> None:
        self.assertEqual(format_invoice_number("AB12345678"), "AB-12345678")
        self.assertEqual(format_invoice_number("ab12345678"), "AB-12345678")
        # Non-invoice strings are uppercased by the implementation.
        self.assertEqual(format_invoice_number("not-an-invoice"), "NOT-AN-INVOICE")


class TestParsePair(unittest.TestCase):
    def test_parse_pair_basic(self) -> None:
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        a = _make_base_payload(prefix=prefix, total_hex="00000064", buyer_id="00000000", seller_id="12345678")
        b = _make_items_payload(prefix)

        inv = parse_taiwan_einvoice_qr_pair(a, b)
        self.assertEqual(inv.invoice_number, "AB12345678")
        self.assertEqual(inv.invoice_date, date(2025, 1, 3))
        self.assertEqual(inv.random_number, "1A2b")
        self.assertEqual(inv.total_amount, 100)
        self.assertEqual(inv.buyer_identifier, "00000000")
        self.assertEqual(inv.seller_identifier, "12345678")

        # Items parsed from the QR with more ':' segments
        self.assertGreaterEqual(len(inv.items), 2)
        self.assertEqual(inv.items[0].name, "Milk")
        self.assertEqual(inv.items[0].quantity, Decimal("2"))
        self.assertEqual(inv.items[0].unit_price, Decimal("30"))

    def test_parse_pair_with_buyer_identifier(self) -> None:
        # Simulate an invoice with buyer tax ID filled in (B2B / has 統編).
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        a = _make_base_payload(prefix=prefix, total_hex="00000064", buyer_id="87654321", seller_id="12345678")
        b = _make_items_payload(prefix)

        inv = parse_taiwan_einvoice_qr_pair(a, b)
        self.assertEqual(inv.buyer_identifier, "87654321")
        self.assertEqual(inv.seller_identifier, "12345678")

    def test_parse_pair_tolerates_leading_junk(self) -> None:
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        a = "\ufeff" + _make_base_payload(prefix=prefix, total_hex="00000064", buyer_id="00000000", seller_id="12345678")
        b = "xx" + _make_items_payload(prefix)

        inv = parse_taiwan_einvoice_qr_pair(a, b)
        self.assertEqual(inv.invoice_number, "AB12345678")
        self.assertEqual(inv.invoice_date, date(2025, 1, 3))
        self.assertEqual(inv.random_number, "1A2b")

    def test_parse_pair_order_independent(self) -> None:
        prefix = _make_prefix()
        a = _make_base_payload(prefix=prefix)
        b = _make_items_payload(prefix)

        inv1 = parse_taiwan_einvoice_qr_pair(a, b)
        inv2 = parse_taiwan_einvoice_qr_pair(b, a)
        self.assertEqual(inv1.invoice_number, inv2.invoice_number)
        self.assertEqual(inv1.invoice_date, inv2.invoice_date)
        self.assertEqual(inv1.total_amount, inv2.total_amount)
        self.assertEqual(inv1.seller_identifier, inv2.seller_identifier)

    def test_parse_pair_prefix_mismatch(self) -> None:
        prefix1 = _make_prefix(rnd="AAAA")
        prefix2 = _make_prefix(rnd="BBBB")
        a = _make_base_payload(prefix=prefix1)
        b = _make_items_payload(prefix2)

        with self.assertRaises(ValueError):
            parse_taiwan_einvoice_qr_pair(a, b)

    def test_parse_pair_too_short(self) -> None:
        with self.assertRaises(ValueError):
            parse_taiwan_einvoice_qr_pair("short", "also_short")


class TestParseBestEffort(unittest.TestCase):
    def test_best_effort_accepts_qr2_marker(self) -> None:
        prefix = _make_prefix(inv_no="AB12345678", roc_date="1140103", rnd="1A2b")
        # Put items in QR1; QR2 is '**' marker (no continuation)
        a = _make_items_payload(prefix)
        inv = parse_taiwan_einvoice_qr_best_effort(a, "**   ")
        self.assertEqual(inv.invoice_number, "AB12345678")
        self.assertEqual(inv.invoice_date, date(2025, 1, 3))
        self.assertEqual(inv.random_number, "1A2b")
        self.assertEqual(inv.total_amount, 100)
        self.assertGreaterEqual(len(inv.items), 2)
        self.assertEqual(inv.items[0].name, "Milk")

    def test_best_effort_repairs_common_mojibake_item_name(self) -> None:
        # A realistic mojibake pattern we've observed in decoded QR payloads.
        # This string is CP932-looking text that can be repaired to readable Chinese.
        mojibake = "､E､GｵLｹ]"
        expected = "九二無鉛"

        prefix = _make_prefix(inv_no="UY17706158", roc_date="1141119", rnd="1A2b")
        base = _make_base_payload(prefix=prefix, total_hex="0000005F", buyer_id="00000000", seller_id="70576604")
        qr1 = base + f":{mojibake}:3.52:27.1"

        inv = parse_taiwan_einvoice_qr_best_effort(qr1, "**")
        self.assertGreaterEqual(len(inv.items), 1)
        self.assertEqual(inv.items[0].name, expected)


class _FakeResponse:
    def __init__(self, *, json_data=None, text: str = "", content_type: str = "application/json"):
        self._json_data = json_data
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_data


class TestMofEnrichment(unittest.TestCase):
    def _base_invoice(self) -> tuple[ParsedTaiwanEInvoice, str, str]:
        prefix = _make_prefix()
        qr_a = _make_base_payload(prefix=prefix)
        qr_b = _make_items_payload(prefix)
        inv = parse_taiwan_einvoice_qr_pair(qr_a, qr_b)
        return inv, qr_a, qr_b

    def test_enrich_network_failures_return_unchanged(self) -> None:
        inv, qr_a, qr_b = self._base_invoice()

        with patch("requests.post", side_effect=Exception("network down")):
            enriched, raw = enrich_from_mof_best_effort(
                inv,
                qr_a=qr_a,
                qr_b=qr_b,
                endpoint="https://example.invalid",
                app_id="dummy",
                api_key="dummy",
            )

        self.assertEqual(enriched, inv)
        self.assertEqual(raw, {})

    def test_enrich_first_http_response_is_error_code_returns_unchanged(self) -> None:
        # Important current behavior: the function stops at the first successful HTTP response
        # even if the API returns an error code like 904.
        inv, qr_a, qr_b = self._base_invoice()
        inv2 = replace(inv, seller_name="")

        fake = _FakeResponse(json_data={"code": 904, "msg": "錯誤的查詢種類"})
        with patch("requests.post", return_value=fake) as post:
            enriched, raw = enrich_from_mof_best_effort(
                inv2,
                qr_a=qr_a,
                qr_b=qr_b,
                endpoint="https://api.example",
                app_id="dummy",
                api_key="dummy",
            )

        self.assertEqual(post.call_count, 1)
        self.assertEqual(enriched, inv2)
        self.assertEqual(raw.get("code"), 904)

    def test_enrich_tries_next_payload_after_exception_and_applies_seller_and_items(self) -> None:
        inv, qr_a, qr_b = self._base_invoice()

        ok_payload = {
            "code": "200",
            "msg": "OK",
            "data": {
                "sellerName": "Test Shop",
                "items": [
                    {"name": "Tea", "quantity": "1", "unitPrice": "35"},
                    {"name": "Cake", "quantity": "2", "unitPrice": "50"},
                ],
            },
        }

        with patch(
            "requests.post",
            side_effect=[Exception("timeout"), _FakeResponse(json_data=ok_payload)],
        ) as post:
            enriched, raw = enrich_from_mof_best_effort(
                inv,
                qr_a=qr_a,
                qr_b=qr_b,
                endpoint="https://api.example",
                app_id="dummy",
                api_key="dummy",
            )

        self.assertGreaterEqual(post.call_count, 2)
        self.assertEqual(raw.get("code"), "200")
        self.assertEqual(enriched.seller_name, "Test Shop")
        self.assertEqual(
            enriched.items,
            (
                InvoiceItem(name="Tea", quantity=Decimal("1"), unit_price=Decimal("35")),
                InvoiceItem(name="Cake", quantity=Decimal("2"), unit_price=Decimal("50")),
            ),
        )

    def test_enrich_parses_non_json_content_type(self) -> None:
        inv, qr_a, qr_b = self._base_invoice()

        text = '{"code":"200","msg":"OK","result":{"sellerName":"X"}}'
        fake = _FakeResponse(json_data=None, text=text, content_type="text/plain")
        with patch("requests.post", return_value=fake):
            enriched, raw = enrich_from_mof_best_effort(
                inv,
                qr_a=qr_a,
                qr_b=qr_b,
                endpoint="https://api.example",
                app_id="dummy",
                api_key="dummy",
            )

        self.assertEqual(raw.get("code"), "200")
        self.assertEqual(enriched.seller_name, "X")


if __name__ == "__main__":
    unittest.main()
