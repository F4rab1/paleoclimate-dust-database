import argparse
import math
import os
import random
from typing import Dict, List

import pandas as pd

REQUIRED_FIELDS = ["ATh230", "ATh232", "AU238"]
CONFIDENCE_THRESHOLD = 0.75

EXPECTED_FIELD_TOKENS = {
    "ATh230": ["230th", "thorium-230", "thorium 230"],
    "ATh232": ["232th", "thorium-232", "thorium 232"],
    "AU238": ["238u", "uranium-238", "uranium 238"],
    "AU234": ["234u", "uranium-234", "uranium 234"],
    "Th230xs": ["xs", "excess", "230th xs"],
}

REQUIRED_AS_COLUMNS = [
    "Sample ID",
    "Depth top [m]",
    "Depth bottom [m]",
    "Depth center [m]",
    "Age [ka B.P.]",
    "Age R.E. [frac., 2σ]",
    "Type",
    "Source file",
    "Source row index",
    "Age source column",
    "Depth source column",
]


def normalize_text(value: str) -> str:
    return str(value).lower().strip()


def expected_conversion_factor(unit_token: str):
    token = normalize_text(unit_token).replace("μ", "µ")
    if "dpm/g" in token:
        return 1.0
    if "mbq/g" in token:
        return 0.06
    if "bq/kg" in token:
        return 0.06
    return None


def load_site_context(output_dir: str, processing_log: pd.DataFrame) -> pd.DataFrame:
    contexts: List[Dict[str, object]] = []
    success_df = processing_log[processing_log["Status"] == "Success"].copy()

    for _, row in success_df.iterrows():
        site = row["Site"]
        prov_path = os.path.join(output_dir, "remapped_tables", site, f"{site}_mapping_provenance.csv")
        calc_path = os.path.join(output_dir, "analysis_output", f"{site}_calc_table.csv")

        has_negative = False
        if os.path.exists(calc_path):
            try:
                calc_df = pd.read_csv(calc_path)
                if "U238auth_flag" in calc_df.columns:
                    has_negative = (calc_df["U238auth_flag"] == "NEGATIVE").any()
            except Exception:
                has_negative = False

        confidence_tier = "unknown"
        if os.path.exists(prov_path):
            try:
                prov_df = pd.read_csv(prov_path)
                req = prov_df[prov_df["target_field"].isin(REQUIRED_FIELDS)]
                if len(req) == len(REQUIRED_FIELDS):
                    min_conf = req["mapping_confidence"].fillna(0).astype(float).min()
                    has_ambiguous = req["ambiguous_candidates"].fillna("").astype(str).str.strip().ne("").any()
                    if min_conf >= 0.95 and not has_ambiguous:
                        confidence_tier = "high"
                    elif min_conf >= CONFIDENCE_THRESHOLD:
                        confidence_tier = "medium"
                    else:
                        confidence_tier = "low"
                else:
                    confidence_tier = "low"
            except Exception:
                confidence_tier = "unknown"

        contexts.append(
            {
                "Site": site,
                "UnitStatus": row.get("UnitStatus", "Unknown"),
                "has_negative_u238auth": bool(has_negative),
                "confidence_tier": confidence_tier,
            }
        )

    return pd.DataFrame(contexts)


def stratified_sample(sites_df: pd.DataFrame, sample_fraction: float, seed: int) -> pd.DataFrame:
    if sites_df.empty:
        return sites_df

    random.seed(seed)
    sampled_parts = []

    grouped = sites_df.groupby(["UnitStatus", "has_negative_u238auth", "confidence_tier"], dropna=False)
    for _, group in grouped:
        n_take = max(1, math.ceil(len(group) * sample_fraction))
        n_take = min(n_take, len(group))
        sampled_parts.append(group.sample(n=n_take, random_state=seed))

    sampled_df = pd.concat(sampled_parts, ignore_index=True).drop_duplicates(subset=["Site"]).reset_index(drop=True)

    target_min = max(1, math.ceil(len(sites_df) * sample_fraction))
    if len(sampled_df) < target_min:
        remaining = sites_df[~sites_df["Site"].isin(sampled_df["Site"])].copy()
        need = min(target_min - len(sampled_df), len(remaining))
        if need > 0:
            sampled_df = pd.concat(
                [sampled_df, remaining.sample(n=need, random_state=seed)], ignore_index=True
            ).drop_duplicates(subset=["Site"]).reset_index(drop=True)

    return sampled_df


def validate_unit_consistency(site: str, prov_df: pd.DataFrame, failures: List[Dict[str, str]]) -> None:
    for field in REQUIRED_FIELDS:
        match = prov_df[prov_df["target_field"] == field]
        if match.empty:
            failures.append(
                {
                    "Site": site,
                    "Check": "unit_consistency",
                    "Severity": "error",
                    "Detail": f"Missing provenance row for required field {field}",
                }
            )
            continue

        row = match.iloc[0]
        unit_class = str(row.get("unit_class", ""))
        status = str(row.get("status", ""))
        unit_token = str(row.get("source_unit_token", ""))
        factor = row.get("conversion_factor", "")

        if unit_class != "activity_supported" or status != "Mapped":
            failures.append(
                {
                    "Site": site,
                    "Check": "unit_consistency",
                    "Severity": "error",
                    "Detail": f"{field} has unit_class={unit_class}, status={status}",
                }
            )
            continue

        expected_factor = expected_conversion_factor(unit_token)
        if expected_factor is None:
            failures.append(
                {
                    "Site": site,
                    "Check": "unit_consistency",
                    "Severity": "error",
                    "Detail": f"{field} has unsupported unit token '{unit_token}'",
                }
            )
            continue

        try:
            factor_val = float(factor)
        except Exception:
            failures.append(
                {
                    "Site": site,
                    "Check": "unit_consistency",
                    "Severity": "error",
                    "Detail": f"{field} has non-numeric conversion factor '{factor}'",
                }
            )
            continue

        if abs(factor_val - expected_factor) > 1e-9:
            failures.append(
                {
                    "Site": site,
                    "Check": "unit_consistency",
                    "Severity": "error",
                    "Detail": (
                        f"{field} conversion factor mismatch: got {factor_val}, expected {expected_factor}"
                    ),
                }
            )


def validate_mapping_accuracy(site: str, prov_df: pd.DataFrame, failures: List[Dict[str, str]]) -> None:
    for _, row in prov_df.iterrows():
        field = str(row.get("target_field", ""))
        source_column = normalize_text(row.get("source_column", ""))
        status = str(row.get("status", ""))
        if field not in EXPECTED_FIELD_TOKENS:
            continue
        if status != "Mapped":
            continue
        if source_column in {"", "nan", "none"}:
            continue

        expected_tokens = EXPECTED_FIELD_TOKENS[field]
        if not any(token in source_column for token in expected_tokens):
            failures.append(
                {
                    "Site": site,
                    "Check": "mapping_accuracy",
                    "Severity": "error",
                    "Detail": f"{field} source column '{source_column}' misses expected tokens",
                }
            )

        if field != "Th230xs" and ("flux" in source_column or "ratio" in source_column):
            failures.append(
                {
                    "Site": site,
                    "Check": "mapping_accuracy",
                    "Severity": "error",
                    "Detail": f"{field} mapped to likely non-concentration column '{source_column}'",
                }
            )

        try:
            confidence = float(row.get("mapping_confidence", 0.0))
        except Exception:
            confidence = 0.0

        if confidence < CONFIDENCE_THRESHOLD:
            failures.append(
                {
                    "Site": site,
                    "Check": "mapping_accuracy",
                    "Severity": "error",
                    "Detail": f"{field} mapping_confidence={confidence} below threshold {CONFIDENCE_THRESHOLD}",
                }
            )


def validate_sample_origin(site: str, output_dir: str, prov_df: pd.DataFrame, failures: List[Dict[str, str]]) -> None:
    as_path = os.path.join(output_dir, "remapped_tables", site, f"{site}_AS_table.txt")
    if not os.path.exists(as_path):
        failures.append(
            {
                "Site": site,
                "Check": "sample_origin_clarity",
                "Severity": "error",
                "Detail": "AS table missing",
            }
        )
        return

    try:
        as_df = pd.read_csv(as_path, sep="\t")
    except Exception as exc:
        failures.append(
            {
                "Site": site,
                "Check": "sample_origin_clarity",
                "Severity": "error",
                "Detail": f"AS table unreadable: {exc}",
            }
        )
        return

    missing_cols = [col for col in REQUIRED_AS_COLUMNS if col not in as_df.columns]
    if missing_cols:
        failures.append(
            {
                "Site": site,
                "Check": "sample_origin_clarity",
                "Severity": "error",
                "Detail": f"AS missing columns: {', '.join(missing_cols)}",
            }
        )
        return

    null_counts = as_df[REQUIRED_AS_COLUMNS].isna().sum()
    bad_cols = [col for col, count in null_counts.items() if count > 0]
    if bad_cols:
        failures.append(
            {
                "Site": site,
                "Check": "sample_origin_clarity",
                "Severity": "error",
                "Detail": f"AS provenance columns contain nulls: {', '.join(bad_cols)}",
            }
        )

    age_prov = prov_df[prov_df["target_field"] == "Age"]
    depth_prov = prov_df[prov_df["target_field"] == "Depth"]
    if not age_prov.empty:
        age_source = str(age_prov.iloc[0].get("source_column", ""))
        if as_df["Age source column"].astype(str).str.strip().eq("").any():
            failures.append(
                {
                    "Site": site,
                    "Check": "sample_origin_clarity",
                    "Severity": "error",
                    "Detail": "AS age source column has empty values",
                }
            )
        elif not as_df["Age source column"].astype(str).str.contains(age_source, regex=False).all():
            failures.append(
                {
                    "Site": site,
                    "Check": "sample_origin_clarity",
                    "Severity": "error",
                    "Detail": "AS age source column does not match provenance age mapping",
                }
            )

    if not depth_prov.empty:
        depth_source = str(depth_prov.iloc[0].get("source_column", ""))
        if as_df["Depth source column"].astype(str).str.strip().eq("").any():
            failures.append(
                {
                    "Site": site,
                    "Check": "sample_origin_clarity",
                    "Severity": "error",
                    "Detail": "AS depth source column has empty values",
                }
            )
        elif not as_df["Depth source column"].astype(str).str.contains(depth_source, regex=False).all():
            failures.append(
                {
                    "Site": site,
                    "Check": "sample_origin_clarity",
                    "Severity": "error",
                    "Detail": "AS depth source column does not match provenance depth mapping",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--sample_fraction", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = args.output_dir
    processing_log_path = os.path.join(output_dir, "processing_log.csv")
    if not os.path.exists(processing_log_path):
        raise FileNotFoundError(f"processing_log.csv not found at {processing_log_path}")

    processing_log = pd.read_csv(processing_log_path)
    context_df = load_site_context(output_dir, processing_log)

    sampled_df = stratified_sample(context_df, args.sample_fraction, args.seed)
    sampled_df.to_csv(os.path.join(output_dir, "integrity_validation_sample.csv"), index=False)

    failures: List[Dict[str, str]] = []
    for _, row in sampled_df.iterrows():
        site = row["Site"]
        prov_path = os.path.join(output_dir, "remapped_tables", site, f"{site}_mapping_provenance.csv")
        try:
            prov_df = pd.read_csv(prov_path)
        except Exception:
            failures.append(
                {
                    "Site": site,
                    "Check": "mapping_accuracy",
                    "Severity": "error",
                    "Detail": "Missing or unreadable mapping provenance file",
                }
            )
            continue

        validate_unit_consistency(site, prov_df, failures)
        validate_mapping_accuracy(site, prov_df, failures)
        validate_sample_origin(site, output_dir, prov_df, failures)

    failures_df = pd.DataFrame(failures, columns=["Site", "Check", "Severity", "Detail"])
    failures_df.to_csv(os.path.join(output_dir, "integrity_validation_failures.csv"), index=False)

    total_success = len(context_df)
    sampled_count = len(sampled_df)
    target_min = max(1, math.ceil(total_success * args.sample_fraction)) if total_success else 0

    check_counts = {
        "unit_consistency": int((failures_df["Check"] == "unit_consistency").sum()) if not failures_df.empty else 0,
        "mapping_accuracy": int((failures_df["Check"] == "mapping_accuracy").sum()) if not failures_df.empty else 0,
        "sample_origin_clarity": int((failures_df["Check"] == "sample_origin_clarity").sum()) if not failures_df.empty else 0,
    }

    summary_path = os.path.join(output_dir, "integrity_validation_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("Integrity Validation Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"Total successful sites: {total_success}\n")
        f.write(f"Sample fraction: {args.sample_fraction}\n")
        f.write(f"Target minimum sample size: {target_min}\n")
        f.write(f"Actual sampled sites: {sampled_count}\n")
        f.write(f"Validation failures: {len(failures_df)}\n")
        f.write("\nFailure counts by check:\n")
        for check_name, count in check_counts.items():
            f.write(f"  - {check_name}: {count}\n")

    print(f"Saved integrity validation sample to {os.path.join(output_dir, 'integrity_validation_sample.csv')}")
    print(f"Saved integrity validation failures to {os.path.join(output_dir, 'integrity_validation_failures.csv')}")
    print(f"Saved integrity validation summary to {summary_path}")


if __name__ == "__main__":
    main()
