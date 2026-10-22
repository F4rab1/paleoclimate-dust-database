
import os
import csv
import json
import requests
import time
import xml.etree.ElementTree as ET
import argparse

# Usage: python add_coordinates.py --dataset_dir ../data/YYYYMMDD_HHMMSS/dataset

NS = {'md': 'http://www.pangaea.de/MetaData'}

def get_coordinates(doi):
    """
    Fetches the metadata for a DOI and returns mean Lat/Lon.
    Uses the PANGAEA ElasticSearch API.
    """
    url = "https://ws.pangaea.de/es/pangaea/_search"
    # Search by DOI (URI)
    query = {
        "query": {
            "query_string": {
                "query": f'"{doi}"',
                "default_operator": "AND"
            }
        },
        "size": 1
    }
    
    try:
        response = requests.post(url, json=query)
        response.raise_for_status()
        data = response.json()
        
        if not data['hits']['hits']:
            print(f"  No info found for DOI: {doi}")
            return None, None

        hit = data['hits']['hits'][0]
        source = hit.get('_source', {})

        if 'meanPosition' in source and source['meanPosition']:
            pos = source['meanPosition']
            return pos.get('lat'), pos.get('lon')
            
        if 'southBoundLatitude' in source and 'northBoundLatitude' in source:
            min_lat = source['southBoundLatitude']
            max_lat = source['northBoundLatitude']
            min_lon = source['westBoundLongitude']
            max_lon = source['eastBoundLongitude']
            
            mean_lat = (min_lat + max_lat) / 2.0
            mean_lon = (min_lon + max_lon) / 2.0
            return mean_lat, mean_lon
            
    except Exception as e:
        print(f"  Error fetching {doi}: {e}")
        return None, None
        
    return None, None
        
    return None, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset_dir', required=True, help='Path to the dataset directory (e.g. data/timestamp/dataset)')
    args = parser.parse_args()
    
    dataset_dir = args.dataset_dir
    categories = ['D_only', 'D_plus_A', 'D_plus_X', 'D_plus_A_plus_X']
    
    all_sites = []
    
    print(f"Processing datasets in {dataset_dir}...")
    
    for cat in categories:
        cat_dir = os.path.join(dataset_dir, cat)
        input_csv = os.path.join(cat_dir, 'pangaea_d_samples.csv')
        
        if not os.path.exists(input_csv):
            print(f"Skipping {cat} (file not found)")
            continue
            
        print(f"Processing Category: {cat}")
        
        rows = []
        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        updated_rows = []
        for i, row in enumerate(rows):
            doi = row['doi']
            print(f"  [{i+1}/{len(rows)}] Fetching coords for {doi}...", end='\r')
            lat, lon = get_coordinates(doi)
            
            row['latitude'] = lat if lat is not None else ''
            row['longitude'] = lon if lon is not None else ''
            row['category'] = cat # Add category for master file
            
            updated_rows.append(row)
            all_sites.append(row)
            time.sleep(0.1) # Rate limit
            
        print(f"\n  Completed {cat}.")
        
        # Save updated category CSV
        output_csv = os.path.join(cat_dir, 'pangaea_d_samples_coords.csv')
        fieldnames = list(updated_rows[0].keys())
        
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

    # Save Master CSV with Coords and Categories
    master_csv = os.path.join(dataset_dir, 'all_sites_with_coords.csv')
    if all_sites:
        fieldnames = list(all_sites[0].keys())
        with open(master_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_sites)
        print(f"\nSaved Global Master List to: {master_csv}")
    else:
        print("No data found!")

if __name__ == "__main__":
    main()
