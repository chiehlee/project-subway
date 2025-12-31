from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import pandas as pd


DATE_COL_PATTERN = re.compile(r"^\d{1,2}/\d{1,2}$")
SKIP_NAMES = {"總時數", "加班1", "加班2", "正常時數", "當天總時數"}
REGULAR_EMPLOYEES = {"Stella", "鄭雅樺"}
COLOR_REGULAR = "#e6861a"  # orange
COLOR_PARTTIME = "#4e79a7"  # blue


@dataclass
class Shift:
    employee: str
    start: datetime
    end: datetime

    @property
    def duration_hours(self) -> float:
        delta = self.end - self.start
        return delta.total_seconds() / 3600


def format_hours(hours: float) -> str:
    """Render hours like 5 or 5.5 without trailing zeros."""
    text = f"{hours:.1f}".rstrip("0").rstrip(".")
    return f"{text}h"


def summarize_hours(shifts: List[Shift]) -> tuple[float, float, float]:
    """Return (regular_total, parttime_total, overall_total)."""
    reg = sum(s.duration_hours for s in shifts if s.employee in REGULAR_EMPLOYEES)
    pt = sum(s.duration_hours for s in shifts if s.employee not in REGULAR_EMPLOYEES)
    return reg, pt, reg + pt


def parse_hhmm(val: object) -> Optional[timedelta]:
    """Parse HH:MM strings like 9:00 or 7:30 into a timedelta from midnight."""
    if pd.isna(val):
        return None
    text = str(val).strip()
    if not text:
        return None
    match = re.match(r"^(?P<hour>\d{1,2})(:(?P<minute>\d{2}))?$", text)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    return timedelta(hours=hour, minutes=minute)


def collect_shifts(df: pd.DataFrame, year: int) -> Dict[str, List[Shift]]:
    """Return day->list[Shift] from the semi-structured sheet."""
    date_cols = [c for c in df.columns if DATE_COL_PATTERN.match(str(c))]
    if not date_cols:
        raise ValueError("No date columns found")

    # Month is taken from the first date column (e.g., 12/1 -> month 12).
    sample_month = int(str(date_cols[0]).split("/")[0])
    per_day: Dict[str, List[Shift]] = {col: [] for col in date_cols}
    day_order = sorted(
        [(col, datetime(year, sample_month, int(str(col).split('/')[1])).date()) for col in date_cols],
        key=lambda x: x[1],
    )

    for idx, name in df["姓名"].items():
        if pd.isna(name) or str(name) in SKIP_NAMES:
            continue
        # The next row contains the corresponding end times.
        if idx + 1 not in df.index:
            continue
        end_row = df.loc[idx + 1]
        for col in date_cols:
            start_td = parse_hhmm(df.at[idx, col])
            end_td = parse_hhmm(end_row[col])
            if not start_td or not end_td:
                continue
            # Skip if end precedes start.
            if end_td <= start_td:
                continue
            month_part, day_part = str(col).split("/")
            day = int(day_part)
            start_dt = datetime(year, sample_month, day) + start_td
            end_dt = datetime(year, sample_month, day) + end_td
            per_day[col].append(Shift(str(name), start_dt, end_dt))

    return per_day, day_order


def render_day(day_key: str, shifts: List[Shift], out_dir: Path) -> Optional[Path]:
    """Render a single-day Gantt chart to the output directory."""
    if not shifts:
        return None

    shifts = sorted(shifts, key=lambda s: (s.start, s.employee))
    y_positions = list(range(len(shifts)))
    fig_height = max(2.5, len(shifts) * 0.6)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    for y, shift in zip(y_positions, shifts):
        start_hours = shift.start.hour + shift.start.minute / 60
        color = COLOR_REGULAR if shift.employee in REGULAR_EMPLOYEES else COLOR_PARTTIME
        ax.barh(
            y,
            shift.duration_hours,
            left=start_hours,
            height=0.5,
            color=color,
            edgecolor="black",
        )
        label = f"{shift.employee} ({format_hours(shift.duration_hours)})"
        ax.text(
            start_hours + shift.duration_hours / 2,
            y,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=10,  # Slightly larger for readability inside bars
        )

    ax.set_xlabel("Hour of day", fontsize=8)
    ax.set_xlim(7, 23)
    ax.set_yticks([])
    major_hours = list(range(7, 24))
    ax.set_xticks(major_hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in major_hours])
    ax.tick_params(axis="x", which="major", labelrotation=0, labelsize=8, pad=4)

    reg_hours, pt_hours, total_hours = summarize_hours(shifts)
    summary = (
        f"Regular: {format_hours(reg_hours)}, "
        f"PT: {format_hours(pt_hours)}, "
        f"Total: {format_hours(total_hours)}"
    )
    ax.text(
        1.0,
        -0.18,
        summary,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        color="#444444",
    )

    day_date = shifts[0].start.date()
    weekday = day_date.strftime("%a")  # e.g., Mon, Tue
    title = f"{day_date} ({weekday}) shifts"
    ax.set_title(title, fontsize=8)
    ax.grid(axis="x", linestyle="--", linewidth=0.5, alpha=0.7)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{title.replace(' ', '_').replace(':', '-')}.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def draw_day_axes(ax, day_date: datetime.date, shifts: List[Shift]) -> None:
    """Draw a single day's chart on a provided axes (for weekly collage)."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    for y, shift in enumerate(sorted(shifts, key=lambda s: (s.start, s.employee))):
        start_hours = shift.start.hour + shift.start.minute / 60
        color = COLOR_REGULAR if shift.employee in REGULAR_EMPLOYEES else COLOR_PARTTIME
        ax.barh(
            y,
            shift.duration_hours,
            left=start_hours,
            height=0.5,
            color=color,
            edgecolor="black",
        )
        label = f"{shift.employee} ({format_hours(shift.duration_hours)})"
        ax.text(
            start_hours + shift.duration_hours / 2,
            y,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=10,
        )

    ax.set_xlim(7, 23)
    ax.set_yticks([])
    major_hours = list(range(7, 24))
    ax.set_xticks(major_hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in major_hours], fontsize=8)
    ax.tick_params(axis="x", which="major", labelrotation=0, labelsize=8, pad=2)

    reg_hours, pt_hours, total_hours = summarize_hours(shifts)
    summary = (
        f"Regular: {format_hours(reg_hours)}, "
        f"PT: {format_hours(pt_hours)}, "
        f"Total: {format_hours(total_hours)}"
    )
    ax.text(
        1.0,
        1.02,
        summary,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#444444",
    )

    weekday = day_date.strftime("%a")
    title = f"{day_date} ({weekday})"
    ax.set_title(title, fontsize=8, loc="left", pad=6)
    ax.grid(axis="x", linestyle="--", linewidth=0.4, alpha=0.5)


def render_week(
    week_index: int,
    day_tuples: List[tuple[str, datetime.date, List[Shift]]],
    out_dir: Path,
    month_label: str,
) -> Optional[Path]:
    """Render a weekly collage; one subplot per day (even if empty)."""
    if not day_tuples:
        return None

    heights = []
    for _, _, shifts in day_tuples:
        heights.append(max(1.2, len(shifts) * 0.45 + 0.8))
    fig_height = sum(heights)

    fig, axes = plt.subplots(
        len(day_tuples),
        1,
        figsize=(10, fig_height),
        sharex=True,
    )
    if len(day_tuples) == 1:
        axes = [axes]

    for ax, (day_key, day_date, shifts), h in zip(axes, day_tuples, heights):
        draw_day_axes(ax, day_date, shifts)
        ax.set_ylim(-0.6, max(len(shifts) - 0.4, 0.6))

    axes[-1].set_xlabel("Hour of day", fontsize=8)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month_label}-W{week_index}.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate per-day Gantt charts from the Google Sheet export."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(
            "/Users/chieh/Library/CloudStorage/Dropbox/subway/project-subway/data/working_hours/2025-12-googlesheet.csv"
        ),
        help="Path to the working-hours CSV exported from Google Sheets.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Year to use when constructing dates (month inferred from columns).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("project-subway/data/working_hours/2025-12-gantt"),
        help="Directory to write PNG charts.",
    )
    args = parser.parse_args()

    # Help matplotlib render Chinese text if available on the host.
    plt.rcParams["font.sans-serif"] = [
        "Arial Unicode MS",
        "Noto Sans CJK TC",
        "PingFang TC",
        "Microsoft JhengHei",
        "sans-serif",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    df = pd.read_csv(args.csv)
    per_day, day_order = collect_shifts(df, args.year)

    # Daily charts
    written = []
    for day_key, shifts in per_day.items():
        out_path = render_day(day_key, shifts, args.out)
        if out_path:
            written.append(out_path)

    # Weekly collages (chunks of 7 days starting from the first day in the month).
    weekly_out = args.out / "weekly"
    weekly_written = []
    month_label = day_order[0][1].strftime("%Y-%m") if day_order else "week"
    for i in range(0, len(day_order), 7):
        chunk = day_order[i : i + 7]
        week_idx = i // 7 + 1
        day_tuples = [(col, day_date, per_day.get(col, [])) for col, day_date in chunk]
        out_path = render_week(week_idx, day_tuples, weekly_out, month_label)
        if out_path:
            weekly_written.append(out_path)

    print(f"Wrote {len(written)} daily charts to {args.out.resolve()}")
    print(f"Wrote {len(weekly_written)} weekly charts to {weekly_out.resolve()}")


if __name__ == "__main__":
    main()
