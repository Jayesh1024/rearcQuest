import pandas as pd
import boto3, os
import json, io

def handle(event=None, context=None):
    s3 = boto3.client('s3',
        region_name=os.getenv('AWS_REGION')
    )

    bucket = os.getenv('AWS_BUCKET')

    # --- Fetch the api json file ---
    api_data = s3.get_object(Bucket=bucket, Key='api/data.json')
    api_data:dict = json.loads(api_data['Body'].read().decode('utf-8'))

    # --- Fetch the csv file ---
    csv_data = s3.get_object(Bucket=bucket, Key='csv/pr.data.0.Current.csv')
    csv_data = csv_data['Body'].read()

    df_csv = pd.read_csv(io.BytesIO(csv_data),delimiter='\t')

    df_api = pd.DataFrame(api_data['data'])
    filter_api = (df_api['Year'] >= 2013) & (df_api['Year'] <= 2018)
    df_api_filtered = df_api[filter_api]

    print(f"Mean of the US annual population: {df_api_filtered['Population'].mean()}")
    print(f"Standard deviation of the US annual population: {df_api_filtered['Population'].std()}")

    # --- Removing whitespace from column names ---
    df_csv.rename(
        {
            'series_id        ': 'series_id',
            '       value': 'value'
        },
        axis = 1,
        inplace = True
    )

    for col in df_csv.columns:
        if df_csv[col].dtype == object:
            df_csv[col] = df_csv[col].str.strip()

    # --- Aggregating the data by series_id and year for calculating the sum of the values ---
    df_csv_agg = df_csv.groupby(['series_id', 'year']) \
        .agg({'value': 'mean'}) \
        .reset_index()

    # --- Calculating the dense rank of the values ---
    df_csv_agg['dense_rank'] = df_csv_agg.groupby(['series_id'])['value'] \
        .rank(
            ascending=False,
            method='dense'
        )

    # --- Selecting the top 1 value for each series_id ---
    cols = ['series_id', 'year', 'value']
    print(df_csv_agg[df_csv_agg['dense_rank'] == 1][cols].reset_index(drop=True))

    df_filtered = df_csv[(df_csv['series_id'] == 'PRS30006032') & (df_csv['period'] == 'Q01')]

    df_merged = pd.merge(
        df_filtered,
        df_api,
        left_on = 'year',
        right_on = 'Year',
        how = 'inner'
    )

    cols_to_keep = ['series_id', 'year', 'period', 'value', 'Population']

    print(df_merged[cols_to_keep])
