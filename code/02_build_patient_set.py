#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import pandas as pd


def clean_patient_id(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    s = s.str.replace(r"\s+", "", regex=True)
    s = s.mask(s.str.contains(r"[\u4e00-\u9fff]", regex=True), "")
    s = s.replace({"nan": "", "None": "", "<NA>": "", "NaN": ""})
    return s


def parse_args():
    parser = argparse.ArgumentParser(description="Step2: 从 hospital 两组结果构建患者编号集合")
    parser.add_argument(
        "--hospital-csv",
        default="/data/zhangl/coinfection/codemulti_cleaned_data/01_hospital_two_group/hospital_two_group.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="/data/zhangl/coinfection/codemulti_cleaned_data/02_patient_set",
    )
    parser.add_argument("--chunksize", type=int, default=200000)
    return parser.parse_args()


def main():
    args = parse_args()
    hospital_csv = Path(args.hospital_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not hospital_csv.exists():
        raise FileNotFoundError(f"hospital csv not found: {hospital_csv}")

    patient_ids = set()
    rows_in = 0
    rows_missing_pid = 0
    usecols = {"患者编号", "感染分组"}

    for chunk in pd.read_csv(hospital_csv, chunksize=args.chunksize, dtype=object, low_memory=False, usecols=lambda c: c in usecols):
        rows_in += len(chunk)
        if "患者编号" not in chunk.columns:
            continue
        if "感染分组" in chunk.columns:
            infection_group = chunk["感染分组"].fillna("").astype(str).str.strip().str.upper()
            chunk = chunk.loc[(infection_group != "") & (infection_group != "UNKNOWN")].copy()
            if chunk.empty:
                continue
        pid = clean_patient_id(chunk["患者编号"])
        valid = pid.astype(str).str.len() > 0
        rows_missing_pid += int((~valid).sum())
        pid = pid[valid]

        patient_ids.update(pid.tolist())

    patient_ids_sorted = sorted(patient_ids)
    patient_file_df = pd.DataFrame({"患者编号": patient_ids_sorted}) if patient_ids_sorted else pd.DataFrame(columns=["患者编号"])

    patient_csv = out_dir / "hospital_patient_ids.csv"

    patient_file_df.to_csv(patient_csv, index=False, encoding="utf-8-sig")

    summary = {
        "hospital_csv": str(hospital_csv),
        "output_dir": str(out_dir),
        "rows_in_hospital": rows_in,
        "rows_missing_pid": int(rows_missing_pid),
        "unique_patient_ids": len(patient_ids_sorted),
        "unique_patient_file_pairs": int(len(patient_file_df)),
        "patient_csv": str(patient_csv)
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] step2 done summary={out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
