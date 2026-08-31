import re
import math
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect

# ==========================================
# PAGE CONFIGURATION & DARK THEME
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
    .agent-console {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
    }
    .agent-stream {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #c7d2fe;
        line-height: 1.6;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DYNAMIC SCHEMA RESOLUTION ENGINE
# ==========================================
COLUMN_SYNONYMS = {
    "sku": ["sku", "product_id", "productid", "item_id", "itemid", "item_code", "itemcode", "barcode", "code", "prod_id", "id"],
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

def clean_str(s: str) -> str:
    return re.sub(r'[\s_\-]+', '', str(s)).lower()

def resolve_and_normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if df.empty:
        return df, {}
    
    normalized_df = df.copy()
    detected_mapping = {}
    cleaned_df_cols = {clean_str(c): c for c in df.columns}

    for canonical_key, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            cleaned_syn = clean_str(syn)
            if cleaned_syn in cleaned_df_cols:
                original_col = cleaned_df_cols[cleaned_syn]
                detected_mapping[canonical_key] = original_col
                normalized_df[canonical_key] = df[original_col]
                break

    defaults = {
        "sku": [f"SKU_{i+1:03d}" for i in range(len(normalized_df))],
        "name": "Item",
        "category": "Uncategorized",
        "stock": 0,
        "lead_time": 2,
        "moq": 1,
        "pack_size": 1,
        "vendor": "Unassigned",
        "email": "",
        "expiry_days": 30,
        "quantity_sold": 1
    }
    for field, default_val in defaults.items():
        if field not in normalized_df.columns:
            normalized_df[field] = default_val

    return normalized_df, detected_mapping

# ==========================================
# DATABASE CONNECTION HANDLER
# ==========================================
@st.cache_resource(show_spinner=False)
def get_db_engine(connection_string: str):
    if not connection_string or not connection_string.strip():
        return None
    try:
        clean_uri = connection_string.strip()
        clean_uri = clean_uri.replace("require?sslmode=require", "require")
        if clean_uri.count("?sslmode=require") > 1:
            clean_uri = clean_uri.split("?sslmode=require")[0] + "?sslmode=require"

        engine = create_engine(clean_uri, pool_pre_ping=True, pool_recycle=300)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.sidebar.error(f"Connection Failed: {e}")
        return None

# ==========================================
# SIDEBAR CONFIGURATION (ZERO API KEY PROMPT)
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ **inventro.ai**")
    st.caption("Autonomous Retail Operating System")
    st.divider()

    st.markdown("**1. Database Configuration**")
    connection_mode = st.radio("Mode:", ["Connection URL / URI", "Host & Credentials"], horizontal=True)

    db_uri = ""
    if connection_mode == "Connection URL / URI":
        db_uri = st.text_input(
            "Database Connection URL",
            placeholder="postgresql://user:pass@host:5432/dbname?sslmode=require",
            type="password"
        )
    else:
        db_dialect = st.selectbox("Engine", ["PostgreSQL", "MySQL", "MS SQL Server", "SQLite"])
        db_host = st.text_input("Host", placeholder="e.g. ep-xyz.aws.neon.tech")
        db_port = st.text_input("Port", placeholder="5432")
        db_name = st.text_input("Database Name", placeholder="dbname")
        db_user = st.text_input("Username", placeholder="db_user")
        db_pass = st.text_input("Password", placeholder="••••••••", type="password")

        if db_host and db_name:
            clean_dbname = db_name.split("?")[0].strip()
            if db_dialect == "PostgreSQL":
                db_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port or '5432'}/{clean_dbname}?sslmode=require"
            elif db_dialect == "MySQL":
                db_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port or '3306'}/{clean_dbname}"
            elif db_dialect == "MS SQL Server":
                db_uri = f"mssql+pyodbc://{db_user}:{db_pass}@{db_host}:{db_port or '1433'}/{clean_dbname}?driver=ODBC+Driver+17+for+SQL+Server"
            else:
                db_uri = f"sqlite:///{clean_dbname}.db"

    st.divider()
    st.markdown("**2. SMTP Vendor Dispatcher**")
    smtp_server = st.text_input("SMTP Server", placeholder="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=587)
    smtp_sender = st.text_input("Sender Email", placeholder="your-email@domain.com")
    smtp_password = st.text_input("App Password", placeholder="••••••••", type="password")

    sync_btn = st.button("🔄 Sync Database Feed", use_container_width=True)

engine = get_db_engine(db_uri) if db_uri else None
is_connected = engine is not None

if is_connected:
    st.sidebar.success("🟢 Connected to Live DB")
else:
    st.sidebar.warning("⚪ Awaiting Connection")

# ==========================================
# INGESTION & AUTO-NORMALIZATION
# ==========================================
raw_products, raw_sales, raw_movements = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

if is_connected:
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            prod_target = next((t for t in tables if "product" in t.lower() or "item" in t.lower() or "inventory" in t.lower()), None)
            if prod_target:
                raw_products = pd.read_sql(text(f"SELECT * FROM {prod_target}"), conn)
            
            sales_target = next((t for t in tables if "sale" in t.lower() or "order" in t.lower() or "txn" in t.lower()), None)
            if sales_target:
                raw_sales = pd.read_sql(text(f"SELECT * FROM {sales_target} ORDER BY 1 DESC LIMIT 2000"), conn)

            move_target = next((t for t in tables if "movement" in t.lower() or "audit" in t.lower() or "log" in t.lower()), None)
            if move_target:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {move_target} ORDER BY 1 DESC LIMIT 50"), conn)
    except Exception as e:
        st.error(f"Data Fetch Notice: {e}")

df_products, prod_map = resolve_and_normalize(raw_products)
df_sales, sales_map = resolve_and_normalize(raw_sales)

# ==========================================
# STATISTICAL LEARNING / ROP ENGINE
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
        matrix["daily_velocity"] = 1.0
        matrix["daily_volatility"] = 0.5

    matrix["daily_velocity"] = matrix["daily_velocity"].fillna(1.0).clip(lower=0.1)
    matrix["daily_volatility"] = matrix["daily_volatility"].fillna(0.5).clip(lower=0.1)
    
    # Gaussian 95% Confidence (Z = 1.65)
    Z = 1.65
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
            return max(int(row.get("moq", 1)), batch)
        return 0

    matrix["suggested_po_qty"] = matrix.apply(calc_po, axis=1)
    return matrix

analytics_df = compute_analytics(df_products, df_sales)

# ==========================================
# 100% OFFLINE LOCAL SEMANTIC AI ENGINE
# ==========================================
def local_ai_agent(user_query: str, matrix: pd.DataFrame) -> str:
    """Processes natural language questions locally using vectorized tabular reasoning."""
    if matrix.empty:
        return "No inventory data is loaded. Please connect a database to analyze."

    q = user_query.lower()
    critical = matrix[matrix["reorder_status"] == "RESTOCK NEEDED"]
    perishables = matrix[matrix["expiry_risk"] == "HIGH EXPIRY RISK"]
    overstocked = matrix[matrix["days_runway"] > 30]

    # 1. Specific Product Lookup
    for _, row in matrix.iterrows():
        name_tokens = [t for t in re.split(r'\s+', row["name"].lower()) if len(t) > 2]
        if row["sku"].lower() in q or (name_tokens and any(token in q for token in name_tokens)):
            return (
                f"**Analysis for {row['name']} (`{row['sku']}`):**\n"
                f"- **Stock Level:** {row['stock']} units on hand\n"
                f"- **Safety Stock & ROP:** Safety Cushion = {row['safety_stock']}, Reorder Trigger = {row['rop']}\n"
                f"- **Sales Velocity:** {row['daily_velocity']:.1f} units/day (Runway: **{row['days_runway']} days**)\n"
                f"- **Supplier:** {row['vendor']} (Lead time: {row['lead_time']} days, MOQ: {row['moq']})\n"
                f"- **Current Status:** {'🚨 **RESTOCK REQUIRED** (Suggested Order: +' + str(row['suggested_po_qty']) + ' units)' if row['reorder_status'] == 'RESTOCK NEEDED' else '🟢 **Stock is Healthy**'}"
            )

    # 2. Stockout & Depletion Intent
    if any(k in q for k in ["run out", "stockout", "lowest", "first", "deplete", "empty", "critical", "danger"]):
        worst = matrix.sort_values(by="days_runway").iloc[0]
        return (
            f"**`{worst['name']}`** is projected to run out first:\n"
            f"- **Current Stock:** {worst['stock']} units\n"
            f"- **Daily Consumption:** {worst['daily_velocity']:.1f} units/day\n"
            f"- **Estimated Runway:** Only **{worst['days_runway']} days remaining** before complete stockout."
        )

    # 3. Replenishment & Purchase Order Intent
    if any(k in q for k in ["order", "purchase", "buy", "restock", "po", "replenish", "supplier", "vendor"]):
        if not critical.empty:
            directives = []
            for _, r in critical.iterrows():
                directives.append(f"• **{r['vendor']}**: Order **{r['suggested_po_qty']} units** of *{r['name']}* (Current: {r['stock']} / ROP: {r['rop']})")
            return "**Active Purchase Order Directives:**\n" + "\n".join(directives)
        return "✨ All product lines are currently above their statistical reorder points. Zero purchase orders required."

    # 4. Expiration & Shelf-Life Intent
    if any(k in q for k in ["expire", "expiry", "perish", "spoil", "shelf life", "decay"]):
        if not perishables.empty:
            exp_lines = []
            for _, r in perishables.iterrows():
                exp_lines.append(f"• **{r['name']}**: **{r['expiry_days']} days left** (Stock: {r['stock']} units, Runway: {r['days_runway']} days)")
            return "**Urgent Perishability Alerts (≤ 7 Days):**\n" + "\n".join(exp_lines)
        return "✨ All items have sufficient shelf-life buffers (> 7 days remaining)."

    # 5. Overstock & Working Capital Intent
    if any(k in q for k in ["overstock", "excess", "slow", "capital", "dead stock", "too much"]):
        if not overstocked.empty:
            slowest = overstocked.sort_values(by="days_runway", ascending=False).head(3)
            slow_lines = [f"• **{r['name']}**: **{r['days_runway']} days runway** ({r['stock']} units in stock)" for _, r in slowest.iterrows()]
            return "**Highest Overstock / Capital Locked Lines:**\n" + "\n".join(slow_lines) + "\n\n*Recommendation: Pause restock orders on these lines.*"

    # 6. Top Fast Movers / Best Sellers
    if any(k in q for k in ["fast", "popular", "top", "best", "velocity", "highest sales"]):
        top_sellers = matrix.sort_values(by="daily_velocity", ascending=False).head(3)
        top_lines = [f"• **{r['name']}**: **{r['daily_velocity']:.1f} units/day** (Stock: {r['stock']})" for _, r in top_sellers.iterrows()]
        return "**Top High-Velocity Products:**\n" + "\n".join(top_lines)

    # Default Full Summary
    return (
        f"**Fleet Intelligence Overview:**\n"
        f"- **Total Catalog:** {len(matrix)} SKUs across {matrix['category'].nunique()} categories\n"
        f"- **Inventory Volume:** {int(matrix['stock'].sum()):,} units active in fleet\n"
        f"- **Depletion Warnings:** {len(critical)} lines need replenishment\n"
        f"- **Perishable Risks:** {len(perishables)} lines near expiration\n"
        f"- **Average Fleet Runway:** {round(matrix['days_runway'].mean(), 1)} days"
    )

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("inventro.ai")
st.caption("Autonomous Retail Operating System & Dynamic Reorder Engine")

tab_agent, tab_analytics, tab_pos, tab_dispatcher, tab_infra = st.tabs([
    "🤖 Autonomous AI Supply Agent",
    "📊 Catalog & Analytics Matrix",
    "⚡ POS Transaction Scanner",
    "✉️ Autonomous PO Dispatcher",
    "🔌 Database Infrastructure Terminal"
])

# ------------------------------------------
# TAB 1: AUTONOMOUS AI AGENT & CHATBOT
# ------------------------------------------
with tab_agent:
    st.markdown("#### **🤖 Autonomous AI Supply Agent & Copilot (100% Offline & Free)**")
    st.caption("Self-directed diagnostic loop analyzing stockout vectors, lead times, and decay risks in real time.")
    
    if analytics_df.empty:
        st.warning("Agent is currently idle. Connect your database or provision tables in the Infrastructure tab to begin.")
    else:
        critical_items = analytics_df[analytics_df["reorder_status"] == "RESTOCK NEEDED"]
        perishable_items = analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"]
        
        # Autonomous EDA Diagnostics
        missing_cells = raw_products.isnull().sum().sum() + raw_sales.isnull().sum().sum()
        total_cells = (raw_products.size + raw_sales.size) or 1
        completeness = round(((total_cells - missing_cells) / total_cells) * 100, 2)
        top_cat = analytics_df["category"].mode()[0] if not analytics_df.empty else "General"
        avg_lead = round(analytics_df["lead_time"].mean(), 1)
        fast_movers = analytics_df.sort_values(by="daily_velocity", ascending=False).head(3)
        fast_movers_str = ", ".join([f"{r['name']} ({r['daily_velocity']:.1f}/day)" for _, r in fast_movers.iterrows()])
        
        agent_reasoning = f"""[PHASE 1: AUTONOMOUS EXPLORATORY DATA ANALYSIS (EDA)]
• Ingestion Profile: Scanned {len(raw_products)} master catalog items & {len(raw_sales)} ledger transactions.
• Data Health: {completeness}% populated fields. Dynamic schema normalized {len(prod_map)} operational keys.
• Total Volume: {int(analytics_df['stock'].sum()):,} units active in fleet across {analytics_df['category'].nunique()} categories. Primary group: '{top_cat}'.
• Velocity Ranking: Top fast-moving items -> {fast_movers_str}.
• Supply Turnaround: Average vendor lead time is {avg_lead} days.

[PHASE 2: STOCHASTIC PROBABILISTIC MODELING]
• Service Level Objective: 95% Confidence Interval (Gaussian Normal Distribution Z = 1.65).
• Reorder Point Breaches: {len(critical_items)} of {len(analytics_df)} SKUs have breached dynamic safety thresholds.
• Spoilage Vectors: {len(perishable_items)} SKUs are within critical 7-day shelf-life horizons.

[PHASE 3: PRESCRIPTIVE AUTONOMOUS DECISIONS]
• Replenishment Action: Prescribed restock batches satisfying Minimum Order Quantities (MOQ) and Case Multipliers.
• Suppliers Queued for Dispatch: {', '.join(critical_items['vendor'].unique()) if not critical_items.empty else 'None (All lines operating safely)'}."""

        st.markdown('<div class="agent-console">', unsafe_allow_html=True)
        st.markdown("### **🧠 Autonomous Agent Execution & Diagnostic Stream**")
        st.markdown(f'<div class="agent-stream">{agent_reasoning}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # Conversational Chatbot Interface
        st.markdown("#### **💬 Ask the AI Inventory Agent**")
        st.caption("Ask anything about stockout risks, demand forecasts, expirations, or vendor purchase orders.")

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": "Hello! I am connected to your live database. Ask me anything about stockout risks, demand velocity, perishables, or supplier restock orders."}
            ]

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask about stock levels, risks, or predictions..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                ai_answer = local_ai_agent(user_prompt, analytics_df)
                st.markdown(ai_answer)
            
            st.session_state.chat_messages.append({"role": "assistant", "content": ai_answer})

# ------------------------------------------
# TAB 2: CATALOG & ANALYTICS MATRIX
# ------------------------------------------
with tab_analytics:
    if analytics_df.empty:
        st.info("No active catalog data detected.")
    else:
        st.markdown("#### **Dynamic ROP & Statistical Safety Stock Matrix**")
        display_cols = ["sku", "name", "category", "stock", "lead_time", "daily_velocity", "safety_stock", "rop", "days_runway", "reorder_status", "expiry_days", "suggested_po_qty", "vendor"]
        available_display_cols = [c for c in display_cols if c in analytics_df.columns]
        st.dataframe(analytics_df[available_display_cols], use_container_width=True, hide_index=True)

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
                                VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Live POS checkout decrement')
                                """),
                                {"ts": datetime.now(), "sku": selected_sku, "qty": -scan_qty}
                            )
                        st.toast(f"✅ Deducted {scan_qty}x {sku_data['name']} from DB.", icon="🛒")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Transaction Failed: {err}")
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
            
            target_email = vendor_orders["email"].iloc[0] if ("email" in vendor_orders.columns and str(vendor_orders["email"].iloc[0]).strip()) else ""
            recipient_email = st.text_input("Supplier Dispatch Email", value=target_email, placeholder="supplier-contact@domain.com")
            
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
                elif not recipient_email or not recipient_email.strip():
                    st.error("Please provide a valid recipient email address.")
                else:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = smtp_sender
                        msg["To"] = recipient_email.strip()
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
        st.markdown("**Clean Schema Provisioning**")
        st.caption("Creates empty production schema structures (`products_master`, `sales_ledger`, and `stock_movements`) without inserting dummy records.")
        
        if st.button("🛠️ Provision Clean Schema Tables"):
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
                            moq INT DEFAULT 1,
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
                    st.success("✅ Clean relational schemas initialized successfully.")
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