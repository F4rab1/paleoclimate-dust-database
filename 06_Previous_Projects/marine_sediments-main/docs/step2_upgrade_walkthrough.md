# Step 2 Upgrade Walkthrough

## Why this change was needed

The original Step 2 flow produced useful outputs, but it had three gaps:

1. Limited traceability from raw PANGAEA columns to remapped/analysis fields.
2. Negative `U238auth` values were visible but not consistently explained at row level.
3. Quality checks were implicit (manual spot checks) instead of a reproducible validation step.

The upgrade was designed to make every accepted result auditable, keep scientifically unsafe inputs blocked in `strict` mode, and still support higher-coverage exploration in `relaxed` mode.

## Requirements-to-Implementation mapping

### 1) Flag and explain negative `U238auth` values

Implemented in `step2_analysis/scripts/D3v1_01.py`:

- Added `U238auth_flag` (`OK` / `NEGATIVE`) for all rows.
- Added root-cause columns:
  - `U238auth_root_cause`
  - `U238auth_root_cause_detail`
- Deterministic root-cause categories:
  - `LITHOGENIC_DOMINANCE`
  - `SUSPECT_UNIT_MAPPING`
  - `SUSPECT_COLUMN_MAPPING`
  - `EDGE_NEAR_ZERO_BALANCE`
  - `INSUFFICIENT_METADATA`
- Outputs:
  - Per-site: `analysis_output/<Site>_validation_report.txt`
  - Global: `u238auth_negative_diagnostics.csv`

### 2) Ensure each successful dataset has an age model

Implemented in `step2_analysis/scripts/process_datasets.py`:

- Age source inference priority: `Age`, `Age model`, `Age dated`.
- Age model normalization:
  - drop null depth/age pairs
  - deduplicate `(Depth, Age)` pairs
  - sort by depth
- Enforced minimum of 2 valid points; otherwise dataset fails with explicit failure code.
- Output for successful remaps:
  - `<Site>_Age_model_table.txt`

### 3) Standardize dataset structure and preserve original sample linkage in AS table

Implemented in `step2_analysis/scripts/process_datasets.py`:

- `AS_table` is mandatory for successful remaps.
- Standardized columns include provenance linkage:
  - `Sample ID`
  - `Depth top [m]`
  - `Depth bottom [m]`
  - `Depth center [m]`
  - `Age [ka B.P.]`
  - `Age R.E. [frac., 2σ]`
  - `Type`
  - `Source file`
  - `Source row index`
  - `Age source column`
  - `Depth source column`

### 4) Conduct sample-based integrity validation

Implemented in new script `step2_analysis/scripts/validate_integrity.py` and wired into `run_step2_analysis.sh`.

- Default stratified sampling: `10%` (`--sample_fraction 0.10`, `--seed 42`).
- Validation checks:
  - `unit_consistency`
  - `mapping_accuracy`
  - `sample_origin_clarity`
- Outputs:
  - `integrity_validation_sample.csv`
  - `integrity_validation_failures.csv`
  - `integrity_validation_summary.txt`

## Provenance-first remapping model

`process_datasets.py` now writes mapping provenance at two levels:

- Per-site: `remapped_tables/<Site>/<Site>_mapping_provenance.csv`
- Global: `mapping_provenance_summary.csv`

Each mapped target field records:

- `target_field`
- `source_column`
- `source_unit_token`
- `unit_class`
- `conversion_factor`
- `mapping_rule`
- `mapping_confidence`
- `ambiguous_candidates`
- `status`

This enables direct auditing of mapping and unit decisions.

## Unit policy and scientific safety

Supported activity units:

- `dpm/g`
- `Bq/kg` (converted by `0.06`)
- `mBq/g` (converted by `0.06`)

Unsupported activity-like/mass units:

- `mg/kg`
- `ug/kg` / `µg/kg`
- `ppm`
- `ppb`

Important: there is no automatic conversion from mass concentration units to activity units in this workflow.

## Strict vs Relaxed contract mode

Implemented in `process_datasets.py` and exposed via `run_step2_analysis.sh`.

- `strict` (default):
  - Missing/unsupported required activity fields fail remap.
  - `processing_log.csv` records `Status=Failed`, `UnitStatus=Failed`.

- `relaxed`:
  - Remap is preserved with `NaN` in missing/unsupported required activity fields.
  - `processing_log.csv` records `Status=Success`, `UnitStatus=Warning`, and keeps `FailureCode`/`FailureDetail`.

This preserves strict scientific outputs while allowing broader exploratory coverage when needed.

## Pipeline integration changes

`run_step2_analysis.sh` now:

1. Accepts mode argument: `./run_step2_analysis.sh [strict|relaxed]`
2. Passes mode to remapping: `--contract_mode`
3. Runs `validate_integrity.py` after analysis
4. Copies global negative diagnostics to run root:
   `u238auth_negative_diagnostics.csv`

## Additional robustness fix

`D3v1_01.py` age interpolation was hardened to avoid failures when depth top/bottom values are missing (`NaN`).

- Added safe interpolation helper.
- Added fallback from missing top/bottom depth to center depth.
- Prevented all-`NaN` nearest-neighbor indexing crashes.

## New and changed artifacts

Per timestamped Step 2 run:

- `processing_log.csv` (extended with `AgeModelStatus`, `AgeModelPoints`, `ASStatus`, `UnitStatus`, `FailureCode`, `FailureDetail`)
- `mapping_provenance_summary.csv`
- `u238auth_negative_diagnostics.csv`
- `integrity_validation_sample.csv`
- `integrity_validation_failures.csv`
- `integrity_validation_summary.txt`

Per successful site:

- `<Site>_DS_table.txt`
- `<Site>_AS_table.txt`
- `<Site>_Age_model_table.txt`
- `<Site>_info_table.txt`
- `<Site>_mapping_provenance.csv`

