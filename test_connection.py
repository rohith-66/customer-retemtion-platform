import os
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))
datasets = list(client.list_datasets())
print("Connected! Datasets found:")
for d in datasets:
    print(f"  {d.dataset_id}")