import argparse
import csv
import os
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

# Fixed Params
LITH_CORR = "0.6"
LITH_CORR_ERR = "0.1"

# Target variables in Notebook schema
TARGET_SCHEMA = [
    "Site",
    "Depth top [m]",
    "Depth bottom [m]",
    "Depth center [m]",
    "Age [ka B.P.]",
    "Age R.E. [frac., 2σ]",
    "ATh230 [dpm/g]",
    "ATh230 R.E. [frac., 2σ]",
    "ATh232 [dpm/g]",
    "ATh232 R.E. [frac., 2σ]",
    "AU238 [dpm/g]",
    "AU238 R.E. [frac., 2σ]",
    "AU234 [dpm/g]",
    "AU234 R.E. [frac., 2σ]",
    "Th230xs [dpm/g]",
    "Th230xs R.E. [frac., 2σ]",
]

DEFAULT_AGE_RE = 0.1

REQUIRED_ACTIVITY_FIELDS = {"ATh230", "ATh232", "AU238"}

ACTIVITY_SUPPORTED_FACTORS = {
    "dpm/g": 1.0,
    "bq/kg": 0.06,
    "mbq/g": 0.06,
}

ACTIVITY_UNSUPPORTED_HINTS = ["mg/kg", "ug/kg", "µg/kg", "ppm", "ppb"]

FIELD_CONFIG = {
    "ATh232": {
        "include": ["232th", "thorium-232", "thorium 232"],
        "exclude": ["flux", "ratio", "xs", "excess"],
        "required": True,
    },
    "ATh230": {
        "include": ["230th", "thorium-230", "thorium 230"],
        "exclude": ["flux", "ratio", "xs", "excess"],
        "required": True,
    },
    "AU238": {
        "include": ["238u", "uranium-238", "uranium 238"],
        "exclude": ["flux", "ratio"],
        "required": True,
    },
    "AU234": {
        "include": ["234u", "uranium-234", "uranium 234"],
        "exclude": ["flux", "ratio"],
        "required": False,
    },
    "Th230xs": {
        "include": ["230th xs", "230thxs", "thorium-230 excess", "230th excess", "xs,0"],
        "exclude": ["flux", "ratio", "norm"],
        "required": False,
    },
}

PROVENANCE_FIELDS = ["ATh230", "ATh232", "AU238", "AU234", "Th230xs", "Age", "Depth"]


def download_data(doi: str, output_path: str) -> bool:
    if os.path.exists(output_path):
        return True

    clean_doi = doi.replace("doi:", "").strip()
    clean_doi = (
        clean_doi.replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .replace("https://doi.pangaea.de/", "")
    )
    if not clean_doi.startswith("10."):
        clean_doi = clean_doi.split("doi.org/")[-1]

    url = f"https://doi.pangaea.de/{clean_doi}?format=textfile"
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(output_path, "wb") as file_obj:
            file_obj.write(response.content)
        return True
    except Exception as exc:
        print(f"  Error downloading {doi}: {exc}")
        return False


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def extract_unit_token(column_name: str) -> str:
    match = re.search(r"\[([^\]]+)\]", column_name)
    if not match:
        return ""
    return normalize_text(match.group(1)).replace("μ", "µ")


def classify_activity_unit(column_name: str) -> Tuple[str, str, Optional[float]]:
    lowered = normalize_text(column_name).replace("μ", "µ")
    unit_token = extract_unit_token(column_name)

    if "ratio" in lowered or re.search(r"\([^)]*/[^)]*\)", lowered):
        return "ratio_or_nonactivity", unit_token, None

    if "flux" in lowered:
        return "ratio_or_nonactivity", unit_token, None

    if "mbq/g" in unit_token:
        return "activity_supported", "mBq/g", ACTIVITY_SUPPORTED_FACTORS["mbq/g"]
    if "bq/kg" in unit_token:
        return "activity_supported", "Bq/kg", ACTIVITY_SUPPORTED_FACTORS["bq/kg"]
    if "dpm/g" in unit_token:
        return "activity_supported", "dpm/g", ACTIVITY_SUPPORTED_FACTORS["dpm/g"]

    for hint in ACTIVITY_UNSUPPORTED_HINTS:
        if hint in unit_token:
            return "activity_unsupported", unit_token, None

    if unit_token:
        return "ratio_or_nonactivity", unit_token, None

    if "ratio" in lowered or "/" in lowered:
        return "ratio_or_nonactivity", unit_token, None

    return "ratio_or_nonactivity", unit_token, None


def find_header_row(lines: List[str]) -> int:
    header_row = 0
    for index, line in enumerate(lines):
        if "*/" in line:
            header_row = index + 1
            break

    if header_row == 0:
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if "\t" in stripped:
                header_row = index
                break

    return header_row


def read_pangaea_table(file_path: str) -> pd.DataFrame:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file_obj:
        lines = file_obj.readlines()

    header_row = find_header_row(lines)
    frame = pd.read_csv(file_path, sep="\t", skiprows=header_row, encoding="utf-8", on_bad_lines="skip")
    frame = frame.loc[:, ~frame.columns.astype(str).str.contains(r"^Unnamed")]
    return frame


def find_candidates(columns: List[str], include: List[str], exclude: List[str]) -> List[Tuple[int, int, str]]:
    candidates = []
    for index, column in enumerate(columns):
        lowered = normalize_text(column)
        if any(term in lowered for term in exclude):
            continue
        score = sum(1 for term in include if term in lowered)
        if score > 0:
            candidates.append((score, -index, column))
    candidates.sort(reverse=True)
    return candidates


def find_sd_column(columns: List[str], base_include: List[str], value_column: str) -> Optional[str]:
    value_idx = columns.index(value_column)
    sd_terms = ["std dev", "standard deviation", "error", "uncert", "sd", " e [±]", "std"]

    ranked: List[Tuple[int, int, str]] = []
    for idx, column in enumerate(columns):
        lowered = normalize_text(column)
        if "flux" in lowered:
            continue
        if not any(term in lowered for term in sd_terms):
            continue
        if not any(term in lowered for term in base_include):
            continue
        distance_score = max(0, 100 - abs(value_idx - idx))
        match_score = sum(1 for term in base_include if term in lowered)
        ranked.append((distance_score + match_score, -idx, column))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][2]


def choose_activity_column(columns: List[str], field_name: str) -> Dict[str, object]:
    config = FIELD_CONFIG[field_name]
    candidates = find_candidates(columns, config["include"], config["exclude"])

    unsupported = []
    supported = []
    non_activity = []
    for score, neg_idx, column in candidates:
        unit_class, unit_token, factor = classify_activity_unit(column)
        candidate_info = {
            "score": score,
            "column": column,
            "unit_class": unit_class,
            "unit_token": unit_token,
            "factor": factor,
            "order_idx": -neg_idx,
        }
        if unit_class == "activity_supported":
            supported.append(candidate_info)
        elif unit_class == "activity_unsupported":
            unsupported.append(candidate_info)
        else:
            non_activity.append(candidate_info)

    selected = supported[0] if supported else None
    ambiguous_candidates = [entry["column"] for entry in supported[1:]]
    if not ambiguous_candidates:
        ambiguous_candidates = [entry["column"] for entry in unsupported[:3]]

    confidence = 1.0
    if selected and ambiguous_candidates:
        confidence = 0.75
    if not selected:
        confidence = 0.0

    if selected:
        return {
            "status": "Mapped",
            "column": selected["column"],
            "unit_class": selected["unit_class"],
            "unit_token": selected["unit_token"],
            "factor": selected["factor"],
            "mapping_rule": "keyword_activity_unit_filter",
            "mapping_confidence": confidence,
            "ambiguous_candidates": ambiguous_candidates,
        }

    if unsupported:
        chosen = unsupported[0]
        return {
            "status": "UnsupportedUnit",
            "column": chosen["column"],
            "unit_class": chosen["unit_class"],
            "unit_token": chosen["unit_token"],
            "factor": None,
            "mapping_rule": "keyword_activity_unit_filter",
            "mapping_confidence": 0.0,
            "ambiguous_candidates": [entry["column"] for entry in unsupported[1:]],
        }

    return {
        "status": "Missing",
        "column": None,
        "unit_class": "ratio_or_nonactivity",
        "unit_token": "",
        "factor": None,
        "mapping_rule": "keyword_activity_unit_filter",
        "mapping_confidence": 0.0,
        "ambiguous_candidates": [entry["column"] for entry in non_activity[:3]],
    }


def choose_depth_columns(columns: List[str]) -> Dict[str, object]:
    center_priority = [
        ["depth center"],
        ["depth sed"],
        ["depth", "sediment"],
        ["depth"],
    ]

    def first_match(priority_groups: List[List[str]], exclude_terms: List[str]) -> Optional[str]:
        for group in priority_groups:
            found = []
            for column in columns:
                lowered = normalize_text(column)
                if any(term in lowered for term in exclude_terms):
                    continue
                if all(term in lowered for term in group):
                    found.append(column)
            if found:
                return found[0]
        return None

    center_col = first_match(center_priority, ["water", "elevation", "pressure", "date/time"])
    top_col = first_match([["depth top"], ["depth min"]], ["water", "elevation"])
    bot_col = first_match([["depth bot"], ["depth bottom"], ["depth max"]], ["water", "elevation"])

    if not center_col and top_col and bot_col:
        center_col = top_col

    confidence = 1.0 if center_col else 0.0
    if center_col and (top_col is None or bot_col is None):
        confidence = 0.85

    unit_class = "activity_supported"
    unit_token = extract_unit_token(center_col) if center_col else ""
    factor = 1.0
    if center_col and "[cm]" in normalize_text(center_col):
        factor = 0.01

    return {
        "status": "Mapped" if center_col else "Missing",
        "center_col": center_col,
        "top_col": top_col,
        "bot_col": bot_col,
        "unit_class": unit_class,
        "unit_token": unit_token,
        "factor": factor,
        "mapping_rule": "depth_priority_match",
        "mapping_confidence": confidence,
        "ambiguous_candidates": [],
    }


def choose_age_column(columns: List[str]) -> Dict[str, object]:
    priorities = [
        ["age", "ka bp"],
        ["age model"],
        ["age dated"],
        ["age"],
    ]

    excluded = ["age e", "std dev", "error", "uncert", "dated material"]
    matches = []
    for group_idx, group in enumerate(priorities):
        group_matches = []
        for column in columns:
            lowered = normalize_text(column)
            if any(term in lowered for term in excluded):
                continue
            if all(term in lowered for term in group):
                group_matches.append(column)
        if group_matches:
            matches = group_matches
            confidence = max(0.6, 1.0 - (group_idx * 0.1))
            return {
                "status": "Mapped",
                "column": group_matches[0],
                "unit_class": "ratio_or_nonactivity",
                "unit_token": extract_unit_token(group_matches[0]),
                "factor": 1.0,
                "mapping_rule": "age_priority_match",
                "mapping_confidence": confidence if len(group_matches) == 1 else min(confidence, 0.75),
                "ambiguous_candidates": group_matches[1:],
            }

    return {
        "status": "Missing",
        "column": None,
        "unit_class": "ratio_or_nonactivity",
        "unit_token": "",
        "factor": None,
        "mapping_rule": "age_priority_match",
        "mapping_confidence": 0.0,
        "ambiguous_candidates": matches,
    }


def choose_age_error_column(columns: List[str], age_column: str) -> Optional[str]:
    if age_column is None:
        return None
    age_idx = columns.index(age_column)
    age_terms = ["age", "age model", "age dated"]
    err_terms = ["std dev", "error", "uncert", "age e", " e [±]"]

    ranked: List[Tuple[int, int, str]] = []
    for idx, column in enumerate(columns):
        lowered = normalize_text(column)
        if not any(term in lowered for term in age_terms):
            continue
        if not any(term in lowered for term in err_terms):
            continue
        distance_score = max(0, 50 - abs(age_idx - idx))
        ranked.append((distance_score, -idx, column))

    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][2]


def append_provenance(
    records: List[Dict[str, object]],
    site: str,
    target_field: str,
    source: Dict[str, object],
) -> None:
    records.append(
        {
            "Site": site,
            "target_field": target_field,
            "source_column": source.get("column") or source.get("center_col") or "",
            "source_unit_token": source.get("unit_token", ""),
            "unit_class": source.get("unit_class", ""),
            "conversion_factor": source.get("factor", ""),
            "mapping_rule": source.get("mapping_rule", ""),
            "mapping_confidence": source.get("mapping_confidence", 0.0),
            "ambiguous_candidates": "|".join(source.get("ambiguous_candidates", [])),
            "status": source.get("status", "Missing"),
        }
    )


def remap_file(
    file_path: str,
    site_name: str,
    contract_mode: str = "strict",
) -> Tuple[Optional[pd.DataFrame], List[Dict[str, object]], Dict[str, object]]:
    frame = read_pangaea_table(file_path)
    if frame.empty:
        return None, [], {"reason": "Empty dataset", "failure_code": "EmptyDataset", "failure_detail": "No rows parsed"}

    columns = list(frame.columns)
    remapped = pd.DataFrame(index=frame.index)
    remapped["Site"] = site_name
    remapped["Sample ID"] = frame["Sample label"] if "Sample label" in frame.columns else frame.iloc[:, 0]
    remapped["Type"] = 1
    remapped["Source row index"] = frame.index.astype(int)

    provenance_records: List[Dict[str, object]] = []

    depth_choice = choose_depth_columns(columns)
    append_provenance(provenance_records, site_name, "Depth", depth_choice)
    if depth_choice["status"] != "Mapped":
        return None, provenance_records, {
            "reason": "Missing Depth Column",
            "failure_code": "MissingDepthColumn",
            "failure_detail": "No depth-like sediment column found",
        }

    center_vals = pd.to_numeric(frame[depth_choice["center_col"]], errors="coerce") * depth_choice["factor"]
    remapped["Depth center [m]"] = center_vals

    if depth_choice["top_col"]:
        top_vals = pd.to_numeric(frame[depth_choice["top_col"]], errors="coerce")
        if "[cm]" in normalize_text(depth_choice["top_col"]):
            top_vals = top_vals * 0.01
        remapped["Depth top [m]"] = top_vals
    else:
        remapped["Depth top [m]"] = remapped["Depth center [m]"]

    if depth_choice["bot_col"]:
        bot_vals = pd.to_numeric(frame[depth_choice["bot_col"]], errors="coerce")
        if "[cm]" in normalize_text(depth_choice["bot_col"]):
            bot_vals = bot_vals * 0.01
        remapped["Depth bottom [m]"] = bot_vals
    else:
        remapped["Depth bottom [m]"] = remapped["Depth center [m]"]

    age_choice = choose_age_column(columns)
    append_provenance(provenance_records, site_name, "Age", age_choice)
    if age_choice["status"] != "Mapped":
        return None, provenance_records, {
            "reason": "Missing Age Column",
            "failure_code": "MissingAgeColumn",
            "failure_detail": "No Age/Age model/Age dated column found",
        }

    age_values = pd.to_numeric(frame[age_choice["column"]], errors="coerce")
    remapped["Age [ka B.P.]"] = age_values

    age_error_col = choose_age_error_column(columns, age_choice["column"])
    if age_error_col:
        age_sd = pd.to_numeric(frame[age_error_col], errors="coerce")
        age_re = (age_sd * 2.0) / age_values
        age_re = age_re.replace([np.inf, -np.inf], np.nan)
        remapped["Age R.E. [frac., 2σ]"] = age_re.fillna(DEFAULT_AGE_RE)
    else:
        remapped["Age R.E. [frac., 2σ]"] = DEFAULT_AGE_RE

    unit_failures = []
    for field_name in ["ATh230", "ATh232", "AU238", "AU234", "Th230xs"]:
        choice = choose_activity_column(columns, field_name)
        append_provenance(provenance_records, site_name, field_name, choice)

        value_col = f"{field_name} [dpm/g]"
        err_col = f"{field_name} R.E. [frac., 2σ]"

        if choice["status"] == "Mapped":
            values = pd.to_numeric(frame[choice["column"]], errors="coerce") * float(choice["factor"])
            if values.notna().sum() == 0 and field_name in REQUIRED_ACTIVITY_FIELDS:
                unit_failures.append((f"NoNumericValues_{field_name}", choice["column"]))
                remapped[value_col] = np.nan
                remapped[err_col] = np.nan
                continue

            remapped[value_col] = values
            sd_col = find_sd_column(columns, FIELD_CONFIG[field_name]["include"], choice["column"])
            if sd_col:
                sds = pd.to_numeric(frame[sd_col], errors="coerce") * float(choice["factor"])
                re_vals = (sds * 2.0) / values
                re_vals = re_vals.replace([np.inf, -np.inf], np.nan)
                remapped[err_col] = re_vals
            else:
                remapped[err_col] = np.nan

        elif choice["status"] == "UnsupportedUnit":
            remapped[value_col] = np.nan
            remapped[err_col] = np.nan
            if field_name in REQUIRED_ACTIVITY_FIELDS:
                token = choice.get("unit_token") or "unknown"
                unit_failures.append((f"UnsupportedUnit_{field_name}_{token}", choice.get("column", "")))
        else:
            remapped[value_col] = np.nan
            remapped[err_col] = np.nan
            if field_name in REQUIRED_ACTIVITY_FIELDS:
                unit_failures.append((f"MissingRequiredField_{field_name}", ""))

    if unit_failures:
        first_code, first_detail = unit_failures[0]
        if contract_mode == "strict":
            return None, provenance_records, {
                "reason": "Required activity fields missing or unsupported",
                "failure_code": first_code,
                "failure_detail": first_detail,
                "unit_status": "Failed",
            }
        # Relaxed mode keeps remapped output for broader coverage, but preserves warnings.
        remap_status = {
            "reason": "Required activity fields missing or unsupported (relaxed remap)",
            "failure_code": first_code,
            "failure_detail": first_detail,
            "unit_status": "Warning",
        }
    else:
        remap_status = {
            "reason": "Success",
            "failure_code": "",
            "failure_detail": "",
            "unit_status": "OK",
        }

    # Keep expected table order first, then extra provenance columns for downstream traceability.
    ordered_cols = [col for col in TARGET_SCHEMA if col in remapped.columns]
    extra_cols = [col for col in remapped.columns if col not in ordered_cols]
    remapped = remapped[ordered_cols + extra_cols]

    return remapped, provenance_records, remap_status


def build_age_model(remapped_df: pd.DataFrame) -> pd.DataFrame:
    age_df = pd.DataFrame(
        {
            "Depth [m]": remapped_df["Depth center [m]"],
            "Age [ka B.P.]": remapped_df["Age [ka B.P.]"],
            "Age R.E. [frac., 2σ]": remapped_df["Age R.E. [frac., 2σ]"],
        }
    )
    age_df["Age R.E. [frac., 2σ]"] = age_df["Age R.E. [frac., 2σ]"].fillna(DEFAULT_AGE_RE)
    age_df = age_df.dropna(subset=["Depth [m]", "Age [ka B.P.]"])
    age_df = age_df.drop_duplicates(subset=["Depth [m]", "Age [ka B.P.]"], keep="first")
    age_df = age_df.sort_values(by="Depth [m]").reset_index(drop=True)
    return age_df


def build_as_table(
    remapped_df: pd.DataFrame,
    raw_file: str,
    age_source_col: str,
    depth_source_col: str,
) -> pd.DataFrame:
    as_df = pd.DataFrame(
        {
            "Sample ID": remapped_df["Sample ID"],
            "Depth top [m]": remapped_df["Depth top [m]"],
            "Depth bottom [m]": remapped_df["Depth bottom [m]"],
            "Depth center [m]": remapped_df["Depth center [m]"],
            "Age [ka B.P.]": remapped_df["Age [ka B.P.]"],
            "Age R.E. [frac., 2σ]": remapped_df["Age R.E. [frac., 2σ]"].fillna(DEFAULT_AGE_RE),
            "Type": 1,
            "Source file": os.path.basename(raw_file),
            "Source row index": remapped_df["Source row index"],
            "Age source column": age_source_col,
            "Depth source column": depth_source_col,
        }
    )
    as_df = as_df.dropna(subset=["Depth center [m]", "Age [ka B.P.]"]).reset_index(drop=True)
    return as_df


def extract_elevation(raw_file: str) -> str:
    elevation = "-9999"
    try:
        with open(raw_file, "r", encoding="utf-8", errors="ignore") as file_obj:
            head = file_obj.read(5000)
        if "ELEVATION:" in head:
            part = head.split("ELEVATION:", 1)[1].split("m", 1)[0].strip()
            elevation = part.split("*")[0].strip()
    except Exception:
        pass
    return elevation


def build_failure_log(site_name: str, reason: str, failure_code: str, failure_detail: str) -> Dict[str, object]:
    return {
        "Site": site_name,
        "Status": "Failed",
        "Reason": reason,
        "AgeModelStatus": "NotCreated",
        "AgeModelPoints": 0,
        "ASStatus": "NotCreated",
        "UnitStatus": "Failed",
        "FailureCode": failure_code,
        "FailureDetail": failure_detail,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", required=True)
    parser.add_argument("--workspace_root", default="../")
    parser.add_argument("--output_dir", help="Timestamped output directory (overrides workspace_root for outputs)")
    parser.add_argument(
        "--contract_mode",
        choices=["strict", "relaxed"],
        default="strict",
        help="strict: fail on missing/unsupported required activity fields; relaxed: keep remap with warnings",
    )
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    master_csv = os.path.join(dataset_dir, "all_sites_with_coords.csv")
    if not os.path.exists(master_csv):
        print("Master CSV not found. Run add_coordinates.py first.")
        return

    if args.output_dir:
        output_root = os.path.abspath(args.output_dir)
    else:
        output_root = os.path.abspath(os.path.join(args.workspace_root, "data"))

    remapped_root = os.path.join(output_root, "remapped_tables")
    os.makedirs(remapped_root, exist_ok=True)

    processed_dir = os.path.join(dataset_dir, "D_plus_A", "processed")
    raw_dir = os.path.join(dataset_dir, "D_plus_A", "raw_data")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    print(f"Reading {master_csv}...")
    with open(master_csv, "r", encoding="utf-8") as file_obj:
        rows = list(csv.DictReader(file_obj))

    target_rows = [row for row in rows if row.get("category") in ["D_plus_A", "D_plus_A_plus_X"]]
    print(f"Found {len(target_rows)} D+A or D+A+X datasets.")
    print(f"Contract mode: {args.contract_mode}")

    sites_list: List[Dict[str, object]] = []
    processing_log: List[Dict[str, object]] = []
    provenance_summary_rows: List[Dict[str, object]] = []

    for row in target_rows:
        doi = row.get("doi", "")
        safe_id = doi.split(".")[-1]
        site_name = f"PANGAEA_{safe_id}"

        lat = row.get("latitude", "")
        lon = row.get("longitude", "")
        if not lat or not lon:
            print(f"Skipping {site_name} (no coords)")
            processing_log.append(build_failure_log(site_name, "No Coordinates", "NoCoordinates", "Latitude/Longitude missing"))
            continue

        site_dir = os.path.join(remapped_root, site_name)
        os.makedirs(site_dir, exist_ok=True)
        raw_file = os.path.join(raw_dir, f"{safe_id}.tab")

        print(f"Processing {site_name}...")
        if not download_data(doi, raw_file):
            processing_log.append(build_failure_log(site_name, "Download Error", "DownloadError", doi))
            continue

        remapped_df, provenance_rows, remap_status = remap_file(raw_file, site_name, contract_mode=args.contract_mode)
        provenance_summary_rows.extend(provenance_rows)

        if remapped_df is None or remapped_df.empty:
            print(f"  Failed: {remap_status['reason']}")
            processing_log.append(
                build_failure_log(
                    site_name,
                    remap_status["reason"],
                    remap_status.get("failure_code", "RemapFailed"),
                    remap_status.get("failure_detail", ""),
                )
            )
            continue

        age_df = build_age_model(remapped_df)
        if len(age_df) < 2:
            processing_log.append(
                build_failure_log(
                    site_name,
                    "Age model has fewer than 2 valid points",
                    "AgeModelInsufficientPoints",
                    f"points={len(age_df)}",
                )
            )
            print(f"  Failed: {site_name} has insufficient age-model points ({len(age_df)})")
            continue

        # Save DS table
        ds_table_path = os.path.join(site_dir, f"{site_name}_DS_table.txt")
        remapped_df.to_csv(ds_table_path, sep="\t", index=False)

        # Save age model table
        age_table_path = os.path.join(site_dir, f"{site_name}_Age_model_table.txt")
        age_df.to_csv(age_table_path, sep="\t", index=False)

        # Save AS table (mandatory for successful remaps)
        prov_df = pd.DataFrame(provenance_rows)
        age_source_col = ""
        depth_source_col = ""
        if not prov_df.empty:
            age_rows = prov_df[prov_df["target_field"] == "Age"]
            depth_rows = prov_df[prov_df["target_field"] == "Depth"]
            if not age_rows.empty:
                age_source_col = str(age_rows.iloc[0]["source_column"])
            if not depth_rows.empty:
                depth_source_col = str(depth_rows.iloc[0]["source_column"])

        as_df = build_as_table(remapped_df, raw_file, age_source_col, depth_source_col)
        if as_df.empty:
            processing_log.append(
                build_failure_log(
                    site_name,
                    "AS table has no valid rows",
                    "ASModelEmpty",
                    "No rows with both depth and age",
                )
            )
            print(f"  Failed: {site_name} generated empty AS table")
            continue

        as_table_path = os.path.join(site_dir, f"{site_name}_AS_table.txt")
        as_df.to_csv(as_table_path, sep="\t", index=False)

        # Save per-site provenance
        provenance_path = os.path.join(site_dir, f"{site_name}_mapping_provenance.csv")
        prov_df.to_csv(provenance_path, index=False)

        # Create Info Table
        info_path = os.path.join(site_dir, f"{site_name}_info_table.txt")
        elevation = extract_elevation(raw_file)
        title = row.get("title", "Unknown Title")
        vars_list = row.get("variables", "Unknown Variables")
        reference = f"{row.get('first_author', 'Unknown')}, {doi}"
        area = row.get("agg_location", "Unknown")

        with open(info_path, "w", encoding="utf-8") as info_file:
            info_file.write(f"Site Name\t{site_name}\n")
            info_file.write(f"Lat [deg. N]\t{lat}\n")
            info_file.write(f"Lon [deg. E]\t{lon}\n")
            info_file.write(f"Elevation [m]\t{elevation}\n")
            info_file.write(f"Area\t{area}\n")
            info_file.write(f"Lith. Corr.\t{LITH_CORR}\n")
            info_file.write(f"Lith. Corr. Abs. Err.\t{LITH_CORR_ERR}\n")
            info_file.write(f"Reference\t{reference}\n")
            info_file.write(f"note\tDataset: {title}. Variables: {vars_list}\n")
            info_file.write(f"Site\t{site_name}\n")

        unit_status = remap_status.get("unit_status", "OK")
        if unit_status == "Warning":
            print(
                f"  Saved tables for {site_name} (relaxed warning: "
                f"{remap_status.get('failure_code', '')})"
            )
        else:
            print(f"  Saved tables for {site_name}")
        processing_log.append(
            {
                "Site": site_name,
                "Status": "Success",
                "Reason": "Remapped Successfully" if unit_status == "OK" else remap_status.get("reason", "Remapped"),
                "AgeModelStatus": "Created",
                "AgeModelPoints": len(age_df),
                "ASStatus": f"Created:{len(as_df)}",
                "UnitStatus": unit_status,
                "FailureCode": remap_status.get("failure_code", ""),
                "FailureDetail": remap_status.get("failure_detail", ""),
            }
        )
        sites_list.append({"Site": site_name, "Type": 1, "Longitude E": lon, "Latitide N": lat})

    # Save sites_table.txt
    if sites_list:
        sites_table_path = os.path.join(output_root, "sites_table.txt")
        sites_df = pd.DataFrame(sites_list)[["Site", "Type", "Longitude E", "Latitide N"]]
        sites_df.to_csv(sites_table_path, sep="\t", index=False)
        print(f"Saved sites_table.txt with {len(sites_df)} sites.")

    # Save processing log
    log_path = os.path.join(output_root, "processing_log.csv")
    pd.DataFrame(processing_log).to_csv(log_path, index=False)
    print(f"Saved processing log to {log_path}")

    # Save global provenance summary
    summary_path = os.path.join(output_root, "mapping_provenance_summary.csv")
    summary_columns = [
        "Site",
        "target_field",
        "source_column",
        "source_unit_token",
        "unit_class",
        "conversion_factor",
        "mapping_rule",
        "mapping_confidence",
        "ambiguous_candidates",
        "status",
    ]
    pd.DataFrame(provenance_summary_rows, columns=summary_columns).to_csv(summary_path, index=False)
    print(f"Saved mapping provenance summary to {summary_path}")

    print("Done.")


if __name__ == "__main__":
    main()
