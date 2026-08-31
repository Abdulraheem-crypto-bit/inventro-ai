import os
import re
import json
import math
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="inventro.ai | Autonomous Retail OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }
    .agent-card {
        background: rgba(99, 102, 241, 0.05);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 15px;
    }
    .agent-thought {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #94a3b8;
        background: rgba(15, 23, 42, 0.6);
        padding: 12px;
        border-radius: 8px;
        border-left: 3px solid #6366f1;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DYNAMIC SCHEMA RESOLUTION (NO API KEY NEEDED)
# ==========================================
COLUMN_SYNONYMS = {
    "sku": ["sku", "product_id", "productid", "item_id", "itemid", "item_code", "itemcode", "barcode", "code", "prod_id"],
    "name": ["name", "product_name", "productname", "item_name", "itemname", "title", "description", "product", "article"],
    "category": ["category", "cat", "department", "dept", "product_type", "type", "group", "segment"],
    "stock": ["stock", "current_stock", "qty", "quantity", "inventory", "on_hand", "stock_qty", "units_in_stock", "qty_on_hand"],
    "lead_time": ["lead_time", "leadtime", "lead_days", "delivery_days", "transit_time", "supplier_lead_time", "tat_days"],
    "moq": ["moq", "min_order_qty", "min_order", "minimum_order", "min_qty"],
    "pack_size": ["pack_size", "packsize", "case_size", "bundle_size", "package_size", "multiplier"],
    "vendor": ["vendor", "supplier", "vendor_name", "supplier_name", "distributor", "manufacturer"],
    "email": ["email", "vendor_email", "supplier_email", "contact_email", "dispatch_email", "inbox"],
    "expiry_days": ["expiry_days", "shelf_life", "expiry", "expiration_days", "days_to_expire", "perishability_days"],
    "quantity_sold": ["quantity_sold", "qty_sold", "units_sold", "sales", "volume", "sold_qty", "quantity"],
    "transaction_date": ["transaction_date", "timestamp", "date", "sale_date", "txn_date", "created_at"]
}

def clean_name(s: str) -> str:
    return re.sub(r'[\s_\-]+', '', str(s)).lower()

def resolve_and_normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if df.empty:
        return df, {}
    
    normalized_df = df.copy()
    detected_mapping = {}
    cleaned_df_cols = {clean_name(c): c for c in df.columns}

    for canonical_key, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            cleaned_syn = clean_name(syn)
            if cleaned_syn in cleaned_df_cols:
                original_col = cleaned_df_cols[cleaned_syn]
                detected_mapping[canonical_key] = original_col
                normalized_df[canonical_key] = df[original_col]
                break

    defaults = {
        "sku": [f"SKU_{i+1:03d}" for i in range(len(normalized_df))],
        "name": "Unnamed Item",
        "category": "General",
        "stock": 0,
        "lead_time": 2,
        "moq": 10,
        "pack_size": 1,
        "vendor": "General Supplier",
        "email": "",
        "expiry_days": 30,
        "quantity_sold": 1
    }
    for field, default_val in defaults.items():
        if field not in normalized_df.columns:
            normalized_df[field] = default_val

    return normalized_df, detected_mapping

# ==========================================
# DATABASE ENGINE CONNECTION
# ==========================================
@st.cache_resource(show_spinner=False)
def get_db_engine(connection_string: str):
    if not connection_string or not connection_string.strip():
        return None
    try:
        engine = create_engine(connection_string.strip(), pool_pre_ping=True, pool_recycle=300)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.sidebar.error(f"Connection Failed: {e}")
        return None

# ==========================================
# SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ **inventro.ai**")
    st.caption("Autonomous Retail Inventory Engine")
    st.divider()

    st.markdown("**1. Database Configuration**")
    connection_mode = st.radio("Connect via:", ["Connection URL / URI", "Host & Credentials"], horizontal=True)

    db_uri = ""
    if connection_mode == "Connection URL / URI":
        db_uri = st.text_input(
            "Database Connection URL",
            placeholder="postgresql://user:pass@host/db?sslmode=require",
            type="password"
        )
    else:
        db_dialect = st.selectbox("Platform Engine", ["PostgreSQL", "MySQL", "MS SQL Server", "SQLite"])
        db_host = st.text_input("Host", placeholder="ep-xyz.aws.neon.tech")
        db_port = st.text_input("Port", placeholder="5432")
        db_name = st.text_input("Database Name", placeholder="neondb")
        db_user = st.text_input("Username", placeholder="neondb_owner")
        db_pass = st.text_input("Password", placeholder="••••••••", type="password")

        if db_host and db_name:
            if db_dialect == "PostgreSQL":
                db_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port or '5432'}/{db_name}?sslmode=require"
            elif db_dialect == "MySQL":
                db_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port or '3306'}/{db_name}"
            elif db_dialect == "MS SQL Server":
                db_uri = f"mssql+pyodbc://{db_user}:{db_pass}@{db_host}:{db_port or '1433'}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server"
            else:
                db_uri = f"sqlite:///{db_name}.db"

    st.divider()
    st.markdown("**2. SMTP Vendor Dispatcher**")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587)
    smtp_sender = st.text_input("Sender Email", placeholder="orders@store.com")
    smtp_password = st.text_input("App Password", placeholder="••••••••", type="password")

    sync_btn = st.button("🔄 Sync Database Feed", use_container_width=True)

engine = get_db_engine(db_uri) if db_uri else None
is_connected = engine is not None

if is_connected:
    st.sidebar.success("🟢 Connected to Live DB")
else:
    st.sidebar.warning("⚪ Awaiting Connection")

# ==========================================
# DATA INGESTION & AUTO NORMALIZATION
# ==========================================
raw_products, raw_sales, raw_movements = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

if is_connected:
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            prod_target = next((t for t in tables if "product" in t.lower() or "item" in t.lower()), "products_master")
            if prod_target in tables:
                raw_products = pd.read_sql(text(f"SELECT * FROM {prod_target}"), conn)
            
            sales_target = next((t for t in tables if "sale" in t.lower() or "order" in t.lower()), "sales_ledger")
            if sales_target in tables:
                raw_sales = pd.read_sql(text(f"SELECT * FROM {sales_target} ORDER BY 1 DESC LIMIT 2000"), conn)

            move_target = next((t for t in tables if "movement" in t.lower() or "audit" in t.lower()), "stock_movements")
            if move_target in tables:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {move_target} ORDER BY 1 DESC LIMIT 50"), conn)
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")

df_products, prod_map = resolve_and_normalize(raw_products)
df_sales, sales_map = resolve_and_normalize(raw_sales)

# ==========================================
# STATISTICAL ROP COMPUTATION
# ==========================================
def compute_analytics(products_df: pd.DataFrame, sales_df: pd.DataFrame) -> pd.DataFrame:
    if products_df.empty:
        return pd.DataFrame()

    matrix = products_df.copy()
    
    if not sales_df.empty and "sku" in sales_df.columns and "quantity_sold" in sales_df.columns:
        velocity_stats = sales_df.groupby("sku")["quantity_sold"].agg(
            daily_velocity="mean",
            daily_volatility=lambda x: x.std(ddof=1) if len(x) > 1 else 0.5
        ).reset_index()
        matrix = matrix.merge(velocity_stats, on="sku", how="left")
    else:
        matrix["daily_velocity"] = 3.0
        matrix["daily_volatility"] = 1.0

    matrix["daily_velocity"] = matrix["daily_velocity"].fillna(2.0).clip(lower=0.1)
    matrix["daily_volatility"] = matrix["daily_volatility"].fillna(0.8).clip(lower=0.1)
    
    Z = 1.65  # 95% Confidence Cycle Service Level
    matrix["safety_stock"] = np.ceil(Z * matrix["daily_volatility"] * np.sqrt(matrix["lead_time"].astype(float))).astype(int)
    matrix["rop"] = np.ceil((matrix["daily_velocity"] * matrix["lead_time"].astype(float)) + matrix["safety_stock"]).astype(int)
    matrix["days_runway"] = np.round(matrix["stock"] / matrix["daily_velocity"], 1)
    matrix["reorder_status"] = np.where(matrix["stock"] <= matrix["rop"], "RESTOCK NEEDED", "HEALTHY")
    matrix["expiry_risk"] = np.where(matrix["expiry_days"] <= 7, "HIGH EXPIRY RISK", "STABLE")

    def calc_po(row):
        if row["reorder_status"] == "RESTOCK NEEDED" or row["expiry_risk"] == "HIGH EXPIRY RISK":
            deficit = max(0, (2 * row["rop"]) - row["stock"])
            pack_mult = max(1, int(row.get("pack_size", 1)))
            batch = math.ceil(deficit / pack_mult) * pack_mult
            return max(int(row.get("moq", 10)), batch)
        return 0

    matrix["suggested_po_qty"] = matrix.apply(calc_po, axis=1)
    return matrix

analytics_df = compute_analytics(df_products, df_sales)

# ==========================================
# MAIN APPLICATION INTERFACE
# ==========================================
st.title("inventro.ai")
st.caption("Autonomous Retail Operating System & Dynamic Reorder Engine")

tab_analytics, tab_agent, tab_pos, tab_dispatcher, tab_infra = st.tabs([
    "📊 Catalog & Analytics Matrix",
    "🤖 Autonomous AI Supply Agent",
    "⚡ POS Transaction Scanner",
    "✉️ Autonomous PO Dispatcher",
    "🔌 Database Infrastructure Terminal"
])

# ------------------------------------------
# TAB 1: CATALOG & ANALYTICS MATRIX
# ------------------------------------------
with tab_analytics:
    if analytics_df.empty:
        st.info("No active catalog data detected. Connect your database or provision sample schemas in the Infrastructure tab.")
    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        restock_count = len(analytics_df[analytics_df["reorder_status"] == "RESTOCK NEEDED"])
        expiry_count = len(analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"])
        
        with kpi1:
            st.metric("Monitored SKUs", len(analytics_df))
        with kpi2:
            st.metric("Restock Breaches (Stock ≤ ROP)", restock_count, delta=-restock_count if restock_count > 0 else 0, delta_color="inverse")
        with kpi3:
            st.metric("Perishable Risks (≤ 7 Days)", expiry_count, delta=-expiry_count if expiry_count > 0 else 0, delta_color="inverse")
        with kpi4:
            st.metric("Average Runway", f"{round(analytics_df['days_runway'].mean(), 1)} Days")

        display_cols = ["sku", "name", "category", "stock", "lead_time", "daily_velocity", "safety_stock", "rop", "days_runway", "reorder_status", "expiry_days", "suggested_po_qty", "vendor"]
        available_display_cols = [c for c in display_cols if c in analytics_df.columns]
        
        st.dataframe(analytics_df[available_display_cols], use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 2: AUTONOMOUS AI SUPPLY AGENT
# ------------------------------------------
with tab_agent:
    st.markdown("#### **🤖 Autonomous AI Inventory Agent & Copilot**")
    st.caption("Self-directed supply chain diagnostic loop analyzing stockout vectors, lead times, and decay risks in real time.")
    
    if analytics_df.empty:
        st.warning("Agent is idle. Connect a database to allow the agent to inspect inventory streams.")
    else:
        # Agent Autonomous Diagnostic Pipeline
        critical_items = analytics_df[analytics_df["reorder_status"] == "RESTOCK NEEDED"]
        perishable_items = analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"]
        overstock_items = analytics_df[analytics_df["days_runway"] > 45]

        st.markdown('<div class="agent-card">', unsafe_allow_html=True)
        st.markdown("### **🧠 Agent Thought & Execution Stream**")
        
        # Simulated Agent Decision Steps
        thought_log = f"""
[OBSERVATION] Scanning {len(analytics_df)} registered SKUs across live transaction channels.
[ANALYSIS] {len(critical_items)} SKUs breached statistical dynamic Reorder Points (ROP @ 95% Confidence, Z=1.65).
[RISK CHECK] {len(perishable_items)} SKUs are within the critical 7-day shelf-life decay horizon.
[DECISION] Prescribing immediate PO batches with MOQ constraint validation for suppliers: {', '.join(critical_items['vendor'].unique()) if not critical_items.empty else 'None'}.
[STATUS] Closed-loop autonomous monitoring active. No manual intervention required.
"""
        st.markdown(f'<div class="agent-thought">{thought_log.strip()}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("#### **⚡ Agent Proactive Prescriptions**")
        agent_col1, agent_col2, agent_col3 = st.columns(3)

        with agent_col1:
            st.markdown(f"**🚨 Urgent Replenishments ({len(critical_items)})**")
            if not critical_items.empty:
                for _, r in critical_items.iterrows():
                    st.error(f"**{r['name']}** (`{r['sku']}`)\n- Stock: {r['stock']} / ROP: {r['rop']}\n- Order: **+{r['suggested_po_qty']} units** from *{r['vendor']}*")
            else:
                st.success("No stockout risks detected.")

        with agent_col2:
            st.markdown(f"**⏳ Expiry & Spoilage Vectors ({len(perishable_items)})**")
            if not perishable_items.empty:
                for _, r in perishable_items.iterrows():
                    st.warning(f"**{r['name']}** (`{r['sku']}`)\n- Shelf Life: **{r['expiry_days']} days left**\n- Clearance Runway: {r['days_runway']} days")
            else:
                st.success("Zero high-risk perishable items.")

        with agent_col3:
            st.markdown(f"**📦 Working Capital Trapped ({len(overstock_items)})**")
            if not overstock_items.empty:
                for _, r in overstock_items.iterrows():
                    st.info(f"**{r['name']}** (`{r['sku']}`)\n- Runway: **{r['days_runway']} days**\n- Recommendation: Pause replenishment.")
            else:
                st.success("Healthy inventory turnover fleet-wide.")

        st.divider()

        # Interactive Copilot Query
        st.markdown("#### **💬 Query Inventory AI Copilot**")
        user_query = st.text_input("Ask anything about your stock, demand, or suppliers:", placeholder="e.g. Which item will run out of stock first?")
        
        if user_query:
            q = user_query.lower()
            st.markdown("**Agent Response:**")
            
            if "out of stock" in q or "run out" in q or "first" in q:
                lowest_runway = analytics_df.sort_values(by="days_runway").iloc[0]
                st.markdown(f"👉 **`{lowest_runway['name']}`** is at greatest risk. It has **{lowest_runway['days_runway']} days of runway left** with **{lowest_runway['stock']} units** remaining and a daily sales velocity of **{lowest_runway['daily_velocity']} units/day**.")
            
            elif "order" in q or "purchase" in q or "buy" in q or "supplier" in q:
                if not critical_items.empty:
                    summary = "\n".join([f"- **{r['vendor']}**: {r['suggested_po_qty']}x {r['name']}" for _, r in critical_items.iterrows()])
                    st.markdown(f"👉 You should order the following restock batches today:\n{summary}")
                else:
                    st.markdown("👉 All SKUs are healthy. Zero purchase orders required today.")
                    
            elif "perish" in q or "expire" in q or "spoil" in q:
                if not perishable_items.empty:
                    p_summary = "\n".join([f"- **{r['name']}**: expires in {r['expiry_days']} days ({r['stock']} units in stock)" for _, r in perishable_items.iterrows()])
                    st.markdown(f"👉 The following products need urgent attention before expiration:\n{p_summary}")
                else:
                    st.markdown("👉 All items have comfortable expiration buffers (> 7 days).")
            else:
                st.markdown(f"👉 **Fleet Summary:** Monitoring {len(analytics_df)} SKUs. {len(critical_items)} require reordering, and {len(perishable_items)} are near shelf-life expiry. Average fleet runway is {round(analytics_df['days_runway'].mean(), 1)} days.")

# ------------------------------------------
# TAB 3: POS TRANSACTION SCANNER
# ------------------------------------------
with tab_pos:
    st.markdown("#### **Point of Sale Barcode Intake Terminal**")
    pos_col1, pos_col2 = st.columns([1, 1.5])
    
    with pos_col1:
        if not analytics_df.empty:
            sku_options = analytics_df["sku"].tolist()
            selected_sku = st.selectbox("Select Barcode / SKU Scan", sku_options)
            sku_data = analytics_df[analytics_df["sku"] == selected_sku].iloc[0]
            
            scan_qty = st.number_input("Checkout Units", min_value=1, max_value=int(max(1, sku_data['stock'])), value=1)
            
            st.markdown(f"""
            **Item:** `{sku_data['name']}`  
            **Current Physical Stock:** `{sku_data['stock']} units`  
            **Active ROP Threshold:** `{sku_data['rop']} units`  
            """)
            
            if st.button("⚡ Execute POS Transaction", type="primary", use_container_width=True):
                if is_connected:
                    try:
                        with engine.begin() as conn:
                            stock_col = prod_map.get("stock", "stock")
                            sku_col = prod_map.get("sku", "sku")
                            conn.execute(
                                text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku"),
                                {"qty": scan_qty, "sku": selected_sku}
                            )
                            conn.execute(
                                text("""
                                INSERT INTO sales_ledger (transaction_date, sku, product_name, category, quantity_sold, is_weekend)
                                VALUES (:tdate, :sku, :name, :cat, :qty, :wkd)
                                """),
                                {
                                    "tdate": datetime.now(),
                                    "sku": selected_sku,
                                    "name": sku_data["name"],
                                    "cat": sku_data["category"],
                                    "qty": scan_qty,
                                    "wkd": 1 if datetime.now().weekday() >= 5 else 0
                                }
                            )
                            conn.execute(
                                text("""
                                INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes)
                                VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Live POS scan checkout')
                                """),
                                {"ts": datetime.now(), "sku": selected_sku, "qty": -scan_qty}
                            )
                        st.toast(f"✅ Deducted {scan_qty}x {sku_data['name']} from DB.", icon="🛒")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Transaction Execution Failed: {err}")
                else:
                    st.error("No database engine connected.")
        else:
            st.warning("No catalog data available.")

    with pos_col2:
        st.markdown("**Live Stock Audit Trail (`stock_movements`)**")
        if not raw_movements.empty:
            st.dataframe(raw_movements.head(10), use_container_width=True, hide_index=True)
        else:
            st.caption("No recent stock movement logs found.")

# ------------------------------------------
# TAB 4: AUTONOMOUS PO DISPATCHER
# ------------------------------------------
with tab_dispatcher:
    st.markdown("#### **Autonomous Purchase Order Dispatch Center**")
    
    if not analytics_df.empty:
        po_candidates = analytics_df[analytics_df["suggested_po_qty"] > 0]
        
        if po_candidates.empty:
            st.success("✨ All product lines are operating within safe inventory thresholds. No purchase orders needed.")
        else:
            st.warning(f"⚠️ {len(po_candidates)} product line(s) require replenishment.")
            
            selected_vendor = st.selectbox("Group Orders by Supplier", po_candidates["vendor"].unique())
            vendor_orders = po_candidates[po_candidates["vendor"] == selected_vendor]
            
            default_email = vendor_orders["email"].iloc[0] if "email" in vendor_orders.columns and vendor_orders["email"].iloc[0] else "vendor-orders@partner.com"
            recipient_email = st.text_input("Supplier Dispatch Email", value=default_email)
            
            po_body_lines = [
                f"PURCHASE ORDER — INVENTRO.AI AUTONOMOUS REPLENISHMENT\n",
                f"Supplier: {selected_vendor}",
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "-" * 60,
                f"{'SKU':<12} | {'Item Name':<25} | {'Stock':<6} | {'ROP':<6} | {'Order Qty'}",
                "-" * 60
            ]
            for _, r in vendor_orders.iterrows():
                po_body_lines.append(f"{r['sku']:<12} | {r['name'][:24]:<25} | {r['stock']:<6} | {r['rop']:<6} | {r['suggested_po_qty']} units")
            po_body_lines.append("-" * 60)
            po_body_lines.append("\nPlease confirm order dispatch turnaround time.")
            
            po_payload = "\n".join(po_body_lines)
            st.text_area("Purchase Order Preview", value=po_payload, height=220)
            
            if st.button(f"✉️ Dispatch Purchase Order to {selected_vendor}", type="primary"):
                if not smtp_sender or not smtp_password:
                    st.error("Please configure SMTP Sender Email and App Password in the sidebar.")
                else:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = smtp_sender
                        msg["To"] = recipient_email
                        msg["Subject"] = f"URGENT: Purchase Order Restock - {selected_vendor} [{datetime.now().strftime('%Y-%m-%d')}]"
                        msg.attach(MIMEText(po_payload, "plain"))
                        
                        server = smtplib.SMTP(smtp_server, int(smtp_port))
                        server.starttls()
                        server.login(smtp_sender, smtp_password)
                        server.send_message(msg)
                        server.quit()
                        
                        st.success(f"🚀 Purchase Order successfully dispatched via TLS to {recipient_email}!")
                    except Exception as mail_err:
                        st.error(f"SMTP Dispatch Error: {mail_err}")
    else:
        st.info("Database not connected.")

# ------------------------------------------
# TAB 5: DATABASE INFRASTRUCTURE & TERMINAL
# ------------------------------------------
with tab_infra:
    st.markdown("#### **Database Infrastructure & Schema Provisioner**")
    col_prov, col_sql = st.columns([1, 1.2])
    
    with col_prov:
        st.markdown("**Schema Initialization**")
        st.caption("Provisions missing `products_master`, `sales_ledger`, and `stock_movements` tables with seed data.")
        
        if st.button("🛠️ Provision Missing Schemas & Seed Data"):
            if is_connected:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS products_master (
                            sku VARCHAR(50) PRIMARY KEY,
                            name VARCHAR(150),
                            category VARCHAR(50),
                            stock INT DEFAULT 0,
                            lead_time INT DEFAULT 2,
                            moq INT DEFAULT 10,
                            pack_size INT DEFAULT 1,
                            vendor VARCHAR(100),
                            email VARCHAR(100),
                            expiry_days INT DEFAULT 30
                        );
                        """))
                        conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS sales_ledger (
                            id SERIAL PRIMARY KEY,
                            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            sku VARCHAR(50),
                            product_name VARCHAR(150),
                            category VARCHAR(50),
                            quantity_sold INT DEFAULT 1,
                            is_weekend INT DEFAULT 0
                        );
                        """))
                        conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS stock_movements (
                            id SERIAL PRIMARY KEY,
                            movement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            sku VARCHAR(50),
                            movement_type VARCHAR(50),
                            quantity INT,
                            notes VARCHAR(255)
                        );
                        """))
                        res = conn.execute(text("SELECT COUNT(*) FROM products_master")).scalar()
                        if res == 0:
                            conn.execute(text("""
                            INSERT INTO products_master (sku, name, category, stock, lead_time, moq, pack_size, vendor, email, expiry_days) VALUES
                            ('SKU-1001', 'Amul Pasteurized Milk 1L', 'Dairy', 12, 1, 20, 10, 'Amul Dairy Co', 'orders@amuldairy.com', 3),
                            ('SKU-1002', 'Aashirvaad Whole Wheat Atta 5kg', 'Grains', 8, 3, 10, 5, 'ITC Foods Ltd', 'supply@itc.com', 90),
                            ('SKU-1003', 'Tata Salt Iodized 1kg', 'Pantry', 35, 2, 25, 25, 'Tata Consumer Products', 'orders@tataconsumer.com', 180),
                            ('SKU-1004', 'Cadbury Dairy Milk Silk 150g', 'Confectionery', 5, 2, 15, 10, 'Mondelez India', 'restock@mondelez.com', 45);
                            """))
                    st.success("✅ Database schemas successfully verified & provisioned.")
                    st.rerun()
                except Exception as p_err:
                    st.error(f"Provisioning Failed: {p_err}")
            else:
                st.error("Connect to a database in the sidebar before provisioning.")

    with col_sql:
        st.markdown("**Direct SQL Query Terminal**")
        custom_sql = st.text_area("Execute Query on Active DB:", placeholder="SELECT * FROM products_master LIMIT 10;")
        if st.button("⚡ Execute Query"):
            if custom_sql and custom_sql.strip() and is_connected:
                try:
                    with engine.connect() as conn:
                        query_res = pd.read_sql(text(custom_sql), conn)
                        st.dataframe(query_res, use_container_width=True)
                except Exception as q_err:
                    st.error(f"SQL Error: {q_err}")
            else:
                st.warning("Please provide an active query and verify connection.")