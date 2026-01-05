import os
import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go

# --------------------------
# Setup
# --------------------------

load_dotenv()

# Ensure environment variable is set correctly
# Make sure DATABRICKS_HOST and DATABRICKS_TOKEN are also set in your environment/env file
assert os.getenv('DATABRICKS_WAREHOUSE_ID'), "DATABRICKS_WAREHOUSE_ID must be set in app.yaml or .env"

CATALOG = "business_intelligence_systems"
SCHEMA = "03_Gold_Retail_Banking"

def sqlQuery(query: str) -> pd.DataFrame:
    cfg = Config() # Pull environment variables for auth
    with sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
        credentials_provider=lambda: cfg.authenticate
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            # Fetch as Arrow for performance, then convert to Pandas
            return cursor.fetchall_arrow().to_pandas()

st.set_page_config(layout="wide", page_title="Retail Banking Dashboard")

# --------------------------
# Data Loaders
# --------------------------

@st.cache_data(ttl=300)
def get_demographics_geo():
    """Fetches aggregated client demographics by state."""
    query = f"""
    SELECT *
    FROM {CATALOG}.{SCHEMA}.kpi_client_demographics_geographics
    """
    return sqlQuery(query)

@st.cache_data(ttl=300)
def get_card_distribution():
    """Aggregates card types dynamically since the source table is granular."""
    query = f"""
    SELECT 
        card_type, 
        COUNT(1) as card_count 
    FROM {CATALOG}.{SCHEMA}.kpi_client_card_profile
    GROUP BY card_type
    ORDER BY card_count DESC
    """
    return sqlQuery(query)

@st.cache_data(ttl=300)
def get_monthly_transactions():
    """Fetches monthly transaction trends."""
    query = f"""
    SELECT *
    FROM {CATALOG}.{SCHEMA}.kpi_completedtrans_monthly
    ORDER BY kpi_month
    """
    return sqlQuery(query)

@st.cache_data(ttl=300)
def get_crm_stats():
    """Fetches CRM call stats by hour."""
    query = f"""
    SELECT *
    FROM {CATALOG}.{SCHEMA}.crm_calls_by_hour
    ORDER BY hour
    """
    return sqlQuery(query)

@st.cache_data(ttl=300)
def get_complaints_stats():
    """Fetches complaints by product."""
    query = f"""
    SELECT *
    FROM {CATALOG}.{SCHEMA}.crm_complaints_by_product
    ORDER BY count DESC
    """
    return sqlQuery(query)

# --------------------------
# Sidebar & Global Filters
# --------------------------

st.sidebar.title("Filters")

# Load Data
df_demo = get_demographics_geo().copy()
df_trans = get_monthly_transactions().copy()
df_cards = get_card_distribution().copy()
df_crm_calls = get_crm_stats().copy()
df_complaints = get_complaints_stats().copy()

# Filter: State (Applies primarily to the Client Demographics tab)
all_states = sorted(df_demo["state_name"].unique())
selected_states = st.sidebar.multiselect("Select States (Client View)", all_states, default=all_states[:5])

# Apply Filter to Demographics Data
if selected_states:
    df_demo_filtered = df_demo[df_demo["state_name"].isin(selected_states)]
else:
    df_demo_filtered = df_demo

# --------------------------
# Dashboard Layout
# --------------------------

st.title("🏦 Retail Banking Insights")
st.markdown("Overview of Client Demographics, Transaction Trends, and CRM Performance based on Gold Layer data.")

tab_clients, tab_trans, tab_crm = st.tabs(["👥 Clients & Accounts", "💳 Transaction Trends", "📞 CRM & Support"])

# --- TAB 1: Clients & Accounts ---
with tab_clients:
    st.subheader("Client Demographics & Card Portfolio")
    
    # Top Level Metrics
    total_clients_in_view = df_demo_filtered["client_count"].sum()
    st.metric(label="Total Clients (Selected States)", value=f"{total_clients_in_view:,}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Age Group Distribution
        fig_age = px.bar(
            df_demo_filtered.groupby("age_group")["client_count"].sum().reset_index(),
            x="age_group",
            y="client_count",
            title="Client Distribution by Age Group",
            color_discrete_sequence=["#3366CC"]
        )
        st.plotly_chart(fig_age, use_container_width=True)
        
    with col2:
        # Gender Distribution
        fig_sex = px.pie(
            df_demo_filtered.groupby("sex")["client_count"].sum().reset_index(),
            values="client_count",
            names="sex",
            title="Client Distribution by Gender",
            hole=0.4
        )
        st.plotly_chart(fig_sex, use_container_width=True)

    st.divider()
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Geographic Map (using State Names)
        # Note: If these are US states, scope="usa". If Czech (original dataset), might need geojson.
        # Assuming generic bar chart is safer if region is unknown/custom.
        fig_state = px.bar(
            df_demo_filtered.groupby("state_name")["client_count"].sum().reset_index().sort_values("client_count", ascending=False).head(10),
            x="client_count",
            y="state_name",
            orientation='h',
            title="Top States by Client Count",
            color="client_count",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_state, use_container_width=True)

    with col4:
        # Card Types
        fig_cards = px.bar(
            df_cards,
            x="card_type",
            y="card_count",
            title="Credit Card Portfolio Mix",
            color="card_type",
            text_auto=True
        )
        st.plotly_chart(fig_cards, use_container_width=True)

# --- TAB 2: Transaction Trends ---
with tab_trans:
    st.subheader("Financial Performance Over Time")
    
    # ensure datetime
    df_trans["kpi_month"] = pd.to_datetime(df_trans["kpi_month"])
    
    # Metrics
    latest_month = df_trans["kpi_month"].max()
    latest_data = df_trans[df_trans["kpi_month"] == latest_month].iloc[0]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Latest Monthly Volume", f"${latest_data['total_amount']:,.0f}")
    m2.metric("Latest Tx Count", f"{latest_data['transaction_count']:,}")
    m3.metric("Avg Ending Balance", f"${latest_data['average_ending_balance']:,.0f}")

    # Dual Axis Chart: Amount vs Count
    fig_trend = go.Figure()
    
    fig_trend.add_trace(go.Bar(
        x=df_trans["kpi_month"],
        y=df_trans["total_amount"],
        name="Total Amount",
        marker_color='rgb(26, 118, 255)',
        opacity=0.6
    ))
    
    fig_trend.add_trace(go.Scatter(
        x=df_trans["kpi_month"],
        y=df_trans["transaction_count"],
        name="Transaction Count",
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='rgb(255, 65, 54)', width=3)
    ))
    
    fig_trend.update_layout(
        title="Monthly Transaction Volume vs Count",
        xaxis_title="Month",
        yaxis=dict(title="Total Amount ($)"),
        yaxis2=dict(title="Count", overlaying='y', side='right'),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # Balance Trend
    fig_bal = px.line(
        df_trans,
        x="kpi_month",
        y="average_ending_balance",
        title="Average Account Balance Trends",
        markers=True
    )
    st.plotly_chart(fig_bal, use_container_width=True)
    
    with st.expander("🔍 View Transaction Data"):
        st.dataframe(df_trans.style.format({"total_amount": "${:,.2f}", "average_ending_balance": "${:,.2f}"}), use_container_width=True)

# --- TAB 3: CRM & Support ---
with tab_crm:
    st.subheader("Customer Support Analysis")
    
    c1, c2 = st.columns(2)
    
    with c1:
        # Calls by Hour
        fig_calls = px.bar(
            df_crm_calls,
            x="hour",
            y="count",
            title="Call Center Volume by Hour of Day",
            labels={"hour": "Hour of Day (24h)", "count": "Number of Calls"},
            color="average_time", # Color by duration
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_calls, use_container_width=True)
        st.caption("Bar color indicates average call duration (seconds).")
        
    with c2:
        # Complaints by Product
        fig_comp = px.bar(
            df_complaints,
            y="product",
            x="count",
            orientation='h',
            title="Complaints by Product Category",
            color="count",
            color_continuous_scale="Reds"
        )
        fig_comp.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_comp, use_container_width=True)

    # Detailed CRM Data
    with st.expander("🔍 View CRM Source Data"):
        st.write("Calls by Priority")
        st.dataframe(df_crm_calls, use_container_width=True)