import urllib3
import json

url_api = 'https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population&limit=1000&offset=0'

http = urllib3.PoolManager()

def extract_api(url: str):
    response = http.request('GET', url)
    if response.status == 200:
        return json.loads(response.data.decode('utf-8'))
    else:
        raise Exception(f"Failed to get data from {url}, with status code {response.status}")
   
