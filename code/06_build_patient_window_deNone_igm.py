#!/usr/bin/env python3
"""Build the IgM-retained direct-detection patient-window cohort.

The default output is
``06_patient_window_master_igm/direct_all_igm_retained/patient_window_master_deNone.csv``.
Input paths remain configurable so this script can be used with the upstream
tables generated in either code tree.
"""
import argparse
from functools import lru_cache
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd


KEY_COL = "患者编号"
DEFAULT_HOSPITAL_CSV = "/data/zhangl/coinfection/codemulti_cleaned_data/04_clean_hospital/hospital_two_group_clean_visit_below15.csv"
DEFAULT_EXAM_CSV = "/data/zhangl/coinfection/codemulti_cleaned_data/03_related_extract/exam.csv"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = str(SCRIPT_DIR / "06_patient_window_master_igm")
DEFAULT_HOSPITAL_CITY_REF = "/data/zhangl/coinfection/codemulti_cleaned_data/hospital_city_reference.json"

VISIT_USECOLS = [
    "医院名称",
    "患者编号",
    "就诊日期",
    "入院日期",
    "出院日期",
    "就诊科室",
    "诊断（ICD编码）",
    "感染分组",
    "年龄_清洗",
    "性别_清洗",
    "就诊类型_清洗",
    "日期_清洗",
    "季节_清洗",
    "感染类型_清洗",
    "是否ICU_清洗",
    "是否死亡_清洗",
]
EXAM_USECOLS = [
    "医院名称",
    "患者编号",
    "检查名称",
    "检查名称_原始",
    "检查日期",
    "检查结果",
    "检查类别",
]

PATHOGEN_ORDER = [
    "新冠",
    "季节性冠状病毒",
    "甲流",
    "乙流",
    "流感",
    "肺炎支原体",
    "肺炎衣原体",
    "呼吸道合胞病毒",
    "腺病毒",
    "副流感病毒",
    "鼻病毒",
    "偏肺病毒",
    "博卡病毒",
    "呼吸道病毒未分型",
    "肠道病毒",
    "柯萨奇病毒",
    "埃可病毒",
    "军团菌",
    "百日咳杆菌",
    "肺炎链球菌",
    "流感嗜血杆菌",
    "卡他莫拉菌",
    "肺炎克雷伯菌",
    "大肠埃希菌",
    "阴沟肠杆菌",
    "鲍曼不动杆菌",
    "铜绿假单胞菌",
    "嗜麦芽窄食单胞菌",
    "变形杆菌",
    "金黄色葡萄球菌",
    "念珠菌",
    "曲霉",
    "真菌未分型",
    "隐球菌",
    "肺孢子菌",
    "结核分枝杆菌",
    "EB病毒",
    "巨细胞病毒",
    "单纯疱疹病毒",
]

PATHOGEN_ALIASES = {
    "新冠": [
        "新冠",
        "新冠病毒",
        "新型冠状病毒",
        "2019新型冠状病毒",
        "covid-19",
        "2019-ncov",
        "2019ncov",
        "sars-cov-2",
        "sars cov 2",
        "新冠核酸",
        "新冠抗原",
    ],
    "季节性冠状病毒": [
        "季节性冠状病毒",
        "人冠状病毒",
        "冠状病毒（229e\\oc43\\nl63\\hku1）",
        "冠状病毒（229e/oc43/nl63/hku1）",
        "冠状病毒(229e\\oc43\\nl63\\hku1)",
        "冠状病毒(229e/oc43/nl63/hku1)",
        "人冠状病毒229e",
        "人冠状病毒oc43",
        "人冠状病毒nl63",
        "人冠状病毒hku1",
        "冠状病毒229e",
        "冠状病毒oc43",
        "冠状病毒nl63",
        "冠状病毒hku1",
        "229e",
        "oc43",
        "nl63",
        "hku1",
        "hcov",
        "新冠核酸",
        "新冠抗原",
    ],
    "甲流": [
        "甲流",
        "甲型流感",
        "甲型流感病毒",
        "甲型流感病毒rna",
        "甲型流感病毒抗原",
        "甲型流感病毒(FluA)",
        "influenza a",
        "flu-av",
        "flu a",
        "h1n1",
        "h3n2",
    ],
    "乙流": [
        "乙流",
        "乙型流感",
        "乙型流感病毒",
        "乙型流感病毒rna",
        "乙型流感病毒抗原",
        "乙型流感病毒(FluB)",
        "influenza b",
        "flu-bv",
        "flu b",
    ],
    "流感": [
        "流感病毒",
        "influenza",
        "甲型/乙型流感",
        "甲型乙型流感",
        "甲乙型流感",
        "甲乙流",
    ],
    "肺炎支原体": [
        "肺炎支原体",
        "肺炎支原体rna",
        "肺炎支原体dna",
        "肺炎支原体核酸",
        "肺炎支原体抗体",
        "肺炎支原体抗原",
        "mycoplasma pneumoniae",
        "mycoplasma",
        "mp",
        "支原体",
    ],
    "肺炎衣原体": [
        "肺炎衣原体",
        "肺炎衣原体dna",
        "肺炎衣原体核酸",
        "肺炎衣原体抗体",
        "chlamydia pneumoniae",
        "chlamydia",
        "cp",
        "衣原体",
    ],
    "呼吸道合胞病毒": ["呼吸道合胞病毒", "合胞病毒", "rsv", "respiratory syncytial virus"],
    "腺病毒": ["腺病毒", "adenovirus", "adv"],
    "副流感病毒": [
        "副流感病毒",
        "副流感",
        "人副流感病毒",
        "副流感病毒1型",
        "副流感病毒2型",
        "副流感病毒3型",
        "副流感病毒4型",
        "人副流感病毒1型",
        "人副流感病毒2型",
        "人副流感病毒3型",
        "人副流感病毒4型",
        "副流感1型",
        "副流感2型",
        "副流感3型",
        "副流感4型",
        "parainfluenza",
        "hpiv",
    ],
    "鼻病毒": ["鼻病毒", "rhinovirus", "hrv"],
    "偏肺病毒": ["偏肺病毒", "人偏肺病毒", "metapneumovirus", "hmpv"],
    "博卡病毒": ["博卡病毒", "bocavirus", "hbov"],
    "呼吸道病毒未分型": ["呼吸道病毒",
        "呼吸道病毒抗体检测",
        "呼吸道病毒抗体谱检测",
        "呼吸道感染相关13种病毒核酸检测",
        "病毒培养与鉴定(组合)",
        "病毒培养与鉴定（组合）",
        "病毒培养与鉴定",],
    "肠道病毒": ["肠道病毒", "enterovirus"],
    "柯萨奇病毒": ["柯萨奇病毒", "柯萨奇", "coxsackievirus"],
    "埃可病毒": ["埃可病毒", "埃可", "echovirus"],
    "军团菌": ["军团菌", "嗜肺军团菌", "legionella"],
    "百日咳杆菌": ["百日咳杆菌", "百日咳", "百日咳鲍特菌", "bordetella pertussis", "pertussis"],
    "肺炎链球菌": ["肺炎链球菌",  "链球菌", "streptococcus pneumoniae", "s. pneumoniae", "streptococcus"],
    "流感嗜血杆菌": ["流感嗜血杆菌", "嗜血杆菌", "haemophilus influenzae", "h. influenzae"],
    "卡他莫拉菌": ["卡他莫拉菌", "卡它莫拉菌", "moraxella catarrhalis", "m. catarrhalis"],
    "肺炎克雷伯菌": ["肺炎克雷伯菌", "克雷伯菌", "肺炎克雷伯氏菌", "克雷伯", "肺炎克雷伯氏菌肺炎亚种", "klebsiella", "klebsiella pneumoniae", "k. pneumoniae"],
    "大肠埃希菌": ["大肠埃希菌", "大肠杆菌", "escherichia coli", "e. coli"],
    "阴沟肠杆菌": ["阴沟肠杆菌", "enterobacter cloacae", "e. cloacae"],
    "鲍曼不动杆菌": ["鲍曼不动杆菌", "鲍曼", "皮氏不动杆菌", "琼氏不动杆菌", "医院不动杆菌", "贝雷占氏不动杆菌", "acinetobacter baumannii", "a. baumannii"],
    "铜绿假单胞菌": ["铜绿", "铜绿假单胞菌", "铜绿假单胞菌(Pae)", "pseudomonas aeruginosa", "p. aeruginosa"],
    "嗜麦芽窄食单胞菌": ["嗜麦芽窄食单胞菌", "嗜麦芽", "stenotrophomonas maltophilia", "s. maltophilia"],
    "变形杆菌": ["变形杆菌", "proteus"],
    "金黄色葡萄球菌": ["金黄色葡萄球菌", "staphylococcus aureus", "s. aureus"],
    "念珠菌": ["白色念珠菌", "念珠菌", "candida"],
    "曲霉": ["曲霉", "aspergillus"],
    "真菌未分型": ["真菌", "fungus", "fungal"],
    "隐球菌": ["隐球菌", "cryptococcus"],
    "肺孢子菌": ["肺孢子菌", "耶氏肺孢子菌", "pneumocystis", "jirovecii", "肺孢子虫", "pneumocystis jirovecii", "pjp", "pcp"],
    "结核分枝杆菌": ["结核分枝杆菌", "结核杆菌", "结核", "抗酸杆菌", "抗酸阳性杆菌", "痰涂片找抗酸杆菌", "mycobacterium tuberculosis", "m. tuberculosis", "mtb"],
    "EB病毒": ["eb病毒", "ebv", "epstein-barr", "人疱疹病毒4型", "eb-dna", "eb病毒核酸", "eb病毒衣壳抗原", "eb病毒dna定量"],
    "巨细胞病毒": ["巨细胞病毒", "cmv", "cytomegalovirus", "人疱疹病毒5型", "人巨细胞病毒", "cmv-dna", "巨细胞病毒dna定量"],
    "单纯疱疹病毒": ["单纯疱疹病毒", "单纯疱疹", "疱疹病毒", "hsv", "hsv-1", "hsv-2", "herpes simplex", "人疱疹病毒1型", "人疱疹病毒2型"],
}

INFECTION_TEXT_TO_CODE = {
    "LRTI": "LRTI",
    "URTI": "URTI",
    "肺炎": "LRTI",
    "下呼吸道感染": "LRTI",
    "上呼吸道感染": "URTI",
}
NEGATIVE_HINTS = ["阴性", "未检出", "未检测到", "未发现", "未查见", "(-)"]
POSITIVE_HINTS = ["阳性", "检出", "检测到", "发现", "查见", "(+)", "弱阳性"]
IDENTIFICATION_HINTS = ["鉴定", "培养", "分离"]
TOKEN_SPLIT_RE = re.compile(r"[;,，；、|/\\\\\s=:+（）()\[\]]+")

ANTIBODY_RE = re.compile(r"抗体|免疫球蛋白|血清学|(?<![a-z])ig[mag](?![a-z])|滴度|补体结合|凝集(?:试验|实验)?", re.I)
IGM_RE = re.compile(r"(?<![a-z])igm(?![a-z])", re.I)
IGM_DIRECT_POSITIVE_RE = re.compile(
    r"(?:igm|免疫球蛋白\s*m)\s*(?:抗体)?\s*(?:[:：=]?\s*)?(?:阳性|检出|检测到|发现|查见|\(\+\)|弱阳性)",
    re.I,
)
DIRECT_METHOD_RE = re.compile(
    r"核酸|rna|dna|pcr|抗原|培养|鉴定|分离|涂片|染色|镜检|测序|宏基因组|mngs|恒温扩增|lamp|胶体金|免疫荧光",
    re.I,
)
DIRECT_CATEGORY_RE = re.compile(r"病原体检测|微生物检查", re.I)
DIRECT_PANEL_RE = re.compile(r"多重检测|呼吸道病原体.{0,8}(?:项|种|panel)|呼吸道感染相关.{0,12}检测", re.I)
UPPER_SPECIMEN_RE = re.compile(
    r"鼻咽|鼻拭子|咽拭子|口咽|咽部|鼻腔|咽漱|鼻分泌物|痰液|痰标本|痰培养|痰涂片|痰菌|nasopharyn|oropharyn|nasal swab|throat swab|sputum",
    re.I,
)
LOWER_SPECIMEN_RE = re.compile(
    r"肺泡灌洗|灌洗液|balf|bronchoalveolar|支气管.{0,8}(?:灌洗|刷检|分泌物|吸取|抽吸)|气管.{0,8}(?:吸引|分泌物|抽吸)|胸腔积液|胸水|肺组织|bronchial|tracheal aspirate|pleural fluid",
    re.I,
)
COHORT_SPECIMENS = {"direct_all": None}

LEGACY_OUTPUTS = [
    "sampled_keys.csv",
    "clinical_patient_level_table.csv",
    "clinical_visit_level_table.csv",
    "exam_daily_detected_table.csv",
    "exam_daily_detected_with_clinical_match.csv",
    "exam_daily_with_windows.csv",
    "hospital_region_mapping_reference.csv",
    "hospital_region_unmatched.csv",
    "hospital_region_mapping_reference.json",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Build antibody-excluded direct-detection sensitivity cohorts")
    parser.add_argument("--hospital-clean-csv", default=DEFAULT_HOSPITAL_CSV)
    parser.add_argument("--exam-csv", default=DEFAULT_EXAM_CSV)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--hospital-city-json", default=DEFAULT_HOSPITAL_CITY_REF)
    parser.add_argument("--chunksize", type=int, default=100000)
    parser.add_argument("--max-hospital-rows", type=int, default=0)
    parser.add_argument("--max-exam-rows", type=int, default=0)
    parser.add_argument("--keep-temp-db", action="store_true")
    parser.add_argument(
        "--retain-igm",
        action="store_true",
        default=True,
        help="Retain records explicitly labelled IgM while excluding other antibody/serology records (default: enabled).",
    )
    parser.add_argument(
        "--cohort-suffix",
        default="_igm_retained",
        help="Suffix appended to direct_all/upper_respiratory/lower_respiratory output cohort names.",
    )
    parser.add_argument(
        "--summary-name",
        default="summary_igm_retained.json",
        help="Summary filename written under the output directory.",
    )
    return parser.parse_args()


def combined_exam_text(row: dict) -> str:
    return " ".join(
        norm_text(row.get(col, ""))
        for col in ["检查名称", "检查名称_原始", "检查类别"]
        if str(row.get(col, "") or "").strip()
    )


def classify_specimen(text: str) -> str:
    if LOWER_SPECIMEN_RE.search(text):
        return "lower_respiratory"
    if UPPER_SPECIMEN_RE.search(text):
        return "upper_respiratory"
    return "unspecified"


def norm_text(value) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text


NORMALIZED_PATHOGEN_ALIASES = {
    pathogen: tuple(norm_text(alias) for alias in aliases)
    for pathogen, aliases in PATHOGEN_ALIASES.items()
}


def clean_patient_id_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def to_day_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d").fillna("")


def coalesce_day_columns(df: pd.DataFrame, columns) -> pd.Series:
    out = pd.Series("", index=df.index, dtype=object)
    for col in columns:
        if col not in df.columns:
            continue
        parsed = to_day_series(df[col])
        fill_mask = out.eq("") & parsed.ne("")
        out.loc[fill_mask] = parsed.loc[fill_mask]
    return out


def normalize_hospital_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip())


def load_hospital_region_lookup(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if isinstance(data, dict):
            return {normalize_hospital_name(k): str(v or "").strip() for k, v in data.items() if str(k).strip()}
    except json.JSONDecodeError:
        pass
    df = pd.read_csv(path, dtype=object, low_memory=False, encoding="utf-8-sig")
    hospital_col = "医院名称" if "医院名称" in df.columns else df.columns[0]
    region_col = "地区" if "地区" in df.columns else df.columns[-1]
    mapping = {}
    for hospital, region in zip(df[hospital_col].fillna(""), df[region_col].fillna("")):
        key = normalize_hospital_name(hospital)
        value = str(region or "").strip()
        if key:
            mapping[key] = value
    return mapping


def region_from_hospital(name: str, region_lookup: dict[str, str]) -> str:
    return region_lookup.get(normalize_hospital_name(name), "")


def choose_infection_code(*values) -> str:
    for value in values:
        text = str(value or "").strip()
        if text in INFECTION_TEXT_TO_CODE:
            return INFECTION_TEXT_TO_CODE[text]
    return ""


def choose_cap_severity(icd_text: str) -> str:
    text = str(icd_text or "").upper()
    if not text:
        return "Unknown"
    if "SCAP" in text:
        return "SCAP"
    if re.search(r"J1[2-8]", text) or "J10.0" in text or "J11.0" in text or "CAP" in text:
        return "Non-SCAP"
    return "Not pneumonia"


def build_candidate_regex():
    keywords = []
    for pathogen, aliases in PATHOGEN_ALIASES.items():
        for alias in aliases:
            alias = alias.strip().lower()
            if not alias:
                continue
            if len(alias) <= 2 and not re.search(r"[\u4e00-\u9fff]", alias):
                continue
            keywords.append(re.escape(alias))
    return re.compile("|".join(sorted(set(keywords), key=len, reverse=True)))


CANDIDATE_REGEX = build_candidate_regex()


def tokenize_text(text: str) -> set[str]:
    normalized = norm_text(text)
    if not normalized:
        return set()
    tokens = {normalized}
    for token in TOKEN_SPLIT_RE.split(normalized):
        token = token.strip()
        if token:
            tokens.add(token)
    return tokens


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def alias_matches(alias: str, name_text: str, raw_name_text: str, result_tokens: set[str], category_text: str) -> bool:
    if alias in name_text or alias in raw_name_text or alias in category_text:
        return True
    if contains_cjk(alias):
        return any(token == alias or token.startswith(alias) for token in result_tokens)
    boundary_pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")
    return any(boundary_pattern.search(token) for token in result_tokens)


def infer_single_pathogen_state(name_text: str, raw_name_text: str, result_text: str, category_text: str, full_text: str, aliases) -> str:
    result_tokens = tokenize_text(result_text)
    if not any(alias_matches(alias, name_text, raw_name_text, result_tokens, category_text) for alias in aliases):
        return ""
    # IgM positivity is retained as evidence of current infection in the
    # IgM-retained sensitivity analysis, including IgM+IgG combinations.
    igm_in_name = bool(IGM_RE.search(" ".join([name_text, raw_name_text, category_text])))
    igm_positive_in_result = bool(IGM_DIRECT_POSITIVE_RE.search(result_text))
    if igm_positive_in_result or (
        igm_in_name
        and result_text
        and any(hint in result_text for hint in POSITIVE_HINTS)
        and not any(hint in result_text for hint in NEGATIVE_HINTS)
    ):
        return "是"
    if any(hint in full_text for hint in NEGATIVE_HINTS):
        return "否"
    if any(hint in full_text for hint in POSITIVE_HINTS):
        return "是"
    if any(hint in name_text or hint in raw_name_text or hint in result_text for hint in IDENTIFICATION_HINTS):
        return "是"
    if result_text and any(alias in result_text for alias in aliases):
        return "是"
    return ""


def merge_pathogen_state(old: str, new: str) -> str:
    if old == "是" or new == "是":
        return "是"
    if old == "否" or new == "否":
        return "否"
    return old or new or ""


@lru_cache(maxsize=250000)
def detect_pathogen_states(name: str, raw_name: str, result: str, category: str) -> dict[str, str]:
    name_text = norm_text(name)
    raw_name_text = norm_text(raw_name)
    result_text = norm_text(result)
    category_text = norm_text(category)
    full_text = " ".join(x for x in [name_text, raw_name_text, result_text, category_text] if x)
    states = {}
    if not full_text or not CANDIDATE_REGEX.search(full_text):
        return states
    for pathogen in PATHOGEN_ORDER:
        aliases = NORMALIZED_PATHOGEN_ALIASES.get(pathogen, ())
        state = infer_single_pathogen_state(name_text, raw_name_text, result_text, category_text, full_text, aliases)
        if state:
            states[pathogen] = state
            if pathogen in {"甲流", "乙流"}:
                states["流感"] = merge_pathogen_state(states.get("流感", ""), state)
    return states


def cleanup_legacy_outputs(output_dir: Path):
    for filename in LEGACY_OUTPUTS:
        path = output_dir / filename
        if path.exists():
            path.unlink()


def init_db(conn: sqlite3.Connection):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        """
        CREATE TABLE visits (
            visit_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            hospital_name TEXT,
            region TEXT,
            visit_date TEXT,
            visit_date_dt TEXT,
            department TEXT,
            diagnosis_icd TEXT,
            age_clean TEXT,
            sex_clean TEXT,
            visit_type_clean TEXT,
            season_clean TEXT,
            infection_group TEXT,
            infection_type_clean TEXT,
            infection_code TEXT,
            cap_severity TEXT,
            icu_clean TEXT,
            death_clean TEXT,
            original_order INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE exam_detected (
            visit_row_id INTEGER,
            patient_id TEXT,
            exam_date TEXT,
            exam_date_dt TEXT,
            exam_name TEXT,
            positive_pathogens TEXT,
            negative_pathogens TEXT,
            specimen_group TEXT,
            exam_record_count INTEGER
        )
        """
    )
    conn.commit()


def load_visits_into_db(hospital_csv: Path, conn: sqlite3.Connection, region_lookup: dict[str, str], chunksize: int, max_rows: int):
    rows_in = 0
    rows_kept = 0
    original_order = 0
    insert_sql = (
        "INSERT INTO visits (patient_id, hospital_name, region, visit_date, visit_date_dt, department, diagnosis_icd, "
        "age_clean, sex_clean, visit_type_clean, season_clean, infection_group, infection_type_clean, infection_code, "
        "cap_severity, icu_clean, death_clean, original_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    for chunk_idx, chunk in enumerate(
        pd.read_csv(
            hospital_csv,
            dtype=object,
            usecols=lambda c: c in VISIT_USECOLS,
            chunksize=chunksize,
            low_memory=False,
            nrows=max_rows or None,
        ),
        start=1,
    ):
        rows_in += len(chunk)
        for col in VISIT_USECOLS:
            if col not in chunk.columns:
                chunk[col] = ""
        chunk[KEY_COL] = clean_patient_id_series(chunk[KEY_COL])
        chunk["visit_date"] = coalesce_day_columns(chunk, ["日期_清洗", "就诊日期", "入院日期"])
        chunk = chunk[chunk[KEY_COL].ne("")].copy()
        if chunk.empty:
            continue
        rows = []
        for row in chunk.to_dict("records"):
            original_order += 1
            infection_code = choose_infection_code(row.get("感染分组", ""), row.get("感染类型_清洗", ""))
            visit_date = str(row.get("visit_date", "") or "").strip()
            rows.append(
                (
                    row.get(KEY_COL, ""),
                    normalize_hospital_name(row.get("医院名称", "")),
                    region_from_hospital(row.get("医院名称", ""), region_lookup),
                    visit_date,
                    visit_date,
                    str(row.get("就诊科室", "") or "").strip(),
                    str(row.get("诊断（ICD编码）", "") or "").strip(),
                    str(row.get("年龄_清洗", "") or "").strip(),
                    str(row.get("性别_清洗", "") or "").strip(),
                    str(row.get("就诊类型_清洗", "") or "").strip(),
                    str(row.get("季节_清洗", "") or "").strip(),
                    str(row.get("感染分组", "") or "").strip(),
                    str(row.get("感染类型_清洗", "") or "").strip(),
                    infection_code,
                    choose_cap_severity(row.get("诊断（ICD编码）", "")),
                    str(row.get("是否ICU_清洗", "") or "").strip(),
                    str(row.get("是否死亡_清洗", "") or "").strip(),
                    original_order,
                )
            )
        conn.executemany(insert_sql, rows)
        conn.commit()
        rows_kept += len(rows)
        if chunk_idx % 20 == 0:
            print(f"[INFO] hospital chunk={chunk_idx} rows_in={rows_in} visits_loaded={rows_kept}", flush=True)
    conn.execute("CREATE INDEX idx_visits_pid_date ON visits(patient_id, visit_date_dt, visit_row_id)")
    conn.commit()
    return {"hospital_rows_in": int(rows_in), "visit_rows": int(rows_kept)}


def fetch_visit_subset(conn: sqlite3.Connection, patient_ids: list[str]) -> pd.DataFrame:
    if not patient_ids:
        return pd.DataFrame(columns=["visit_row_id", "patient_id", "visit_date_dt"])
    all_parts = []
    batch_size = 800
    for start in range(0, len(patient_ids), batch_size):
        batch = patient_ids[start : start + batch_size]
        placeholders = ",".join("?" for _ in batch)
        sql = (
            "SELECT visit_row_id, patient_id, visit_date_dt, original_order "
            f"FROM visits WHERE patient_id IN ({placeholders}) "
            "ORDER BY patient_id, visit_date_dt, original_order, visit_row_id"
        )
        all_parts.append(pd.read_sql_query(sql, conn, params=batch))
    if not all_parts:
        return pd.DataFrame(columns=["visit_row_id", "patient_id", "visit_date_dt"])
    subset = pd.concat(all_parts, ignore_index=True)
    subset["visit_date_dt"] = pd.to_datetime(subset["visit_date_dt"], errors="coerce")
    return subset


def choose_assigned_visit_id(exam_date_dt: pd.Timestamp, visit_rows: list[tuple[int, pd.Timestamp]]) -> Optional[int]:
    if not visit_rows:
        return None
    if len(visit_rows) == 1:
        return visit_rows[0][0]
    if pd.isna(exam_date_dt):
        return visit_rows[0][0]
    last_prior_id = None
    for visit_id, visit_dt in visit_rows:
        if pd.isna(visit_dt):
            continue
        if visit_dt <= exam_date_dt:
            last_prior_id = visit_id
        else:
            break
    if last_prior_id is not None:
        return last_prior_id
    for visit_id, visit_dt in visit_rows:
        if not pd.isna(visit_dt):
            return visit_id
    return visit_rows[0][0]


def load_exam_rows_into_db(
    exam_csv: Path,
    conn: sqlite3.Connection,
    chunksize: int,
    max_rows: int,
    retain_igm: bool = False,
):
    rows_in = 0
    rows_candidate = 0
    rows_antibody_excluded = 0
    rows_non_direct_excluded = 0
    rows_detected = 0
    specimen_counts = {"upper_respiratory": 0, "lower_respiratory": 0, "unspecified": 0}
    insert_sql = (
        "INSERT INTO exam_detected (visit_row_id, patient_id, exam_date, exam_date_dt, exam_name, positive_pathogens, negative_pathogens, specimen_group, exam_record_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    for chunk_idx, chunk in enumerate(
        pd.read_csv(
            exam_csv,
            dtype=object,
            usecols=lambda c: c in EXAM_USECOLS,
            chunksize=chunksize,
            low_memory=False,
            nrows=max_rows or None,
        ),
        start=1,
    ):
        rows_in += len(chunk)
        for col in EXAM_USECOLS:
            if col not in chunk.columns:
                chunk[col] = ""
        chunk[KEY_COL] = clean_patient_id_series(chunk[KEY_COL])
        chunk["exam_date"] = to_day_series(chunk["检查日期"])
        chunk["candidate_text"] = (
            chunk["检查名称"].fillna("").astype(str)
            + " "
            + chunk["检查名称_原始"].fillna("").astype(str)
            + " "
            + chunk["检查结果"].fillna("").astype(str)
            + " "
            + chunk["检查类别"].fillna("").astype(str)
        ).str.lower()
        chunk = chunk[
            chunk[KEY_COL].ne("")
            & chunk["exam_date"].ne("")
            & chunk["candidate_text"].str.contains(CANDIDATE_REGEX, regex=True, na=False)
        ].copy()
        rows_candidate += len(chunk)
        if chunk.empty:
            continue

        method_text = (
            chunk["检查名称"].fillna("").astype(str)
            + " "
            + chunk["检查名称_原始"].fillna("").astype(str)
            + " "
            + chunk["检查类别"].fillna("").astype(str)
        ).str.lower()
        antibody_mask = method_text.str.contains(ANTIBODY_RE, regex=True, na=False)
        igm_mask = method_text.str.contains(IGM_RE, regex=True, na=False)
        if retain_igm:
            antibody_mask = antibody_mask & ~igm_mask
        direct_mask = (
            method_text.str.contains(DIRECT_METHOD_RE, regex=True, na=False)
            | method_text.str.contains(DIRECT_CATEGORY_RE, regex=True, na=False)
            | method_text.str.contains(DIRECT_PANEL_RE, regex=True, na=False)
            | (igm_mask if retain_igm else False)
        ) & ~antibody_mask
        rows_antibody_excluded += int(antibody_mask.sum())
        rows_non_direct_excluded += int((~antibody_mask & ~direct_mask).sum())
        chunk = chunk.loc[direct_mask].copy()
        if chunk.empty:
            continue

        insert_rows = []
        for row in chunk.to_dict("records"):
            method_text = combined_exam_text(row)
            states = detect_pathogen_states(
                row.get("检查名称", ""),
                row.get("检查名称_原始", ""),
                row.get("检查结果", ""),
                row.get("检查类别", ""),
            )
            if not states:
                continue
            pos = sorted([k for k, v in states.items() if v == "是"])
            neg = sorted([k for k, v in states.items() if v == "否" and k not in pos])
            if not pos and not neg:
                continue
            exam_name = str(row.get("检查名称_原始", "") or row.get("检查名称", "") or "").strip()
            specimen_group = classify_specimen(method_text)
            insert_rows.append(
                (
                    None,
                    row.get(KEY_COL, ""),
                    row.get("exam_date", ""),
                    row.get("exam_date", ""),
                    exam_name,
                    ";".join(pos),
                    ";".join(neg),
                    specimen_group,
                    1,
                )
            )
        if not insert_rows:
            continue
        conn.executemany(insert_sql, insert_rows)
        conn.commit()
        rows_detected += len(insert_rows)
        for insert_row in insert_rows:
            specimen_counts[insert_row[7]] += 1
        if chunk_idx % 20 == 0:
            print(
                f"[INFO] exam chunk={chunk_idx} rows_in={rows_in} candidate_exam_rows={rows_candidate} detected_exam_rows={rows_detected}",
                flush=True,
            )
    conn.execute("CREATE INDEX idx_exam_patient_date ON exam_detected(patient_id, exam_date_dt)")
    conn.commit()
    return {
        "exam_rows_in": int(rows_in),
        "candidate_exam_rows": int(rows_candidate),
        "antibody_candidate_rows_excluded": int(rows_antibody_excluded),
        "non_direct_candidate_rows_excluded": int(rows_non_direct_excluded),
        "detected_exam_rows": int(rows_detected),
        "detected_exam_rows_by_specimen": specimen_counts,
    }


def assign_exam_visits(conn: sqlite3.Connection):
    before = int(conn.execute("SELECT COUNT(*) FROM exam_detected").fetchone()[0])
    conn.execute(
        """
        UPDATE exam_detected
        SET visit_row_id = COALESCE(
            (
                SELECT v.visit_row_id
                FROM visits AS v
                WHERE v.patient_id = exam_detected.patient_id
                  AND v.visit_date_dt <= exam_detected.exam_date_dt
                ORDER BY v.visit_date_dt DESC, v.original_order DESC, v.visit_row_id DESC
                LIMIT 1
            ),
            (
                SELECT v.visit_row_id
                FROM visits AS v
                WHERE v.patient_id = exam_detected.patient_id
                ORDER BY CASE WHEN v.visit_date_dt IS NULL OR v.visit_date_dt = '' THEN 1 ELSE 0 END,
                         v.visit_date_dt, v.original_order, v.visit_row_id
                LIMIT 1
            )
        )
        """
    )
    conn.execute("DELETE FROM exam_detected WHERE visit_row_id IS NULL")
    conn.execute("CREATE INDEX idx_exam_visit_date ON exam_detected(visit_row_id, exam_date_dt)")
    conn.commit()
    after = int(conn.execute("SELECT COUNT(*) FROM exam_detected").fetchone()[0])
    return {"detected_before_visit_match": before, "detected_after_visit_match": after, "unmatched_rows": before - after}


def split_items(text: str) -> list[str]:
    return [item.strip() for item in str(text or "").split(";") if item.strip()]


def build_rows_for_visit(visit: dict, exam_rows: list[dict]):
    base = {
        "患者编号": visit["patient_id"],
        "医院名称": visit["hospital_name"],
        "地区": visit["region"],
        "匹配临床日期": visit["visit_date"],
        "年龄_清洗": visit["age_clean"],
        "性别_清洗": visit["sex_clean"],
        "就诊类型_清洗": visit["visit_type_clean"],
        "季节_清洗": visit["season_clean"],
        "感染类型代码": visit["infection_code"],
        "感染类型_清洗": visit["infection_type_clean"],
        "社区获得性肺炎分层": visit["cap_severity"],
        "诊断（ICD编码）": visit["diagnosis_icd"],
        "是否ICU_清洗": visit["icu_clean"],
        "是否死亡_清洗": visit["death_clean"],
        "就诊科室": visit["department"],
        "临床记录数": 1,
        "临床日期列表": visit["visit_date"],
        "诊断（ICD编码）_患者汇总": visit["diagnosis_icd"],
        "就诊科室_患者汇总": visit["department"],
        "就诊记录编号": int(visit["visit_row_id"]),
    }
    if not exam_rows:
        row = dict(base)
        row.update(
            {
                "窗口开始日期": visit["visit_date"],
                "窗口结束日期": visit["visit_date"],
                "窗口日期列表": "",
                "窗口覆盖检测天数": 0,
                "窗口内检测记录数": 0,
                "检测名称汇总": "",
                "阳性病原体": "",
                "阴性病原体": "",
                "已检测病原体": "",
                "阳性病原体数量": 0,
                "已检测病原体数量": 0,
                "是否共感染": "未检测",
                "_window_local_index": 0,
            }
        )
        for pathogen in PATHOGEN_ORDER:
            row[f"病原体状态::{pathogen}"] = "未检测"
        return [row]

    daily_map = {}
    for exam_row in exam_rows:
        key = exam_row["exam_date"]
        rec = daily_map.setdefault(
            key,
            {
                "exam_name_set": set(),
                "pos_set": set(),
                "neg_set": set(),
                "count": 0,
            },
        )
        if exam_row["exam_name"]:
            rec["exam_name_set"].add(exam_row["exam_name"])
        rec["pos_set"].update(split_items(exam_row["positive_pathogens"]))
        rec["neg_set"].update(split_items(exam_row["negative_pathogens"]))
        rec["neg_set"] -= rec["pos_set"]
        rec["count"] += int(exam_row["exam_record_count"] or 0)

    daily_items = []
    for exam_date, rec in daily_map.items():
        daily_items.append(
            {
                "exam_date": exam_date,
                "exam_date_dt": pd.to_datetime(exam_date, errors="coerce"),
                "exam_name_set": rec["exam_name_set"],
                "pos_set": rec["pos_set"],
                "neg_set": rec["neg_set"],
                "count": rec["count"],
            }
        )
    daily_items.sort(key=lambda x: (pd.Timestamp.max if pd.isna(x["exam_date_dt"]) else x["exam_date_dt"], x["exam_date"]))

    out_rows = []
    current_window = []
    window_start_dt = None
    local_index = 0

    def flush_window():
        nonlocal current_window, window_start_dt, local_index
        if not current_window:
            return
        local_index += 1
        pos_set = set()
        neg_set = set()
        exam_names = set()
        date_list = []
        total_count = 0
        for item in current_window:
            pos_set.update(item["pos_set"])
            neg_set.update(item["neg_set"])
            neg_set -= pos_set
            exam_names.update(item["exam_name_set"])
            date_list.append(item["exam_date"])
            total_count += item["count"]
        tested_set = pos_set | neg_set
        row = dict(base)
        row.update(
            {
                "窗口开始日期": date_list[0],
                "窗口结束日期": date_list[-1],
                "窗口日期列表": ";".join(date_list),
                "窗口覆盖检测天数": len(date_list),
                "窗口内检测记录数": total_count,
                "检测名称汇总": ";".join(sorted(exam_names)),
                "阳性病原体": ";".join(sorted(pos_set)),
                "阴性病原体": ";".join(sorted(neg_set)),
                "已检测病原体": ";".join(sorted(tested_set)),
                "阳性病原体数量": len(pos_set),
                "已检测病原体数量": len(tested_set),
                "是否共感染": "是" if len(pos_set) >= 2 else "否",
                "_window_local_index": local_index,
            }
        )
        for pathogen in PATHOGEN_ORDER:
            if pathogen in pos_set:
                state = "是"
            elif pathogen in neg_set:
                state = "否"
            else:
                state = "未检测"
            row[f"病原体状态::{pathogen}"] = state
        out_rows.append(row)
        current_window = []
        window_start_dt = None

    for item in daily_items:
        if window_start_dt is None or pd.isna(item["exam_date_dt"]) or pd.isna(window_start_dt):
            window_start_dt = item["exam_date_dt"]
            current_window = [item]
            continue
        if (item["exam_date_dt"] - window_start_dt).days <= 2:
            current_window.append(item)
        else:
            flush_window()
            window_start_dt = item["exam_date_dt"]
            current_window = [item]
    flush_window()
    return out_rows


def stream_master_table(conn: sqlite3.Connection, output_dir: Path, chunksize: int, specimen_filter: Optional[str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "patient_window_master_deNone.csv"
    temp_output_csv = output_dir / "patient_window_master_deNone.tmp.csv"
    if output_csv.exists():
        output_csv.unlink()
    if temp_output_csv.exists():
        temp_output_csv.unlink()

    conn.execute("DROP TABLE IF EXISTS relevant_visit_ids")
    conn.execute("CREATE TEMP TABLE relevant_visit_ids (visit_row_id INTEGER PRIMARY KEY)")
    specimen_sql = " WHERE specimen_group = ?" if specimen_filter else ""
    conn.execute(
        f"INSERT OR IGNORE INTO relevant_visit_ids SELECT visit_row_id FROM exam_detected{specimen_sql}",
        [specimen_filter] if specimen_filter else [],
    )
    total_visit_rows = conn.execute("SELECT COUNT(*) FROM relevant_visit_ids").fetchone()[0]
    rows_written = 0
    tested_rows = 0
    visit_rows_without_exam = 0
    header_written = False

    for offset in range(0, int(total_visit_rows), chunksize):
        visits_df = pd.read_sql_query(
            "SELECT v.* FROM visits AS v JOIN relevant_visit_ids AS r ON r.visit_row_id = v.visit_row_id ORDER BY v.visit_row_id LIMIT ? OFFSET ?",
            conn,
            params=[chunksize, offset],
        )
        if visits_df.empty:
            continue
        min_id = int(visits_df["visit_row_id"].min())
        max_id = int(visits_df["visit_row_id"].max())
        specimen_exam_sql = " AND specimen_group = ?" if specimen_filter else ""
        params = [min_id, max_id] + ([specimen_filter] if specimen_filter else [])
        exam_df = pd.read_sql_query(
            f"SELECT * FROM exam_detected WHERE visit_row_id BETWEEN ? AND ?{specimen_exam_sql} AND visit_row_id IN (SELECT visit_row_id FROM relevant_visit_ids) ORDER BY visit_row_id, exam_date_dt, exam_date",
            conn,
            params=params,
        )
        exam_group = {
            int(visit_id): group.to_dict("records")
            for visit_id, group in exam_df.groupby("visit_row_id", sort=False)
        }

        out_rows = []
        for visit in visits_df.to_dict("records"):
            visit_exam_rows = exam_group.get(int(visit["visit_row_id"]), [])
            if not visit_exam_rows:
                visit_rows_without_exam += 1
            out_rows.extend(build_rows_for_visit(visit, visit_exam_rows))

        out_df = pd.DataFrame(out_rows)
        out_df = out_df[pd.to_numeric(out_df["已检测病原体数量"], errors="coerce").fillna(0).gt(0)].copy()
        if out_df.empty:
            continue
        out_df["窗口开始日期_dt"] = pd.to_datetime(out_df["窗口开始日期"], errors="coerce")
        date_code = out_df["窗口开始日期_dt"].dt.strftime("%Y%m%d")
        visit_code = pd.to_numeric(out_df["就诊记录编号"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(8)
        window_code = pd.to_numeric(out_df["_window_local_index"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(2)
        out_df["时间窗口编号"] = date_code.where(date_code.notna(), visit_code) + window_code
        out_df = out_df.drop(columns=["窗口开始日期_dt", "_window_local_index"], errors="ignore")
        out_df.to_csv(
            temp_output_csv,
            mode="a",
            index=False,
            header=not header_written,
            encoding="utf-8-sig",
        )
        header_written = True
        rows_written += len(out_df)
        tested_rows += int((out_df["已检测病原体数量"] > 0).sum())
        print(
            f"[INFO] master chunk offset={offset} visit_rows={len(visits_df)} output_rows={rows_written}",
            flush=True,
        )

    if temp_output_csv.exists():
        temp_output_csv.replace(output_csv)

    pathogen_columns = [f"病原体状态::{pathogen}" for pathogen in PATHOGEN_ORDER]
    (output_dir / "pathogen_columns.txt").write_text("\n".join(pathogen_columns) + "\n", encoding="utf-8")
    return {
        "visit_rows": int(total_visit_rows),
        "master_rows": int(rows_written),
        "tested_master_rows": int(tested_rows),
        "visit_rows_without_exam": int(visit_rows_without_exam),
        "master_csv": str(output_csv),
        "specimen_filter": specimen_filter or "all",
        "pathogen_columns_txt": str(output_dir / "pathogen_columns.txt"),
    }


def main():
    args = parse_args()
    hospital_csv = Path(args.hospital_clean_csv)
    exam_csv = Path(args.exam_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not hospital_csv.exists():
        raise FileNotFoundError(f"hospital clean csv not found: {hospital_csv}")
    if not exam_csv.exists():
        raise FileNotFoundError(f"exam csv not found: {exam_csv}")

    region_lookup = load_hospital_region_lookup(Path(args.hospital_city_json))
    db_path = output_dir / "_patient_window_build.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        print("[INFO] loading visit backbone from hospital csv", flush=True)
        visit_stats = load_visits_into_db(
            hospital_csv=hospital_csv,
            conn=conn,
            region_lookup=region_lookup,
            chunksize=args.chunksize,
            max_rows=args.max_hospital_rows,
        )
        print("[INFO] assigning exams to nearest prior visits", flush=True)
        exam_stats = load_exam_rows_into_db(
            exam_csv=exam_csv,
            conn=conn,
            chunksize=args.chunksize,
            max_rows=args.max_exam_rows,
            retain_igm=args.retain_igm,
        )
        print("[INFO] batch-assigning detected exams to nearest prior visits", flush=True)
        exam_stats.update(assign_exam_visits(conn))
        print("[INFO] writing sensitivity cohort master tables", flush=True)
        master_stats = {}
        cohort_specs = {
            f"{cohort}{args.cohort_suffix}": specimen_filter
            for cohort, specimen_filter in COHORT_SPECIMENS.items()
        }
        for cohort, specimen_filter in cohort_specs.items():
            print(f"[INFO] cohort={cohort}", flush=True)
            master_stats[cohort] = stream_master_table(conn, output_dir / cohort, args.chunksize, specimen_filter)
    finally:
        conn.close()
        if db_path.exists() and not args.keep_temp_db:
            db_path.unlink()

    summary = {
        "hospital_clean_csv": str(hospital_csv),
        "exam_csv": str(exam_csv),
        "output_dir": str(output_dir),
        "chunksize": int(args.chunksize),
        "max_hospital_rows": int(args.max_hospital_rows),
        "max_exam_rows": int(args.max_exam_rows),
        "matching_rule": "If a patient has multiple visits, each exam is attached to the nearest prior visit date; if no prior visit exists, fall back to the first dated visit, and if only one visit exists, attach all exams to that visit.",
        "detection_rule": (
            "Explicit IgM records are retained; an explicit IgM-positive result (including IgM+IgG) is classified as infection positive, while other antibody/IgG/IgA/serology/titre/complement-fixation/agglutination records are excluded. "
            if args.retain_igm else
            "Antibody/IgM/IgG/serology tests are excluded. "
        ) + "Retained rows must be identifiable as culture, nucleic acid, antigen, microscopy, sequencing, a multiplex pathogen panel, or a pathogen/microbiology-category test.",
        "specimen_rule": "Specimen subgroups use explicit wording only. lower_respiratory is checked first. upper_respiratory follows the supplied operational definition and includes nasal/nasopharyngeal/oropharyngeal/throat swabs and sputum. Unspecified specimens are excluded from specimen-specific cohorts.",
        "window_rule": "Within each visit and analysis cohort, retained exams are merged into 3-day windows by exam date. Only windows with at least one tested pathogen are saved.",
        "saved_outputs": [
            *[f"{cohort}/patient_window_master_deNone.csv" for cohort in master_stats],
            "*/pathogen_columns.txt",
            args.summary_name,
        ],
        "visit_stats": visit_stats,
        "exam_stats": exam_stats,
        "master_stats": master_stats,
    }
    (output_dir / args.summary_name).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for cohort, stats in master_stats.items():
        print(f"[INFO] cohort={cohort} master_rows={stats['master_rows']}", flush=True)
    print(f"[INFO] summary={output_dir / args.summary_name}", flush=True)


if __name__ == "__main__":
    main()
