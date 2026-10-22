#!/bin/bash
set -e

echo "=== Step 1: PANGAEA Data Discovery ==="

# 1. Search (using parameter from args or default)
# Note: Output goes to step1_discovery/data/YYYYMMDD...
# But to make it cleaner, we might want a fixed 'latest' folder or explicit path
# For now, let's just run it and let it create the timestamped folder.
# But subsequent scripts need to know THAT folder.
# So we should probably define a fixed folder for this run or find the latest.

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "Activated virtual environment: .venv"
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Activated virtual environment: venv"
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="step1_discovery/data/${TIMESTAMP}"

MAX_RESULTS=${1:-1000}

echo "Running search with max_results=${MAX_RESULTS}..."
python3 step1_discovery/scripts/pangaea_search.py --output "${OUTPUT_DIR}" --max_results ${MAX_RESULTS}

echo "Converting results..."
# Search created dataset/ inside OUTPUT_DIR
python3 step1_discovery/scripts/convert_results.py --data_dir "${OUTPUT_DIR}" --report_dir "${OUTPUT_DIR}/reports"

echo "Adding coordinates..."
python3 step1_discovery/scripts/add_coordinates.py --dataset_dir "${OUTPUT_DIR}"

echo "Generating Global Site Map..."
python3 step1_discovery/scripts/plot_sites.py \
    --input_csv "${OUTPUT_DIR}/all_sites_with_coords.csv" \
    --output_dir "${OUTPUT_DIR}/reports"

cp "${OUTPUT_DIR}/reports/global_site_map.png" step1_discovery/reports/global_site_map.png

echo "Step 1 Complete. Results in ${OUTPUT_DIR}"
echo "Latest run stored in variable: ${OUTPUT_DIR}"
