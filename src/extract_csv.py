from datetime import datetime
import requests
import re
import json
import os



headers = {
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
}

base = 'https://download.bls.gov'
path = '/pub/time.series/pr'

def list_files(url:str, headers:dict) -> list[tuple[str, str]]:
    response = requests.get(url, headers=headers)
    res = response.text
    if response.status_code == 200:
        pattern = re.compile(
            r'(?i)<br>\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM))\s+\d+\s+<a\s+href="(/pub/time\.series/pr/pr\.[^"]+)"'
        )
        matches = pattern.findall(res)
        return [(base + match[1], match[0]) for match in matches]
    else:
        raise Exception(f"Failed to get files from {url}, with status code {response.status_code}")


def sync_files(files:list[tuple[str, str]], metadata_fp:str) -> None:
    metadata_incoming:list[dict[str,str]] = []
    incoming:set[str] = set()
    # --- Handle inserts and updates ---
    for url, date in files:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            key = f'csv/{url.split("/")[-1]}.csv'
            s3.put_object(Bucket=bucket, Key=key, Body=response.content)
        else:
            raise Exception(f"Failed to get file from {url}, with status code {response.status_code}")

        metadata_incoming.append({
            'filename': url.split('/')[-1],
            'url': url,
            'update_at': datetime.strptime(date, '%m/%d/%Y %I:%M %p').isoformat(),
            'ingestion_time': datetime.now().isoformat()
        })
        incoming.add(url.split('/')[-1])
    
    # --- Handle deletes ---
    try:
        metadata_current = s3.get_object(Bucket=bucket, Key=metadata_fp)
        metadata_current = json.loads(metadata_current['Body'].read().decode('utf-8'))
        current:set[str] = set()
        for file in metadata_current:
            current.add(file['filename'])

        to_delete = current - incoming
        for file in metadata_current:
            if file['filename'] in to_delete:
                s3.delete_object(Bucket=bucket, Key=f'csv/{file["filename"]}.csv')
    except Exception as e:
        print(f"No metadata file found, this may be the first time running the script, error: {e}")

    s3.put_object(Bucket=bucket, Key=metadata_fp, Body=json.dumps(metadata_incoming, indent=4).encode('utf-8'))


full_url = base + path
files = list_files(full_url, headers)
sync_files(files, 'config/metadata.json')
