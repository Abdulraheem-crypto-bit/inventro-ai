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

# Optional AI SDK import for Schema Inference Agent
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

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
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .badge-critical {
        background-color: rgba(239, 68, 68, 0.2);
        color: #f87171;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .badge-healthy {
        background-color: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# AI SCHEMA RESOLUTION & FALLBACK AGENT
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

def resolve_schema_heuristic(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Heuristic fallback matcher using regex and token synonyms."""
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

    return normalized_df, detected_mapping

def resolve_schema_with_ai(df: pd.DataFrame, table_hint: str = "products", gemini_api_key: str = None) -> tuple[pd.DataFrame, dict]:
    """
    Autonomous LLM Schema Resolution Agent.
    Inspects column names and sample data rows using Gemini to build an intelligent mapping.
    Falls back to heuristic token matching if the LLM key is absent or unavailable.
    """
    if df.empty:
        return df, {}

    if not GENAI_AVAILABLE or not gemini_api_key:
        normalized_df, mapping = resolve_schema_heuristic(df)
        return apply_canonical_defaults(normalized_df), mapping

    try:
        sample_rows = df.head(3).to_dict(orient="records")
        client = genai.Client(api_key=gemini_api_key)
        
        prompt = f"""
You are an expert Data Engineer & Schema Resolution Agent.
Map the detected table columns to our target canonical fields based on names and data examples.

Canonical Target Fields:
- 'sku': Product identifier, item code, barcode, or primary key.
- 'name': Product description, item name, title.
- 'category': Department, product category, group.
- 'stock': Current available stock, quantity on hand.
- 'lead_time': Supplier turnaround in days.
- 'moq': Minimum order quantity.
- 'pack_size': Case multiplier / packaging bundle size.
- 'vendor': Supplier or distributor name.
- 'email': Supplier contact email.
- 'expiry_days': Remaining shelf life / days to expire.
- 'quantity_sold': Count of units decremented/sold.
- 'transaction_date': Transaction timestamp or date.

Table Context: {table_hint}
Detected Columns: {list(df.columns)}
Data Sample: {json.dumps(sample_rows, default=str)}

Return ONLY a valid JSON object where keys are the detected column names and values are the matching canonical fields (or null if irrelevant).
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        inferred = json.loads(response.text)
        
        normalized_df = df.copy()
        applied_mapping = {}
        for original_col, canonical_key in inferred.items():
            if canonical_key and original_col in df.columns:
                applied_mapping[canonical_key] = original_col
                normalized_df[canonical_key] = df[original_col]

        # Combine with heuristics for any unmapped canonical fields
        heuristic_df, heuristic_mapping = resolve_schema_heuristic(df)
        for k, v in heuristic_mapping.items():
            if k not in applied_mapping:
                applied_mapping[k] = v
                normalized_df[k] = heuristic_df[k]

        return apply_canonical_defaults(normalized_df), applied_mapping

    except Exception:
        normalized_df, mapping = resolve_schema_heuristic(df)
        return apply_canonical_defaults(normalized_df), mapping

def apply_canonical_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Injects standard safe defaults for missing optional columns to prevent runtime math failures."""
    defaults = {
        "sku": [f"SKU_{i+1:03d}" for i in range(len(df))] if "sku" not in df.columns else df["sku"],
        "name": "Unnamed SKU",
        "category": "General",
        "stock": 0,
        "lead_time": 2,
        "moq": 10,
        "pack_size": 1,
        "vendor": "Default Supplier",
        "email": "",
        "expiry_days": 30,
        "quantity_sold": 1
    }
    for field, default_val in defaults.items():
        if field not in df.columns:
            df[field] = default_val
    return df

# ==========================================
# DATABASE ENGINE CONNECTION HANDLER
# ==========================================
@st.cache_resource(show_spinner=False)
def get_db_engine(connection_string: str):
    if not connection_string or not connection_string.strip():
        return None
    try:
        engine = create_engine(
            connection_string.strip(),
            pool_pre_ping=True,
            pool_recycle=300
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.sidebar.error(f"Database Handshake Failed: {e}")
        return None

# ==========================================
# SIDEBAR CONTROLS & AUTHENTICATION
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

    gemini_key = st.text_input("Gemini API Key (Schema Agent)", placeholder="AIzaSy...", type="password")
    
    st.divider()
    st.markdown("**2. SMTP Vendor Dispatcher**")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587)
    smtp_sender = st.text_input("Sender Email", placeholder="orders@retailstore.com")
    smtp_password = st.text_input("Sender App Password", placeholder="••••••••", type="password")

    sync_btn = st.button("🔄 Sync Database Feed", use_container_width=True)

# Establish active database connection
engine = get_db_engine(db_uri) if db_uri else None
is_connected = engine is not None

if is_connected:
    st.sidebar.success("🟢 Connected to Database")
else:
    st.sidebar.warning("⚪ Waiting for Database Connection")

# ==========================================
# DATA INGESTION & AGENT NORMALIZATION
# ==========================================
raw_products = pd.DataFrame()
raw_sales = pd.DataFrame()
raw_movements = pd.DataFrame()

if is_connected:
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            # Fetch products
            prod_target = next((t for t in tables if "product" in t.lower() or "item" in t.lower()), "products_master")
            if prod_target in tables:
                raw_products = pd.read_sql(text(f"SELECT * FROM {prod_target}"), conn)
            
            # Fetch sales ledger
            sales_target = next((t for t in tables if "sale" in t.lower() or "order" in t.lower() or "txn" in t.lower()), "sales_ledger")
            if sales_target in tables:
                raw_sales = pd.read_sql(text(f"SELECT * FROM {sales_target} ORDER BY 1 DESC LIMIT 2000"), conn)

            # Fetch stock audit
            move_target = next((t for t in tables if "movement" in t.lower() or "audit" in t.lower()), "stock_movements")
            if move_target in tables:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {move_target} ORDER BY 1 DESC LIMIT 100"), conn)
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")

# Reconcile schemas dynamically with AI Schema Agent
df_products, prod_schema_map = resolve_schema_with_ai(raw_products, table_hint="products_master", gemini_api_key=gemini_key)
df_sales, sales_schema_map = resolve_schema_with_ai(raw_sales, table_hint="sales_ledger", gemini_api_key=gemini_key)

# ==========================================
# STATISTICAL MACHINE LEARNING / ROP ENGINE
# ==========================================
def compute_analytics(products_df: pd.DataFrame, sales_df: pd.DataFrame) -> pd.DataFrame:
    if products_df.empty:
        return pd.DataFrame()

    matrix = products_df.copy()
    
    # Calculate rolling 14-day metrics from sales ledger
    if not sales_df.empty and "sku" in sales_df.columns and "quantity_sold" in sales_df.columns:
        # Group by SKU to calculate daily consumption velocity and variance
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
    
    # Statistical Learning Calculations (Z = 1.65 for 95% service level)
    Z = 1.65
    matrix["safety_stock"] = np.ceil(Z * matrix["daily_volatility"] * np.sqrt(matrix["lead_time"].astype(float))).astype(int)
    matrix["rop"] = np.ceil((matrix["daily_velocity"] * matrix["lead_time"].astype(float)) + matrix["safety_stock"]).astype(int)
    
    # Health and Runway metrics
    matrix["days_runway"] = np.round(matrix["stock"] / matrix["daily_velocity"], 1)
    matrix["reorder_status"] = np.where(matrix["stock"] <= matrix["rop"], "RESTOCK NEEDED", "HEALTHY")
    matrix["expiry_risk"] = np.where(matrix["expiry_days"] <= 7, "HIGH EXPIRY RISK", "STABLE")

    # Suggested PO batch calculation with MOQ and Pack Size constraints
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
st.caption("Autonomous Retail Operating System & Dynamic Reorder Optimization")

tab_analytics, tab_pos, tab_dispatcher, tab_infra = st.tabs([
    "📊 Catalog & Analytics Matrix",
    "⚡ POS Transaction Scanner",
    "✉️ Autonomous PO Dispatcher",
    "🔌 Database Infrastructure Terminal"
])

# ------------------------------------------
# TAB 1: CATALOG & ANALYTICS MATRIX
# ------------------------------------------
with tab_analytics:
    if analytics_df.empty:
        st.info("No active catalog data detected. Connect a database or provision sample schemas in the Infrastructure tab.")
    else:
        # High Level KPI Cards
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        restock_count = len(analytics_df[analytics_df["reorder_status"] == "RESTOCK NEEDED"])
        expiry_count = len(analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"])
        
        with kpi1:
            st.metric("Total Monitored SKUs", len(analytics_df))
        with kpi2:
            st.metric("Restock Breaches (Stock ≤ ROP)", restock_count, delta=-restock_count if restock_count > 0 else 0, delta_color="inverse")
        with kpi3:
            st.metric("Critical Perishables (≤ 7 Days)", expiry_count, delta=-expiry_count if expiry_count > 0 else 0, delta_color="inverse")
        with kpi4:
            avg_runway = round(analytics_df["days_runway"].mean(), 1)
            st.metric("Average Fleet Runway", f"{avg_runway} Days")

        st.markdown("#### **Dynamic ROP & Statistical Safety Stock Matrix**")
        if prod_schema_map:
            with st.expander("🤖 Dynamic AI Schema Mappings (Active)", expanded=False):
                st.json(prod_schema_map)

        display_cols = ["sku", "name", "category", "stock", "lead_time", "daily_velocity", "safety_stock", "rop", "days_runway", "reorder_status", "expiry_days", "suggested_po_qty", "vendor"]
        available_display_cols = [c for c in display_cols if c in analytics_df.columns]
        
        st.dataframe(
            analytics_df[available_display_cols],
            use_container_width=True,
            hide_index=True
        )

# ------------------------------------------
# TAB 2: POS TRANSACTION SCANNER
# ------------------------------------------
with tab_pos:
    st.markdown("#### **Point of Sale Barcode Intake Terminal**")
    st.caption("Live checkout decrementing directly synced to relational cloud storage.")
    
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
            **Category:** `{sku_data['category']}`  
            **Active ROP:** `{sku_data['rop']} units`  
            """)
            
            if st.button("⚡ Execute POS Transaction", type="primary", use_container_width=True):
                if is_connected:
                    try:
                        with engine.begin() as conn:
                            # 1. Decrement products stock
                            sku_col = prod_schema_map.get("sku", "sku")
                            stock_col = prod_schema_map.get("stock", "stock")
                            conn.execute(
                                text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku"),
                                {"qty": scan_qty, "sku": selected_sku}
                            )
                            # 2. Append to sales ledger
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
                            # 3. Log stock audit trail
                            conn.execute(
                                text("""
                                INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes)
                                VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Live cashier terminal checkout')
                                """),
                                {"ts": datetime.now(), "sku": selected_sku, "qty": -scan_qty}
                            )
                        st.toast(f"✅ Deducted {scan_qty}x {sku_data['name']} from DB.", icon="🛒")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Transaction Execution Failed: {err}")
                else:
                    st.error("No active database engine attached.")
        else:
            st.warning("No catalog data available to execute checkout transactions.")

    with pos_col2:
        st.markdown("**Live Stock Audit Ledger (`stock_movements`)**")
        if not raw_movements.empty:
            st.dataframe(raw_movements.head(10), use_container_width=True, hide_index=True)
        else:
            st.caption("No recent stock movement logs found.")

# ------------------------------------------
# TAB 3: AUTONOMOUS PO DISPATCHER
# ------------------------------------------
with tab_dispatcher:
    st.markdown("#### **Autonomous Purchase Order Dispatch Center**")
    st.caption("Prescriptive vendor order fulfillment with packaging constraints and direct SMTP relay.")
    
    if not analytics_df.empty:
        po_candidates = analytics_df[analytics_df["suggested_po_qty"] > 0]
        
        if po_candidates.empty:
            st.success("✨ All product lines are operating within optimal safety stock thresholds. Zero replenishments required.")
        else:
            st.warning(f"⚠️ {len(po_candidates)} product line(s) have breached safety thresholds and require immediate purchase orders.")
            
            selected_vendor = st.selectbox("Group Orders by Supplier", po_candidates["vendor"].unique())
            vendor_orders = po_candidates[po_candidates["vendor"] == selected_vendor]
            
            default_email = vendor_orders["email"].iloc[0] if "email" in vendor_orders.columns and vendor_orders["email"].iloc[0] else "vendor-fulfillment@partner.com"
            recipient_email = st.text_input("Supplier Dispatch Email", value=default_email)
            
            po_body_lines = []
            po_body_lines.append(f"PURCHASE ORDER — INVENTRO.AI AUTONOMOUS REPLENISHMENT\n")
            po_body_lines.append(f"Supplier: {selected_vendor}")
            po_body_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            po_body_lines.append("-" * 60)
            po_body_lines.append(f"{'SKU':<12} | {'Item Name':<25} | {'Stock':<6} | {'ROP':<6} | {'Order Qty'}")
            po_body_lines.append("-" * 60)
            
            for _, r in vendor_orders.iterrows():
                po_body_lines.append(f"{r['sku']:<12} | {r['name'][:24]:<25} | {r['stock']:<6} | {r['rop']:<6} | {r['suggested_po_qty']} units")
            po_body_lines.append("-" * 60)
            po_body_lines.append("\nPlease acknowledge receipt and dispatch according to our standard SLA turnaround.")
            
            po_payload = "\n".join(po_body_lines)
            st.text_area("Purchase Order Payload Preview", value=po_payload, height=220)
            
            if st.button(f"✉️ Dispatch Purchase Order to {selected_vendor}", type="primary"):
                if not smtp_sender or not smtp_password:
                    st.error("Please configure SMTP Sender Email and App Password in the sidebar.")
                else:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = smtp_sender
                        msg["To"] = recipient_email
                        msg["Subject"] = f"URGENT: Purchase Order Restock Request - {selected_vendor} [{datetime.now().strftime('%Y-%m-%d')}]"
                        msg.attach(MIMEText(po_payload, "plain"))
                        
                        server = smtplib.SMTP(smtp_server, int(smtp_port))
                        server.starttls()
                        server.login(smtp_sender, smtp_password)
                        server.send_message(msg)
                        server.quit()
                        
                        st.success(f"🚀 Purchase Order successfully dispatched via TLS to {recipient_email}!")
                    except Exception as mail_err:
                        st.error(f"SMTP Transmission Failed: {mail_err}")
    else:
        st.info("Database not connected.")

# ------------------------------------------
# TAB 4: DATABASE INFRASTRUCTURE & TERMINAL
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
                        # 1. Products Master
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
                        
                        # 2. Sales Ledger
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

                        # 3. Stock Audit movements
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
                        
                        # Seed baseline data if empty
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