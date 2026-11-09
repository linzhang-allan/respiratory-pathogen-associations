#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_RAW_DIR = Path('/data/zhangl/coinfection/rawdata_cleaned')
DEFAULT_RUN_DIR = Path('/data/zhangl/coinfection/codemulti_cleaned_data')


def parse_args():
    parser = argparse.ArgumentParser(description='Step3: 基于患者集合直接从 cleaned test csv 提取 exam.csv')
    parser.add_argument('--test-csv', default=str(DEFAULT_RAW_DIR / 'test_data.csv'))
    parser.add_argument('--patient-id-file', default=str(DEFAULT_RUN_DIR / '02_patient_set' / 'hospital_patient_ids.csv'))
    parser.add_argument('--output-dir', default=str(DEFAULT_RUN_DIR / '03_related_extract'))
    parser.add_argument('--chunksize', type=int, default=200000)
    parser.add_argument('--max-rows', type=int, default=0)
    return parser.parse_args()


def norm_text(series: pd.Series) -> pd.Series:
    s = series.fillna('').astype(str).str.strip()
    s = s.replace({'nan': '', 'None': '', '<NA>': '', 'NaN': ''})
    return s


def clean_patient_id(series: pd.Series) -> pd.Series:
    s = norm_text(series)
    s = s.str.replace(r'\.0$', '', regex=True)
    s = s.str.replace(r'\s+', '', regex=True)
    return s


def load_patient_index(patient_id_file: Path):
    df = pd.read_csv(patient_id_file, dtype=object, low_memory=False)
    if '患者编号' not in df.columns:
        raise ValueError(f'患者编号 column missing in {patient_id_file}')
    pid = clean_patient_id(df['患者编号'])
    valid = pid.str.len() > 0
    pid_set = set(pid[valid].tolist())
    return pid_set

def main():
    args = parse_args()
    test_csv = Path(args.test_csv)
    patient_id_file = Path(args.patient_id_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not test_csv.exists():
        raise FileNotFoundError(f'test csv not found: {test_csv}')
    if not patient_id_file.exists():
        raise FileNotFoundError(f'patient id file not found: {patient_id_file}')

    pid_set = load_patient_index(patient_id_file)
    exam_out = output_dir / 'exam.csv'
    summary_out = output_dir / 'summary.json'
    if exam_out.exists():
        exam_out.unlink()

    rows_in = 0
    rows_out = 0
    processed_rows = 0
    wrote_header = False
    needed_cols = {'patient_code', 'hospital_name', 'test_name_std', 'test_name', 'test_date', 'test_result', 'test_category', 'raw_id', 'created_at'}
    for chunk in pd.read_csv(test_csv, chunksize=args.chunksize, dtype=object, low_memory=False, usecols=lambda c: c in needed_cols):
        rows_in += len(chunk)
        if args.max_rows and processed_rows >= args.max_rows:
            break
        if args.max_rows and processed_rows + len(chunk) > args.max_rows:
            chunk = chunk.iloc[: args.max_rows - processed_rows].copy()

        patient_id = clean_patient_id(chunk['patient_code']) if 'patient_code' in chunk.columns else pd.Series([''] * len(chunk), index=chunk.index)
        hospital_name = norm_text(chunk['hospital_name']) if 'hospital_name' in chunk.columns else pd.Series([''] * len(chunk), index=chunk.index)
        pid_mask = patient_id.isin(pid_set)
        mask = pid_mask

        picked = chunk.loc[mask].copy()
        if picked.empty:
            processed_rows += len(chunk)
            continue

        test_name_std = norm_text(picked['test_name_std']) if 'test_name_std' in picked.columns else pd.Series([''] * len(picked), index=picked.index)
        test_name = norm_text(picked['test_name']) if 'test_name' in picked.columns else pd.Series([''] * len(picked), index=picked.index)
        out = pd.DataFrame(index=picked.index)
        out['医院名称'] = hospital_name.loc[picked.index]
        out['患者编号'] = patient_id.loc[picked.index]
        out['检查名称'] = test_name_std.where(test_name_std.ne(''), test_name)
        out['检查日期'] = norm_text(picked['test_date']) if 'test_date' in picked.columns else ''
        out['检查结果'] = norm_text(picked['test_result']) if 'test_result' in picked.columns else ''
        out['检查名称_原始'] = test_name
        out['检查类别'] = norm_text(picked['test_category']) if 'test_category' in picked.columns else ''
        out['原始行ID'] = norm_text(picked['raw_id']) if 'raw_id' in picked.columns else ''
        out['创建时间'] = norm_text(picked['created_at']) if 'created_at' in picked.columns else ''
        out = out.loc[out['患者编号'].str.len() > 0].copy()
        if out.empty:
            processed_rows += len(chunk)
            continue
        out.to_csv(exam_out, index=False, encoding='utf-8-sig', mode='a' if wrote_header else 'w', header=not wrote_header)
        wrote_header = True
        rows_out += len(out)
        processed_rows += len(chunk)

    if not exam_out.exists():
        pd.DataFrame(columns=['医院名称', '患者编号', '数据来源文件', '所属文件夹', '数据来源Sheet', '检查名称', '检查日期', '检查结果']).to_csv(exam_out, index=False, encoding='utf-8-sig')


    summary = {
        'test_csv': str(test_csv),
        'patient_id_file': str(patient_id_file),
        'output_dir': str(output_dir),
        'rows_in_test_csv': int(rows_in),
        'rows_out_exam_csv': int(rows_out),
        'matched_by_full_key': 0,
        'matched_by_pid_only': int(rows_out),
        'exam_csv': str(exam_out),
        'oxygen_removed': True,
    }
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[INFO] exam csv: {exam_out}')
    print(f'[INFO] summary: {summary_out}')


if __name__ == '__main__':
    main()
