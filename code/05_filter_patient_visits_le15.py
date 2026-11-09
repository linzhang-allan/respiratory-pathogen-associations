#!/usr/bin/env python3
"""Keep visits for patients with no more than a specified number of visits.

This reproduces the patient-frequency filter in
``/data/zhangl/coinfection/codemulti_cleaned_data/data_sel.ipynb``.
"""

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT_CSV = Path(
    "/data/zhangl/coinfection/codemulti_cleaned_data/04_clean_hospital/"
    "hospital_three_group_clean.csv"
)
DEFAULT_OUTPUT_CSV = Path(
    "/data/zhangl/coinfection/codemulti_cleaned_data/04_clean_hospital/"
    "hospital_two_group_clean_visit_below15.csv"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter out patients with more than N visits."
    )
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--max-visits", type=int, default=15)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.max_visits < 1:
        raise ValueError("--max-visits must be at least 1")
    if not args.input_csv.is_file():
        raise FileNotFoundError(f"Input CSV not found: {args.input_csv}")

    visits = pd.read_csv(args.input_csv)
    if "患者编号" not in visits.columns:
        raise ValueError(f"Column '患者编号' not found in {args.input_csv}")

    patient_counts = visits["患者编号"].value_counts()
    eligible_patient_ids = patient_counts[
        patient_counts <= args.max_visits
    ].index
    filtered_visits = visits[
        visits["患者编号"].isin(eligible_patient_ids)
    ].copy()

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    filtered_visits.to_csv(args.output_csv, index=False)

    print(f"Input rows: {len(visits):,}")
    print(f"Input patients: {visits['患者编号'].nunique():,}")
    print(f"Maximum visits per patient: {args.max_visits}")
    print(f"Retained rows: {len(filtered_visits):,}")
    print(f"Retained patients: {filtered_visits['患者编号'].nunique():,}")
    print(f"Output: {args.output_csv}")


if __name__ == "__main__":
    main()
