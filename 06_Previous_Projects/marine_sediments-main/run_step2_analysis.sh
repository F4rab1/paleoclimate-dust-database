#!/bin/bash
set -e

echo "=== Step 2: Data Processing & Analysis ==="

CONTRACT_MODE="${1:-strict}"
if [ "${CONTRACT_MODE}" != "strict" ] && [ "${CONTRACT_MODE}" != "relaxed" ]; then
    echo "Usage: ./run_step2_analysis.sh [strict|relaxed]"
    exit 1
fi

# We need to know where the Input Data (Step 1 output) is.
# For simplicity, we'll find the latest timestamped folder in step1_discovery/data
LATEST_DATA_DIR=$(ls -td step1_discovery/data/*/ | head -1)

if [ -z "$LATEST_DATA_DIR" ]; then
    echo "No input data found in step1_discovery/data/. Run Step 1 first."
    exit 1
fi

# Activate virtual environment if it exists
VENV_PATH=""
if [ -f ".venv/bin/activate" ]; then
    VENV_PATH="$(pwd)/.venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    VENV_PATH="$(pwd)/venv/bin/activate"
fi

if [ -n "$VENV_PATH" ]; then
    source "$VENV_PATH"
    echo "Activated virtual environment: $VENV_PATH"
fi

DATASET_DIR="${LATEST_DATA_DIR}"
echo "Using input data from: ${DATASET_DIR}"
echo "Contract mode: ${CONTRACT_MODE}"

# Create timestamped output directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="step2_analysis/data/${TIMESTAMP}"
mkdir -p "${OUTPUT_DIR}"

echo "Output will be saved to: ${OUTPUT_DIR}"

echo "1. Remapping Datasets..."
python3 step2_analysis/scripts/process_datasets.py \
    --dataset_dir "${DATASET_DIR}" \
    --workspace_root "step2_analysis" \
    --output_dir "${OUTPUT_DIR}" \
    --contract_mode "${CONTRACT_MODE}"

echo "2. Running Analysis (D3v1_01)..."
python3 step2_analysis/scripts/D3v1_01.py \
    --data_dir "${OUTPUT_DIR}" \
    --output_dir "${OUTPUT_DIR}/analysis_output"

# Keep global diagnostics also at timestamp root for easier downstream discovery.
cp "${OUTPUT_DIR}/analysis_output/u238auth_negative_diagnostics.csv" "${OUTPUT_DIR}/u238auth_negative_diagnostics.csv" 2>/dev/null || true

echo "3. Running Sample-Based Integrity Validation..."
python3 step2_analysis/scripts/validate_integrity.py \
    --output_dir "${OUTPUT_DIR}" \
    --sample_fraction 0.10 \
    --seed 42

echo "4. Generating Diagnostic Map..."
python3 step2_analysis/scripts/diagnostic_map.py \
    --input_csv "${DATASET_DIR}all_sites_with_coords.csv" \
    --output_dir "${OUTPUT_DIR}" \
    --data_tables_dir "${OUTPUT_DIR}/remapped_tables"

# Copy Global Site Map from Step 1 for completeness
if [ -f "${DATASET_DIR}reports/global_site_map.png" ]; then
    echo "Copying Global Site Map from Step 1..."
    cp "${DATASET_DIR}reports/global_site_map.png" "${OUTPUT_DIR}/global_site_map.png"
fi

# Copy latest outputs to stable location for README
cp "${OUTPUT_DIR}/analysis_output"/*.pdf step2_analysis/data/analysis_output/ 2>/dev/null || true
cp "${OUTPUT_DIR}/remapping_diagnostic_map.png" step2_analysis/data/remapping_diagnostic_map.png 2>/dev/null || true
cp "${OUTPUT_DIR}/global_site_map.png" step2_analysis/data/global_site_map.png 2>/dev/null || true

echo "Step 2 Complete. Results in ${OUTPUT_DIR}"
echo "Latest run stored in variable: ${OUTPUT_DIR}"
