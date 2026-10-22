# Marine Sediments Codebase Guide (for AI Agents)

## Purpose
This repository implements a 2-step pipeline for marine sediment dust-deposition analysis:
1. Discover and classify candidate PANGAEA datasets (D, D+A, D+X, D+A+X).
2. Remap D+A-like datasets into D3-compatible tables and run the legacy `D3v1_01` analysis workflow.

Primary goal: produce standardized per-site tables and analysis PDFs without inventing missing scientific variables.

## Repository Map
- `run_step1_discovery.sh`: end-to-end Step 1 runner.
- `run_step2_analysis.sh`: end-to-end Step 2 runner (uses latest Step 1 output).
- `step1_discovery/scripts/`: discovery, conversion, coordinates, map, validation/report helpers.
- `step2_analysis/scripts/`: remapping (`process_datasets.py`), scientific analysis (`D3v1_01.py`), remap diagnostics map.
- `step1_discovery/data/<timestamp>/`: timestamped discovery outputs (ignored by git).
- `step2_analysis/data/<timestamp>/`: timestamped remap + analysis outputs (ignored by git).
- `step2_analysis/data/remapped_tables/`, `step2_analysis/data/analysis_output/`: stable copies used for quick access/demo.
- `example_files/`: template-like table examples (`*_DS_table.txt`, `*_AS_table.txt`, `*_age_model_table.txt`, `*_info_table.txt`).
- `docs/`: project notes on known issues (AS table semantics, lithogenic correction, age inversions, negative DMAR diagnostics).

## Environment
- Python dependencies: `requirements.txt` (`pandas`, `numpy`, `matplotlib`, `cartopy`, `requests`, `scipy`, `seaborn`, `tqdm`, `more_itertools`).
- Recommended setup:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt`
- Network is required for discovery/remapping download steps (PANGAEA API + DOI textfile fetches).

## Canonical Run Flow
1. Step 1:
   - `./run_step1_discovery.sh [MAX_RESULTS]`
   - Produces `step1_discovery/data/<timestamp>/...`
   - Key artifact: `all_sites_with_coords.csv`
2. Step 2:
   - `./run_step2_analysis.sh`
   - Auto-selects latest `step1_discovery/data/*/`
   - Produces `step2_analysis/data/<timestamp>/`

Important: `run_step2_analysis.sh` depends on Step 1 timestamp folder shape and expects `all_sites_with_coords.csv` in that folder.

## Step 1 Data Contract
- `pangaea_search.py`:
  - Queries PANGAEA ES endpoint for Th/U keywords.
  - Deduplicates by DOI.
  - Applies D-sample filters: marine context, isotope presence, sediment depth (not only water depth).
  - Writes:
    - `pangaea_d_samples.csv`
    - `pangaea_all_results_raw.csv`
    - category CSVs in `D_only/`, `D_plus_A/`, `D_plus_X/`, `D_plus_A_plus_X/`
- `convert_results.py`:
  - Converts CSV(s) to JSON + markdown catalog(s).
- `add_coordinates.py`:
  - Adds `latitude`, `longitude`, `category`.
  - Writes per-category `pangaea_d_samples_coords.csv` and master `all_sites_with_coords.csv`.
- `plot_sites.py`:
  - Creates `global_site_map.png`.

## Step 2 Data Contract
- `process_datasets.py`:
  - Input: `all_sites_with_coords.csv`, processes categories `D_plus_A` and `D_plus_A_plus_X`.
  - Downloads raw `?format=textfile` tables by DOI.
  - Fuzzy-maps columns (depth, age, isotopes), converts units (`Bq/kg`/`mBq/g` to `dpm/g` via `0.06`), computes relative errors where possible.
  - Writes per-site folder in `remapped_tables/<Site>/` with:
    - `<Site>_DS_table.txt`
    - `<Site>_Age_model_table.txt`
    - `<Site>_info_table.txt`
    - optionally `<Site>_AS_table.txt` when dating-method signals are detected
  - Writes global:
    - `sites_table.txt`
    - `processing_log.csv`
- `D3v1_01.py`:
  - Input: `sites_table.txt` + `remapped_tables/`.
  - Output per site in `analysis_output/`:
    - `<Site>_calc_table.csv`
    - `<Site>_summary.pdf`
    - optional `<Site>_validation_report.txt` for negative `U238auth` diagnostics.
- `diagnostic_map.py`:
  - Joins `all_sites_with_coords.csv` with remap outcomes.
  - Writes `remapping_diagnostics.csv` and `remapping_diagnostic_map.png`.

## Naming and Schema Conventions
- Site identifier: `PANGAEA_<doi_suffix>` (e.g. DOI `10.1594/PANGAEA.811988` -> `PANGAEA_811988`).
- Core table suffixes:
  - `*_DS_table.txt`: dust/isotope data by depth.
  - `*_AS_table.txt`: age-sample tie points (optional/conditional in current logic).
  - `*_Age_model_table.txt`: depth-age pairs required by `D3v1_01.py` interpolation.
  - `*_info_table.txt`: site metadata and lithogenic correction defaults.
- `sites_table.txt` column names are consumed as-is by `D3v1_01.py` (includes typo `Latitide N`); do not rename without coordinated updates.

## Known Caveats (from code + docs)
- AS table semantics are imperfect: many PANGAEA records do not clearly expose age tie-point method metadata.
- Age inversions/multi-core mixed sequences can create visually odd line connections in PDFs.
- Negative DMAR/U238auth can occur due to input chemistry/assumptions (not always a code bug).
- Lithogenic correction is currently defaulted (0.6 with abs err 0.1) unless manually changed.
- `D3v1_01.py` is a notebook-derived script with broad `try/except`; failures may be logged and skipped per site instead of hard-failing.

## Editing Guidance for Agents
- Preserve table/file naming expected by `D3v1_01.py`.
- Prefer minimal, localized changes; this pipeline is path- and schema-sensitive.
- Keep CLI compatibility for existing run scripts (`run_step1_discovery.sh`, `run_step2_analysis.sh`).
- Avoid modifying generated timestamp data unless task explicitly targets outputs.
- If changing remap schema, update both producer (`process_datasets.py`) and consumer (`D3v1_01.py`) in the same change.

## Validation Checklist After Changes
1. Run `python3 -m compileall step1_discovery/scripts step2_analysis/scripts`.
2. For Step 1 changes: run on a small sample (`./run_step1_discovery.sh 50`) and confirm `all_sites_with_coords.csv` + map output.
3. For Step 2 changes: run `./run_step2_analysis.sh` and confirm:
   - `processing_log.csv` exists and has success/failure rows.
   - `sites_table.txt` exists.
   - At least one `*_DS_table.txt` and `*_summary.pdf` are generated.
4. Spot-check one remapped site folder against expected suffix set.

## Non-Goals
- Do not treat this repository as a generalized geochemistry framework; it is a task-specific pipeline with hardcoded scientific assumptions.
- Do not silently "fix" scientific constants without documenting rationale in `docs/` and code comments.
