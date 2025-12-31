#!/usr/bin/env python3
# scripts/fetch_weather_info.py

import os
import sys
import json
import gzip
import datetime as dt
import time
import xml.etree.ElementTree as ET
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import requests
import pandas as pd

BASE = "https://opendata.cwa.gov.tw"
HISTORY_S3_BASE = "https://cwaopendata.s3.ap-northeast-1.amazonaws.com/history/Observation"
TZ_TW = dt.timezone(dt.timedelta(hours=8))

API_KEY = os.getenv("CWA_API_KEY")
COUNTY = os.getenv("CWA_COUNTY", "臺北市").strip()
TOWN = os.getenv("CWA_TOWN", "北投區").strip()
DAYS = int(os.getenv("CWA_DAYS", "8"))  # past 7 + today

INSECURE_SSL = os.getenv("CWA_INSECURE_SSL", "0").strip() in ("1", "true", "TRUE", "yes", "YES")
VERIFY = not INSECURE_SSL

SESSION = requests.Session()

# Cache downloaded history files to avoid re-downloading on every run.
# Default: data/weather/cwa (relative to repo root when running from project root).
CACHE_DIR = Path(os.getenv("CWA_CACHE_DIR", "data/weather/cwa")).expanduser()
NEGATIVE_CACHE_TTL_SECONDS = int(os.getenv("CWA_CACHE_NEGATIVE_TTL_SECONDS", str(6 * 60 * 60)))

# runtime cache stats
cache_hit = 0
cache_miss = 0
cache_saved = 0
cache_neg_hit = 0

# Find stationId from realtime 10-min dataset (works for you)
CURRENT_DATA_ID = os.getenv("CWA_CURRENT_DATA_ID", "O-A0003-001").strip()

# Hourly obs history dataset (temperature/humidity/wind/etc.)
HISTORY_DATA_ID = os.getenv("CWA_HISTORY_DATA_ID", "O-A0001-001").strip()

# -----------------------
def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def sanitize_url(u: str) -> str:
    """Remove secrets from URLs before printing to logs."""
    try:
        parts = urlsplit(u)
        if not parts.query:
            return u
        q = [(k, ("***" if k.lower() == "authorization" else v)) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
    except Exception:
        # best-effort
        return u.replace("Authorization=", "Authorization=***")

def req(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 60) -> requests.Response:
    return SESSION.get(url, params=params, timeout=timeout, verify=VERIFY)

def datastore_url(data_id: str) -> str:
    return f"{BASE}/api/v1/rest/datastore/{data_id}"

def history_metadata_url(data_id: str) -> str:
    # per dev guide: /historyapi/v1/getMetadata/{dataid}?Authorization=...   [oai_citation:2‡Open Data CWA](https://opendata.cwa.gov.tw/devManual/insrtuction?utm_source=chatgpt.com)
    return f"{BASE}/historyapi/v1/getMetadata/{data_id}"

def iso_plus0800(t: dt.datetime) -> str:
    # HistoryAPI commonly uses +0800 format in examples
    return t.strftime("%Y-%m-%dT%H:%M:%S%z")

def iso_no_tz(t: dt.datetime) -> str:
    # HistoryAPI also commonly accepts timestamps without timezone suffix.
    # Use local Asia/Taipei wall clock time.
    return t.strftime("%Y-%m-%dT%H:%M:%S")

def req_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    max_attempts: int = 4,
    base_sleep_s: float = 0.8,
) -> requests.Response:
    """GET with small retry/backoff for transient CWA outages (5xx/429)."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = req(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            return r
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts:
                break
            time.sleep(base_sleep_s * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc

def _cache_key_for_url(u: str) -> str:
    """Create a stable filename key for cached payloads.

    - S3 history URLs already include a stable filename.
    - historyapi getData URLs are path-based; convert to a stable filename.
    """
    parts = urlsplit(u)
    path = parts.path

    # S3 history: .../history/Observation/<stamp>.<suffix>
    if "cwaopendata.s3." in parts.netloc and "/history/Observation/" in path:
        name = Path(path).name
        return name

    # History API getData: /historyapi/v1/getData/<dataid>/YYYY/MM/DD/HH/MM/SS
    if "/historyapi/v1/getData/" in path:
        seg = [s for s in path.split("/") if s]
        try:
            idx = seg.index("getData")
            dataid = seg[idx + 1]
            y, m, d, hh, mm, ss = seg[idx + 2: idx + 8]
            return f"{dataid}_{y}{m}{d}{hh}{mm}{ss}.xml"
        except Exception:
            pass

    # Fallback: use last path component
    name = Path(path).name or "payload"
    if "." not in name:
        name = name + ".bin"
    return name

def _negative_marker_path(key: str) -> Path:
    return CACHE_DIR / (key + ".missing")

def _is_negative_cached(key: str) -> bool:
    global cache_neg_hit
    if NEGATIVE_CACHE_TTL_SECONDS <= 0:
        return False
    marker = _negative_marker_path(key)
    if not marker.exists():
        return False
    try:
        age = time.time() - marker.stat().st_mtime
    except Exception:
        return False
    if age <= NEGATIVE_CACHE_TTL_SECONDS:
        cache_neg_hit += 1
        return True
    return False

def _touch_negative_marker(key: str) -> None:
    if NEGATIVE_CACHE_TTL_SECONDS <= 0:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _negative_marker_path(key).touch()
    except Exception:
        pass

def _clear_negative_marker(key: str) -> None:
    try:
        _negative_marker_path(key).unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        try:
            p = _negative_marker_path(key)
            if p.exists():
                p.unlink()
        except Exception:
            pass

def _cache_path(key: str) -> Path:
    return CACHE_DIR / key

def generate_observation_s3_urls(start_local: dt.datetime, end_local: dt.datetime) -> List[str]:
    """Generate per-hour Observation history URLs from CWA's public S3 history bucket.

    The filenames are UTC timestamps like YYYYMMDDHHMM.<suffix>.
    For station observations, the default suffix observed via History API redirects is:
    `QPESUMS_AUTO_STATION.10M.xml`.
    """
    suffix = os.getenv("CWA_HISTORY_S3_SUFFIX", "QPESUMS_AUTO_STATION.10M.xml").strip()
    step_minutes = int(os.getenv("CWA_HISTORY_STEP_MINUTES", "60"))
    if step_minutes <= 0:
        step_minutes = 60

    urls: List[str] = []
    t = start_local
    end_inclusive = end_local
    while t <= end_inclusive:
        t_utc = t.astimezone(dt.timezone.utc)
        stamp = t_utc.strftime("%Y%m%d%H%M")
        urls.append(f"{HISTORY_S3_BASE}/{stamp}.{suffix}")
        t += dt.timedelta(minutes=step_minutes)
    return urls

# -----------------------
def find_station_id_by_county_town() -> Tuple[str, str]:
    # Allow explicit override
    forced_station_id = os.getenv("CWA_STATION_ID", "").strip()

    url = datastore_url(CURRENT_DATA_ID)
    r = req(url, params={"Authorization": API_KEY, "format": "JSON"})
    r.raise_for_status()
    data = r.json()

    stations = data.get("records", {}).get("Station", [])
    if not isinstance(stations, list) or not stations:
        die("Current dataset returned no records.Station")

    # Candidates in the requested County/Town.
    # Prefer a lower-altitude station (more like downtown) unless user overrides.
    candidates: List[Dict[str, Any]] = []
    for st in stations:
        geo = (st.get("GeoInfo") or {})
        sid = str(st.get("StationId", "")).strip()
        if forced_station_id and sid == forced_station_id:
            return (st.get("StationName", ""), sid)
        if geo.get("CountyName") != COUNTY or geo.get("TownName") != TOWN:
            continue

        alt_raw = geo.get("StationAltitude") or geo.get("StationHeight") or geo.get("Altitude")
        try:
            altitude_m = float(alt_raw)
        except Exception:
            altitude_m = None

        lat = lon = None
        for c in (geo.get("Coordinates") or []):
            name = str(c.get("CoordinateName", "")).lower()
            if name.startswith("wgs84") or name == "wgs84":
                lat = c.get("StationLatitude")
                lon = c.get("StationLongitude")
                break
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            lat_f = lon_f = None

        candidates.append({
            "name": st.get("StationName", ""),
            "id": sid,
            "altitude_m": altitude_m,
            "lat": lat_f,
            "lon": lon_f,
        })

    if forced_station_id:
        die(f"CWA_STATION_ID={forced_station_id} not found in {CURRENT_DATA_ID}")

    if not candidates:
        die(f"No station found for {COUNTY}{TOWN} in {CURRENT_DATA_ID}")

    # If multiple candidates exist, choose by nearest to target lat/lon if provided.
    target_lat = os.getenv("CWA_TARGET_LAT", "").strip()
    target_lon = os.getenv("CWA_TARGET_LON", "").strip()
    try:
        tlat = float(target_lat) if target_lat else None
        tlon = float(target_lon) if target_lon else None
    except Exception:
        tlat = tlon = None

    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    chosen = None
    if tlat is not None and tlon is not None:
        with_coords = [c for c in candidates if c["lat"] is not None and c["lon"] is not None]
        if with_coords:
            chosen = min(with_coords, key=lambda c: haversine_km(tlat, tlon, c["lat"], c["lon"]))

    if chosen is None:
        # Prefer lowest altitude when available
        with_alt = [c for c in candidates if c["altitude_m"] is not None]
        chosen = min(with_alt, key=lambda c: c["altitude_m"]) if with_alt else candidates[0]

    return (chosen["name"], chosen["id"])

def extract_urls_from_metadata(meta: Any) -> List[str]:
    """
    getMetadata response schema can vary; we extract any value that looks like a download URL.
    """
    urls: List[str] = []

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and v.startswith("http"):
                    urls.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(meta)
    # de-dup preserve order
    out: List[str] = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def download_and_parse_json(url: str) -> Dict[str, Any]:
    # Backward-compatible wrapper: history getData is often XML.
    kind, payload = download_and_parse_payload(url)
    if kind != "json":
        raise ValueError(f"Expected JSON but got {kind} from {url}")
    return payload

def download_and_parse_payload(url: str) -> Tuple[str, Any]:
    """Download and parse either JSON or XML payload."""
    global cache_hit, cache_miss, cache_saved

    key = _cache_key_for_url(url)
    cache_path = _cache_path(key)

    # Negative cache for known-missing timestamps (e.g., S3 404)
    if _is_negative_cached(key):
        resp = requests.Response()
        resp.status_code = 404
        resp.url = url
        raise requests.HTTPError("HTTP 404", response=resp)

    # Positive cache
    if cache_path.exists():
        cache_hit += 1
        content = cache_path.read_bytes()
    else:
        cache_miss += 1
        r = req_with_retry(url, timeout=120)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            if getattr(e, "response", None) is not None and e.response.status_code == 404:
                _touch_negative_marker(key)
            raise
        content = r.content
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(content)
            cache_saved += 1
            _clear_negative_marker(key)
        except Exception:
            # If caching fails, continue without breaking the run
            pass

    is_gzip = url.endswith(".gz") or content[:2] == b"\x1f\x8b"
    if is_gzip:
        content = gzip.decompress(content)

    sniff = content.lstrip()[:1]
    if sniff == b"<":
        # XML (history getData default)
        try:
            text = content.decode("utf-8")
        except Exception:
            text = content.decode("utf-8-sig")
        return "xml", text

    # JSON
    try:
        return "json", json.loads(content.decode("utf-8"))
    except Exception:
        return "json", json.loads(content.decode("utf-8-sig"))

def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]

def _child(parent: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    if parent is None:
        return None
    for ch in list(parent):
        if _strip_ns(ch.tag) == name:
            return ch
    return None

def _child_text(parent: Optional[ET.Element], name: str) -> Optional[str]:
    ch = _child(parent, name)
    if ch is None:
        return None
    return (ch.text or "").strip()

def extract_station_rows_from_xml(xml_text: str, station_id: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    rows: List[Dict[str, Any]] = []

    for st in root.iter():
        if _strip_ns(st.tag) != "Station":
            continue
        sid = (_child_text(st, "StationId") or "").strip()
        if sid != station_id:
            continue

        obs_time_el = _child(st, "ObsTime")
        obs_time = _child_text(obs_time_el, "DateTime")

        we = _child(st, "WeatherElement")
        now = _child(we, "Now") if we is not None else None

        rows.append({
            "datetime": obs_time,
            "weather": _child_text(we, "Weather"),
            "temp_c": _child_text(we, "AirTemperature"),
            "rh_pct": _child_text(we, "RelativeHumidity"),
            "pressure_hpa": _child_text(we, "AirPressure"),
            "wind_dir_deg": _child_text(we, "WindDirection"),
            "wind_speed_ms": _child_text(we, "WindSpeed"),
            "precip_mm": _child_text(now, "Precipitation"),
        })
    return rows

def extract_station_rows(payload: Dict[str, Any], station_id: str) -> List[Dict[str, Any]]:
    stations = payload.get("records", {}).get("Station", [])
    if not isinstance(stations, list):
        return []

    rows: List[Dict[str, Any]] = []
    for st in stations:
        if str(st.get("StationId", "")).strip() != station_id:
            continue

        obs_time = (st.get("ObsTime") or {}).get("DateTime")
        we = (st.get("WeatherElement") or {})
        now = (we.get("Now") or {})

        rows.append({
            "datetime": obs_time,
            "weather": we.get("Weather"),
            "temp_c": we.get("AirTemperature"),
            "rh_pct": we.get("RelativeHumidity"),
            "pressure_hpa": we.get("AirPressure"),
            "wind_dir_deg": we.get("WindDirection"),
            "wind_speed_ms": we.get("WindSpeed"),
            "precip_mm": now.get("Precipitation"),
        })
    return rows

def _weather_to_simple(w: Optional[str]) -> Optional[str]:
    if not w:
        return None
    w = str(w).strip()
    if not w or w == "-99":
        return None
    if "雨" in w:
        return "雨"
    if "晴" in w:
        return "晴"
    if ("雲" in w) or ("陰" in w):
        return "多雲"
    return None

def _mode_simple(series: pd.Series) -> Optional[str]:
    vals = [v for v in series.tolist() if isinstance(v, str) and v]
    if not vals:
        return None
    counts: Dict[str, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    # tie-break priority
    priority = {"雨": 3, "晴": 2, "多雲": 1}
    return sorted(counts.items(), key=lambda kv: (kv[1], priority.get(kv[0], 0)), reverse=True)[0][0]

def _display_width(s: str) -> int:
    """Approximate terminal display width (CJK wide chars count as 2)."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w

def _pad_right(s: str, width: int) -> str:
    pad = width - _display_width(s)
    if pad <= 0:
        return s
    return s + (" " * pad)

def render_grid_table(headers: List[str], rows: List[List[Any]]) -> str:
    s_headers = ["" if h is None else str(h) for h in headers]
    s_rows = [["" if v is None else str(v) for v in row] for row in rows]
    widths = [_display_width(h) for h in s_headers]
    for row in s_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _display_width(cell))

    def sep(char_h: str = "-", char_cross: str = "+") -> str:
        return char_cross + char_cross.join(char_h * (w + 2) for w in widths) + char_cross

    out: List[str] = []
    out.append(sep())
    out.append("|" + "|".join(f" {_pad_right(s_headers[i], widths[i])} " for i in range(len(s_headers))) + "|")
    out.append(sep())
    for row in s_rows:
        out.append("|" + "|".join(f" {_pad_right(row[i], widths[i])} " for i in range(len(s_headers))) + "|")
    out.append(sep())
    return "\n".join(out)

# -----------------------
def main() -> None:
    if not API_KEY:
        die('Missing API key. export CWA_API_KEY="CWA-..."')

    now = dt.datetime.now(TZ_TW)

    # History hourly datasets may not have the current partial hour available.
    # To avoid server-side errors, query up to the latest full hour.
    end = now.replace(minute=0, second=0, microsecond=0)
    start = (end - dt.timedelta(days=DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    station_name, station_id = find_station_id_by_county_town()

    print(f"📍 StationName : {station_name}")
    print(f"🆔 StationId   : {station_id}")
    print(f"📌 Location    : {COUNTY}{TOWN}\n")
    print(f"🗓️  Range: {start.isoformat()}  ~  {end.isoformat()}")
    print(f"🔐 SSL verify: {'ON' if VERIFY else 'OFF (CWA_INSECURE_SSL=1)'}")
    print(f"🧾 History dataset: {HISTORY_DATA_ID} (hourly obs)")  #  [oai_citation:3‡Open Data CWA](https://opendata.cwa.gov.tw/opendatadoc/Observation/O-A0001-001.pdf?utm_source=chatgpt.com)
    print("-" * 100)

    # 1) getMetadata -> urls
    meta_url = history_metadata_url(HISTORY_DATA_ID)
    base_params = {
        "Authorization": API_KEY,
        "format": "JSON",
    }
    # CWA history API is picky; try the most compatible timestamp formats.
    meta: Dict[str, Any]
    last_err: Optional[Exception] = None
    for tf, tt in (
        (iso_no_tz(start), iso_no_tz(end)),
        (iso_plus0800(start), iso_plus0800(end)),
    ):
        params = dict(base_params)
        params.update({"timeFrom": tf, "timeTo": tt})
        try:
            mr = req_with_retry(meta_url, params=params)
            mr.raise_for_status()
            meta = mr.json()
            break
        except Exception as e:
            last_err = e
    else:
        raise last_err  # type: ignore[misc]

    urls = extract_urls_from_metadata(meta)

    # The History API window for some datasets is only ~24h. If it doesn't cover the
    # requested DAYS range, fall back to public S3 history files (UTC timestamped).
    expected_hours = int((end - start).total_seconds() // 3600) + 1
    use_s3 = os.getenv("CWA_USE_S3_HISTORY", "").strip().lower() in ("1", "true", "yes")
    if not urls or len(urls) < min(expected_hours, 24):
        use_s3 = True

    if use_s3:
        urls = generate_observation_s3_urls(start, end)
        print(f"🧩 Source: S3 history ({len(urls)} files @ {int(os.getenv('CWA_HISTORY_STEP_MINUTES','60'))} min step)")
    else:
        print(f"🧩 Source: History API getMetadata ({len(urls)} files)")

    # 2) download each file, extract station rows
    all_rows: List[Dict[str, Any]] = []
    missing_files_404 = 0
    other_failures = 0
    for u in urls:
        try:
            kind, payload = download_and_parse_payload(u)
            if kind == "xml":
                rows = extract_station_rows_from_xml(payload, station_id)
            else:
                rows = extract_station_rows(payload, station_id)
            all_rows.extend(rows)
        except Exception as e:
            # S3 history has occasional missing timestamps; treat 404 as normal missing data.
            if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
                if e.response.status_code == 404:
                    missing_files_404 += 1
                    continue
            other_failures += 1
            print(f"WARN: failed to download/parse {sanitize_url(u)}: {e}", file=sys.stderr)

    if not all_rows:
        die(
            "Downloaded history files but found no station rows.\n"
            "Tip: print meta URLs and inspect file schema; stationId may be absent in this data slice."
        )

    df = pd.DataFrame(all_rows)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime")

    # local filter (just in case files include wider range)
    df = df[(df["datetime"] >= start) & (df["datetime"] <= end)].copy()

    # numeric coercion
    for c in ["temp_c", "rh_pct", "pressure_hpa", "wind_dir_deg", "wind_speed_ms", "precip_mm"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # CWA sometimes uses sentinel values (e.g. -99) for missing observations.
    df = df.replace({-99: pd.NA, -999: pd.NA, -99.0: pd.NA, -999.0: pd.NA})

    df["precip_mm"] = df["precip_mm"].fillna(0.0)
    df["date"] = df["datetime"].dt.date
    df["weather_simple"] = df["weather"].map(_weather_to_simple)

    daily = (
        df.groupby("date", as_index=False)
          .agg(
              weather=("weather_simple", _mode_simple),
              temp_max_c=("temp_c", "max"),
              temp_min_c=("temp_c", "min"),
              temp_avg_c=("temp_c", "mean"),
              rh_avg_pct=("rh_pct", "mean"),
              precip_total_mm=("precip_mm", "sum"),
              samples=("datetime", "count"),
          )
          .sort_values("date")
    )

    for c in ["temp_max_c", "temp_min_c", "temp_avg_c", "rh_avg_pct", "precip_total_mm"]:
        daily[c] = pd.to_numeric(daily[c], errors="coerce").round(2)

    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 50)

    print(f"Files processed:                 {len(urls)}")
    print(f"Rows collected for station:       {len(df)}")
    print(f"Cache (hit/miss/saved/404-skip):  {cache_hit}/{cache_miss}/{cache_saved}/{cache_neg_hit}")
    print("-" * 100)

    # Chinese headers
    daily_cn = daily.rename(
        columns={
            "date": "日期",
            "weather": "天氣",
            "temp_max_c": "最高溫(°C)",
            "temp_min_c": "最低溫(°C)",
            "temp_avg_c": "平均溫(°C)",
            "rh_avg_pct": "平均濕度(%)",
            "precip_total_mm": "累積雨量(mm)",
            "samples": "筆數",
        }
    )
    # Ensure stable string formatting
    daily_cn["日期"] = daily_cn["日期"].astype(str)
    for c in ["最高溫(°C)", "最低溫(°C)", "平均溫(°C)", "平均濕度(%)", "累積雨量(mm)"]:
        if c in daily_cn.columns:
            daily_cn[c] = pd.to_numeric(daily_cn[c], errors="coerce").round(2)
            daily_cn[c] = daily_cn[c].map(lambda x: "" if pd.isna(x) else ("{:.2f}".format(float(x)).rstrip("0").rstrip(".")))

    print("=== 過去{}天(含今天)天氣摘要 ===".format(DAYS))
    headers = list(daily_cn.columns)
    rows = daily_cn.values.tolist()
    print(render_grid_table(headers, rows))

    if missing_files_404:
        print(f"\n缺檔(404): {missing_files_404}")
    if other_failures:
        print(f"其他下載/解析失敗: {other_failures}")

if __name__ == "__main__":
    main()