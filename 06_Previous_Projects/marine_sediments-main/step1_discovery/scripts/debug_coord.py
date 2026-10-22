
import requests
import xml.etree.ElementTree as ET

doi = "10.1594/PANGAEA.811988"
url = "https://ws.pangaea.de/es/pangaea/_search"
query = {
    "query": {
        "query_string": {
            "query": f'"{doi}"',
            "default_operator": "AND"
        }
    },
    "size": 1
}

r = requests.post(url, json=query)
data = r.json()
source = data['hits']['hits'][0]['_source']
print("JSON Keys:", source.keys())
for k in ['minLatitude', 'maxLatitude', 'minLongitude', 'maxLongitude', 'southBoundLatitude', 'northBoundLatitude', 'westBoundLongitude', 'eastBoundLongitude', 'meanPosition']:
    if k in source:
        print(f"{k}: {source[k]} (Type: {type(source[k])})")


xml_content = source.get('xml')
# Search for 'Latitude' in raw XML
if 'Latitude' in xml_content:
    print("Found 'Latitude' in XML text at index:", xml_content.find('Latitude'))
    print("Context:", xml_content[xml_content.find('Latitude')-50:xml_content.find('Latitude')+100])

root = ET.fromstring(xml_content)
NS = {'md': 'http://www.pangaea.de/MetaData'}

print("\n--- Searching for Extent ---")
extent = root.find(f".//md:extent", NS)
print(f"Extent: {extent}")

