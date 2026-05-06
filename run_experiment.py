#!/usr/bin/env python3
"""Run the four README experiments and export CSV results."""

import argparse
from pathlib import Path

from dedup.experiments import (
    run_cdc_parameter_experiment,
    run_correctness_experiment,
    run_scale_experiment,
    run_scenario_comparison,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dedup experiments defined in README")
    parser.add_argument("--dataset-root", type=Path, default=Path("test_data"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--experiment",
        choices=["all", "correctness", "scenario", "cdc-params", "scale"],
        default="all",
    )
    parser.add_argument("--repeats", type=int, default=3, help="Repeat count for timing experiments")
    args = parser.parse_args()

    outputs = []
    if args.experiment in ("all", "correctness"):
        outputs.append(run_correctness_experiment(args.dataset_root, args.results_dir, repeats=1))
    if args.experiment in ("all", "scenario"):
        outputs.append(run_scenario_comparison(args.dataset_root, args.results_dir, repeats=args.repeats))
    if args.experiment in ("all", "cdc-params"):
        outputs.append(run_cdc_parameter_experiment(args.dataset_root, args.results_dir, repeats=args.repeats))
    if args.experiment in ("all", "scale"):
        outputs.append(run_scale_experiment(args.dataset_root, args.results_dir, repeats=args.repeats))

    print("Generated result files:")
    for output in outputs:
        print(f"  {output}")


if __name__ == "__main__":
    main()
