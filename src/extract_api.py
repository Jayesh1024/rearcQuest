import requests
import json
import os
import boto3, dotenv

dotenv.load_dotenv(override=True)

s3 = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bucket = os.getenv('AWS_BUCKET')

url = 'https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population&limit=1000&offset=0'

def extract_api(url:str) -> None:
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get data from {url}, with status code {response.status_code}")

data = extract_api(url)

s3.put_object(Bucket=bucket, Key='api/data.json', Body=json.dumps(data, indent=4).encode('utf-8'))