
import requests
import json
import csv
import xml.etree.ElementTree as ET
import time
import sys
import re
import argparse
import os

# Constants
BASE_URL = "https://ws.pangaea.de/es/pangaea/_search"
MANDATORY_KEYWORDS = [
    "Thorium-232", "232Th",
    "Thorium-230", "230Th",
    "Thorium-230 excess", "230Th xs",
    "Uranium-238", "238U",
    "U-238"
]
NS = {'md': 'http://www.pangaea.de/MetaData'}

def search_pangaea(keyword, size=1000):
    """Searches PANGAEA for a given keyword."""
    print(f"Searching for: {keyword}")
    try:
        response = requests.get(f"{BASE_URL}", params={"q": keyword, "size": size})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error searching for {keyword}: {e}")
        return None

def extract_metadata(hit, keyword):
    """
    Extracts metadata from a PANGAEA search hit (ES result).
    Parses the embeded XML for detailed fields.
    """
    source = hit.get('_source', {})
    xml_content = source.get('xml')
    
    if not xml_content:
        return None

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    # DOI
    doi = source.get('URI', '')
    if not doi:
        # Try to find in XML
        uri_elem = root.find('.//md:citation/md:URI', NS)
        if uri_elem is not None:
            doi = uri_elem.text

    # Title
    title = ""
    title_elem = root.find('.//md:citation/md:title', NS)
    if title_elem is not None:
        title = title_elem.text

    # Authors (First Author)
    first_author = ""
    author_elem = root.find('.//md:citation/md:author/md:lastName', NS)
    if author_elem is not None:
        first_author = author_elem.text
    
    # Variables (Parameters)
    variables = []
    for param in root.findall('.//md:matrixColumn/md:parameter/md:name', NS):
        if param.text:
            variables.append(param.text)
    
    # Aggregated Location / Basis for Marine check
    agg_location = source.get('agg-location', [])
    basis = source.get('agg-basis', '')
    
    metadata = {
        'id': hit.get('_id'),
        'doi': doi,
        'title': title,
        'first_author': first_author,
        'variables': "; ".join(variables),
        'agg_location': "; ".join(agg_location) if isinstance(agg_location, list) else agg_location,
        'basis': basis,
        'search_keyword': keyword,
        'raw_variables': variables # Keep list for filtering
    }
    return metadata

def is_d_sample(metadata):
    """
    Determines if a dataset qualifies as a D-Sample.
    Criteria:
    1. Marine sediment archive
    2. Presence of Th/U isotope
    3. Presence of sediment depth info
    """
    
    # 1. Marine Check
    is_marine = False
    loc_str = str(metadata.get('agg_location', '')).lower()
    basis_str = str(metadata.get('basis', '')).lower()
    title_str = str(metadata.get('title', '')).lower()
    
    marine_indicators = ['ocean', 'sea', 'marine', 'core', 'sediment', 'basin', 'gulf']
    if any(ind in loc_str for ind in marine_indicators):
        is_marine = True
    elif any(ind in basis_str for ind in marine_indicators):
        is_marine = True
    elif any(ind in title_str for ind in marine_indicators):
        # Fallback to title if location/basis is empty, but be careful
        is_marine = True
        
    if not is_marine:
        return False, "Not Marine"

    # 2. Th/U Check
    is_d_sample_isotope = False
    isotope_keywords = ['thorium', 'uranium', '230th', '232th', '238u']
    
    # Check variables for isotope keywords
    for var in metadata['raw_variables']:
        v_lower = var.lower()
        if any(ik in v_lower for ik in isotope_keywords):
            is_d_sample_isotope = True
            break
            
    if not is_d_sample_isotope:
        return False, "No Thorium or Uranium variables found"

    # 3. Depth Check
    has_depth = False
    
    # We want to exclude "water depth" if it's the only depth. 
    # Valid sediment depths often look like: "Depth, sediment/rock", "Depth top", "Depth bot", "Depth [m]", "Depth" (if not water)
    
    for var in metadata['raw_variables']:
        v_lower = var.lower()
        
        # Explicit exclude for water depth variables
        if 'water' in v_lower:
            continue
            
        if 'depth' in v_lower:
            has_depth = True
            # We found a non-water depth variable
            break
            
    if not has_depth:
        return False, "No Sediment Depth (Found only Water Depth or None)"

    return True, "Qualified"


def categorize_sample(variables_str):
    """Categorizes the sample based on variable availability."""
    v = variables_str.lower()
    has_age = 'age' in v or 'time' in v
    has_grain = any(x in v for x in ['grain','sand','silt','clay','size'])
    
    if has_age and has_grain:
        return 'D_plus_A_plus_X'
    elif has_age:
        return 'D_plus_A'
    elif has_grain:
        return 'D_plus_X'
    else:
        return 'D_only'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='../data', help='Output directory for results')
    parser.add_argument('--max_results', type=int, default=1000, help='Maximum number of results to fetch per keyword')
    args = parser.parse_args()
    
    max_results = args.max_results
    output_dir = args.output

    # Ensure directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_results = []
    
    print("Starting PANGAEA D-Sample Discovery...")
    print(f"  Max results per keyword: {max_results}")
    
    # 1. Search
    for kw in MANDATORY_KEYWORDS:
        data = search_pangaea(kw, size=max_results)
        if data and 'hits' in data and 'hits' in data['hits']:
            hits = data['hits']['hits']
            print(f"  Found {len(hits)} results for '{kw}'")
            for hit in hits:
                meta = extract_metadata(hit, kw)
                if meta:
                    all_results.append(meta)
        time.sleep(1) # Be polite to API

    # 2. Deduplicate
    unique_datasets = {}
    for res in all_results:
        doi = res['doi']
        if doi not in unique_datasets:
            unique_datasets[doi] = res
        else:
            unique_datasets[doi]['search_keyword'] += f", {res['search_keyword']}"

    print(f"Total unique datasets found: {len(unique_datasets)}")

    # 3. Filter and Categorize
    d_samples = []
    rejected = []
    
    # Dictionary to hold lists for each category
    categories = {
        'D_only': [],
        'D_plus_A': [],
        'D_plus_X': [],
        'D_plus_A_plus_X': []
    }

    for doi, data in unique_datasets.items():
        is_qualified, reason = is_d_sample(data)
        if is_qualified:
            data['classification'] = 'D-Sample'
            d_samples.append(data)
            
            # Sub-categorization
            cat = categorize_sample(data['variables'])
            categories[cat].append(data)
        else:
            data['classification'] = f"Excluded: {reason}"
            rejected.append(data)

    print(f"Qualified D-Samples: {len(d_samples)}")

    # 4. Save Results
    fieldnames = ['doi', 'first_author', 'title', 'variables', 'agg_location', 'basis', 'search_keyword', 'classification']
    
    # Save Main D-Samples
    d_samples_path = os.path.join(output_dir, 'pangaea_d_samples.csv')
    with open(d_samples_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(d_samples)
        
    # Save Categorized D-Samples
    for cat_name, items in categories.items():
        if not items:
            continue
            
        cat_dir = os.path.join(output_dir, cat_name)
        if not os.path.exists(cat_dir):
            os.makedirs(cat_dir)
            
        cat_file = os.path.join(cat_dir, 'pangaea_d_samples.csv')
        with open(cat_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(items)
        print(f"  Saved {len(items)} samples to {cat_name}/pangaea_d_samples.csv")
        
    # Save All (including excluded) for transparency
    all_results_path = os.path.join(output_dir, 'pangaea_all_results_raw.csv')
    with open(all_results_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(d_samples + rejected)

    print(f"Results saved to '{d_samples_path}' and '{all_results_path}'")

if __name__ == "__main__":
    main()
