import os
import time
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv
from datetime import datetime, timezone
import uuid

load_dotenv()

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET = "bronze"
TABLE = "raw_churn_events"
CSV_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"
BATCH_SIZE = 50
SLEEP_SECONDS = 5

client = bigquery.Client(project=PROJECT_ID)

def load_data():
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.lower().replace(" ", "_").replace("(", "").replace(")", "") for c in df.columns]
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["event_id"] = [f"evt_{i}_{int(time.time())}" for i in range(len(df))]
    return df



def push_batch(batch_df):
    table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        autodetect=True,
    )
    job_id = f"replay_{uuid.uuid4().hex}"
    job = client.load_table_from_dataframe(
        batch_df, 
        table_ref, 
        job_config=job_config,
        job_id=job_id
    )
    job.result()
    print(f"[{datetime.now()}] Pushed {len(batch_df)} rows to {table_ref}")

def replay():
    df = load_data()
    total = len(df)
    print(f"Loaded {total} customer records. Starting replay...")

    for start in range(0, total, BATCH_SIZE):
        batch = df.iloc[start:start + BATCH_SIZE].copy()
        push_batch(batch)
        time.sleep(SLEEP_SECONDS)

    print("Replay complete. All records pushed to BigQuery bronze.")

if __name__ == "__main__":
    replay()