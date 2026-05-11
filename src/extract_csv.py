from datetime import datetime
import urllib3
import re
import json
import boto3

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

base = 'https://download.bls.gov'
path = '/pub/time.series/pr'

http = urllib3.PoolManager()

def list_files(url:str, headers:dict) -> list[tuple[str, str]]:
    response = http.request(
        'GET',
        url,
        headers=headers
    )
    res = response.data.decode('utf-8')
    if response.status == 200:
        pattern = re.compile(
            r'(?i)<br>\s*(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM))\s+\d+\s+<a\s+href="(/pub/time\.series/pr/pr\.[^"]+)"'
        )
        matches = pattern.findall(res)
        return [(base + match[1], match[0]) for match in matches]
    else:
        raise Exception(f"Failed to get files from {url}, with status code {response.status}")

def sync_files(files:list[tuple[str, str]], metadata_fp:str, s3:boto3.client, bucket:str) -> None:
    metadata_incoming:list[dict[str,str]] = []
    incoming:set[str] = set()
    # --- Handle inserts and updates ---
    for url, date in files:
        response = http.request(
            'GET',
            url,
            headers=headers
        )
        if response.status == 200:
            key = f'csv/{url.split("/")[-1]}.csv'
            s3.put_object(Bucket=bucket, Key=key, Body=response.data)
        else:
            raise Exception(f"Failed to get file from {url}, with status code {response.status}")

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
