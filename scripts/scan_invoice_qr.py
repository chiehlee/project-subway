"""Scan Taiwan e-invoice paper QR codes via webcam (macOS) and export TSV/CSV.

Workflow
- Open webcam
- Collect 2 distinct QR payloads from the same invoice
- Parse best-effort invoice fields
- Append a row to an output file

Output columns (Traditional Chinese):
時間	金額	發票編號	購買清單 (單價 x 數量)	類型	發票類型	賣方	賣方統一編號

Notes
- The QR payload does not always include seller name / exact time; this script
  defaults time to 00:00:00 and leaves seller name/category empty when missing.

Dependencies
- Python packages: opencv-python, pyzbar
- System (macOS): `brew install zbar` (required by pyzbar)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Any, Iterable


# When running `python scripts/scan_invoice_qr.py`, Python sets sys.path[0] to
# the scripts/ directory, not the repository root. Add repo root so we can
# import sibling packages like `utilities`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Taiwan e-invoice QR via webcam and export TSV/CSV")
    parser.add_argument(
        "--output",
        default="data/invoices/invoices.tsv",
        help="Output file path (default: data/invoices/invoices.tsv)",
    )
    parser.add_argument(
        "--format",
        choices=["tsv", "csv"],
        default="csv",
        help="Output delimiter format (default: csv)",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="OpenCV camera index (default: 0)",
    )
    parser.add_argument(
        "--input-dir",
        default="",
        help="If set, scan images in a directory (offline) instead of using the webcam.",
    )
    parser.add_argument(
        "--glob",
        default="*.png,*.jpg,*.jpeg,*.webp",
        help="Comma-separated glob(s) for --input-dir images (default: *.png,*.jpg,*.jpeg,*.webp)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Stop after N invoices are saved (0 = no limit)",
    )
    parser.add_argument(
        "--capture-dir",
        default="data/invoices/captures",
        help="Where to store captured frames (default: data/invoices/captures)",
    )
    parser.add_argument(
        "--debug-decode",
        action="store_true",
        help="Print privacy-safe decode summaries (length/hash/key-detected) to help debugging.",
    )

    # Default to allow saving from a single usable payload, because the right QR can be
    # a no-continuation marker ('**') or blank.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--allow-single",
        dest="allow_single",
        action="store_true",
        help=(
            "Allow saving when only 1 QR payload is usable (default: enabled). "
            "Useful when the right QR is blank/continuation-only or hard to decode."
        ),
    )
    group.add_argument(
        "--no-allow-single",
        dest="allow_single",
        action="store_false",
        help="Disable single-payload saving (require a locally-parseable pair).",
    )
    parser.set_defaults(allow_single=True)
    return parser.parse_args()


def _mask_invoice_key(key: str) -> str:
    s = (key or "").strip()
    if len(s) < 21:
        return "<invalid>"
    inv = s[:10]
    roc = s[10:17]
    rnd = s[17:21]
    # AB12345678 -> AB******78
    inv_mask = inv[:2] + "******" + inv[-2:]
    roc_mask = roc[:3] + "****"
    rnd_mask = "***" + rnd[-1:]
    return f"{inv_mask}{roc_mask}{rnd_mask}"


def _debug_decode_summary(texts: list[str]) -> None:
    """Print privacy-safe summary of decoded texts.

    Avoid printing raw payloads (may contain item names or identifiers).
    """
    import hashlib

    from utilities.tw_einvoice_qr import dedupe_keep_order, invoice_key_from_qr

    texts = dedupe_keep_order(texts)
    if not texts:
        log_info("[debug] decoded_texts=0")
        return

    log_info(f"[debug] decoded_texts={len(texts)}")
    for i, t in enumerate(texts[:8]):
        s_raw = t or ""
        s_trim = s_raw.strip()
        h = hashlib.sha256(s_raw.encode("utf-8", errors="ignore")).hexdigest()[:10]
        k = invoice_key_from_qr(s_raw)
        if k:
            log_info(
                f"[debug] hit[{i}] len={len(s_raw)} trim_len={len(s_trim)} colons={s_raw.count(':')} key={_mask_invoice_key(k)} sha={h}"
            )
        else:
            log_info(
                f"[debug] hit[{i}] len={len(s_raw)} trim_len={len(s_trim)} colons={s_raw.count(':')} key=<none> sha={h}"
            )


HEADERS = [
    "時間",
    "金額",
    "發票編號",
    "購買清單 (單價 x 數量)",
    "類型",
    "發票類型",
    "賣方",
    "賣方統一編號",
]


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}")


def log_error(message: str) -> None:
    print(f"[ERROR] {message}")


def append_row(path: Path, row: list[str], delimiter: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        if write_header:
            writer.writerow(HEADERS)
        writer.writerow(row)


def decode_qr_texts_offline(image_bgr: Any) -> list[str]:
    """Heavier decode for a captured still frame (more preprocessing + fallbacks)."""
    hits: list[str] = []
    seen: set[str] = set()

    def _add_text(t: str) -> None:
        # Preserve raw payload (including potential padding).
        s_raw = t or ""
        if not s_raw or not s_raw.strip():
            return
        if s_raw in seen:
            return
        seen.add(s_raw)
        hits.append(s_raw)

    # 1) OpenCV with multiple preprocessing variants
    try:
        import cv2

        def _roi_variants(img):
            """Generate region-of-interest crops.

            Taiwan e-invoice paper usually prints the two QRs near the bottom.
            Cropping and splitting can dramatically improve decode reliability.
            """
            rois = []
            try:
                h, w = img.shape[:2]
                if h and w:
                    # Full frame
                    rois.append(img)

                    # Full-frame left/right halves
                    mid_full = int(w * 0.50)
                    rois.append(img[:, 0:mid_full])
                    rois.append(img[:, mid_full:w])

                    # Bottom portions
                    rois.append(img[int(h * 0.35) : h, 0:w])
                    rois.append(img[int(h * 0.50) : h, 0:w])

                    # Split bottom portion into left/right halves
                    y0 = int(h * 0.50)
                    mid = int(w * 0.50)
                    bottom = img[y0:h, 0:w]
                    rois.append(bottom[:, 0:mid])
                    rois.append(bottom[:, mid:w])

                    # Slightly wider center crop (handles off-center framing)
                    x0 = int(w * 0.10)
                    x1 = int(w * 0.90)
                    rois.append(img[y0:h, x0:x1])
            except Exception:
                rois.append(img)

            # Add rotated variants (webcam captures often have slight rotations)
            try:
                rotated = []
                for r in rois:
                    rotated.append(r)
                    try:
                        rotated.append(cv2.rotate(r, cv2.ROTATE_90_CLOCKWISE))
                        rotated.append(cv2.rotate(r, cv2.ROTATE_180))
                        rotated.append(cv2.rotate(r, cv2.ROTATE_90_COUNTERCLOCKWISE))
                    except Exception:
                        pass
                rois = rotated
            except Exception:
                pass
            return rois

        # 0) Preferred: ZXing (many scanner apps use ZXing; handles hard QRs well)
        try:
            import zxingcpp  # type: ignore

            def _zxing_read(mat, *, pure: bool = False):
                return zxingcpp.read_barcodes(
                    mat,
                    formats=zxingcpp.BarcodeFormat.QRCode,
                    try_rotate=not pure,
                    try_downscale=True,
                    text_mode=zxingcpp.TextMode.HRI,
                    binarizer=zxingcpp.Binarizer.LocalAverage,
                    is_pure=pure,
                )

            # 0a) Detect QR corners with OpenCV, warp to square, then run ZXing in pure mode.
            # This helps when the QR is detected but normal decode returns garbage.
            try:
                detector_pts = cv2.QRCodeDetector()
                try:
                    ok_pts, pts = detector_pts.detectMulti(image_bgr)
                except Exception:
                    ok_pts, _decoded, pts, _ = detector_pts.detectAndDecodeMulti(image_bgr)

                if ok_pts and pts is not None:
                    for quad in pts:
                        try:
                            import numpy as np

                            q = np.array(quad, dtype="float32")
                            # expected 4 points
                            if q.shape[0] != 4:
                                continue
                            size = 900
                            dst = np.array(
                                [[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]],
                                dtype="float32",
                            )
                            M = cv2.getPerspectiveTransform(q, dst)
                            warped = cv2.warpPerspective(image_bgr, M, (size, size))
                            warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
                            # extra upscales help when each QR is small
                            for fx in (1.0, 1.5, 2.0):
                                try:
                                    g = warped_gray if fx == 1.0 else cv2.resize(
                                        warped_gray, None, fx=fx, fy=fx, interpolation=cv2.INTER_CUBIC
                                    )
                                except Exception:
                                    g = warped_gray
                                for r in _zxing_read(g, pure=True):
                                    _add_text(getattr(r, "text", "") or "")
                                if len(hits) >= 2:
                                    return hits
                        except Exception:
                            continue
            except Exception:
                pass

            for roi in _roi_variants(image_bgr):
                try:
                    # Try both grayscale and original ROI
                    candidates = []
                    if len(getattr(roi, "shape", ())) == 3:
                        try:
                            candidates.append(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY))
                        except Exception:
                            pass
                        candidates.append(roi)
                    else:
                        candidates.append(roi)

                    for cand in candidates:
                        results = _zxing_read(cand, pure=False)
                        for r in results:
                            _add_text(getattr(r, "text", "") or "")
                    if len(hits) >= 2:
                        return hits
                except Exception:
                    continue
        except Exception:
            pass

        def _variants(img):
            out = []
            # Try multiple ROIs first
            for roi in _roi_variants(img):
                out.append(roi)
                try:
                    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                except Exception:
                    gray = None
                if gray is not None:
                    out.append(gray)

                # upscale
                try:
                    out.append(cv2.resize(roi, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC))
                except Exception:
                    pass
                if gray is not None:
                    try:
                        out.append(cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC))
                    except Exception:
                        pass

                if gray is not None:
                    try:
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                        eq = clahe.apply(gray)
                        out.append(eq)
                        out.append(
                            cv2.adaptiveThreshold(
                                eq, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
                            )
                        )

                        blur = cv2.GaussianBlur(eq, (0, 0), 1.0)
                        sharp = cv2.addWeighted(eq, 1.8, blur, -0.8, 0)
                        out.append(sharp)
                    except Exception:
                        pass
            return out

        detector = cv2.QRCodeDetector()
        for var in _variants(image_bgr):
            try:
                ok, decoded, points, _ = detector.detectAndDecodeMulti(var)
                if not ok or not decoded or points is None:
                    continue
                for txt, _pts in zip(decoded, points):
                    _add_text(txt or "")
                if len(hits) >= 2:
                    return hits
            except Exception:
                continue
    except Exception:
        pass

    # 3) Fallback: pyzbar (silence stderr warning spam)
    try:
        import contextlib
        import os

        from pyzbar.pyzbar import ZBarSymbol, decode

        with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull):
            # Only decode QR codes to avoid picking up 1D barcodes on invoices
            # (which often yield very short strings and confuse debugging).
            decoded_objs = decode(image_bgr, symbols=[ZBarSymbol.QRCODE])

        for obj in decoded_objs:
            try:
                text = obj.data.decode("utf-8", errors="replace")
            except Exception:
                text = str(obj.data)
            _add_text(text or "")
    except Exception:
        pass

    return hits


def _pick_invoice_pair_from_texts(texts: list[str]) -> tuple[str, str, str] | None:
    """Pick a usable (qr_a, qr_b, key) from decoded texts.

    Prefer grouping by invoice_key (21-char prefix). If that fails (e.g., one QR
    doesn't pass strict validation), try all pairs and accept the first that parses.
    """
    from utilities.tw_einvoice_qr import dedupe_keep_order, invoice_key_from_qr, parse_taiwan_einvoice_qr_best_effort

    texts = dedupe_keep_order(texts)

    grouped: dict[str, list[str]] = {}
    for text in texts:
        k = invoice_key_from_qr(text)
        if not k:
            continue
        grouped.setdefault(k, []).append(text)

    for k, payloads in grouped.items():
        payloads = dedupe_keep_order(payloads)
        if len(payloads) < 2:
            continue
        ordered = sorted(payloads, key=lambda s: s.count(":"), reverse=True)
        return ordered[0], ordered[1], k

    # Fallback: brute force pairs
    candidates = sorted(texts, key=lambda s: s.count(":"), reverse=True)
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            try:
                inv = parse_taiwan_einvoice_qr_best_effort(a, b)
            except Exception:
                continue
            k = invoice_key_from_qr(a) or invoice_key_from_qr(b) or inv.invoice_number
            return a, b, k

    return None


def _stash_add_texts(stash: dict[str, list[str]], texts: list[str], *, context_key: str = "") -> list[str]:
    """Add decoded texts into stash grouped by invoice key.

    Returns list of keys that were updated.
    """
    from utilities.tw_einvoice_qr import dedupe_keep_order, invoice_key_from_qr

    updated: list[str] = []

    deduped = dedupe_keep_order(texts)
    keys_in_batch = dedupe_keep_order([invoice_key_from_qr(t) for t in deduped if invoice_key_from_qr(t)])
    inferred_key = ""
    if len(keys_in_batch) == 1:
        inferred_key = keys_in_batch[0]
    elif context_key and (context_key in stash or len(stash) <= 1):
        inferred_key = context_key
    elif len(stash) == 1:
        inferred_key = next(iter(stash.keys()))

    for t in deduped:
        k = invoice_key_from_qr(t) or inferred_key
        if not k:
            continue
        if k not in stash:
            stash[k] = []
        before = len(stash[k])
        stash[k] = dedupe_keep_order([*stash[k], t])
        # keep memory bounded (allow a bit more since we may keep an unkeyed QR2)
        stash[k] = stash[k][:6]
        if len(stash[k]) != before:
            updated.append(k)
    return updated


def _stash_pick_ready_pair(stash: dict[str, list[str]], prefer_key: str = "") -> tuple[str, str, str] | None:
    """Pick a ready (qr_a, qr_b, key) from stash.

    A key is "ready" only if we can form a locally-parseable pair. Unkeyed payloads
    (e.g. '**' + padding) are still kept in stash but do not
    count as "ready" by themselves.
    """
    from utilities.tw_einvoice_qr import dedupe_keep_order

    keys = list(stash.keys())
    if prefer_key and prefer_key in stash:
        keys.remove(prefer_key)
        keys.insert(0, prefer_key)

    for k in keys:
        payloads = dedupe_keep_order(stash.get(k, []))
        if len(payloads) < 2:
            continue
        picked = _pick_invoice_pair_from_texts(payloads)
        if picked is not None:
            return picked[0], picked[1], k
    return None


def _stash_pick_best_for_single(stash: dict[str, list[str]], key: str) -> tuple[str, str] | None:
    """Pick (qr_a, qr_b) for --allow-single.

    - qr_a: prefer a payload that contains an invoice key (header QR)
    - qr_b: prefer an unkeyed payload, especially one that starts with '**'

    This is meant as a best-effort save path when a locally-parseable pair is unavailable.
    """
    from utilities.tw_einvoice_qr import dedupe_keep_order, invoice_key_from_qr

    payloads = dedupe_keep_order(stash.get(key, []))
    if not payloads:
        return None

    keyed = [p for p in payloads if invoice_key_from_qr(p)]
    unkeyed = [p for p in payloads if not invoice_key_from_qr(p)]

    qr_a_candidates = keyed or payloads
    qr_a = sorted(qr_a_candidates, key=lambda s: s.count(":"), reverse=True)[0]

    b_candidates: list[str] = []
    b_candidates.extend(unkeyed)
    b_candidates.extend([p for p in payloads if p != qr_a])

    if b_candidates:
        qr_b = sorted(b_candidates, key=lambda s: (s.lstrip().startswith("**"), s.count(":")), reverse=True)[0]
    else:
        qr_b = qr_a

    return qr_a, qr_b


def invoice_to_row(inv) -> list[str]:
    return [
        inv.timestamp_str(),
        inv.amount_str(),
        inv.invoice_number_str(),
        inv.items_str(),
        inv.category or "",
        inv.invoice_type or "",
        inv.seller_name or "",
        inv.seller_identifier or "",
    ]


def run_webcam(args: argparse.Namespace) -> None:
    try:
        import cv2
    except Exception as e:
        raise RuntimeError(
            "OpenCV not installed. Run: `poetry add opencv-python` (and `poetry install`)."
        ) from e

    def _silence_opencv_logs() -> None:
        # OpenCV QR decoder can emit noisy warnings (e.g., ECI not supported properly).
        # These are usually non-fatal and don't affect successful decodes.
        try:
            if hasattr(cv2, "setLogLevel") and hasattr(cv2, "LOG_LEVEL_ERROR"):
                cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
                return
        except Exception:
            pass
        try:
            logging = getattr(cv2, "utils", None)
            if logging is not None and hasattr(logging, "logging"):
                # type: ignore[attr-defined]
                logging.logging.setLogLevel(logging.logging.LOG_LEVEL_ERROR)
        except Exception:
            pass

    def _request_best_camera_resolution(cap: "cv2.VideoCapture") -> None:
        """Best-effort: request the highest supported resolution.

        OpenCV doesn't reliably expose the list of supported modes across drivers.
        We try a descending list of common modes and keep the highest that sticks.
        """

        candidates: list[tuple[int, int]] = [
            (7680, 4320),  # 8K
            (5120, 2880),  # 5K
            (4096, 2160),  # DCI 4K
            (3840, 2160),  # UHD 4K
            (2560, 1440),
            (1920, 1080),
            (1600, 1200),
            (1280, 720),
        ]

        def _try_set(w: int, h: int) -> tuple[int, int]:
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(w))
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(h))
            except Exception:
                return 0, 0

            # Prefer real frame dimensions (more reliable than CAP_PROP getters).
            try:
                ok, frm = cap.read()
                if ok and frm is not None and hasattr(frm, "shape"):
                    hh, ww = frm.shape[:2]
                    return int(ww), int(hh)
            except Exception:
                pass

            try:
                ww = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                hh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                return ww, hh
            except Exception:
                return 0, 0

        best = (0, 0)
        for w, h in candidates:
            ww, hh = _try_set(w, h)
            if ww * hh > best[0] * best[1]:
                best = (ww, hh)
            # If driver gave us at least what we asked, stop early.
            if ww >= w and hh >= h:
                break

        if best != (0, 0):
            log_info(f"Camera resolution: {best[0]}x{best[1]}")

    output_path = Path(args.output)
    delimiter = "\t" if args.format == "tsv" else ","

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(
            "Cannot open webcam. Check macOS Camera permission for your terminal/VS Code, "
            "or try a different --camera index (e.g., 1)."
        )

    _silence_opencv_logs()

    # Ask for the highest supported resolution to improve offline QR decoding success rate.
    _request_best_camera_resolution(cap)

    log_info("Webcam opened. Show the invoice QR codes to the camera.")
    log_info("Keys: [c] capture+decode, [s] save, [r] reset, [q] quit")

    # Stash payloads across multiple captures (helps when each capture only decodes one QR).
    stash: dict[str, list[str]] = {}

    # Avoid duplicate saves of the same invoice key in a single session.
    saved_keys: set[str] = set()

    # Current (latest decoded) invoice key + selected pair
    current_key: str = ""
    current_pair: tuple[str, str] | None = None
    saved = 0
    last_frame = None
    capture_dir = Path(args.capture_dir)
    capture_dir.mkdir(parents=True, exist_ok=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            log_warn("Failed to read frame from webcam")
            continue

        last_frame = frame

        # overlay status
        gray = (160, 160, 160)
        green = (0, 255, 0)
        ready = current_pair is not None
        cv2.putText(
            frame,
            "QR: 2/2" if ready else "QR: 0/2",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            green if ready else gray,
            2,
        )

        # Capture hint
        cv2.putText(frame, "Press 'c' to capture", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.imshow("scan_invoice_qr", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("r"):
            current_key = ""
            current_pair = None
            stash = {}
            log_info("Reset current invoice capture")
            continue

        if key == ord("c"):
            if last_frame is None:
                continue
            try:
                from datetime import datetime

                ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            except Exception:
                ts = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}"
            # Save lossless to avoid JPEG artifacts hurting QR decoding.
            out_path = capture_dir / f"invoice_capture_{ts}.png"
            try:
                cv2.imwrite(str(out_path), last_frame)
                log_info(f"Captured frame: {out_path}")
            except Exception as e:
                log_warn(f"Capture save failed: {e}")

            # Run heavier decoding on the still frame
            offline_texts = decode_qr_texts_offline(last_frame)
            if args.debug_decode:
                _debug_decode_summary(offline_texts)
            if not offline_texts:
                log_warn("Offline decode found no QR")
                continue

            updated_keys = _stash_add_texts(stash, offline_texts, context_key=current_key)
            prefer = updated_keys[0] if updated_keys else current_key

            # In single-invoice webcam mode, treat the most recent key as context
            # to help stash unkeyed QR2 payloads across subsequent captures.
            if not current_key and updated_keys:
                # Only set if it looks unambiguous.
                if len(set(updated_keys)) == 1:
                    current_key = updated_keys[0]
            ready = _stash_pick_ready_pair(stash, prefer_key=prefer)
            if ready is None:
                # Not enough yet; keep accumulating.
                if updated_keys:
                    k = updated_keys[0]
                    log_info(f"Stashed payload(s) for invoice key {k} ({len(stash.get(k, []))}/2)")
                else:
                    keys_seen = _keys_seen_from_texts(offline_texts)
                    if keys_seen:
                        k = keys_seen[0]
                        log_info(f"Decoded e-invoice payload already stashed for invoice key {k} ({len(stash.get(k, []))}/2)")
                    else:
                        log_warn("Offline decode returned QR(s) but none looked like e-invoice payload")
                continue

            qr_a, qr_b, chosen_key = ready
            current_key = chosen_key
            current_pair = (qr_a, qr_b)
            log_info(f"Offline decode ready (2/2) for invoice key {chosen_key}")
            continue

        if key == ord("s"):
            qr_a = ""
            qr_b = ""
            if current_key and current_pair:
                qr_a, qr_b = current_pair
            else:
                # If allowed, try saving with a single payload from stash.
                if args.allow_single and stash:
                    # Prefer current_key if available, else any key.
                    k = current_key if current_key in stash else next(iter(stash.keys()))
                    picked = _stash_pick_best_for_single(stash, k)
                    if picked is None:
                        log_warn("Nothing to save yet. Press 'c' to capture+decode first.")
                        continue
                    qr_a, qr_b = picked
                    current_key = k
                else:
                    log_warn("Nothing to save yet. Press 'c' to capture+decode first.")
                    continue

            try:
                from utilities.tw_einvoice_qr import parse_taiwan_einvoice_qr_best_effort

                if current_key and current_key in saved_keys:
                    log_warn(f"Already saved invoice key {current_key} in this session; skipping")
                    continue

                inv = parse_taiwan_einvoice_qr_best_effort(qr_a, qr_b)
                preview = "\t".join(invoice_to_row(inv))
                log_info("Parsed invoice (preview):")
                print(preview)
                append_row(output_path, invoice_to_row(inv), delimiter=delimiter)
                saved += 1
                if current_key:
                    saved_keys.add(current_key)
                log_info(f"Saved to {output_path} (count={saved})")
                # Reset after a successful save
                current_key = ""
                current_pair = None
                stash = {}
            except Exception as e:
                log_warn(f"Parse/save failed: {e}")

            if args.max and saved >= args.max:
                log_info(f"Reached --max={args.max}; stopping")
                break

    cap.release()
    cv2.destroyAllWindows()


def iter_image_files(input_dir: Path, patterns: str) -> Iterable[Path]:
    globs = [p.strip() for p in (patterns or "").split(",") if p.strip()]
    seen: set[Path] = set()
    for g in globs:
        for p in sorted(input_dir.glob(g)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p


def _keys_seen_from_texts(texts: list[str]) -> list[str]:
    from utilities.tw_einvoice_qr import dedupe_keep_order, invoice_key_from_qr

    keys_seen = [invoice_key_from_qr(t) for t in dedupe_keep_order(texts)]
    return [k for k in keys_seen if k]


def run_input_dir(args: argparse.Namespace) -> None:
    try:
        import cv2
    except Exception as e:
        raise RuntimeError("OpenCV not installed. Run: `poetry add opencv-python`. ") from e

    # Silence OpenCV warning spam in batch mode too.
    try:
        if hasattr(cv2, "setLogLevel") and hasattr(cv2, "LOG_LEVEL_ERROR"):
            cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
    except Exception:
        pass

    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        raise RuntimeError(f"--input-dir not found or not a directory: {input_dir}")

    input_dir_resolved = input_dir.resolve()

    def _delete_bad_image(p: Path) -> None:
        try:
            if p.is_symlink():
                return
            rp = p.resolve()
            try:
                rp.relative_to(input_dir_resolved)
            except Exception:
                return
            rp.unlink(missing_ok=True)
            log_info(f"Deleted bad image (no payload): {p}")
        except Exception as e:
            log_warn(f"Failed to delete bad image {p}: {e}")

    output_path = Path(args.output)
    delimiter = "\t" if args.format == "tsv" else ","

    from utilities.tw_einvoice_qr import parse_taiwan_einvoice_qr_best_effort

    saved = 0
    stash: dict[str, list[str]] = {}
    saved_keys: set[str] = set()

    for path in iter_image_files(input_dir, args.glob):
        img = cv2.imread(str(path))
        if img is None:
            log_warn(f"Skip unreadable image: {path}")
            continue

        texts = decode_qr_texts_offline(img)
        if args.debug_decode:
            log_info(f"[debug] file={path}")
            _debug_decode_summary(texts)
        updated_keys = _stash_add_texts(stash, texts)
        if not updated_keys:
            keys_seen = _keys_seen_from_texts(texts)
            if keys_seen:
                k = keys_seen[0]
                log_info(f"Decoded e-invoice payload already stashed for invoice key {k} ({len(stash.get(k, []))}/2)")
            else:
                log_warn(f"No e-invoice payload detected in: {path}")
                _delete_bad_image(path)
            continue

        # Save any invoices that became complete after this image.
        saved_any = False
        while True:
            ready = _stash_pick_ready_pair(stash, prefer_key=updated_keys[0])
            if ready is None:
                break

            qr_a, qr_b, k = ready
            if k in saved_keys:
                log_warn(f"Already saved invoice key {k} in this run; skipping")
                stash.pop(k, None)
                saved_any = True
                continue
            try:
                inv = parse_taiwan_einvoice_qr_best_effort(qr_a, qr_b)
                append_row(output_path, invoice_to_row(inv), delimiter=delimiter)
                saved += 1
                saved_any = True
                saved_keys.add(k)
                log_info(f"Saved invoice key {k} (count={saved})")
                # Clear this key to avoid duplicate saves.
                stash.pop(k, None)
            except Exception as e:
                log_warn(f"Parse/save failed for invoice key {k}: {e}")
                # Avoid infinite loops on a bad pair.
                stash.pop(k, None)

        if not saved_any:
            # Still incomplete; keep stashing.
            k = updated_keys[0]
            log_info(f"Stashed payload(s) for invoice key {k} ({len(stash.get(k, []))}/2)")

        if args.max and saved >= args.max:
            log_info(f"Reached --max={args.max}; stopping")
            break

    if stash:
        # Summarize incomplete invoices (best-effort; do not dump payload content)
        for k, payloads in list(stash.items())[:10]:
            log_warn(f"Incomplete invoice key {k} (payloads={len(payloads)}/2)")

        # Optional: save header-only rows for incomplete keys.
        if args.allow_single:
            try:
                from utilities.tw_einvoice_qr import parse_taiwan_einvoice_qr_best_effort

                for k, payloads in list(stash.items()):
                    picked = _stash_pick_best_for_single(stash, k)
                    if picked is None:
                        continue
                    qr_a, qr_b = picked
                    inv = parse_taiwan_einvoice_qr_best_effort(qr_a, qr_b)
                    append_row(output_path, invoice_to_row(inv), delimiter=delimiter)
                    saved += 1
                    log_info(f"Saved header-only invoice key {k} (count={saved})")
            except Exception as e:
                log_warn(f"Header-only save failed: {e}")

def main() -> None:
    args = parse_args()
    try:
        if args.input_dir:
            run_input_dir(args)
        else:
            run_webcam(args)
    except ModuleNotFoundError as e:
        log_error(str(e))
        if "pyzbar" in str(e) or "zbar" in str(e) or "cv2" in str(e):
            log_error("Missing dependency. Try: `brew install zbar` then `poetry add pyzbar opencv-python`.")
        elif "utilities" in str(e):
            log_error("Cannot import local package 'utilities'. Run from repo root, or keep the sys.path bootstrap at top of this script.")
        else:
            log_error("Missing module. Install dependencies and try again.")
        sys.exit(2)
    except RuntimeError as e:
        log_error(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
