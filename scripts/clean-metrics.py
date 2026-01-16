#!/usr/bin/env python3
"""
Normalize Grafana-exported Hypha metrics CSVs for Typst plotting.

Given a base directory that contains run subdirectories (e.g. runs/faults/r600...),
this script extracts loss, round duration, log levels, RTT, and traffic metrics,
converts times to hours since the start of each run, normalizes units, and writes
combined CSVs under the output directory.

Usage:
    python report/tools/clean_metrics.py --source runs/faults --output report/clean/faults
"""

import argparse
import math
import os
from pathlib import Path
from turtle import Pen
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd

LOSS_PREFIX = "Loss-data"
ROUND_PREFIX = "Round Duration"
LOG_PREFIXES = (
    "Log by level-data-as-joinbyfield",
    "Log by level",
    "level-data",
    "Log by level-data",
)
RTT_PREFIX = "hypha_rtt_ms_milliseconds-data"
RTT_JOIN_PREFIX = "hypha_rtt_ms_milliseconds-data-as-joinbyfield"
TRAFFIC_PREFIX = "Network Traffic-data-as-joinbyfield"
TRAFFIC_BY_SERVICE_PREFIX = "Network Traffic (by Service)-data-as-joinbyfield"
SPEED_PREFIX = "Network Speed (by Service)-data-as-joinbyfield"

# Additional metrics
SLICE_REDIRECT_PREFIX = "Slice Redirect_h-data"
ROUNDS_PREFIX = "Rounds_h-data"
EVAL_RETURN_PREFIX = "Evaluation Return-data"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", required=True, help="Base directory containing run subdirectories"
    )
    ap.add_argument("--output", required=True, help="Output directory for cleaned CSVs")
    ap.add_argument(
        "--glob",
        default="r6*",
        help="Glob for selecting run subdirectories (default: r6*)",
    )
    return ap.parse_args()


def parse_duration_s(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    txt = str(val).strip()
    if not txt:
        return None
    if txt.endswith(" ms"):
        return float(txt[:-3].strip()) / 1000.0
    if txt.endswith(" s"):
        return float(txt[:-2].strip())
    if txt.endswith(" mins"):
        return float(txt[:-5].strip()) * 60.0
    if txt.endswith(" min"):
        return float(txt[:-4].strip()) * 60.0
    if txt.endswith(" h"):
        return float(txt[:-2].strip()) * 3600.0
    try:
        return float(txt)
    except ValueError:
        return None


def parse_count(val) -> float:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0.0
    txt = str(val).strip()
    if not txt:
        return 0.0
    if txt.endswith("K"):
        return float(txt[:-1].strip()) * 1000.0
    if txt.endswith("M"):
        return float(txt[:-1].strip()) * 1_000_000.0
    try:
        return float(txt)
    except ValueError:
        return 0.0


def parse_ms(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    txt = str(val).strip()
    if not txt:
        return None
    if txt.endswith(" ms"):
        return float(txt[:-3].strip())
    if txt.endswith(" s"):
        return float(txt[:-2].strip()) * 1000.0
    try:
        return float(txt)
    except ValueError:
        return None


def parse_speed_mbps(val) -> Optional[float]:
    """Parse speed values like '199 Mb/s', '4.76 kb/s' to Mb/s."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    txt = str(val).strip()
    if not txt:
        return None
    if txt.endswith(" Gb/s"):
        return float(txt[:-5].strip()) * 1000.0
    if txt.endswith(" Mb/s"):
        return float(txt[:-5].strip())
    if txt.endswith(" kb/s"):
        return float(txt[:-5].strip()) / 1000.0
    if txt.endswith(" b/s"):
        return float(txt[:-4].strip()) / 1_000_000.0
    try:
        return float(txt)
    except ValueError:
        return None


def parse_size_mb(val) -> Optional[float]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    txt = str(val).strip().replace(",", "")
    if not txt:
        return None
    # Normalize: handle both "1.5 GB" and "1.5GB" formats, case-insensitive
    txt_lower = txt.lower()
    if txt_lower.endswith("tb"):
        return float(txt[:-2].strip()) * 1024.0 * 1024.0
    if txt_lower.endswith("gb"):
        return float(txt[:-2].strip()) * 1024.0
    if txt_lower.endswith("mb"):
        return float(txt[:-2].strip())
    if txt_lower.endswith("kb"):
        return float(txt[:-2].strip()) / 1024.0
    if txt_lower.endswith("b"):
        return float(txt[:-1].strip()) / (1024.0 * 1024.0)
    try:
        return float(txt)
    except ValueError:
        return None


def find_first(run_dir: Path, prefix: str) -> Optional[Path]:
    print(f"Searching for prefixes {prefix} in {run_dir}")
    for p in sorted(run_dir.iterdir()):
        print(f"Checking file {p}: {prefix}")
        if p.name.startswith(prefix):
            return p
    return None


def find_first_in_list(run_dir: Path, prefixes: Iterable[str]) -> Optional[Path]:
    print(f"Searching for prefixes {prefixes} in {run_dir}")
    for pref in prefixes:
        p = find_first(run_dir, pref)
        if p:
            return p
    return None


def add_time_offset(df: pd.DataFrame, run: str) -> pd.DataFrame:
    if "Time" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    # Check if Time column contains epoch milliseconds (large integers)
    first_val = df["Time"].iloc[0]
    # Use pd.api.types to handle numpy integers properly
    if pd.api.types.is_number(first_val) and first_val > 1e12:
        # Epoch milliseconds
        df["Time"] = pd.to_datetime(df["Time"], unit="ms")
    else:
        df["Time"] = pd.to_datetime(df["Time"])
    df = df.sort_values("Time")
    t0 = df["Time"].iloc[0]
    df["t_hours"] = (df["Time"] - t0).dt.total_seconds() / 3600.0
    df["run"] = run
    return df


def clean_run(run_dir: Path) -> Dict[str, pd.DataFrame]:
    run = run_dir.name
    out: Dict[str, pd.DataFrame] = {}

    loss_file = find_first(run_dir, LOSS_PREFIX)
    print(f"Processing loss_file {loss_file}")
    if loss_file:
        df = pd.read_csv(loss_file)
        df = add_time_offset(df, run)
        if "Weighted Average" in df.columns:
            df = df[["run", "t_hours", "Weighted Average"]].rename(
                columns={"Weighted Average": "loss"}
            )
            df = df.dropna(subset=["loss"])
            out["loss"] = df
        else:
            # Join-by-field format: average across workers
            cols = [c for c in df.columns if c not in ("Time", "run", "t_hours")]
            if cols:
                for c in cols:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                df["loss"] = df[cols].mean(axis=1)
                df = df.dropna(subset=["loss"])
                out["loss"] = df[["run", "t_hours", "loss"]]

    round_file = find_first(run_dir, ROUND_PREFIX)
    print(f"Processing round_file {round_file}")
    if round_file:
        df = pd.read_csv(round_file)
        df = add_time_offset(df, run)
        if df.shape[1] >= 2:
            # Handle join-by-field format: average across worker columns
            cols = [c for c in df.columns if c not in ("Time", "run", "t_hours")]
            if cols:
                series = []
                for _, row in df.iterrows():
                    vals = [parse_duration_s(row[c]) for c in cols if pd.notna(row[c])]
                    vals = [v for v in vals if v is not None]
                    if not vals:
                        continue
                    series.append(
                        {
                            "run": run,
                            "t_hours": row["t_hours"],
                            "round_s": sum(vals) / len(vals),
                        }
                    )
                if series:
                    out["round"] = pd.DataFrame(series)
    else:
        # Compute round duration from Rounds_h (rounds per interval)
        rounds_file = find_first(run_dir, ROUNDS_PREFIX)
        if rounds_file:
            df = pd.read_csv(rounds_file)
            df = add_time_offset(df, run)
            if "Value" in df.columns and len(df) >= 2:
                # Compute interval in seconds from timestamps
                interval_s = (df["t_hours"].iloc[1] - df["t_hours"].iloc[0]) * 3600
                df["rounds_count"] = df["Value"].apply(parse_count)
                # Round duration = interval / rounds_per_interval
                df["round_s"] = df["rounds_count"].apply(
                    lambda r: interval_s / r if r > 0 else None
                )
                df = df.dropna(subset=["round_s"])
                out["round"] = df[["run", "t_hours", "round_s"]]

    log_file = find_first_in_list(run_dir, LOG_PREFIXES)
    print(f"Processing log_file {log_file}")
    if log_file:
        df = pd.read_csv(log_file)
        df = add_time_offset(df, run)
        if "error" in df.columns or "warn" in df.columns:
            err_col = next((c for c in df.columns if c.lower() == "error"), None)
            warn_col = next((c for c in df.columns if c.lower() == "warn"), None)
            if err_col or warn_col:
                df["errors"] = df[err_col].apply(parse_count) if err_col else 0.0
                df["warns"] = df[warn_col].apply(parse_count) if warn_col else 0.0
                out["logs"] = df[["run", "t_hours", "errors", "warns"]]

    rtt_file = find_first(run_dir, RTT_PREFIX)
    rtt_join_file = find_first(run_dir, RTT_JOIN_PREFIX)
    print(f"Processing rtt_file {rtt_file}")
    if rtt_file:
        df = pd.read_csv(rtt_file)
        df = add_time_offset(df, run)
        if df.shape[1] >= 2:
            val_col = df.columns[1]
            df["rtt_ms"] = df[val_col].apply(parse_ms)
            df = df.dropna(subset=["rtt_ms"])
            out["rtt"] = df[["run", "t_hours", "rtt_ms"]]
    elif rtt_join_file:
        df = pd.read_csv(rtt_join_file)
        df = add_time_offset(df, run)
        cols = [c for c in df.columns if c != "Time"]
        series = []
        for _, row in df.iterrows():
            vals = [parse_ms(row[c]) for c in cols if pd.notna(row[c])]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            series.append(
                {"run": run, "t_hours": row["t_hours"], "rtt_ms": sum(vals) / len(vals)}
            )
        if series:
            out["rtt"] = pd.DataFrame(series)

    traffic_file = find_first(run_dir, TRAFFIC_PREFIX)
    traffic_by_service_file = find_first(run_dir, TRAFFIC_BY_SERVICE_PREFIX)

    # Use regular traffic file if available, otherwise use by-service file
    if traffic_file:
        print(f"Processing traffic_file {traffic_file}")
        df = pd.read_csv(traffic_file)
        df = add_time_offset(df, run)
        in_col = next((c for c in df.columns if c.startswith("in:")), None)
        out_col = next((c for c in df.columns if c.startswith("out:")), None)
        sum_col = next((c for c in df.columns if c.startswith("sum:")), None)
        if in_col or out_col or sum_col:
            df["in_mb_raw"] = df[in_col].apply(parse_size_mb) if in_col else None
            df["out_mb_raw"] = df[out_col].apply(parse_size_mb) if out_col else None
            df["sum_mb_raw"] = df[sum_col].apply(parse_size_mb) if sum_col else None

            # Handle counter resets/drops: accumulate only positive deltas
            # When workers restart or go offline, we only count forward progress
            # Always start from zero (subtract initial baseline for hot workers)
            for col_raw, col_out in [
                ("in_mb_raw", "in_mb"),
                ("out_mb_raw", "out_mb"),
                ("sum_mb_raw", "sum_mb"),
            ]:
                if col_raw in df.columns and df[col_raw].notna().any():
                    values = df[col_raw].values
                    cumulative = []
                    total = 0.0
                    prev_val = None
                    baseline = None
                    for val in values:
                        if pd.isna(val):
                            cumulative.append(None)
                            continue
                        if baseline is None:
                            # First valid value becomes baseline - subtract it to start from zero
                            baseline = val
                        if prev_val is not None:
                            delta = val - prev_val
                            if delta > 0:
                                total += delta
                        # First value after baseline: total stays 0
                        cumulative.append(total)
                        prev_val = val
                    df[col_out] = cumulative
                else:
                    df[col_out] = None

            df = df.dropna(subset=["sum_mb"], how="all")
            out["traffic"] = df[["run", "t_hours", "in_mb", "out_mb", "sum_mb"]]
    elif traffic_by_service_file:
        # Handle "by Service" format - sum across worker columns
        df = pd.read_csv(traffic_by_service_file)
        df = add_time_offset(df, run)
        # Find in/out/sum columns for workers (exclude gateway, scheduler)
        in_cols = [
            c
            for c in df.columns
            if c.startswith("in:")
            and "gateway" not in c.lower()
            and "scheduler" not in c.lower()
        ]
        out_cols = [
            c
            for c in df.columns
            if c.startswith("out:")
            and "gateway" not in c.lower()
            and "scheduler" not in c.lower()
        ]
        sum_cols = [
            c
            for c in df.columns
            if c.startswith("sum:")
            and "gateway" not in c.lower()
            and "scheduler" not in c.lower()
        ]
        if sum_cols:
            series = []
            for _, row in df.iterrows():
                in_vals = [parse_size_mb(row[c]) for c in in_cols if pd.notna(row[c])]
                in_vals = [v for v in in_vals if v is not None]
                out_vals = [parse_size_mb(row[c]) for c in out_cols if pd.notna(row[c])]
                out_vals = [v for v in out_vals if v is not None]
                sum_vals = [parse_size_mb(row[c]) for c in sum_cols if pd.notna(row[c])]
                sum_vals = [v for v in sum_vals if v is not None]
                if not sum_vals:
                    continue
                series.append(
                    {
                        "run": run,
                        "t_hours": row["t_hours"],
                        "in_mb_raw": sum(in_vals) if in_vals else None,
                        "out_mb_raw": sum(out_vals) if out_vals else None,
                        "sum_mb_raw": sum(sum_vals),
                    }
                )
            if series:
                tdf = pd.DataFrame(series)
                # Apply counter reset handling for each metric
                # Always start from zero (subtract initial baseline for hot workers)
                for col_raw, col_out in [
                    ("in_mb_raw", "in_mb"),
                    ("out_mb_raw", "out_mb"),
                    ("sum_mb_raw", "sum_mb"),
                ]:
                    if col_raw in tdf.columns and tdf[col_raw].notna().any():
                        values = tdf[col_raw].values
                        cumulative = []
                        total = 0.0
                        prev_val = None
                        baseline = None
                        for val in values:
                            if pd.isna(val):
                                cumulative.append(None)
                                continue
                            if baseline is None:
                                # First valid value becomes baseline - subtract it to start from zero
                                baseline = val
                            if prev_val is not None:
                                delta = val - prev_val
                                if delta > 0:
                                    total += delta
                            # First value after baseline: total stays 0
                            cumulative.append(total)
                            prev_val = val
                        tdf[col_out] = cumulative
                    else:
                        tdf[col_out] = None
                out["traffic"] = tdf[["run", "t_hours", "in_mb", "out_mb", "sum_mb"]]

    # Network speed (by service) - sum across workers
    speed_file = find_first(run_dir, SPEED_PREFIX)
    if speed_file:
        df = pd.read_csv(speed_file)
        df = add_time_offset(df, run)
        # Exclude non-worker columns (scheduler, gateway)
        worker_cols = [
            c
            for c in df.columns
            if c not in ("Time", "run", "t_hours", "scheduler", "gateway1", "gateway")
        ]
        if worker_cols:
            series = []
            for _, row in df.iterrows():
                vals = [
                    parse_speed_mbps(row[c]) for c in worker_cols if pd.notna(row[c])
                ]
                vals = [v for v in vals if v is not None]
                if not vals:
                    continue
                series.append(
                    {
                        "run": run,
                        "t_hours": row["t_hours"],
                        "speed_mbps": sum(vals),
                    }
                )
            if series:
                out["speed"] = pd.DataFrame(series)

    # Slice redirect count (cumulative redirects over time)
    slice_redirect_file = find_first(run_dir, SLICE_REDIRECT_PREFIX)
    if slice_redirect_file:
        df = pd.read_csv(slice_redirect_file)
        df = add_time_offset(df, run)
        if "Value" in df.columns:
            df["redirects"] = df["Value"].apply(parse_count)
            df = df.dropna(subset=["redirects"])
            out["sliceredirect"] = df[["run", "t_hours", "redirects"]]

    # Rounds count (cumulative rounds over time)
    rounds_file = find_first(run_dir, ROUNDS_PREFIX)
    if rounds_file:
        df = pd.read_csv(rounds_file)
        df = add_time_offset(df, run)
        if "Value" in df.columns:
            df["rounds"] = df["Value"].apply(parse_count)
            df = df.dropna(subset=["rounds"])
            out["rounds"] = df[["run", "t_hours", "rounds"]]

    # Evaluation return (for RL / PPO experiments)
    eval_return_file = find_first(run_dir, EVAL_RETURN_PREFIX)
    if eval_return_file:
        df = pd.read_csv(eval_return_file)
        df = add_time_offset(df, run)
        # Handle both single-value and join-by-field formats
        if "Value" in df.columns:
            df["eval_return"] = pd.to_numeric(df["Value"], errors="coerce")
            df = df.dropna(subset=["eval_return"])
            out["eval_return"] = df[["run", "t_hours", "eval_return"]]
        elif df.shape[1] >= 2:
            # Join-by-field format: average across workers
            cols = [c for c in df.columns if c not in ("Time", "run", "t_hours")]
            if cols:
                for c in cols:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                df["eval_return"] = df[cols].mean(axis=1)
                df = df.dropna(subset=["eval_return"])
                out["eval_return"] = df[["run", "t_hours", "eval_return"]]

    return out


def main() -> None:
    args = parse_args()
    input_base = Path(args.root).expanduser()
    output_base = Path(args.output).expanduser()
    output_base.mkdir(parents=True, exist_ok=True)

    runs = sorted(input_base.glob(args.glob))
    if not runs:
        raise SystemExit(f"No run directories matched {args.glob} under {input_base}")

    for run_dir in runs:
        if not run_dir.is_dir():
            continue

        for key, df in clean_run(run_dir).items():
            print(f"Writing {run_dir.name}-{key}.csv")
            df.to_csv(output_base / f"{run_dir.name}-{key}.csv", index=False)

    print(f"Wrote cleaned metrics to {output_base}")


if __name__ == "__main__":
    main()
