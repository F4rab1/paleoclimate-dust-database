# Marine Sediments Dust Deposition Pipeline

This repository implements a two-step pipeline for marine sediment dust-deposition analysis using PANGAEA datasets.

The project does two things:

1. Discovers and classifies candidate datasets (Step 1).
2. Remaps D+A datasets into D3-compatible tables and runs the legacy `D3v1_01` analysis workflow (Step 2).

The primary goal is to produce standardized per-site tables and analysis PDFs.

## Repository Structure

- `run_step1_discovery.sh`: end-to-end Step 1 runner.
- `run_step2_analysis.sh`: end-to-end Step 2 runner.
- `step1_discovery/scripts/`: discovery, conversion, coordinates, map.
- `step2_analysis/scripts/process_datasets.py`: remapping + contract enforcement.
- `step2_analysis/scripts/D3v1_01.py`: scientific calculations + PDF generation.
- `step2_analysis/scripts/validate_integrity.py`: stratified sample-based integrity checks.
- `step1_discovery/data/<timestamp>/`: Step 1 timestamped outputs.
- `step2_analysis/data/<timestamp>/`: Step 2 timestamped outputs.

## Prerequisites

- Python 3.10+ recommended.
- Unix-like shell environment.
- Internet access (Step 1 needs to query PANGAEA, and Step 2 may download dataset files).

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

Run Step 1, then Step 2.

```bash
./run_step1_discovery.sh
./run_step2_analysis.sh strict
```

Step 2 supports exactly two modes:

- `strict` (default): analysis-grade only.
- `relaxed`: higher coverage with warning-marked partial remaps.

```bash
./run_step2_analysis.sh strict
./run_step2_analysis.sh relaxed
```

Step 1 search size can be tuned by passing `max_results`:

```bash
./run_step1_discovery.sh 500
./run_step1_discovery.sh 2000
```

## Step 1 Outputs

Each run creates `step1_discovery/data/<timestamp>/`.

Key files:

- `pangaea_all_results_raw.csv`: all search hits returned by PANGAEA before filtering.
- `pangaea_d_samples.csv`: datasets that passed the D-sample filters used by this project.
- `all_sites_with_coords.csv`: main Step 1 handoff file for Step 2, with DOI, title, category, and coordinates.
- `reports/pangaea_d_samples_catalog.md`: human-readable catalog of discovered datasets.
- `reports/global_site_map.png`: map showing where discovered sites are located.

## Step 2 Inputs and Scope

Step 2 automatically uses the latest Step 1 folder and processes only categories:

- `D_plus_A`
- `D_plus_A_plus_X`

For people new to the project: this means Step 2 does not try to analyze every discovered dataset, only those expected to contain age information.

## Step 2 Data Rules (Strict Mode)

In `strict` mode, a dataset must pass these rules:

1. Required activity fields are mapped: `ATh230`, `ATh232`, `AU238`.
2. Required activity units are supported: `dpm/g`, `Bq/kg`, `mBq/g`.
3. Depth and age columns are inferable.
4. Age model has at least 2 valid depth-age points.
5. AS table is creatable with provenance references.

Unsupported concentration units such as `mg/kg`, `ug/kg`, `µg/kg`, `ppm`, and `ppb` are not converted into activity.

This is intentional: strict mode protects scientific validity, even if that means many datasets fail.

## Strict vs Relaxed Behavior

- `strict`:
  - Missing/unsupported required activity fields fail remap.
  - `processing_log.csv` shows `Status=Failed`, `UnitStatus=Failed`.
- `relaxed`:
  - Remap is kept with `NaN` in missing/unsupported required activity fields.
  - `processing_log.csv` shows `Status=Success`, `UnitStatus=Warning`.
  - `FailureCode` and `FailureDetail` still record the issue.

Use `strict` when you need analysis-ready outputs.
Use `relaxed` when you want broader coverage for exploration.

## Step 2 Outputs

Each run creates `step2_analysis/data/<timestamp>/`.

Core outputs:

- `processing_log.csv`: one row per processed dataset with success/failure reason and diagnostic codes.
- `sites_table.txt`: list of successfully remapped sites used as direct input for `D3v1_01.py`.
- `remapped_tables/<Site>/...`: standardized per-site input tables produced by remapping.
- `analysis_output/<Site>_calc_table.csv`: row-level calculated scientific results for each analyzed site.
- `analysis_output/<Site>_summary.pdf`: per-site visual summary (profiles, age model, derived metrics).
- `remapping_diagnostics.csv`: site-level remapping status joined with discovery metadata.
- `remapping_diagnostic_map.png`: map of remapping success/failure outcomes.

Added diagnostics/validation outputs:

- `mapping_provenance_summary.csv`: global traceability table showing source column, unit, and mapping confidence per target field.
- `u238auth_negative_diagnostics.csv`: all rows with negative `U238auth`, including assigned root cause.
- `integrity_validation_sample.csv`: which sites were selected for sample-based validation.
- `integrity_validation_failures.csv`: detailed validation issues found in sampled sites (empty when no issues).
- `integrity_validation_summary.txt`: compact summary of sample size and pass/fail counts by check category.

Per successful site (`remapped_tables/<Site>/`):

- `<Site>_DS_table.txt`: main remapped measurement table (depth, age, isotope/activity fields, errors).
- `<Site>_AS_table.txt`: sample-level table linking depth/age values to source file and source row.
- `<Site>_Age_model_table.txt`: cleaned depth-age pairs used for interpolation in analysis.
- `<Site>_info_table.txt`: site metadata and fixed analysis parameters (for example lithogenic correction defaults).
- `<Site>_mapping_provenance.csv`: per-site mapping audit trail for each target field.

## Negative `U238auth` Diagnostics

`D3v1_01.py` flags every row as `OK` or `NEGATIVE` and classifies negative rows using deterministic causes:

- `LITHOGENIC_DOMINANCE`
- `SUSPECT_UNIT_MAPPING`
- `SUSPECT_COLUMN_MAPPING`
- `EDGE_NEAR_ZERO_BALANCE`
- `INSUFFICIENT_METADATA`

Artifacts:

- Per-site report: `analysis_output/<Site>_validation_report.txt`
- Global report: `u238auth_negative_diagnostics.csv`

## Integrity Validation

`validate_integrity.py` runs automatically in Step 2 and performs stratified sampling (default 10%).

Checks:

- `unit_consistency`
- `mapping_accuracy`
- `sample_origin_clarity`

Read `integrity_validation_summary.txt` first, then inspect `integrity_validation_failures.csv` if non-zero failures are reported.

## Recommended First Analysis Flow

1. Run `./run_step1_discovery.sh`.
2. Confirm `all_sites_with_coords.csv` exists in the new Step 1 timestamp folder.
3. Run `./run_step2_analysis.sh strict`.
4. Inspect `processing_log.csv` and `remapping_diagnostic_map.png`.
5. Inspect `integrity_validation_summary.txt`.
6. Review selected PDFs in `analysis_output/`.
