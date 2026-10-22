
import csv
import json

def convert_to_json(csv_file, json_file):
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Split lists for cleaner JSON
            row['variables'] = [v.strip() for v in row['variables'].split(';')]
            row['search_keyword'] = [k.strip() for k in row['search_keyword'].split(',')]
            data.append(row)
            
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Created {json_file}")
    return data

def convert_to_markdown(data, md_file):
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# PANGAEA D-Sample Catalog\n\n")
        f.write(f"**Total Samples:** {len(data)}\n\n")
        
        for i, item in enumerate(data, 1):
            f.write(f"### {i}. [{item['title']}]({item['doi']})\n")
            f.write(f"- **First Author:** {item['first_author']}\n")
            f.write(f"- **Location:** {item['agg_location']} (Basis: {item['basis']})\n")
            f.write(f"- **Keywords Matched:** {', '.join(item['search_keyword'])}\n")
            f.write("- **Variables:**\n")
            # List first 10 variables to keep it concise, then etc...
            vars_list = item['variables']
            for v in vars_list[:10]:
                f.write(f"  - {v}\n")
            if len(vars_list) > 10:
                f.write(f"  - *(...and {len(vars_list)-10} more)*\n")
            f.write("\n---\n\n")
            
    print(f"Created {md_file}")

def main():
    import argparse
    import os
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', default='../data', help='Directory containing the input CSV')
    parser.add_argument('--json_dir', default=None, help='Directory to save JSON output')
    parser.add_argument('--report_dir', default=None, help='Directory to save Markdown output')
    args = parser.parse_args()
    
    data_dir = args.data_dir
    json_dir = args.json_dir if args.json_dir else data_dir
    report_dir = args.report_dir if args.report_dir else data_dir
    
    if not os.path.exists(json_dir):
        os.makedirs(json_dir)
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    # Process the main file
    print("Processing main catalog...")
    csv_path = os.path.join(data_dir, 'pangaea_d_samples.csv')
    try:
        data = convert_to_json(csv_path, os.path.join(json_dir, 'pangaea_d_samples.json'))
        convert_to_markdown(data, os.path.join(report_dir, 'pangaea_d_samples_catalog.md'))
    except FileNotFoundError:
        print(f"Warning: Main CSV not found at {csv_path}")

    # Process sub-categories
    categories = ['D_only', 'D_plus_A', 'D_plus_X', 'D_plus_A_plus_X']
    for cat in categories:
        cat_data_dir = os.path.join(data_dir, cat)
        cat_csv = os.path.join(cat_data_dir, 'pangaea_d_samples.csv')
        
        if os.path.exists(cat_csv):
            print(f"Processing category: {cat}")
            
            # Setup output dirs (json goes to data/CAT, md goes to reports/CAT)
            cat_json_dir = os.path.join(json_dir, cat)
            cat_report_dir = os.path.join(report_dir, cat)
            
            if not os.path.exists(cat_json_dir):
                os.makedirs(cat_json_dir)
            if not os.path.exists(cat_report_dir):
                os.makedirs(cat_report_dir)
                
            json_out = os.path.join(cat_json_dir, 'pangaea_d_samples.json')
            data = convert_to_json(cat_csv, json_out)
            convert_to_markdown(data, os.path.join(cat_report_dir, 'pangaea_d_samples_catalog.md'))


if __name__ == "__main__":
    main()
