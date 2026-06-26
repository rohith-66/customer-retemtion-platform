import os
import decimal
import streamlit as st
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

PROJECT = os.getenv("GCP_PROJECT_ID")
GOLD = f"{PROJECT}.dbt_dev_gold"

st.set_page_config(
    page_title="Customer Retention Intelligence Platform",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        body { font-family: 'Segoe UI', sans-serif; }
        .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
        div[data-testid="stMetric"] {
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem 1.2rem;
        }
        div[data-testid="stMetric"] label {
            font-size: 0.78rem;
            color: #6b7280;
            font-weight: 500;
        }
        h1 { font-size: 1.5rem; font-weight: 700; color: #111827; }
        h2, h3 { font-size: 1.1rem; font-weight: 600; color: #1f2937; }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def run_query(query):
    client = bigquery.Client(project=PROJECT)
    df = client.query(query).to_dataframe()
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna()
        if not sample.empty and isinstance(sample.iloc[0], decimal.Decimal):
            df[col] = df[col].astype(float)
        else:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
    return df


with st.sidebar:
    st.markdown("### Customer Retention Intelligence")
    st.markdown("---")
    page = st.radio(
        "Section",
        ["Revenue Health", "Churn Intelligence", "At-Risk Customers", "Cohort Retention"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("Pipeline: BigQuery + dbt")
    st.caption("Source: Telco Customer Churn Dataset")
    st.caption("Refresh interval: 5 minutes")


# ── Page 1: Revenue Health ─────────────────────────────────────────────────────
if page == "Revenue Health":
    st.title("Revenue Health")
    st.caption("Monthly recurring revenue breakdown, churn revenue impact, and ARR projection.")
    st.markdown("---")

    mrr = run_query(f"SELECT * FROM `{GOLD}.mrr_by_month`")
    rev_lost = run_query(f"SELECT * FROM `{GOLD}.revenue_lost_to_churn`")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total MRR", f"${mrr['total_mrr'].iloc[0]:,.0f}")
    col2.metric("Active MRR", f"${mrr['active_mrr'].iloc[0]:,.0f}")
    col3.metric("Churned MRR", f"${mrr['churned_mrr'].iloc[0]:,.0f}")
    col4.metric("ARR Projection", f"${mrr['arr_projection'].iloc[0]:,.0f}")
    col5.metric("Churn Revenue %", f"{round(float(mrr['churn_revenue_pct'].iloc[0]), 2)}%")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("MRR Lost by Contract Type")
        contract_rev = rev_lost.groupby("contract_type", as_index=False)["mrr_lost"].sum()
        contract_rev["mrr_lost"] = contract_rev["mrr_lost"].round(2)
        st.bar_chart(data=contract_rev, x="contract_type", y="mrr_lost", height=280)

    with col2:
        st.subheader("MRR Lost by Charge Tier")
        tier_rev = rev_lost.groupby("charge_tier", as_index=False)["mrr_lost"].sum()
        tier_rev["mrr_lost"] = tier_rev["mrr_lost"].round(2)
        st.bar_chart(data=tier_rev, x="charge_tier", y="mrr_lost", height=280)

    st.markdown("---")
    st.subheader("Revenue Lost to Churn - Full Breakdown")

    col1, col2 = st.columns(2)
    with col1:
        tenure_filter = st.multiselect(
            "Tenure Segment",
            options=sorted(rev_lost["tenure_segment"].unique().tolist()),
            default=sorted(rev_lost["tenure_segment"].unique().tolist())
        )
    with col2:
        tier_filter = st.multiselect(
            "Charge Tier",
            options=sorted(rev_lost["charge_tier"].unique().tolist()),
            default=sorted(rev_lost["charge_tier"].unique().tolist())
        )

    filtered_table = rev_lost[
        (rev_lost["tenure_segment"].isin(tenure_filter)) &
        (rev_lost["charge_tier"].isin(tier_filter))
    ]

    st.dataframe(
        filtered_table[[
            "contract_type", "tenure_segment", "charge_tier",
            "churned_customers", "mrr_lost", "arr_lost", "avg_ltv_lost"
        ]].sort_values("mrr_lost", ascending=False),
        use_container_width=True,
        height=320
    )


# ── Page 2: Churn Intelligence ─────────────────────────────────────────────────
elif page == "Churn Intelligence":
    st.title("Churn Intelligence")
    st.caption("Churn rate segmented by contract, tenure, internet service, and payment method.")
    st.markdown("---")

    churn = run_query(f"SELECT * FROM `{GOLD}.churn_rate_by_segment`")

    overall_churn = round(
        churn["churned_customers"].sum() / churn["total_customers"].sum() * 100, 2
    )
    total_customers = churn["total_customers"].sum()
    total_churned = churn["churned_customers"].sum()
    total_active = total_customers - total_churned

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Churn Rate", f"{overall_churn}%")
    col2.metric("Total Customers", f"{total_customers:,}")
    col3.metric("Churned", f"{total_churned:,}")
    col4.metric("Active", f"{total_active:,}")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Churn Rate by Contract Type")
        by_contract = churn.groupby("contract_type").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_contract["churn_rate_pct"] = round(
            by_contract["churned"] / by_contract["total"] * 100, 2
        )
        st.bar_chart(
            data=by_contract, x="contract_type", y="churn_rate_pct", height=280
        )

    with col2:
        st.subheader("Churn Rate by Tenure Segment")
        by_tenure = churn.groupby("tenure_segment").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_tenure["churn_rate_pct"] = round(
            by_tenure["churned"] / by_tenure["total"] * 100, 2
        )
        st.bar_chart(
            data=by_tenure, x="tenure_segment", y="churn_rate_pct", height=280
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Churn Rate by Internet Service")
        by_internet = churn.groupby("internet_service").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_internet["churn_rate_pct"] = round(
            by_internet["churned"] / by_internet["total"] * 100, 2
        )
        st.bar_chart(
            data=by_internet, x="internet_service", y="churn_rate_pct", height=280
        )

    with col2:
        st.subheader("Churn Rate by Payment Method")
        by_payment = churn.groupby("payment_method").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_payment["churn_rate_pct"] = round(
            by_payment["churned"] / by_payment["total"] * 100, 2
        )
        st.bar_chart(
            data=by_payment, x="payment_method", y="churn_rate_pct", height=280
        )

    st.markdown("---")
    st.subheader("Segment Detail Table")

    col1, col2, col3 = st.columns(3)
    with col1:
        contract_filter = st.multiselect(
            "Contract Type",
            options=sorted(churn["contract_type"].unique().tolist()),
            default=sorted(churn["contract_type"].unique().tolist())
        )
    with col2:
        tenure_filter = st.multiselect(
            "Tenure Segment",
            options=sorted(churn["tenure_segment"].unique().tolist()),
            default=sorted(churn["tenure_segment"].unique().tolist())
        )
    with col3:
        internet_filter = st.multiselect(
            "Internet Service",
            options=sorted(churn["internet_service"].unique().tolist()),
            default=sorted(churn["internet_service"].unique().tolist())
        )

    filtered_churn = churn[
        (churn["contract_type"].isin(contract_filter)) &
        (churn["tenure_segment"].isin(tenure_filter)) &
        (churn["internet_service"].isin(internet_filter))
    ]

    st.dataframe(
        filtered_churn[[
            "contract_type", "tenure_segment", "internet_service",
            "gender", "payment_method", "total_customers",
            "churned_customers", "churn_rate_pct"
        ]].sort_values("churn_rate_pct", ascending=False),
        use_container_width=True,
        height=360
    )


# ── Page 3: At-Risk Customers ──────────────────────────────────────────────────
elif page == "At-Risk Customers":
    st.title("At-Risk Customers")
    st.caption("Active customers ranked by churn risk score. Scoring uses contract type, tenure, service profile, and spend signals.")
    st.markdown("---")

    risk = run_query(
        f"SELECT * FROM `{GOLD}.at_risk_customers` ORDER BY risk_score DESC"
    )

    high = len(risk[risk["risk_tier"] == "High"])
    medium = len(risk[risk["risk_tier"] == "Medium"])
    low = len(risk[risk["risk_tier"] == "Low"])
    avg_score = round(risk["risk_score"].mean(), 1)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("High Risk", f"{high:,}")
    col2.metric("Medium Risk", f"{medium:,}")
    col3.metric("Low Risk", f"{low:,}")
    col4.metric("Avg Risk Score", avg_score)

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        tier_filter = st.selectbox("Risk Tier", ["All", "High", "Medium", "Low"])
    with col2:
        contract_filter = st.multiselect(
            "Contract Type",
            options=sorted(risk["contract_type"].unique().tolist()),
            default=sorted(risk["contract_type"].unique().tolist())
        )
    with col3:
        internet_filter = st.multiselect(
            "Internet Service",
            options=sorted(risk["internet_service"].unique().tolist()),
            default=sorted(risk["internet_service"].unique().tolist())
        )
    with col4:
        min_score = st.slider(
            "Minimum Risk Score", 0, 100,
            int(risk["risk_score"].min())
        )

    filtered_risk = risk[
        (risk["contract_type"].isin(contract_filter)) &
        (risk["internet_service"].isin(internet_filter)) &
        (risk["risk_score"] >= min_score)
    ]
    if tier_filter != "All":
        filtered_risk = filtered_risk[filtered_risk["risk_tier"] == tier_filter]

    st.subheader(f"{len(filtered_risk):,} customers match current filters")

    st.dataframe(
        filtered_risk[[
            "customer_id", "risk_tier", "risk_score", "contract_type",
            "tenure_months", "monthly_charges", "charge_tier",
            "internet_service", "tech_support", "online_security", "payment_method"
        ]],
        use_container_width=True,
        height=420
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Customer Count by Risk Tier")
        risk_dist = (
            filtered_risk.groupby("risk_tier", as_index=False)["customer_id"]
            .count()
            .rename(columns={"customer_id": "count"})
        )
        st.bar_chart(data=risk_dist, x="risk_tier", y="count", height=250)

    with col2:
        st.subheader("Avg Risk Score by Contract Type")
        risk_by_contract = (
            filtered_risk.groupby("contract_type", as_index=False)["risk_score"]
            .mean()
            .round(2)
        )
        st.bar_chart(data=risk_by_contract, x="contract_type", y="risk_score", height=250)


# ── Page 4: Cohort Retention ───────────────────────────────────────────────────
elif page == "Cohort Retention":
    st.title("Cohort Retention")
    st.caption("Retention rates by customer tenure cohort and contract type.")
    st.markdown("---")

    cohort = run_query(f"SELECT * FROM `{GOLD}.cohort_retention`")

    best_cohort = cohort.loc[cohort["retention_rate_pct"].idxmax()]
    worst_cohort = cohort.loc[cohort["retention_rate_pct"].idxmin()]
    overall_retention = round(
        (1 - cohort["churned_customers"].sum() /
         cohort["total_customers"].sum()) * 100, 2
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Retention Rate", f"{overall_retention}%")
    col2.metric("Best Cohort", best_cohort["cohort_period"])
    col3.metric("Best Retention", f"{best_cohort['retention_rate_pct']}%")
    col4.metric("Lowest Retention", f"{worst_cohort['retention_rate_pct']}%")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Retention Rate by Tenure Cohort")
        by_cohort = cohort.groupby("cohort_period").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_cohort["retention_rate_pct"] = round(
            (1 - by_cohort["churned"] / by_cohort["total"]) * 100, 2
        )
        st.bar_chart(
            data=by_cohort, x="cohort_period", y="retention_rate_pct", height=280
        )

    with col2:
        st.subheader("Retention Rate by Contract Type")
        by_contract = cohort.groupby("contract_type").agg(
            total=("total_customers", "sum"),
            churned=("churned_customers", "sum")
        ).reset_index()
        by_contract["retention_rate_pct"] = round(
            (1 - by_contract["churned"] / by_contract["total"]) * 100, 2
        )
        st.bar_chart(
            data=by_contract, x="contract_type", y="retention_rate_pct", height=280
        )

    st.markdown("---")
    st.subheader("Cohort Detail Table")

    contract_filter = st.multiselect(
        "Contract Type",
        options=sorted(cohort["contract_type"].unique().tolist()),
        default=sorted(cohort["contract_type"].unique().tolist())
    )

    filtered_cohort = cohort[cohort["contract_type"].isin(contract_filter)]

    st.dataframe(
        filtered_cohort[[
            "cohort_period", "contract_type", "total_customers",
            "churned_customers", "retention_rate_pct", "avg_monthly_charges"
        ]].sort_values("retention_rate_pct", ascending=False),
        use_container_width=True,
        height=360
    )