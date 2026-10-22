
import sys
import requests
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('doi', help='DOI (e.g. 10.1594/PANGAEA.811988)')
    args = parser.parse_args()
    
    doi = args.doi.replace('doi:', '').strip()
    if doi.startswith('http'):
        doi = doi.split('doi.org/')[-1]
        
    url = f"https://doi.pangaea.de/{doi}?format=textfile"
    print(f"Downloading from: {url}")
    
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        
        print("\n--- HEADER & FIRST 20 LINES ---")
        lines = []
        for i, line in enumerate(r.iter_lines(decode_unicode=True)):
            if i < 50:
                print(line)
            lines.append(line)
            if i > 50:
                break
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
