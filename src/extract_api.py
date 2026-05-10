import requests
import json
import os
import datetime

url = 'https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population&limit=1000&offset=0'

def extract_api(url:str) -> None:
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get data from {url}, with status code {response.status_code}")

data = extract_api(url)
with open('output/api.json', 'w') as f:
    json.dump(data, f, indent=4)