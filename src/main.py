import os, boto3, json
from extract_api import extract_api, url_api
from extract_csv import list_files, sync_files, base, path, headers

s3 = boto3.client('s3',
    region_name=os.getenv('AWS_REGION')
)

bucket = os.getenv('AWS_BUCKET')
def handler(event:dict, context:dict) -> None:
    # --- Extract the API data ---
    data = extract_api(url_api)
    s3.put_object(Bucket=bucket, Key='api/data.json', Body=json.dumps(data, indent=4).encode('utf-8'))

    # --- Extract the CSV data ---
    full_url = base + path
    files = list_files(full_url, headers)
    sync_files(files, 'config/metadata.json')

    return {
        'statusCode': 200
    }


handler({}, {})


