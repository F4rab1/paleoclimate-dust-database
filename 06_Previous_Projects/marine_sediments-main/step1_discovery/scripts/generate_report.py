
import csv
import argparse
import os
import datetime

def calculate_stats(csv_path):
    d_only = 0
    d_a = 0
    d_x = 0
    d_a_x = 0
    total_samples = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_samples += 1
            vars_str = row['variables'].lower()
            has_age = 'age' in vars_str or 'time' in vars_str
            has_grain = any(x in vars_str for x in ['grain','sand','silt','clay','size'])
            
            if has_age and has_grain:
                d_a_x += 1
            elif has_age:
                d_a += 1
            elif has_grain:
                d_x += 1
            else:
                d_only += 1
                
    return {
        'total': total_samples,
        'd_only': d_only,
        'd_a': d_a,
        'd_x': d_x,
        'd_a_x': d_a_x
    }

def get_total_found(all_results_path):
    count = 0
    with open(all_results_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = sum(1 for row in reader)
    return count

def generate_markdown(stats, total_found, output_path):
    today = datetime.datetime.now().strftime("%B %d, %Y")
    excluded = total_found - stats['total']
    
    content = f"""# Methodology Report: Mineral Dust Deposition Data Discovery
**Date:** {today}
**Source Database:** PANGAEA (https://www.pangaea.de)
**Access Method:** Systematic API Query (REST/OpenSearch)

## 1. Data Source
Data was retrieved from the PANGAEA Data Publisher for Earth & Environmental Science database using the public ElasticSearch API endpoint (`https://ws.pangaea.de/es/pangaea/_search`). The search focused on identifying marine sediment archives containing Thorium and Uranium isotopic measurements suitable for Dust Mass Accumulation Rate (DMAR) calculation.

## 2. Search Strategy
A systematic, single-keyword search strategy was employed to maximize recall and transparency. Compound queries (e.g., "Thorium AND Sediment") were avoided to prevent false negatives arising from inconsistent metadata tagging.

**Keywords Query List:**
- `Thorium-232`, `232Th`
- `Thorium-230`, `230Th`
- `Thorium-230 excess`, `230Th xs`
- `Uranium-238`, `238U`, `U-238`

**Processing Workflow:**
1. **Query Execution:** Each keyword was queried independently against the PANGAEA index.
2. **Metadata Extraction:** For each hit, high-resolution metadata was parsed from the embedded XML `md:MetaData` object to ensure accurate identification of variables, authors, and archive types.
3. **Deduplication:** Datasets were deduplicated based on their unique Digital Object Identifier (DOI).
4. **Filtering:** Deduplicated results were rigorously filtered according to the inclusion criteria below.

## 3. Inclusion and Exclusion Criteria

**Inclusion Criteria (D-Samples):**
To qualify as a "D-Sample" (Dust-proxy Sample), a dataset must meet **all** of the following:
1. **Archive Type:** Must be a marine sediment core or grab sample. (Identified via location keywords: "Ocean", "Sea", "Marine", or Basis: "Ship Name", "Core").
2. **Isotopic Data:** Must contain at least one Th/U isotope variable matching the search keywords in the dataset's parameter list.
3. **Depth Coordinates:** Must contain a sediment depth variable (e.g., "Depth, sediment/rock").

**Exclusion Criteria:**
- **Water Column Samples:** Datasets containing only water depth information (e.g., "Depth, water") were excluded.
- **Terrestrial/Ice Archives:** Datasets from ice cores or land stations were excluded.
- **Model Output:** Purely synthetic or model-derived datasets were excluded.
- **Age Control:** The presence of an age model (A-Sample) was **NOT** required for inclusion.

## 4. Results Overview

The systematic search yielded the following distribution of datasets:

### Search Statistics
- **Total Unique Datasets Discovered:** {total_found}
- **Qualified D-Samples (Marine Sediment + Th/U + Depth):** {stats['total']}
- **Excluded Datasets:** {excluded}

### Data Availability Breakdown (Qualified D-Samples)
Among the **{stats['total']}** qualified D-Sample sites, the availability of complementary data types (Age models, Grain size) is as follows:

| Category | Definition | Count |
| :--- | :--- | :--- |
| **D only** | Dust (Th/U) data only | {stats['d_only']} |
| **D + A** | Dust + Age Model | {stats['d_a']} |
| **D + X** | Dust + Grain Size | {stats['d_x']} |
| **D + A + X** | Dust + Age + Grain Size | {stats['d_a_x']} |

*Note: "Age model" was identified by the presence of "Age" or "Time" variables; "Grain size" by "Grain size", "Sand", "Silt", or "Clay".*

## 5. Methodological Limitations
1.  **Metadata Heterogeneity:** Variable names in PANGAEA are not perfectly standardized. While the keyword list covers the majority of cases, non-standard spellings (e.g., "232-Thorium") not captured by the specific keyword list may be missed.
2.  **Water vs. Sediment Depth:** The distinction between water samples and sediment top-core samples can be ambiguous in metadata. A strict filter excluding "Depth, water" was applied to minimize false positives, which may exclude some hybrid datasets.
3.  **Separation of Age Models:** Age models are frequently published as separate datasets linked only by the "Event" label. The counts above reflect variables *within* the same dataset file. The actual number of sites with age control available (via dataset linkage) is likely higher.

## 6. Reproducibility Statement
This dataset compilation is fully reproducible. The search script `pangaea_search.py` contains the exact code used to query the API, parse valid XML metadata, and filter results. A robust validation script `validate_results.py` has been included to independently verify that all {stats['total']} datasets strictly meet the inclusion criteria.
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Report generated: {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', required=True, help='Directory containing the results CSVs')
    # Default output is same as data_dir unless specified
    parser.add_argument('--output_dir', default=None, help='Directory to save the report')
    args = parser.parse_args()
    
    data_dir = args.data_dir
    output_dir = args.output_dir if args.output_dir else data_dir
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    d_samples_path = os.path.join(data_dir, 'pangaea_d_samples.csv')
    all_results_path = os.path.join(data_dir, 'pangaea_all_results_raw.csv')
    report_path = os.path.join(output_dir, 'methodology_report.md')
    
    if not os.path.exists(d_samples_path) or not os.path.exists(all_results_path):
        print(f"Error: Required CSV files not found in {data_dir}")
        return

    print("Calculating statistics...")
    stats = calculate_stats(d_samples_path)
    total_found = get_total_found(all_results_path)
    
    print("Generating report...")
    generate_markdown(stats, total_found, report_path)

if __name__ == "__main__":
    main()
