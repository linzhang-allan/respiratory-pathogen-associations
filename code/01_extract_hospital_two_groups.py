#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import pandas as pd
import re

DEFAULT_RAW_DIR = Path('/data/zhangl/coinfection/rawdata_cleaned')
DEFAULT_RUN_DIR = Path('/data/zhangl/coinfection/codemulti_cleaned_data')
GROUP_ORDER = ['URTI', 'LRTI']

COLUMN_RENAME = {
    'hospital_name': '医院名称',
    'patient_code': '患者编号',
    'age': '年龄（周岁）',
    'sex': '性别',
    'visit_date': '就诊日期',
    'admit_date': '入院日期',
    'discharge_date': '出院日期',
    'department': '就诊科室',
    'icd_codes': '诊断（ICD编码）',
    'diagnosis_text': '诊断（文字）',
    'chief_complaint': '主诉',
    'present_illness': '现病史（临床症状）',
    'last_vaccine_date': '末次接种日期',
    'is_admitted': '是否收入院',
    'is_icu': '是否收入ICU',
    'icu_in_date': '入ICU日期',
    'icu_out_date': '出ICU日期',
    'is_death': '是否死亡',
    'death_diagnosis': '死亡诊断',
    'death_date': '死亡日期'
}

SPLIT_RE = re.compile(r'[;,，；、=|\s]+')


def parse_args():
    parser = argparse.ArgumentParser(description='Step1: 直接合并 cleaned inpatient/outpatient csv，生成 hospital_two_group.csv')
    parser.add_argument('--raw-dir', default=str(DEFAULT_RAW_DIR))
    parser.add_argument('--inpatient-csv', default='inpatient_data.csv')
    parser.add_argument('--outpatient-csv', default='outpatient_data.csv')
    parser.add_argument('--output-dir', default=str(DEFAULT_RUN_DIR / '01_hospital_two_group'))
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


def classify_icd_text(text: str):
    if not text:
        return set(), []
    text_norm = str(text).upper().replace(' ', '').replace('。', '.').replace('，', ',').replace('；', ';')
    tokens = re.findall(r'J\d{2}(?:\.\d+)?', text_norm)
    tokens = tokens + [tok for tok in SPLIT_RE.split(text_norm) if tok]
    groups = set()
    hit_codes = []
    for tok in tokens:
        if 'J' not in tok:
            continue
        urti_hit = any(f'J{i:02d}' in tok for i in range(0, 7)) or ('J10.1' in tok)
        lrti_hit = any(f'J{i:02d}' in tok for i in range(20, 23))
        pneumonia_hit = any(f'J{i:02d}' in tok for i in range(12, 19)) or ('J10.0' in tok) or ('J11.0' in tok)
        if urti_hit:
            groups.add('URTI')
            hit_codes.extend([f'J{i:02d}' for i in range(0, 7) if f'J{i:02d}' in tok])
            if 'J10.1' in tok:
                hit_codes.append('J10.1')
        if lrti_hit:
            groups.add('LRTI')
            hit_codes.extend([f'J{i:02d}' for i in range(20, 23) if f'J{i:02d}' in tok])
        if pneumonia_hit:
            groups.add('LRTI')
            hit_codes.extend([f'J{i:02d}' for i in range(12, 19) if f'J{i:02d}' in tok])
            if 'J10.0' in tok:
                hit_codes.append('J10.0')
            if 'J11.0' in tok:
                hit_codes.append('J11.0')
    return groups, sorted(set(hit_codes))


def derive_infection_group(icd_series: pd.Series):
    group_values = []
    hit_code_values = []
    for icd_text in icd_series.tolist():
        groups, hit_codes = classify_icd_text(icd_text)
        ordered = [g for g in GROUP_ORDER if g in groups]
        group_values.append(';'.join(ordered))
        hit_code_values.append(';'.join(hit_codes))
    return pd.Series(group_values, index=icd_series.index, dtype=object), pd.Series(hit_code_values, index=icd_series.index, dtype=object)


def prepare_chunk(chunk: pd.DataFrame, source_tag: str, source_csv_name: str) -> pd.DataFrame:
    chunk = chunk.rename(columns={c: COLUMN_RENAME.get(c, c) for c in chunk.columns})
    out = pd.DataFrame(index=chunk.index)

    for col in [
        '医院名称', '患者编号', '年龄（周岁）', '性别', '就诊日期', '入院日期', '出院日期', '就诊科室',
        '诊断（ICD编码）','是否收入院', '是否收入ICU', 
        '入ICU日期', '出ICU日期', '是否死亡', '感染分组', '命中ICD编码'
    ]:
        out[col] = norm_text(chunk[col]) if col in chunk.columns else ''

    out['患者编号'] = clean_patient_id(out['患者编号'])

    if source_tag == 'inpatient':
        out['是否收入院'] = out['是否收入院'].mask(out['是否收入院'].eq(''), '是')
        out['就诊日期'] = out['就诊日期'].mask(out['就诊日期'].eq(''), out['入院日期'])
    else:
        out['是否收入院'] = out['是否收入院'].mask(out['是否收入院'].eq(''), '否')

    infection_group, hit_codes = derive_infection_group(out['诊断（ICD编码）'])
    out['感染分组'] = infection_group
    out['命中ICD编码'] = hit_codes

    keep_cols = [
        '医院名称', '患者编号', '年龄（周岁）', '性别', '就诊日期', '入院日期', '出院日期', '就诊科室',
        '诊断（ICD编码）','是否收入院', '是否收入ICU', 
        '入ICU日期', '出ICU日期', '是否死亡', '感染分组', '命中ICD编码'
    ]
    return out[keep_cols]


def process_source_csv(input_csv: Path, source_tag: str, out_csv: Path, chunksize: int, max_rows: int):
    rows_in = 0
    rows_out = 0
    processed_rows = 0
    wrote_header = out_csv.exists() and out_csv.stat().st_size > 0
    group_counts = {'URTI': 0, 'LRTI': 0, 'UNKNOWN': 0}
    unique_patients = set()

    for chunk in pd.read_csv(input_csv, chunksize=chunksize, dtype=object, low_memory=False):
        rows_in += len(chunk)
        if max_rows and processed_rows >= max_rows:
            break
        if max_rows and processed_rows + len(chunk) > max_rows:
            chunk = chunk.iloc[: max_rows - processed_rows].copy()
        out = prepare_chunk(chunk, source_tag, input_csv.name)
        out = out.loc[out['患者编号'].str.len() > 0].copy()
        if out.empty:
            continue
        out.to_csv(out_csv, index=False, encoding='utf-8-sig', mode='a' if wrote_header else 'w', header=not wrote_header)
        wrote_header = True
        rows_out += len(out)
        processed_rows += len(chunk)
        unique_patients.update(out['患者编号'].tolist())
        for value, cnt in out['感染分组'].fillna('').replace({'': 'UNKNOWN'}).value_counts().to_dict().items():
            for part in str(value).split(';'):
                part = part or 'UNKNOWN'
                if part in group_counts:
                    group_counts[part] += int(cnt)
    return {
        'source_tag': source_tag,
        'input_csv': str(input_csv),
        'rows_in': int(rows_in),
        'rows_out': int(rows_out),
        'unique_patients': int(len(unique_patients)),
        'infection_group_counts': group_counts,
    }


def main():
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    inpatient_csv = raw_dir / args.inpatient_csv
    outpatient_csv = raw_dir / args.outpatient_csv
    if not inpatient_csv.exists():
        raise FileNotFoundError(f'inpatient csv not found: {inpatient_csv}')
    if not outpatient_csv.exists():
        raise FileNotFoundError(f'outpatient csv not found: {outpatient_csv}')

    out_csv = output_dir / 'hospital_two_group.csv'
    if out_csv.exists():
        out_csv.unlink()

    summaries = []
    summaries.append(process_source_csv(inpatient_csv, 'inpatient', out_csv, args.chunksize, args.max_rows))
    summaries.append(process_source_csv(outpatient_csv, 'outpatient', out_csv, args.chunksize, args.max_rows))

    combined = pd.read_csv(out_csv, dtype=object, low_memory=False)
    (output_dir / 'hospital_two_group_all_columns.txt').write_text('\n'.join(map(str, combined.columns.tolist())), encoding='utf-8')

    summary = {
        'raw_dir': str(raw_dir),
        'output_dir': str(output_dir),
        'hospital_csv': str(out_csv),
        'sources': summaries,
        'final_rows': int(len(combined)),
        'final_unique_patient_ids': int(combined['患者编号'].astype(str).nunique()),
        'final_unique_patient_keys': int(combined[['患者编号']].astype(str).drop_duplicates().shape[0]),
    }
    (output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[INFO] hospital csv: {out_csv}")
    print(f"[INFO] summary: {output_dir / 'summary.json'}")


if __name__ == '__main__':
    main()
