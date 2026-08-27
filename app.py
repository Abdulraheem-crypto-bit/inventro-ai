# app.py - inventro.ai: Enterprise Multi-Database Autonomous Inventory OS
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re

st.set_page_config(
    page_title="inventro.ai | Autonomous Retail OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 0. Deep Aurora Mesh Theme
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }
    
    code, pre, .font-mono {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stApp {
        background-color: #05070E;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.22) 0px, transparent 45%),
            radial-gradient(at 100% 0%, rgba(6, 182, 212, 0.20) 0px, transparent 45%),
            radial-gradient(at 50% 50%, rgba(139, 92, 246, 0.12) 0px, transparent 55%),
            radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.15) 0px, transparent 50%),
            linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px;
        background-attachment: fixed;
        color: #F8FAFC;
    }

    .saas-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.75) 0%, rgba(7, 12, 26, 0.85) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 12px 35px -8px rgba(0, 0, 0, 0.7), inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border-radius: 16px;
        padding: 22px 24px;
        position: relative;
        overflow: hidden;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .saas-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.6), rgba(6, 182, 212, 0.6), transparent);
    }

    .saas-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 16px 40px -10px rgba(99, 102, 241, 0.25);
        transform: translateY(-2px);
    }

    .metric-value {
        font-size: 2.3rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        line-height: 1.1;
        margin: 6px 0;
        background: linear-gradient(135deg, #FFFFFF 30%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-label {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #94A3B8;
    }

    .metric-subtext {
        font-size: 0.8rem;
        font-weight: 500;
        color: #64748B;
    }

    .badge-live {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(6, 182, 212, 0.12);
        color: #22D3EE;
        border: 1px solid rgba(6, 182, 212, 0.35);
        padding: 5px 14px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        box-shadow: 0 0 15px rgba(6, 182, 212, 0.2);
    }

    .pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #22D3EE;
        border-radius: 50%;
        box-shadow: 0 0 10px #22D3EE;
        animation: pulse 1.6s infinite ease-in-out;
    }

    @keyframes pulse {
        0% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.8); }
        70% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 0 8px rgba(34, 211, 238, 0); }
        100% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 0 0 rgba(34, 211, 238, 0); }
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 6px;
        border-radius: 14px;
        backdrop-filter: blur(12px);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        color: #94A3B8;
        font-weight: 600;
        padding: 8px 20px;
        transition: all 0.2s ease;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(6, 182, 212, 0.2) 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(99, 102, 241, 0.45) !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25);
    }

    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
</style>
""", unsafe_allow_html=True)

# One-Shot Money Rain Dispatcher
def trigger_cash_rain():
    cash_script = """
    <script>
    (function() {
        const parentDoc = window.parent.document;
        const container = parentDoc.createElement('div');
        container.style.position = 'fixed';
        container.style.top = '0';
        container.style.left = '0';
        container.style.width = '100vw';
        container.style.height = '100vh';
        container.style.pointerEvents = 'none';
        container.style.zIndex = '9999999';
        parentDoc.body.appendChild(container);

        const symbols = ['💵', '💸', '💰', '💲', '🤑'];
        for (let i = 0; i < 60; i++) {
            const el = parentDoc.createElement('div');
            el.innerText = symbols[Math.floor(Math.random() * symbols.length)];
            el.style.position = 'absolute';
            el.style.top = '-60px';
            el.style.left = (Math.random() * 96) + 'vw';
            el.style.fontSize = (Math.random() * 22 + 24) + 'px';
            el.style.opacity = '1';
            el.style.transition = `top ${Math.random() * 1.5 + 2.2}s cubic-bezier(0.25, 0.46, 0.45, 0.94), transform ${Math.random() * 1.5 + 2.2}s ease, opacity 0.6s ease`;
            container.appendChild(el);

            setTimeout(() => {
                el.style.top = '105vh';
                el.style.transform = `rotate(${Math.random() * 720 - 360}deg)`;
            }, 50 + (i * 20));
        }

        setTimeout(() => {
            container.remove();
        }, 3800);
    })();
    </script>
    """
    components.html(cash_script, height=0, width=0)

# ==========================================
# 1. Multi-Engine Database Gateway
# ==========================================
def create_db_connection(conn_mode, db_type, params):
    try:
        if conn_mode == "Connection URL / URI":
            raw_uri = params.get("uri", "").strip()
            if not raw_uri:
                return None, False, "Please enter a connection URL."
            
            # Auto-format PostgreSQL dialects for SQLAlchemy + psycopg2
            if raw_uri.startswith("postgres://"):
                raw_uri = raw_uri.replace("postgres://", "postgresql+psycopg2://", 1)
            elif raw_uri.startswith("postgresql://"):
                raw_uri = raw_uri.replace("postgresql://", "postgresql+psycopg2://", 1)
            
            engine = create_engine(raw_uri, pool_pre_ping=True, pool_recycle=300)
            return engine, True, ""
        
        else:
            user = params.get("user", "").strip()
            raw_pwd = params.get("password", "")
            pwd = quote_plus(raw_pwd) if raw_pwd else ""
            pwd_str = f":{pwd}" if pwd else ""
            host = params.get("host", "").strip()
            port = str(params.get("port", "")).strip()
            dbname = params.get("dbname", "").strip()

            if not host:
                return None, False, "Host cannot be empty."

            if db_type == "PostgreSQL":
                if not user:
                    return None, False, "Username required for PostgreSQL connection."
                uri = f"postgresql+psycopg2://{user}{pwd_str}@{host}:{port}/{dbname}"
                return create_engine(uri, pool_pre_ping=True, pool_recycle=300), True, ""
                
            elif db_type == "MySQL / MariaDB":
                if not user:
                    user = "root"
                uri = f"mysql+pymysql://{user}{pwd_str}@{host}:{port}/{dbname}"
                return create_engine(uri, pool_pre_ping=True, pool_recycle=300), True, ""
                
            elif db_type == "Microsoft SQL Server":
                driver = params.get("driver", "ODBC Driver 17 for SQL Server").replace(" ", "+")
                uri = f"mssql+pyodbc://{user}{pwd_str}@{host}:{port}/{dbname}?driver={driver}"
                return create_engine(uri, pool_pre_ping=True, pool_recycle=300), True, ""
                
            return None, False, "Unknown engine selected."
    except Exception as e:
        return None, False, str(e)

def init_tables_safely(engine, db_type):
    """Provisions empty standard retail schemas across SQL dialects."""
    if engine is None:
        return False, "No active database connection."

    if db_type == "MySQL / MariaDB":
        auto_id = "INT AUTO_INCREMENT PRIMARY KEY"
    elif db_type == "Microsoft SQL Server":
        auto_id = "INT IDENTITY(1,1) PRIMARY KEY"
    else:  # PostgreSQL / Neon default
        auto_id = "SERIAL PRIMARY KEY"

    try:
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS products_master (
                    sku VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(255),
                    category VARCHAR(64),
                    lead_time INT DEFAULT 2,
                    moq INT DEFAULT 10,
                    pack_size INT DEFAULT 1,
                    vendor VARCHAR(255),
                    email VARCHAR(255),
                    stock INT DEFAULT 0,
                    expiry_days INT DEFAULT 30
                );
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS sales_ledger (
                    id {auto_id},
                    transaction_date VARCHAR(32),
                    sku VARCHAR(64),
                    product_name VARCHAR(255),
                    category VARCHAR(64),
                    quantity_sold INT,
                    is_weekend INT DEFAULT 0
                );
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id {auto_id},
                    movement_timestamp VARCHAR(64),
                    sku VARCHAR(64),
                    movement_type VARCHAR(64),
                    quantity INT,
                    notes VARCHAR(255)
                );
            """))
            conn.commit()
        return True, "Schema provisioned successfully."
    except Exception as e:
        return False, str(e)

# ==========================================
# 2. SMTP Mail Dispatcher
# ==========================================
def send_real_email(sender_email, sender_password, receiver_email, subject, body, smtp_server="smtp.gmail.com", smtp_port=587):
    if not sender_email or not sender_password:
        return False, "Please configure Sender Email and App Password in the sidebar."
    
    clean_sender = re.sub(r'[\s\xa0\u200b\uFEFF]+', '', str(sender_email)).strip()
    clean_password = re.sub(r'[\s\xa0\u200b\uFEFF]+', '', str(sender_password)).strip()
    clean_receiver = re.sub(r'[\s\xa0\u200b\uFEFF]+', '', str(receiver_email)).strip()
    
    try:
        msg = MIMEMultipart()
        msg["From"] = f"inventro.ai Operations <{clean_sender}>"
        msg["To"] = clean_receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(smtp_server.strip(), int(smtp_port))
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(clean_sender, clean_password)
        server.sendmail(clean_sender, [clean_receiver], msg.as_string())
        server.quit()
        return True, "Purchase Order successfully transmitted via SMTP relay."
    except Exception as e:
        return False, f"SMTP Error: {str(e)}"

# ==========================================
# 3. Dynamic ROP Analytics Engine
# ==========================================
def run_analytics(df_sales, df_products):
    if df_products.empty:
        return pd.DataFrame(columns=[
            "SKU", "Product", "Category", "Current Stock", "Reorder Point",
            "Daily Velocity", "Stock Health", "Days Runway", "Status",
            "Suggested Order", "Vendor", "Vendor Email", "Shelf Life", "Needs Restock"
        ])

    forecast_results = []
    for _, product in df_products.iterrows():
        sku = product["sku"]
        sku_sales = df_sales[df_sales["sku"] == sku] if not df_sales.empty else pd.DataFrame()
        
        avg_demand = max(0.1, float(sku_sales["quantity_sold"].tail(14).mean())) if not sku_sales.empty else 1.0
        demand_std = float(sku_sales["quantity_sold"].std()) if len(sku_sales) > 1 else 0.5
        lead_time = int(product.get("lead_time", 2) or 2)
        safety_stock = int(1.65 * demand_std * np.sqrt(lead_time))
        reorder_point = int((avg_demand * lead_time) + safety_stock)
        
        current_stock = int(product.get("stock", 0) or 0)
        days_left = round(current_stock / avg_demand, 1) if avg_demand > 0 else 99.0
        needs_restock = current_stock <= reorder_point
        
        raw_order = max(0, (reorder_point * 2) - current_stock) if needs_restock else 0
        pack_size = int(product.get("pack_size", 1) or 1)
        rounded_order = int(np.ceil(raw_order / pack_size) * pack_size)
        moq_val = int(product.get("moq", 1) or 1)
        final_order = max(moq_val, rounded_order) if needs_restock else 0
        
        health_ratio = min(1.0, current_stock / (reorder_point * 1.5)) if reorder_point > 0 else 1.0
        
        forecast_results.append({
            "SKU": sku,
            "Product": product.get("name", sku),
            "Category": product.get("category", "General"),
            "Current Stock": current_stock,
            "Reorder Point": reorder_point,
            "Daily Velocity": round(avg_demand, 1),
            "Stock Health": health_ratio,
            "Days Runway": days_left,
            "Status": "🚨 Restock Required" if needs_restock else "🟢 Optimal",
            "Suggested Order": final_order,
            "Vendor": product.get("vendor", "Primary Vendor"),
            "Vendor Email": product.get("email", ""),
            "Shelf Life": product.get("expiry_days", 30),
            "Needs Restock": needs_restock
        })
    return pd.DataFrame(forecast_results)

# ==========================================
# 4. Sidebar Configuration
# ==========================================
# Look for Streamlit Secrets dynamically (e.g. DATABASE_URL or NEON_DB_URI)
secret_uri = ""
if "DATABASE_URL" in st.secrets:
    secret_uri = st.secrets["DATABASE_URL"]
elif "NEON_DB_URI" in st.secrets:
    secret_uri = st.secrets["NEON_DB_URI"]

with st.sidebar:
    st.markdown("### 🗄️ Database Hub")
    conn_mode = st.radio(
        "Connection Mode:",
        ["Connection URL / URI", "Host & Credentials"],
        horizontal=True
    )
    
    db_target = "PostgreSQL"
    db_params = {}

    if conn_mode == "Connection URL / URI":
        db_params["uri"] = st.text_input(
            "Database Connection URL:",
            value=secret_uri,
            placeholder="postgresql://user:password@host/neondb?sslmode=require",
            type="password",
            help="Paste full connection string from Neon, Supabase, RDS, or local database"
        )
    else:
        db_target = st.selectbox(
            "Platform Engine:",
            ["PostgreSQL", "MySQL / MariaDB", "Microsoft SQL Server"]
        )
        
        if db_target == "PostgreSQL":
            db_params["host"] = st.text_input("Host", placeholder="e.g. ep-xyz.neon.tech or localhost")
            db_params["port"] = st.text_input("Port", "5432")
            db_params["dbname"] = st.text_input("Database Name", "neondb?sslmode=require")
            db_params["user"] = st.text_input("Username", placeholder="neondb_owner")
            db_params["password"] = st.text_input("Password", type="password")
        elif db_target == "MySQL / MariaDB":
            db_params["host"] = st.text_input("Host", "localhost")
            db_params["port"] = st.text_input("Port", "3306")
            db_params["dbname"] = st.text_input("Database Name", "inventro_db")
            db_params["user"] = st.text_input("Username", "root")
            db_params["password"] = st.text_input("Password", type="password")
        elif db_target == "Microsoft SQL Server":
            db_params["host"] = st.text_input("Host", "localhost")
            db_params["port"] = st.text_input("Port", "1433")
            db_params["dbname"] = st.text_input("Database Name", "master")
            db_params["user"] = st.text_input("Username", "sa")
            db_params["password"] = st.text_input("Password", type="password")
            db_params["driver"] = st.selectbox("ODBC Driver", ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"])

    engine, conn_ok, err_msg = create_db_connection(conn_mode, db_target, db_params)
    is_connected = False
    detected_tables = []

    if conn_ok and engine:
        try:
            with engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
                inspector = inspect(engine)
                detected_tables = inspector.get_table_names()
            st.markdown(f"<div class='badge-live'><div class='pulse-dot'></div> Connected to Live Database</div>", unsafe_allow_html=True)
            is_connected = True
        except Exception as db_err:
            st.error(f"⚠️ Connection Failed: {db_err}")
    else:
        if err_msg:
            st.info(f"💡 {err_msg}")

    st.divider()
    st.markdown("### 📧 SMTP Dispatch Gateway")
    sender_email = st.text_input("Sender Email", value="")
    sender_password = st.text_input("App Password", type="password", help="16-character Google App Password")
    smtp_server = st.text_input("SMTP Server", "smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587)

# Safe Data Retrieval
df_products = pd.DataFrame()
df_sales = pd.DataFrame()
df_movements = pd.DataFrame()

if is_connected:
    try:
        with engine.connect() as conn:
            df_products = pd.read_sql(text("SELECT * FROM products_master ORDER BY sku"), conn)
            df_sales = pd.read_sql(text("SELECT * FROM sales_ledger"), conn)
            df_movements = pd.read_sql(text("SELECT * FROM stock_movements ORDER BY id DESC LIMIT 30"), conn)
    except Exception:
        df_products = pd.DataFrame()
        df_sales = pd.DataFrame()
        df_movements = pd.DataFrame()

forecast_df = run_analytics(df_sales, df_products)
low_stock_items = forecast_df[forecast_df["Needs Restock"]] if not forecast_df.empty else pd.DataFrame()
expiring_items = forecast_df[forecast_df["Shelf Life"] <= 7] if not forecast_df.empty else pd.DataFrame()

# ==========================================
# 5. Main Dashboard Header & KPI Strip
# ==========================================
header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 14px; margin-top: 4px;'>
        <h1 style='margin: 0; font-size: 2.3rem; font-weight: 800; letter-spacing: -0.04em;'>⚡ inventro.ai</h1>
        <div class='badge-live'><div class='pulse-dot'></div> AUTONOMOUS OS</div>
    </div>
    <p style='color: #94A3B8; font-size: 0.95rem; margin-top: 6px;'>
        Direct production database connector (PostgreSQL | MySQL | SQL Server), real-time POS transaction processing, and autonomous PO dispatch.
    </p>
    """, unsafe_allow_html=True)
with header_col2:
    st.write("")
    if st.button("🔄 Sync Database Feed", use_container_width=True, type="primary"):
        st.rerun()

# 4 High-Tech KPI Cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class='saas-card'>
        <div class='metric-label'>Catalog SKUs</div>
        <div class='metric-value'>{len(forecast_df)}</div>
        <div class='metric-subtext'>Synchronized items</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class='saas-card'>
        <div class='metric-label'>Critical Restock</div>
        <div class='metric-value' style='background: linear-gradient(135deg, #F87171, #EF4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>{len(low_stock_items)}</div>
        <div class='metric-subtext'>Breached ROP threshold</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class='saas-card'>
        <div class='metric-label'>Perishability Alert</div>
        <div class='metric-value' style='background: linear-gradient(135deg, #FBBF24, #F59E0B); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>{len(expiring_items)}</div>
        <div class='metric-subtext'>Shelf life ≤ 7 days</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class='saas-card'>
        <div class='metric-label'>Live POS Transactions</div>
        <div class='metric-value' style='background: linear-gradient(135deg, #34D399, #10B981); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>{len(df_sales):,}</div>
        <div class='metric-subtext'>Ledger entries captured</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 6. Navigation Tabs
# ==========================================
tab_po, tab_inout, tab_matrix, tab_db_hub = st.tabs([
    "✉️ Autonomous PO Dispatcher",
    "⚡ Barcode Terminal & Stock Flow",
    "📊 Dynamic ROP Analytics Matrix",
    "🔌 Database Infrastructure Terminal"
])

# TAB 1: Autonomous PO Dispatcher
with tab_po:
    if len(low_stock_items) == 0:
        st.markdown("""
        <div class='saas-card' style='text-align: center; padding: 40px;'>
            <h3 style='color: #34D399; margin: 0;'>🎉 Inventory Reserves Optimal</h3>
            <p style='color: #94A3B8; margin-top: 8px;'>All product stock levels remain above reorder thresholds, or catalog is empty. PO queues are clear.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        v_col1, v_col2 = st.columns([1.1, 0.9])
        with v_col1:
            st.markdown("#### 📦 Supplier Replenishment Queues")
            selected_vendor = st.selectbox("Select Pending Supplier Queue:", list(low_stock_items["Vendor"].unique()))
            vendor_data = low_stock_items[low_stock_items["Vendor"] == selected_vendor]
            
            prio_col, email_col = st.columns([1, 1])
            with prio_col:
                prio = st.selectbox("⚡ Fulfillment Tier:", ["Priority Express (24h)", "Standard Net-30 Delivery"])
            with email_col:
                target_email = st.text_input("📬 Vendor Recipient:", value=vendor_data["Vendor Email"].iloc[0] if not vendor_data.empty else "")
                
            st.markdown("**Staged Line Items:**")
            st.dataframe(
                vendor_data[["SKU", "Product", "Current Stock", "Reorder Point", "Suggested Order"]],
                use_container_width=True,
                hide_index=True
            )

        with v_col2:
            st.markdown("#### ✉️ Autonomous PO Message Payload")
            items_summary = "\n".join([
                f"  • {r['Product']} ({r['SKU']}): {r['Suggested Order']} Units | Stock in DB: {r['Current Stock']} (ROP: {r['Reorder Point']})"
                for _, r in vendor_data.iterrows()
            ])
            
            po_body = f"""Dear {selected_vendor} Logistics Team,\n\nPlease process this inventory replenishment purchase order:\n\n{items_summary}\n\nFulfillment Tier: {prio}\nDestination: Receiving Dock Bay 4\nPayment Terms: Net-30\n\nGenerated autonomously by inventro.ai Enterprise OS"""
            
            edited_body = st.text_area("Live Message Body (Editable)", value=po_body, height=210)
            
            if st.button(f"🚀 Dispatch Live Email to {selected_vendor}", type="primary", use_container_width=True):
                with st.spinner(f"Transmitting PO to {target_email} via SMTP..."):
                    success, msg = send_real_email(
                        sender_email=sender_email,
                        sender_password=sender_password,
                        receiver_email=target_email,
                        subject=f"[{prio.upper()}] PURCHASE ORDER - inventro.ai ({selected_vendor})",
                        body=edited_body,
                        smtp_server=smtp_server,
                        smtp_port=smtp_port
                    )
                    if success:
                        st.success(f"✅ Purchase Order Dispatched to `{target_email}`!")
                        trigger_cash_rain()
                    else:
                        st.error(f"❌ {msg}")

# TAB 2: Barcode Terminal & Stock Flow
with tab_inout:
    if not is_connected:
        st.warning("⚠️ Please establish an active database connection in the sidebar.")
    else:
        scan_col, manual_col = st.columns([1, 1])
        
        with scan_col:
            st.markdown("#### 📷 Instant POS Barcode Scanner")
            st.caption("Point USB barcode scanner here or type SKU and hit Enter to record real checkout scans.")
            
            barcode_input = st.text_input("Barcode Input Field", placeholder="e.g. SKU-PROD-001", label_visibility="collapsed")
            if barcode_input:
                scanned_sku = barcode_input.strip()
                with engine.connect() as conn:
                    prod_exists = conn.execute(text("SELECT name, category, stock FROM products_master WHERE sku = :sku"), {"sku": scanned_sku}).fetchone()
                    if prod_exists:
                        prod_name, prod_cat, curr_stock = prod_exists[0], prod_exists[1], prod_exists[2]
                        if curr_stock > 0:
                            conn.execute(
                                text("UPDATE products_master SET stock = stock - 1 WHERE sku = :sku"),
                                {"sku": scanned_sku}
                            )
                            conn.execute(
                                text("INSERT INTO sales_ledger (transaction_date, sku, product_name, category, quantity_sold, is_weekend) VALUES (:dt, :sku, :name, :cat, 1, 0)"),
                                {"dt": str(datetime.today().date()), "sku": scanned_sku, "name": prod_name, "cat": prod_cat}
                            )
                            conn.execute(
                                text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'POS_SCAN', 1, 'Scanned at Checkout Register')"),
                                {"ts": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "sku": scanned_sku}
                            )
                            conn.commit()
                            st.success(f"⚡ Billed 1 unit of **{prod_name}** (`{scanned_sku}`). Remaining stock: {curr_stock - 1}")
                            st.rerun()
                        else:
                            st.error(f"❌ '{prod_name}' is currently OUT OF STOCK.")
                    else:
                        st.error(f"❌ Barcode `{scanned_sku}` not found in database catalog.")

            st.markdown("---")
            st.markdown("#### 📝 Manual Inventory Adjustment")
            sku_options = (df_products["sku"] + " - " + df_products["name"]).tolist() if not df_products.empty else []
            if sku_options:
                selected_sku_text = st.selectbox("Select Target SKU:", sku_options)
                target_sku = selected_sku_text.split(" - ")[0] if selected_sku_text else ""
                
                move_type = st.radio("Movement Type:", ["STOCK_OUT (POS Sale / Checkout)", "STOCK_IN (Receiving)"], horizontal=True)
                qty = st.number_input("Units Quantity:", min_value=1, max_value=500, value=10)
                note = st.text_input("Audit Note:", value="Manual terminal adjustment")
                
                if st.button("💾 Commit Transaction to Database", type="secondary", use_container_width=True):
                    delta = qty if move_type == "STOCK_IN (Receiving)" else -qty
                    with engine.connect() as conn:
                        conn.execute(
                            text("UPDATE products_master SET stock = CASE WHEN stock + :delta < 0 THEN 0 ELSE stock + :delta END WHERE sku = :sku"),
                            {"delta": delta, "sku": target_sku}
                        )
                        conn.execute(
                            text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, :mtype, :qty, :notes)"),
                            {"ts": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "sku": target_sku, "mtype": move_type, "qty": qty, "notes": note}
                        )
                        conn.commit()
                    st.success(f"✅ Database updated for {target_sku} ({delta:+d} units).")
                    st.rerun()
            else:
                st.info("ℹ️ No items in `products_master` yet. Add products via the Database tab.")

        with manual_col:
            st.markdown("#### 📜 Live Movement Audit Log (`stock_movements`)")
            st.dataframe(
                df_movements,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "movement_timestamp": "Timestamp",
                    "sku": "SKU",
                    "movement_type": "Movement",
                    "quantity": "Qty",
                    "notes": "Reference / Notes"
                }
            )

# TAB 3: Dynamic ROP Analytics Matrix
with tab_matrix:
    st.markdown("#### 📊 Dynamic Safety Stock & Reorder Point Matrix")
    
    if forecast_df.empty:
        st.info("ℹ️ No catalog products available in the connected database.")
    else:
        cats = ["All"] + sorted(list(forecast_df["Category"].unique()))
        selected_cat = st.selectbox("Filter Department:", cats)
        filtered_df = forecast_df if selected_cat == "All" else forecast_df[forecast_df["Category"] == selected_cat]

        st.dataframe(
            filtered_df[[
                "SKU", "Product", "Category", "Current Stock", "Reorder Point", 
                "Daily Velocity", "Stock Health", "Days Runway", "Status", "Suggested Order", "Vendor"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stock Health": st.column_config.ProgressColumn(
                    "Stock Runway",
                    help="Inventory level relative to Reorder Point buffer",
                    format="%.2f",
                    min_value=0.0,
                    max_value=1.0,
                ),
                "Current Stock": st.column_config.NumberColumn("Stock", format="%d units"),
                "Reorder Point": st.column_config.NumberColumn("ROP", format="%d units"),
                "Daily Velocity": st.column_config.NumberColumn("Velocity", format="%.1f /day"),
                "Days Runway": st.column_config.NumberColumn("Days Left", format="%.1f d"),
                "Suggested Order": st.column_config.NumberColumn("PO Size", format="%d units"),
            }
        )

# TAB 4: Database Infrastructure Hub
with tab_db_hub:
    st.subheader("🔌 Database Infrastructure Management")
    if not is_connected:
        st.error("⚠️ No database connection. Please enter valid host credentials or URI in the sidebar.")
    else:
        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            st.markdown("#### 📑 Detected Tables & Schemas")
            st.write(detected_tables if len(detected_tables) > 0 else "No tables detected.")
            if st.button("🛠️ Provision Missing Schemas", type="secondary"):
                ok, msg = init_tables_safely(engine, db_target)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {msg}")

            st.markdown("---")
            st.markdown("#### ➕ Add New SKU to Master Catalog")
            with st.form("new_sku_form", clear_on_submit=True):
                f_sku = st.text_input("SKU Code*", placeholder="e.g. SKU-COFFEE-01")
                f_name = st.text_input("Product Name*", placeholder="e.g. Arabica Coffee Beans 500g")
                f_cat = st.text_input("Category", value="General")
                f_stock = st.number_input("Initial Stock Units", min_value=0, value=50)
                f_lead = st.number_input("Lead Time (Days)", min_value=1, value=3)
                f_moq = st.number_input("Vendor MOQ", min_value=1, value=20)
                f_pack = st.number_input("Pack Size", min_value=1, value=10)
                f_vendor = st.text_input("Vendor Name", placeholder="e.g. BeanCorp Global")
                f_email = st.text_input("Vendor Email", placeholder="orders@beancorp.com")
                f_exp = st.number_input("Shelf Life Days", min_value=1, value=180)
                
                if st.form_submit_button("➕ Insert SKU into Database"):
                    if f_sku and f_name:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("""
                                    INSERT INTO products_master (sku, name, category, lead_time, moq, pack_size, vendor, email, stock, expiry_days)
                                    VALUES (:sku, :name, :cat, :lead, :moq, :pack, :vendor, :email, :stock, :exp)
                                """), {
                                    "sku": f_sku.strip(), "name": f_name.strip(), "cat": f_cat.strip(),
                                    "lead": int(f_lead), "moq": int(f_moq), "pack": int(f_pack),
                                    "vendor": f_vendor.strip(), "email": f_email.strip(), "stock": int(f_stock),
                                    "exp": int(f_exp)
                                })
                                conn.commit()
                            st.success(f"✅ SKU `{f_sku}` registered in database.")
                            st.rerun()
                        except Exception as insert_err:
                            st.error(f"Insert failed: {insert_err}")
                    else:
                        st.error("SKU Code and Product Name are required.")
                    
        with col_d2:
            st.markdown("#### 🔍 Direct SQL Query Terminal")
            custom_sql = st.text_area("Execute Query on Active DB:", value="SELECT * FROM products_master LIMIT 10;")
            if st.button("⚡ Execute Query"):
                try:
                    with engine.connect() as conn:
                        query_res = pd.read_sql(text(custom_sql), conn)
                        st.dataframe(query_res, use_container_width=True)
                except Exception as e:
                    st.error(f"SQL Error: {e}")