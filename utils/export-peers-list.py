import urllib.request
from bs4 import BeautifulSoup
import json

NonAsciiCharDict = {
    '✔': True,
    '✘': False,
    '—': None,
}

url = "https://peering.ee.columbia.edu/peers/"
json_filename = 'Export.json'

with urllib.request.urlopen(url) as rsp:
    html = rsp.read()

    page = BeautifulSoup(html, features="html.parser")

    peers_table = page.find("table")
    peers_rows = peers_table.tbody.find_all("tr")
    peers_attrs = [cell.text.strip() for cell in peers_table.thead.find_all("th")]

    result = []
    for r in peers_rows:
        cells = r.find_all("td")
        entry = {}
        for idx, cell in enumerate(cells):
            value = cell.text.strip()
            if value in NonAsciiCharDict:
                value = NonAsciiCharDict[value]

            if idx < len(peers_attrs):
                entry[peers_attrs[idx]] = value
        
        result.append(entry)
    
    with open(json_filename, 'w') as f:
        json.dump(result, f, indent=2)