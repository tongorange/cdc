#!/usr/bin/env python3
"""Run dedup experiments: fixed vs CDC, collect stats, save CSV and plots.
Run: python run_experiment.py
"""

import sys
import time
import csv
import shutil
from pathlib import Path

# Make sure we can import dedup modules
sys.path.insert(0, str(Path(__file__).parent))

from dedup.cli import store_file
from dedup.stats import collect_stats

# Configuration
TEST_FILES = [
    "base.bin",
    "same_as_base.bin",
    "inserted_prefix.bin",
    "inserted_middle.bin",
    "random.bin",
]
FIXED_PARAMS = {"chunking": "fixed", "chunk_size": 4096}
CDC_PARAMS = {
    "chunking": "cdc",
    "min_size": 2048,
    "avg_size": 4096,
    "max_size": 8192,
    "window_size": 48,
}
DATA_ROOT = Path("exp_data")
RESULTS_DIR = Path("results")
RESULTS_CSV = RESULTS_DIR / "experiment_results.csv"

def run_experiment():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # Write header
    with open(RESULTS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "method", "file", "file_size", "store_time_sec",
            "logical_size", "physical_size", "saving_ratio",
            "chunk_count_total", "chunk_count_unique"
        ])

    for method_name, params in [("fixed", FIXED_PARAMS), ("cdc", CDC_PARAMS)]:
        for fname in TEST_FILES:
            input_path = Path("test_data") / fname
            if not input_path.exists():
                print(f"SKIP: {input_path} missing. Run make_test_data.py first.")
                return

            data_dir = DATA_ROOT / f"{method_name}_{fname.replace('.bin','')}"
            if data_dir.exists():
                shutil.rmtree(data_dir)

            print(f"Running {method_name} on {fname} ...")
            start = time.time()
            store_res = store_file(input_path, data_dir, **params)
            elapsed = time.time() - start
            stats = collect_stats(data_dir)

            with open(RESULTS_CSV, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    method_name, fname, store_res["size"],
                    round(elapsed, 3), stats["logical_size"],
                    stats["physical_size"], round(stats["saving_ratio"], 4),
                    stats["chunk_count_total"], stats["chunk_count_unique"]
                ])
            print(f"  -> saving_ratio = {stats['saving_ratio']:.2%}, time = {elapsed:.3f}s")

    print(f"\nResults saved to {RESULTS_CSV}")

def plot_results():
    """Generate plots if pandas/matplotlib available."""
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
    except ImportError:
        print("Skipping plots: pandas or matplotlib not installed.")
        print("Install with: pip install pandas matplotlib")
        return

    df = pd.read_csv(RESULTS_CSV)
    out_dir = RESULTS_DIR / "figures"
    out_dir.mkdir(exist_ok=True)

    # Label mapping
    labels = {
        "base.bin": "Base",
        "same_as_base.bin": "Identical",
        "inserted_prefix.bin": "Prefix\nInsert",
        "inserted_middle.bin": "Middle\nInsert",
        "random.bin": "Random"
    }
    df["file_label"] = df["file"].map(labels)

    # 1. Saving ratio
    plt.figure(figsize=(8,5))
    for m in df["method"].unique():
        sub = df[df["method"]==m]
        plt.bar(sub["file_label"], sub["saving_ratio"], label=m, alpha=0.7)
    plt.ylabel("Saving Ratio")
    plt.title("Deduplication Saving Ratio")
    plt.legend()
    plt.ylim(0,1.05)
    plt.tight_layout()
    plt.savefig(out_dir/"saving_ratio_by_method.png", dpi=150)
    plt.close()

    # 2. Physical size (MB)
    plt.figure(figsize=(8,5))
    for m in df["method"].unique():
        sub = df[df["method"]==m]
        plt.bar(sub["file_label"], sub["physical_size"]/(1024*1024), label=m, alpha=0.7)
    plt.ylabel("Physical Storage (MB)")
    plt.title("Physical Storage Size")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir/"physical_size_by_method.png", dpi=150)
    plt.close()

    # 3. Store time
    plt.figure(figsize=(8,5))
    for m in df["method"].unique():
        sub = df[df["method"]==m]
        plt.bar(sub["file_label"], sub["store_time_sec"], label=m, alpha=0.7)
    plt.ylabel("Store Time (seconds)")
    plt.title("Storage Time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir/"store_time_by_method.png", dpi=150)
    plt.close()

    print(f"Plots saved in {out_dir}")

if __name__ == "__main__":
    run_experiment()
    plot_results()