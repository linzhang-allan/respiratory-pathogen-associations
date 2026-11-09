#!/usr/bin/env python3
import argparse
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("future.no_silent_downcasting", True)


NA_SET = {"", "nan", "none", "null", "<na>", "nat", "na", "99", "99.0"}

COLUMNS_MAP = {
    "年龄": "年龄（周岁）",
    "科室": "就诊科室",
    "目前科室": "就诊科室",
    "入院时间": "入院日期",
    "收入时间": "入院日期",
    "出院时间": "出院日期",
    "出院时间.1": "出院日期",
    "诊断名称": "诊断（文字）",
    "诊断": "诊断（文字）",
    "现病史": "现病史（临床症状）",
    "疫苗次数": "疫苗接种次数",
    "既往接种新冠疫苗次数": "疫苗接种次数",
    "末次接种时间": "末次接种日期",
    "是否入ICU": "是否收入ICU",
    "是否入住ICU": "是否收入ICU",
    "入ICU时间": "入ICU日期",
    "出ICU时间": "出ICU日期",
    "死亡时间": "死亡日期",
    "处理措施": "医嘱内容",
    "门诊医嘱": "医嘱内容",
}

JOIN_BY_SEMICOLON = {"医嘱内容"}
PEDIATRIC_RE = re.compile(r"(儿科|儿童|新生儿)")
SEX_MALE_RE = re.compile(r"(?:^m$|^male$|^man$|男|男性|^1$)")
SEX_FEMALE_RE = re.compile(r"(?:^f$|^female$|^woman$|女|女性|^2$)")
AGE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")
INFECTION_PRIORITY = ["LRTI", "URTI"]
INFECTION_TYPE_MAP = {
    "URTI": "上呼吸道感染",
    "LRTI": "下呼吸道感染",
    "UNKNOWN": "未知",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Step4: 清洗 hospital_two_group.csv（年龄/性别/门诊住院/季节）")
    parser.add_argument(
        "--input-csv",
        default="/data/zhangl/coinfection/codemulti_cleaned_data/01_hospital_two_group/hospital_two_group.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="/data/zhangl/coinfection/codemulti_cleaned_data/04_clean_hospital",
    )
    parser.add_argument("--chunksize", type=int, default=200000)
    parser.add_argument("--max-rows", type=int, default=0, help="调试参数，0表示全量")
    return parser.parse_args()


def norm_text(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)
    s = s.str.replace("\u3000", " ", regex=False).str.replace("\xa0", " ", regex=False)
    s = s.str.replace("'", "", regex=False)
    s = s.str.replace(r'[\u3000\xa0\u200b\u200c\u200d\ufeff\t\r\n]', ' ', regex=True)
    s = s.str.replace(r"['‘’]", "", regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True)
    s = s.str.strip()
    s = s.mask(s.str.lower().isin(NA_SET), "")
    
    return s

def first_non_empty(df: pd.DataFrame, candidates):
    out = pd.Series([""] * len(df), index=df.index, dtype=object)
    for col in candidates:
        if col in df.columns:
            s = norm_text(df[col])
            out = out.where(out.str.len() > 0, s)
    return out


def join_unique_non_empty(a: pd.Series, b: pd.Series) -> pd.Series:
    a = norm_text(a)
    b = norm_text(b)
    out = a.copy()
    mask_b = b.str.len() > 0
    mask_a = out.str.len() > 0
    out = out.mask(~mask_a & mask_b, b)
    both = mask_a & mask_b
    out = out.mask(both & (out != b), out + ";" + b)
    return out


def apply_column_synonyms(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for src, tgt in COLUMNS_MAP.items():
        if src not in out.columns:
            continue
        if src == tgt:
            continue
        if tgt in out.columns:
            if tgt in JOIN_BY_SEMICOLON:
                out[tgt] = join_unique_non_empty(out[tgt], out[src])
            else:
                tgt_series = norm_text(out[tgt])
                src_series = norm_text(out[src])
                out[tgt] = tgt_series.where(tgt_series.str.len() > 0, src_series)
            out = out.drop(columns=[src])
        else:
            out = out.rename(columns={src: tgt})
    return out


def normalize_sex_text(value: str) -> str:
    v = str(value).strip().lower()
    if not v or v in NA_SET:
        return "未知"
    if SEX_MALE_RE.search(v):
        return "男"
    if SEX_FEMALE_RE.search(v):
        return "女"
    return "未知"


def parse_age_text(value: str):
    text = str(value).strip().lower()
    if not text or text in NA_SET:
        return np.nan, False, "empty"
    if SEX_MALE_RE.search(text) or SEX_FEMALE_RE.search(text):
        return np.nan, False, "sex_token"

    t = text.replace("个", "")
    year_match = re.search(r"(\d+(?:\.\d+)?)\s*岁", t)
    month_match = re.search(r"(\d+(?:\.\d+)?)\s*月", t)
    day_match = re.search(r"(\d+(?:\.\d+)?)\s*天", t)

    # 组合年龄：x岁y月z天 / x岁y月 / y月z天
    if year_match:
        y = float(year_match.group(1))
        age = y
        reason = "year"
        if ("半" in t) and (not month_match) and (not day_match):
            age += 0.5
            reason = "year_half"
        if month_match:
            age += float(month_match.group(1)) / 12.0
            reason = "year_month"
        if day_match:
            age += float(day_match.group(1)) / 365.0
            reason = reason + "_day"
        return age, True, reason

    if month_match:
        m_val = float(month_match.group(1))
        age = m_val / 12.0
        reason = "month_to_year"
        if day_match:
            age += float(day_match.group(1)) / 365.0
            reason = "month_day_to_year"
        return age, True, reason

    if day_match:
        d_val = float(day_match.group(1))
        return d_val / 365.0, True, "day_to_year"

    m = AGE_NUM_RE.search(t)
    if not m:
        return np.nan, False, "no_number"
    n = float(m.group(1))

    # 原始值本身带小数且无明确单位，视为不可靠，按用户要求置空。
    if "." in m.group(1):
        return np.nan, False, "decimal_untrusted"

    return n, True, "integer_year"


def format_age_value(age: float) -> str:
    if pd.isna(age):
        return ""
    age = float(age)
    if age < 0:
        return ""
    # 用户要求：年龄统一向上取整
    return str(int(np.ceil(age)))


def clean_age_sex_joint(age_raw: pd.Series, sex_raw: pd.Series, dept_raw: pd.Series):
    age_s = norm_text(age_raw)
    sex_s = norm_text(sex_raw)
    dept_s = norm_text(dept_raw)

    out_age = []
    out_sex = []
    age_rule = []
    sex_rule = []

    for a, s, d in zip(age_s.tolist(), sex_s.tolist(), dept_s.tolist()):
        sex_from_sex = normalize_sex_text(s)
        sex_from_age = normalize_sex_text(a)

        age_from_age, age_from_age_ok, age_from_age_reason = parse_age_text(a)
        age_from_sex, age_from_sex_ok, age_from_sex_reason = parse_age_text(s)

        final_sex = sex_from_sex if sex_from_sex != "未知" else sex_from_age
        sex_r = "from_性别列" if sex_from_sex != "未知" else ("from_年龄列" if sex_from_age != "未知" else "unknown")

        final_age = age_from_age
        age_r = f"from_年龄列|{age_from_age_reason}"

        if pd.isna(final_age) and not pd.isna(age_from_sex):
            final_age = age_from_sex
            age_r = f"from_性别列_疑似串位|{age_from_sex_reason}"

        if pd.isna(final_age):
            out_age.append("")
            out_sex.append(final_sex)
            age_rule.append("missing")
            sex_rule.append(sex_r)
            continue

        # 儿科场景：明显异常的大于18年龄尝试按10缩放，否则记无效
        if PEDIATRIC_RE.search(d or "") and final_age > 18:
            if final_age >= 30 and (final_age / 10.0) <= 18:
                final_age = final_age / 10.0
                age_r = age_r + "|pediatric_div10"
            else:
                final_age = np.nan
                age_r = age_r + "|pediatric_invalid"

        # 对此项目，>100 多为脏值，置空
        if not pd.isna(final_age) and final_age > 100:
            final_age = np.nan
            age_r = age_r + "|gt100_invalid"

        if not pd.isna(final_age) and final_age < 0:
            final_age = np.nan
            age_r = age_r + "|lt0_invalid"

        out_age.append(format_age_value(final_age))
        out_sex.append(final_sex)
        age_rule.append(age_r)
        sex_rule.append(sex_r)

    return (
        pd.Series(out_age, index=age_s.index, dtype=object),
        pd.Series(out_sex, index=age_s.index, dtype=object),
        pd.Series(age_rule, index=age_s.index, dtype=object),
        pd.Series(sex_rule, index=age_s.index, dtype=object),
    )


def parse_yes(series: pd.Series) -> pd.Series:
    s = norm_text(series).str.lower()
    pos = s.str.contains(r"(?:是|有|阳|true|yes|住院)", regex=True)
    pos = pos | s.isin({"1", "1.0", "y", "t"})
    return pos


def parse_binary_status(series: pd.Series) -> pd.Series:
    s = norm_text(series).str.lower()
    pos = (
        s.str.contains(r"(?:是|有|阳性|true|yes|支持|已实施|已使用|已行|实施)", regex=True)
        | s.isin({"1", "1.0", "y", "t"})
    )
    neg = (
        s.str.contains(r"(?:否|无|阴性|false|no|未行|未予|未使用|无需|未实施|未见)", regex=True)
        | s.isin({"0", "0.0", "n", "f"})
    )
    out = pd.Series(["未知"] * len(series), index=series.index, dtype=object)
    out = out.mask(neg, "否")
    out = out.mask(pos, "是")
    return out


def parse_yes_no_strict(series: pd.Series) -> pd.Series:
    s = norm_text(series).str.lower()
    pos = s.isin({"是", "yes", "true", "1", "1.0", "y", "t"})
    neg = s.isin({"否", "no", "false", "0", "0.0", "n", "f"})
    out = pd.Series(["未知"] * len(series), index=series.index, dtype=object)
    out = out.mask(neg, "否")
    out = out.mask(pos, "是")
    return out


def to_day_str_series(series: pd.Series) -> pd.Series:
    raw = norm_text(series)
    num = pd.to_numeric(raw, errors="coerce")

    safe_mask = num.notna() & np.isfinite(num) & (num >= 1) & (num <= 80000)
    excel_dt = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    if safe_mask.any():
        excel_dt.loc[safe_mask] = pd.to_datetime(
            num.loc[safe_mask].astype("float64"),
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )

    text_candidate = raw.where(~safe_mask)
    txt_dt = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    formats = [
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d%H:%M:%S",
        "%Y%m%d%H:%M",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d",
        "%Y%m%d",
        "%Y年%m月%d日",
        "%Y年%m月%d日 %H:%M:%S",
    ]
    for fmt in formats:
        parsed = pd.to_datetime(text_candidate, format=fmt, errors="coerce")
        txt_dt = txt_dt.fillna(parsed)
        text_candidate = text_candidate.where(txt_dt.isna())

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually",
        )
        fallback = pd.to_datetime(text_candidate, errors="coerce", utc=True)
    txt_dt = txt_dt.fillna(fallback)

    dt = excel_dt.fillna(txt_dt)
    dt = pd.to_datetime(dt, errors="coerce", utc=True).dt.tz_localize(None)
    out = dt.dt.strftime("%Y-%m-%d").fillna("")
    out = out.replace({"1900-01-00": ""})
    return out


def month_to_season(month: pd.Series) -> pd.Series:
    season = pd.Series(["未知"] * len(month), index=month.index, dtype=object)
    season = season.mask(month.isin([3, 4, 5]), "春")
    season = season.mask(month.isin([6, 7, 8]), "夏")
    season = season.mask(month.isin([9, 10, 11]), "秋")
    season = season.mask(month.isin([12, 1, 2]), "冬")
    return season


def clean_infection_type(series: pd.Series) -> pd.Series:
    s = norm_text(series).str.upper()
    s = s.str.replace("PNEUMONIA", "LRTI", regex=False)
    out = pd.Series(["未知"] * len(series), index=series.index, dtype=object)
    for code in INFECTION_PRIORITY:
        out = out.mask((out == "未知") & s.str.contains(code, regex=False), INFECTION_TYPE_MAP[code])
    return out


def infer_visit_type(df: pd.DataFrame) -> pd.Series:
    explicit = first_non_empty(df, ["就诊类型", "门诊住院", "住院门诊", "就诊类别", "门急诊住院"])
    dept = first_non_empty(df, ["就诊科室", "科室", "目前科室"])
    sheet = first_non_empty(df, ["数据来源Sheet"])
    folder = first_non_empty(df, ["所属文件夹"])
    srcfile = first_non_empty(df, ["数据来源文件"])

    visit = pd.Series(["未知"] * len(df), index=df.index, dtype=object)

    explicit_lower = explicit.str.lower()
    explicit_in = explicit.str.contains("住院", regex=False) | explicit_lower.str.contains("inpatient", regex=False)
    explicit_out = (
        explicit.str.contains("门诊", regex=False)
        | explicit.str.contains("急诊", regex=False)
        | explicit_lower.str.contains("outpatient|emergency", regex=True)
    )

    visit = visit.mask(explicit_in, "住院")
    visit = visit.mask((visit == "未知") & explicit_out, "门诊")

    in_hospital_flag = first_non_empty(df, ["是否收入院", "是否入院", "是否收", "入院"])
    in_hospital = parse_yes(in_hospital_flag)
    in_hospital_strict = parse_yes_no_strict(in_hospital_flag)
    adm_date = to_day_str_series(first_non_empty(df, ["入院日期"]))
    dis_date = to_day_str_series(first_non_empty(df, ["出院日期"]))

    visit = visit.mask((visit == "未知") & (in_hospital | (adm_date.str.len() > 0) | (dis_date.str.len() > 0)), "住院")
    visit = visit.mask((visit == "未知") & (in_hospital_strict == "否"), "门诊")

    outpatient_hint = (
        dept.str.contains("门诊|急诊", regex=True)
        | sheet.str.contains("门诊|急诊|门急诊", regex=True)
        | folder.str.contains("门诊|急诊|门急诊", regex=True)
        | srcfile.str.contains("门诊|急诊|门急诊", regex=True)
    )
    visit = visit.mask((visit == "未知") & outpatient_hint, "门诊")
    return visit


def infer_death_status(df: pd.DataFrame) -> pd.Series:
    # 仅当“是否死亡”列内存在明确 是/否 时才判断，否则未知。
    return parse_yes_no_strict(first_non_empty(df, ["是否死亡"]))


def infer_icu_status(df: pd.DataFrame) -> pd.Series:
    # 优先看“是否收入ICU”；若空，再看入/出ICU日期；都无记录则未知。
    icu_flag = parse_yes_no_strict(first_non_empty(df, ["是否收入ICU"]))
    in_icu_day = to_day_str_series(first_non_empty(df, ["入ICU日期"]))
    out_icu_day = to_day_str_series(first_non_empty(df, ["出ICU日期"]))

    out = icu_flag.copy()
    has_icu_date = (in_icu_day.str.len() > 0) | (out_icu_day.str.len() > 0)
    out = out.mask((out == "未知") & has_icu_date, "是")
    return out


def main():
    args = parse_args()
    input_csv = Path(args.input_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"input csv not found: {input_csv}")

    needed_cols = {
        "医院名称", "患者编号", "年龄（周岁）", "性别", "就诊日期", "入院日期", "出院日期", "就诊科室",
        "诊断（ICD编码）", "是否收入院", "是否收入ICU", "入ICU日期", "出ICU日期", "是否死亡", "感染分组", "命中ICD编码"
    }
    header = pd.read_csv(input_csv, nrows=0, dtype=object, usecols=lambda c: c in needed_cols)
    raw_columns = [str(c) for c in header.columns]
    (out_dir / "hospital_three_group_all_columns.txt").write_text("\n".join(raw_columns), encoding="utf-8")

    out_csv = out_dir / "hospital_three_group_clean.csv"
    if out_csv.exists():
        out_csv.unlink()

    total_rows = 0
    wrote_header = False
    processed_rows = 0

    sex_counts = {"男": 0, "女": 0, "未知": 0}
    visit_counts = {"住院": 0, "门诊": 0, "未知": 0}
    season_counts = {"春": 0, "夏": 0, "秋": 0, "冬": 0, "未知": 0}
    death_counts = {"是": 0, "否": 0, "未知": 0}
    icu_counts = {"是": 0, "否": 0, "未知": 0}
    infection_type_counts = {"上呼吸道感染": 0, "下呼吸道感染": 0, "未知": 0}

    keep_cols = [
        "医院名称",
        "患者编号",
        "年龄（周岁）",
        "性别",
        "就诊日期",
        "入院日期",
        "出院日期",
        "就诊科室",
        "诊断（ICD编码）",
        "感染分组",
        "命中ICD编码",
        "是否收入ICU",
        "入ICU日期",
        "出ICU日期",
        "是否死亡"
    ]

    for chunk in pd.read_csv(input_csv, chunksize=args.chunksize, dtype=object, usecols=lambda c: c in needed_cols):
        total_rows += len(chunk)
        chunk.columns = [str(c).strip() for c in chunk.columns]
        chunk = apply_column_synonyms(chunk)

        if args.max_rows and processed_rows >= args.max_rows:
            break
        if args.max_rows and (processed_rows + len(chunk) > args.max_rows):
            chunk = chunk.iloc[: args.max_rows - processed_rows].copy()

        if "感染分组" in chunk.columns:
            infection_group = norm_text(chunk["感染分组"]).str.upper()
            chunk = chunk.loc[(infection_group != "") & (infection_group != "UNKNOWN")].copy()
            if chunk.empty:
                continue

        age_raw = first_non_empty(chunk, ["年龄（周岁）", "年龄"])
        sex_raw = first_non_empty(chunk, ["性别", "sex"])
        dept_raw = first_non_empty(chunk, ["就诊科室"])
        visit_date_raw = first_non_empty(chunk, ["就诊日期"])
        admit_date_raw = first_non_empty(chunk, ["入院日期"])
        discharge_date_raw = first_non_empty(chunk, ["出院日期"])

        clean_age_col, clean_sex_col, _age_rule_col, _sex_rule_col = clean_age_sex_joint(age_raw, sex_raw, dept_raw)
        visit_day = to_day_str_series(visit_date_raw)
        admit_day = to_day_str_series(admit_date_raw)
        discharge_day = to_day_str_series(discharge_date_raw)
        clean_date_col = visit_day.where(visit_day.str.len() > 0, admit_day)
        clean_date_col = clean_date_col.where(clean_date_col.str.len() > 0, discharge_day)

        month = pd.to_datetime(clean_date_col, errors="coerce").dt.month
        clean_season_col = month_to_season(month)
        clean_visit_col = infer_visit_type(chunk)
        clean_icu_col = infer_icu_status(chunk)
        clean_death_col = infer_death_status(chunk)
        clean_infection_type_col = clean_infection_type(first_non_empty(chunk, ["感染分组"]))

        out = pd.DataFrame(index=chunk.index)
        for col in keep_cols:
            out[col] = norm_text(chunk[col]) if col in chunk.columns else ""

        out["年龄_清洗"] = clean_age_col
        out["性别_清洗"] = clean_sex_col
        out["就诊类型_清洗"] = clean_visit_col
        out["日期_清洗"] = clean_date_col
        out["季节_清洗"] = clean_season_col
        out["感染类型_清洗"] = clean_infection_type_col
        out["是否ICU_清洗"] = clean_icu_col
        out["是否死亡_清洗"] = clean_death_col

        out.to_csv(out_csv, index=False, encoding="utf-8-sig", mode="a" if wrote_header else "w", header=not wrote_header)
        wrote_header = True

        processed_rows += len(out)

        for k, v in out["性别_清洗"].value_counts(dropna=False).to_dict().items():
            sex_counts[k] = sex_counts.get(k, 0) + int(v)
        for k, v in out["就诊类型_清洗"].value_counts(dropna=False).to_dict().items():
            visit_counts[k] = visit_counts.get(k, 0) + int(v)
        for k, v in out["季节_清洗"].value_counts(dropna=False).to_dict().items():
            season_counts[k] = season_counts.get(k, 0) + int(v)
        for k, v in out["感染类型_清洗"].value_counts(dropna=False).to_dict().items():
            infection_type_counts[k] = infection_type_counts.get(k, 0) + int(v)
        for k, v in out["是否ICU_清洗"].value_counts(dropna=False).to_dict().items():
            icu_counts[k] = icu_counts.get(k, 0) + int(v)
        for k, v in out["是否死亡_清洗"].value_counts(dropna=False).to_dict().items():
            death_counts[k] = death_counts.get(k, 0) + int(v)

    clean_cols = pd.read_csv(out_csv, nrows=0, dtype=object).columns.tolist() if out_csv.exists() else []
    (out_dir / "hospital_three_group_clean_columns.txt").write_text("\n".join(clean_cols), encoding="utf-8")

    pd.DataFrame([{"类别": k, "数量": v} for k, v in sex_counts.items()]).to_csv(
        out_dir / "sex_counts.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"类别": k, "数量": v} for k, v in visit_counts.items()]).to_csv(
        out_dir / "visit_type_counts.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"类别": k, "数量": v} for k, v in season_counts.items()]).to_csv(
        out_dir / "season_counts.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"类别": k, "数量": v} for k, v in infection_type_counts.items()]).to_csv(
        out_dir / "infection_type_counts.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"类别": k, "数量": v} for k, v in icu_counts.items()]).to_csv(
        out_dir / "icu_counts.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"类别": k, "数量": v} for k, v in death_counts.items()]).to_csv(
        out_dir / "death_counts.csv", index=False, encoding="utf-8-sig"
    )

    summary = {
        "input_csv": str(input_csv),
        "output_dir": str(out_dir),
        "raw_columns": len(raw_columns),
        "clean_columns": len(clean_cols),
        "rows_total_input_scanned": int(total_rows),
        "rows_clean_output": int(processed_rows),
        "max_rows": int(args.max_rows),
        "output_csv": str(out_csv),
        "infection_type_counts_csv": str(out_dir / "infection_type_counts.csv"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] done: {out_csv}")
    print(f"[INFO] summary: {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
