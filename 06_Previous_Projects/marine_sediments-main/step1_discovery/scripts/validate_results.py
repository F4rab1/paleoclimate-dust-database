
import json
import sys

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def check_compliance(dataset):
    """
    Independently verifies if a dataset strictly meets D-Sample criteria.
    Returns (True, None) or (False, Reason).
    """
    
    # 1. Marine Check
    # Must have marine indicator in Location OR Basis OR Title
    marine_keywords = ['ocean', 'sea', 'marine', 'core', 'sediment', 'basin', 'gulf', 'ridge', 'mound', 'plateau', 'trench']
    
    loc = str(dataset.get('agg_location', '')).lower()
    basis = str(dataset.get('basis', '')).lower()
    title = str(dataset.get('title', '')).lower()
    
    is_marine = any(k in loc for k in marine_keywords) or \
                any(k in basis for k in marine_keywords) or \
                any(k in title for k in marine_keywords)
                
    if not is_marine:
        return False, f"Location/Basis not recognized as marine (Loc: {dataset.get('agg_location')}, Basis: {dataset.get('basis')})"

    # 2. Variable Check (Th/U + Sediment Depth)
    variables = [v.lower() for v in dataset.get('variables', [])]
    
    # Isotope Presence
    isotope_keywords = ['thorium', 'uranium', '230th', '232th', '238u']
    has_isotope = any(any(ik in v for ik in isotope_keywords) for v in variables)
    
    if not has_isotope:
        return False, "No Thorium or Uranium variables found"

    # Sediment Depth Presence
    # MUST have a depth variable that is NOT just "depth, water"
    has_sediment_depth = False
    depth_vars = [v for v in variables if 'depth' in v]
    
    for dv in depth_vars:
        if 'water' in dv:
            continue # Skip water depth
        has_sediment_depth = True
        break
        
    if not has_sediment_depth:
        return False, f"Missing Sediment Depth (Found: {depth_vars})"

    return True, None

def main():
    import argparse
    import os
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', default='../data', help='Directory containing the JSON file')
    args = parser.parse_args()
    
    json_file = os.path.join(args.data_dir, 'pangaea_d_samples.json')
    print(f"Auditing {json_file}...\n")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {json_file} not found. Run convert_results.py first.")
        sys.exit(1)
        
    passed = 0
    failed = 0
    failures = []
    
    for item in data:
        is_compliant, reason = check_compliance(item)
        if is_compliant:
            passed += 1
        else:
            failed += 1
            failures.append((item['doi'], reason))

    # Report
    print(f"Total Datasets Audited: {len(data)}")
    print(f"{GREEN}Compliant: {passed}{RESET}")
    print(f"{RED}Non-Compliant: {failed}{RESET}")
    
    if failed > 0:
        print("\n--- Compliance Failures ---")
        for doi, reason in failures:
            print(f"DOI: {doi}")
            print(f"Reason: {reason}")
            print("---")
    else:
        print(f"\n{GREEN}SUCCESS: All datasets meet the D-Sample criteria.{RESET}")

if __name__ == "__main__":
    main()
