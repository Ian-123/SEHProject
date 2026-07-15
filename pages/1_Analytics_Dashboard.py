import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import altair as alt

st.set_page_config(page_title="Analytics Dashboard", page_icon="📊", layout="wide")

st.title("📊 Analytics Dashboard")


# ---------- Load Data ----------
DATA_FILE = "properties.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

properties = load_data()


# ---------- Build Transactions DF ----------
def build_transactions_df(properties):
    rows = []
    for addr, rec in properties.items():
        det = rec.get("details", {}) or {}
        for t in rec.get("transactions", []) or []:
            row = {
                "parcel_address": addr,
                "city": det.get("city"),
                "county": det.get("county"),
                "state": det.get("state"),
                "organization": det.get("organization"),
                "msa": det.get("msa"),
            }
            row.update(t)
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Convert dates to years
    for col in ["year_acquired", "year_sold"]:
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce")
            df[col + "_year"] = dt.dt.year

    # AMI bands
    if "household_income_to_AMI_percent" in df.columns:
        def ami_band(x):
            try:
                x = float(x)
            except:
                return "Unknown"
            if x <= 60:
                return "<=60% AMI"
            elif x <= 80:
                return "60–80% AMI"
            elif x <= 100:
                return "80–100% AMI"
            else:
                return ">=100% AMI"

        df["AMI_band"] = df["household_income_to_AMI_percent"].apply(ami_band)

    return df


tx_df = build_transactions_df(properties)

if tx_df.empty:
    st.warning("No transactions available for analytics yet. Add transactions in the main app.")
    st.stop()


# ---------- Filters ----------
st.subheader("Filters")

f1, f2, f3 = st.columns(3)

with f1:
    f_city = st.text_input("City contains:", "")
with f2:
    f_org = st.text_input("Organization contains:", "")
with f3:
    f_year = st.text_input("Year acquired (exact):", "")

df = tx_df.copy()

if f_city:
    df = df[df["city"].fillna("").str.contains(f_city, case=False)]
if f_org:
    df = df[df["organization"].fillna("").str.contains(f_org, case=False)]
if f_year:
    try:
        y = int(f_year)
        df = df[df["year_acquired_year"] == y]
    except:
        st.warning("Year must be numeric")

st.caption(f"{len(df)} transactions after filters.")


# ---------- KPI Metrics ----------
st.subheader("Key Metrics")

k1, k2, k3 = st.columns(3)
k4, k5, k6 = st.columns(3)

# 1) Affordability
with k1:
    med_aff = df["affordability_relative_to_market"].dropna().median()
    st.metric("Median affordability relative to market (%)", f"{med_aff:,.1f}")

# 2) Tenure
with k2:
    med_tenure = df["length_of_tenure"].dropna().median()
    st.metric("Median length of tenure (years)", f"{med_tenure:,.1f}")

# 3) Household AMI
with k3:
    med_ami = df["household_income_to_AMI_percent"].dropna().median()
    st.metric("Median household income to AMI (%)", f"{med_ami:,.1f}")

# 4) Appraised value
with k4:
    med_app = df["fee_simple_appraisal_value"].dropna().median()
    st.metric("Median Fee simple appraisal value", f"${med_app:,.0f}")

# 5) Monthly payments
with k5:
    med_mp = df["monthly_payments"].dropna().median()
    st.metric("Median monthly payments", f"${med_mp:,.0f}")

# 6) Base price
with k6:
    med_bp = df["base_price"].dropna().median()
    st.metric("Median base /effective purchase price", f"${med_bp:,.0f}")

# ---------- Helper function for histograms ----------
def plot_histogram_for_series(series, title):
    series = series.dropna()
    if series.empty:
        st.info(f"No data to plot for {title}.")
        return

    counts, bin_edges = np.histogram(series, bins=10)

    # Build labels like "0–10", "10–20", etc.
    labels = []
    for i in range(len(bin_edges) - 1):
        labels.append(f"{bin_edges[i]:.1f}–{bin_edges[i+1]:.1f}")

    hist_df = pd.DataFrame({
        "bin": labels,
        "count": counts
    }).set_index("bin")

    st.bar_chart(hist_df)

# ---------- City & Organization distribution (Pie charts) ----------
#st.subheader("City & Organization distribution (transactions)")

col1, col2 = st.columns(2)

# ---------------- CITY PIE ----------------
with col1:
    st.markdown("### City distribution")

    if "city" in df.columns:
        city_counts = (
            df["city"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )
        city_counts.columns = ["city", "count"]

        # Optional top 10 logic
        if len(city_counts) > 10:
            top = city_counts.iloc[:10].copy()
            other_count = city_counts["count"].iloc[10:].sum()
            top.loc[len(top)] = ["Other", other_count]
            city_counts = top

        city_pie = (
            alt.Chart(city_counts)
            .mark_arc()
            .encode(
                theta="count:Q",
                color="city:N",
                tooltip=["city", "count"]
            )
        )

        st.altair_chart(city_pie, use_container_width=True)
    else:
        st.info("No city data available for this view.")

# ---------------- ORGANIZATION PIE ----------------
with col2:
    st.markdown("### Organization distribution")

    if "organization" in df.columns:
        org_counts = (
            df["organization"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )
        org_counts.columns = ["organization", "count"]

        # Optional top 10 logic
        if len(org_counts) > 10:
            top_o = org_counts.iloc[:10].copy()
            other_count = org_counts["count"].iloc[10:].sum()
            top_o.loc[len(top_o)] = ["Other", other_count]
            org_counts = top_o

        org_pie = (
            alt.Chart(org_counts)
            .mark_arc()
            .encode(
                theta="count:Q",
                color="organization:N",
                tooltip=["organization", "count"]
            )
        )

        st.altair_chart(org_pie, use_container_width=True)
    else:
        st.info("No organization data available for this view.")

# ---------- Distributions (10-bin histogram) ----------
st.subheader("Distributions (10-bin histogram)")

# Only include numeric fields likely to exist
numeric_options = []
for col in [
    "affordability_relative_to_market",
    "length_of_tenure",
    "household_income_to_AMI_percent",
    "fee_simple_appraisal_value",
    "monthly_payments",
    "base_price",
]:
    if col in df.columns:
        numeric_options.append(col)

if not numeric_options:
    st.info("No numeric fields available for histograms.")
else:
    pretty_labels = {
        "affordability_relative_to_market": "Affordability relative to market (%)",
        "length_of_tenure": "Length of tenure (years)",
        "household_income_to_AMI_percent": "Household income to AMI (%)",
        "fee_simple_appraisal_value": "Fee simple appraisal value",
        "monthly_payments": "Monthly payments",
        "base_price": "Base price",
    }

    choice = st.selectbox(
        "Choose a variable to view distribution",
        options=numeric_options,
        format_func=lambda c: pretty_labels.get(c, c),
    )

    plot_histogram_for_series(df[choice], pretty_labels.get(choice, choice))


# ---------- Charts ----------
#st.subheader("Household AMI Distribution")
#if "AMI_band" in df.columns:
#    st.bar_chart(df["AMI_band"].value_counts())


st.subheader("Affordability Trend Over Time")

if "year_acquired_year" in df.columns:
    trend = (
        df.groupby("year_acquired_year")["affordability_relative_to_market"]
        .mean()
        .sort_index()
    )
    st.line_chart(trend)

# ---------- Data Table ----------
st.subheader("Filtered Transaction Table")
st.dataframe(df, use_container_width=True, height=350)
st.download_button(
    label="Download data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="filtered_transactions.csv",
    mime="text/csv",
)