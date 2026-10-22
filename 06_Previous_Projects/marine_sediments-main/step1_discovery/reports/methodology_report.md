# Methodology Report: Mineral Dust Deposition Data Discovery
**Date:** December 28, 2025
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
- **Total Unique Datasets Discovered:** 968
- **Qualified D-Samples (Marine Sediment + Th/U + Depth):** 470
- **Excluded Datasets:** 498

### Data Availability Breakdown (Qualified D-Samples)
Among the **470** qualified D-Sample sites, the availability of complementary data types (Age models, Grain size) is as follows:

| Category | Definition | Count |
| :--- | :--- | :--- |
| **D only** | Dust (Th/U) data only | 206 |
| **D + A** | Dust + Age Model | 250 |
| **D + X** | Dust + Grain Size | 9 |
| **D + A + X** | Dust + Age + Grain Size | 5 |

*Note: "Age model" was identified by the presence of "Age" or "Time" variables; "Grain size" by "Grain size", "Sand", "Silt", or "Clay".*

## 5. Methodological Limitations
1.  **Metadata Heterogeneity:** Variable names in PANGAEA are not perfectly standardized. While the keyword list covers the majority of cases, non-standard spellings (e.g., "232-Thorium") not captured by the specific keyword list may be missed.
2.  **Water vs. Sediment Depth:** The distinction between water samples and sediment top-core samples can be ambiguous in metadata. A strict filter excluding "Depth, water" was applied to minimize false positives, which may exclude some hybrid datasets.
3.  **Separation of Age Models:** Age models are frequently published as separate datasets linked only by the "Event" label. The counts above reflect variables *within* the same dataset file. The actual number of sites with age control available (via dataset linkage) is likely higher.

## 6. Reproducibility Statement
This dataset compilation is fully reproducible. The search script `pangaea_search.py` contains the exact code used to query the API, parse valid XML metadata, and filter results. A robust validation script `validate_results.py` has been included to independently verify that all 470 datasets strictly meet the inclusion criteria.
