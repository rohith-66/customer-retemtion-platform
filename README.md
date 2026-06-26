# Customer Retention Intelligence Platform

A production-grade, end-to-end data pipeline and analytics platform built on GCP that processes real customer subscription data through a medallion architecture and surfaces churn risk, revenue health, and cohort retention metrics on a live public dashboard.

**Live Dashboard:** https://customer-retention-platform-472198369547.us-central1.run.app

---

## Overview

Subscription businesses lose significant recurring revenue to churn they cannot see coming. This platform is the infrastructure that closes that gap. It ingests real telecom customer data, models it through a Bronze, Silver, and Gold transformation pipeline using dbt, and presents actionable retention metrics in a format that any business stakeholder can use without writing a query.

The system answers three questions:

- Which active customers are at risk of churning before they leave?
- Where is the business losing recurring revenue, and how much per segment?
- Which customer cohorts retain best over time, and what drives the difference?

---

## Architecture

```
Kaggle Telco Churn Dataset (7,043 customer records)
            |
            v
Python Replay Script (ingestion/replay.py)
Batch ingestion with metadata enrichment
            |
            v
BigQuery - Bronze Layer
raw_churn_events table, append-only source of truth
            |
            v
dbt Cloud - Silver Layer (3 staging models)
Cleaning, standardization, deduplication, type casting
            |
            v
dbt Cloud - Gold Layer (5 business models)
MRR, churn rate by segment, at-risk scoring,
cohort retention, revenue lost to churn
            |
            v
Streamlit Dashboard
Deployed on GCP Cloud Run (public HTTPS endpoint)
```

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Ingestion | Python, pandas | Batch replay script loading CSV to BigQuery Bronze |
| Data Warehouse | BigQuery | Columnar storage and compute for all dbt model runs |
| Transformation | dbt Cloud | SQL-based modeling with dependency management, testing, and lineage |
| Dashboard | Streamlit | Python-native analytics frontend reading from Gold layer |
| Deployment | GCP Cloud Run | Serverless container hosting with public HTTPS endpoint |
| Authentication | GCP Service Account | IAM-based credential management, no hardcoded keys |
| Version Control | GitHub | Full project history, dbt models synced via dbt Cloud integration |

---

## Data Modeling

This project implements the medallion architecture pattern, separating raw ingestion from transformation and business logic across three distinct layers.

### Bronze Layer

**Table:** `bronze.raw_churn_events`

Exact copy of source data with no transformations applied. Two metadata columns are added at ingestion time: `ingested_at` (UTC timestamp) and `event_id` (unique row identifier). This layer serves as the reprocessing source of truth.

### Silver Layer

Three staging models that clean, standardize, and deduplicate the Bronze data.

**`stg_customers`**
Cleans customer demographic and service attributes. Renames all columns to snake_case, casts `monthly_charges` and `total_charges` to NUMERIC with `NULLIF` handling for blank charge records, converts the `churn` string to a boolean `is_churned`, and deduplicates on `customer_id` using `QUALIFY ROW_NUMBER()` to retain the most recent record per customer.

**`stg_subscriptions`**
Isolates subscription and contract attributes. Adds a `tenure_segment` derived column bucketing customers into 0-12 months, 13-24 months, 25-48 months, and 49+ months for cohort analysis.

**`stg_charges`**
Isolates financial attributes. Adds a `charge_tier` classification (low, medium, high) based on monthly charge thresholds, used for revenue segmentation in Gold models.

### Gold Layer

Five business-level models that the dashboard reads from directly. All Gold models are materialized as tables for fast query response.

**`mrr_by_month`**
Produces total MRR, active MRR, churned MRR, ARR projection, and churn revenue percentage. The primary revenue health model.

**`churn_rate_by_segment`**
Calculates churn rate across every combination of contract type, tenure segment, internet service, gender, and payment method. High-cardinality output designed for dynamic dashboard filtering.

**`at_risk_customers`**
Applies a rule-based risk scoring model to all active (non-churned) customers. Scores are computed across six churn signal dimensions: contract type, tenure, internet service, tech support status, online security status, and charge tier. Customers are classified as High (60+), Medium (35-59), or Low risk.

**`cohort_retention`**
Calculates retention rate by tenure cohort and contract type. Groups customers into cohort periods based on tenure and computes the percentage of each cohort still active.

**`revenue_lost_to_churn`**
Quantifies the dollar impact of churn by segment. Produces MRR lost, ARR lost, and average LTV lost per contract type, tenure segment, and charge tier combination.

---

## Dashboard

The Streamlit dashboard is deployed publicly on GCP Cloud Run and reads directly from the BigQuery Gold layer with a 5-minute cache.

**Revenue Health**
KPIs: Total MRR, Active MRR, Churned MRR, ARR Projection, Churn Revenue %. Charts showing MRR lost by contract type and charge tier. Filterable breakdown table by tenure segment and charge tier.

**Churn Intelligence**
KPIs: Overall churn rate, total customers, churned, active. Churn rate charts by contract type, tenure segment, internet service, and payment method. Segment-level detail table with multiselect filters.

**At-Risk Customers**
KPIs: High, medium, and low risk customer counts, average risk score. Filterable customer-level table with risk score, risk tier, contract details, service profile, and spend level. Risk score slider filter.

**Cohort Retention**
KPIs: Overall retention rate, best performing cohort. Retention rate charts by cohort period and contract type. Filterable cohort detail table.

---

## Project Structure

```
customer-retention-platform/
|
|-- ingestion/
|   |-- replay.py               # Batch ingestion script: CSV to BigQuery Bronze
|
|-- models/
|   |-- staging/
|   |   |-- stg_customers.sql
|   |   |-- stg_subscriptions.sql
|   |   |-- stg_charges.sql
|   |-- gold/
|       |-- mrr_by_month.sql
|       |-- churn_rate_by_segment.sql
|       |-- at_risk_customers.sql
|       |-- cohort_retention.sql
|       |-- revenue_lost_to_churn.sql
|
|-- dashboard/
|   |-- app.py                  # Streamlit dashboard, 4 pages
|
|-- Dockerfile                  # Cloud Run container definition
|-- dbt_project.yml             # dbt project configuration
|-- requirements.txt
|-- README.md
```

---

## Local Setup

**Prerequisites**

- Python 3.11+
- GCP project with BigQuery enabled
- GCP service account with BigQuery Admin and Storage Admin roles
- dbt Cloud account (free tier)

**1. Clone the repository**

```bash
git clone https://github.com/rohith-66/customer-retention-platform.git
cd customer-retention-platform
```

**2. Create and activate virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Create a `.env` file in the project root:

```
GOOGLE_APPLICATION_CREDENTIALS=gcp-key.json
GCP_PROJECT_ID=your-gcp-project-id
```

Place your GCP service account JSON key file at the project root as `gcp-key.json`. This file is excluded from version control via `.gitignore`.

**5. Run the ingestion script**

Download the Telco Customer Churn dataset from Kaggle and place the CSV in the `data/` directory, then run:

```bash
python ingestion/replay.py
```

This loads all 7,043 records into `bronze.raw_churn_events` in BigQuery in 50-row batches.

**6. Run dbt models**

Connect dbt Cloud to this repository and your BigQuery project, then run:

```
dbt run
```

This builds all 8 models across the Silver and Gold layers.

**7. Run the dashboard locally**

```bash
streamlit run dashboard/app.py
```

---

## Deployment

The dashboard is containerized and deployed on GCP Cloud Run.

**Build and deploy:**

```bash
gcloud run deploy customer-retention-platform \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars GCP_PROJECT_ID=your-project-id \
  --service-account your-service-account@your-project.iam.gserviceaccount.com
```

Authentication to BigQuery on Cloud Run is handled entirely through the attached service account. No credentials are stored in the container image or environment variables.

---

## Data Source

**Dataset:** Telco Customer Churn (IBM Sample Dataset via Kaggle)

Real customer behavioral data from a telecommunications company containing subscription attributes, service usage, demographic information, and churn outcome for 7,043 customers. The dataset is widely used as a benchmark for churn modeling and retention analytics.

The Python replay script loads this data in batches to simulate a live ingestion stream, enabling the pipeline architecture to be demonstrated without a real-time event source.

---

## Key Metrics

| Metric | Value |
|---|---|
| Total customers | 7,043 |
| Total MRR | $456,117 |
| Active MRR | $316,986 |
| Churned MRR | $139,131 |
| Overall churn rate | ~26% |
| ARR projection | $5,473,399 |
| dbt models | 8 (3 Silver, 5 Gold) |
| Dashboard pages | 4 |

---

## Author

**Rohith Srinivasa**
MS in Data Science and Analytics, Arizona State University

LinkedIn: https://www.linkedin.com/in/rohithsrinivasa/
