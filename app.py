import os
import re
import math
import json
import smtplib
import sqlite3
import hashlib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect

# Groq SDK for High-Speed Conversational LLM
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

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
    .auth-container {
        max-width: 480px;
        margin: 40px auto;
        padding: 30px;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SQLITE AUTHENTICATION & CREDENTIAL VAULT
# ==========================================
VAULT_DB = "users_vault.db"

def init_vault_db():
    conn = sqlite3.connect(VAULT_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            db_uri TEXT DEFAULT '',
            groq_api_key TEXT DEFAULT '',
            smtp_server TEXT DEFAULT '',
            smtp_port INTEGER DEFAULT 587,
            smtp_sender TEXT DEFAULT '',
            smtp_password TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_vault_db()

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_user_account(email: str, password: str) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(VAULT_DB)
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.strip().lower(), hash_pw(password)))
        conn.commit()
        conn.close()
        return True, "Account registered successfully!"
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, str(e)

def verify_user(email: str, password: str):
    conn = sqlite3.connect(VAULT_DB)
    c = conn.cursor()
    c.execute("""
        SELECT id, email, db_uri, groq_api_key, smtp_server, smtp_port, smtp_sender, smtp_password
        FROM users WHERE email = ? AND password_hash = ?
    """, (email.strip().lower(), hash_pw(password)))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "email": row[1],
            "db_uri": row[2] or "",
            "groq_api_key": row[3] or "",
            "smtp_server": row[4] or "",
            "smtp_port": row[5] or 587,
            "smtp_sender": row[6] or "",
            "smtp_password": row[7] or ""
        }
    return None

def save_user_credentials(user_id: int, db_uri: str, groq_key: str, smtp_srv: str, smtp_prt: int, smtp_snd: str, smtp_pwd: str):
    conn = sqlite3.connect(VAULT_DB)
    c = conn.cursor()
    c.execute("""
        UPDATE users
        SET db_uri = ?, groq_api_key = ?, smtp_server = ?, smtp_port = ?, smtp_sender = ?, smtp_password = ?
        WHERE id = ?
    """, (db_uri, groq_key, smtp_srv, smtp_prt, smtp_snd, smtp_pwd, user_id))
    conn.commit()
    conn.close()

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if not st.session_state.authenticated_user:
    st.markdown("<h2 style='text-align: center;'>⚡ inventro.ai</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8;'>Secure Retail OS & Inventory Intelligence Portal</p>", unsafe_allow_html=True)
    
    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.2, 1])
    with auth_col2:
        auth_tab_login, auth_tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
        
        with auth_tab_login:
            st.markdown("##### Access Stored Profile")
            login_email = st.text_input("Email", key="login_email")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("Log In to Workspace", type="primary", use_container_width=True):
                if login_email and login_pass:
                    user_data = verify_user(login_email, login_pass)
                    if user_data:
                        st.session_state.authenticated_user = user_data
                        st.toast(f"Welcome back, {login_email}!", icon="👋")
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
                else:
                    st.warning("Please fill in both email and password.")

        with auth_tab_signup:
            st.markdown("##### New Account Registration")
            signup_email = st.text_input("Email", key="signup_email")
            signup_pass = st.text_input("Password", type="password", key="signup_pass")
            signup_pass2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            
            if st.button("Create ID & Vault", use_container_width=True):
                if not signup_email or not signup_pass:
                    st.warning("Please provide email and password.")
                elif signup_pass != signup_pass2:
                    st.error("Passwords do not match.")
                elif len(signup_pass) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    success, msg = create_user_account(signup_email, signup_pass)
                    if success:
                        st.success("Account created! Please switch to the Sign In tab to log in.")
                    else:
                        st.error(msg)
    st.stop()

# User is authenticated
current_user = st.session_state.authenticated_user

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
# SIDEBAR CONFIGURATION (AUTO-LOADED PROFILE)
# ==========================================
with st.sidebar:
    st.markdown(f"👤 **{current_user['email']}**")
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

    st.divider()
    st.markdown("### ⚡ **inventro.ai**")
    st.caption("Autonomous Retail Operating System")
    st.divider()

    st.markdown("**1. Database Configuration**")
    db_uri_input = st.text_input(
        "PostgreSQL / Neon Connection URL",
        value=current_user["db_uri"],
        placeholder="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require",
        type="password"
    )

    st.divider()
    st.markdown("**2. AI Engine (Groq / Llama 3.3)**")
    groq_key_input = st.text_input(
        "Groq API Key",
        value=current_user["groq_api_key"],
        placeholder="gsk_...",
        type="password",
        help="Get a free key from https://console.groq.com/keys"
    )

    st.divider()
    st.markdown("**3. SMTP Vendor Dispatcher**")
    smtp_server = st.text_input("SMTP Server", value=current_user["smtp_server"], placeholder="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=int(current_user["smtp_port"] or 587))
    smtp_sender = st.text_input("Sender Email", value=current_user["smtp_sender"], placeholder="your-email@domain.com")
    smtp_password = st.text_input("App Password", value=current_user["smtp_password"], placeholder="••••••••", type="password")

    st.divider()
    if st.button("💾 Save Credentials to Profile", type="primary", use_container_width=True):
        save_user_credentials(
            current_user["id"],
            db_uri_input,
            groq_key_input,
            smtp_server,
            smtp_port,
            smtp_sender,
            smtp_password
        )
        current_user["db_uri"] = db_uri_input
        current_user["groq_api_key"] = groq_key_input
        current_user["smtp_server"] = smtp_server
        current_user["smtp_port"] = smtp_port
        current_user["smtp_sender"] = smtp_sender
        current_user["smtp_password"] = smtp_password
        st.toast("Credentials saved! They will auto-load whenever you log in.", icon="💾")

    sync_btn = st.button("🔄 Sync Database Feed", use_container_width=True)

engine = get_db_engine(db_uri_input) if db_uri_input else None
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
# INTELLIGENT AI AGENT ENGINE (GROQ / LLAMA 3.3)
# ==========================================
def intelligent_ai_agent(user_query: str, matrix: pd.DataFrame, custom_key: str) -> str:
    """Uses Groq Llama 3.3 70B to understand and reason over live inventory data."""
    active_key = custom_key.strip() if custom_key else st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

    if not active_key:
        return (
            "🔑 **Groq API Key Required:**\n\n"
            "Please paste your free Groq API key in the sidebar and click **'💾 Save Credentials to Profile'**.\n"
            "*Get a free key in 30 seconds at [console.groq.com/keys](https://console.groq.com/keys).*"
        )

    if not GROQ_AVAILABLE:
        return "⚠️ `groq` is not installed. Add `groq` to your `requirements.txt`."

    try:
        client = Groq(api_key=active_key)

        data_context = matrix[[
            "sku", "name", "category", "stock", "lead_time", 
            "daily_velocity", "safety_stock", "rop", "days_runway", 
            "reorder_status", "expiry_days", "suggested_po_qty", "vendor"
        ]].to_dict(orient="records")

        system_prompt = f"""
You are the AI Brain of inventro.ai, an autonomous retail inventory OS.
You have real-time access to the store's inventory database:

CURRENT INVENTORY DATASET:
{json.dumps(data_context, default=str)}

GUIDELINES:
1. Deeply understand user intent. Answer natural greetings, exact mathematical lookups, scenarios, or vendor logistics.
2. For stock levels, stockout risks, safety buffer math (Z=1.65), reorders, or expiry, calculate exact numbers from the dataset.
3. Be concise, direct, and actionable. Use bullet points and bold formatting for clarity.
"""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=800
        )
        return chat_completion.choices[0].message.content
    except Exception as err:
        return f"⚠️ **AI Engine Error:** {str(err)}\n\nPlease ensure your Groq key is valid at [console.groq.com](https://console.groq.com)."

# ==========================================
# MAIN INTERFACE TABS
# ==========================================
st.title("inventro.ai")
st.caption(f"Autonomous Retail OS — Logged in as `{current_user['email']}`")

tab_agent, tab_analytics, tab_pos, tab_dispatcher, tab_infra = st.tabs([
    "🤖 Autonomous AI Supply Agent",
    "📊 Catalog & Analytics Matrix",
    "⚡ Stock Movement Terminal",
    "✉️ Autonomous PO Dispatcher",
    "🔌 Database Infrastructure Terminal"
])

# ------------------------------------------
# TAB 1: AUTONOMOUS AI AGENT & CHATBOT
# ------------------------------------------
with tab_agent:
    st.markdown("#### **🤖 Autonomous AI Supply Agent & Intelligent Copilot**")
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
        st.caption("Ask questions in natural language. Powered by Groq Llama 3.3 70B.")

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": "Hello! I am connected to your live database. Ask me anything about stockout risks, demand forecasts, expirations, or vendor purchase orders."}
            ]

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask about stock levels, risks, or predictions..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing live inventory..."):
                    ai_answer = intelligent_ai_agent(user_prompt, analytics_df, groq_key_input)
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
# TAB 3: POS & INVENTORY MOVEMENT TERMINAL
# ------------------------------------------
with tab_pos:
    st.markdown("#### **⚡ Real-Time Stock Movement Terminal (In / Out / POS)**")
    st.caption("Execute incoming vendor receipts, live checkout scans, or write-offs directly to the database.")
    
    pos_col1, pos_col2 = st.columns([1.1, 1.4])
    
    with pos_col1:
        if not analytics_df.empty:
            sku_options = analytics_df["sku"].tolist()
            selected_sku = st.selectbox("Select Barcode / SKU", sku_options)
            sku_data = analytics_df[analytics_df["sku"] == selected_sku].iloc[0]
            
            action_type = st.radio(
                "Select Movement Operation:",
                ["📥 Stock IN (Receive Goods)", "⚡ POS Scan (Customer Checkout)", "📤 Stock OUT (Damage / Write-Off)"],
                horizontal=True
            )
            
            units_qty = st.number_input("Units Count", min_value=1, value=1)
            
            st.markdown(f"""
            **Item:** `{sku_data['name']}`  
            **Current Physical Stock:** `{sku_data['stock']} units`  
            **Category:** `{sku_data['category']}` | **Supplier:** `{sku_data['vendor']}`  
            **Active ROP:** `{sku_data['rop']} units`  
            """)
            
            # 1. STOCK IN
            if "Stock IN" in action_type:
                notes_in = st.text_input("Receipt Note / PO Reference", value="Vendor Delivery Intake")
                if st.button("📥 Commit Stock IN (+ Units)", type="primary", use_container_width=True):
                    if is_connected:
                        try:
                            with engine.begin() as conn:
                                stock_col = prod_map.get("stock", "stock")
                                sku_col = prod_map.get("sku", "sku")
                                conn.execute(
                                    text(f"UPDATE products_master SET {stock_col} = {stock_col} + :qty WHERE {sku_col} = :sku"),
                                    {"qty": units_qty, "sku": selected_sku}
                                )
                                conn.execute(
                                    text("""
                                    INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes)
                                    VALUES (:ts, :sku, 'STOCK_IN (Receiving)', :qty, :notes)
                                    """),
                                    {"ts": datetime.now(), "sku": selected_sku, "qty": units_qty, "notes": notes_in}
                                )
                            st.toast(f"✅ Added +{units_qty}x {sku_data['name']} to inventory.", icon="📥")
                            st.rerun()
                        except Exception as err:
                            st.error(f"Stock IN Failed: {err}")
                    else:
                        st.error("Database not connected.")

            # 2. POS CHECKOUT SCAN
            elif "POS Scan" in action_type:
                if st.button("⚡ Execute POS Transaction (- Units)", type="primary", use_container_width=True):
                    if is_connected:
                        if sku_data['stock'] < units_qty:
                            st.error(f"Insufficient stock! Available: {sku_data['stock']} units.")
                        else:
                            try:
                                with engine.begin() as conn:
                                    stock_col = prod_map.get("stock", "stock")
                                    sku_col = prod_map.get("sku", "sku")
                                    conn.execute(
                                        text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku"),
                                        {"qty": units_qty, "sku": selected_sku}
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
                                            "qty": units_qty,
                                            "wkd": 1 if datetime.now().weekday() >= 5 else 0
                                        }
                                    )
                                    conn.execute(
                                        text("""
                                        INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes)
                                        VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Live POS checkout decrement')
                                        """),
                                        {"ts": datetime.now(), "sku": selected_sku, "qty": -units_qty, "notes": "POS register sale"}
                                    )
                                st.toast(f"✅ Deducted -{units_qty}x {sku_data['name']} from DB.", icon="🛒")
                                st.rerun()
                            except Exception as err:
                                st.error(f"POS Transaction Failed: {err}")
                    else:
                        st.error("Database not connected.")

            # 3. STOCK OUT
            elif "Stock OUT" in action_type:
                out_reason = st.selectbox("Reason for Outflow", ["Damaged / Spoiled Goods", "Expired Shelf-Life", "Inventory Audit Shrinkage", "Internal Store Use"])
                if st.button("📤 Commit Stock OUT (- Units)", type="primary", use_container_width=True):
                    if is_connected:
                        if sku_data['stock'] < units_qty:
                            st.error(f"Insufficient stock to write off! Available: {sku_data['stock']} units.")
                        else:
                            try:
                                with engine.begin() as conn:
                                    stock_col = prod_map.get("stock", "stock")
                                    sku_col = prod_map.get("sku", "sku")
                                    conn.execute(
                                        text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku"),
                                        {"qty": units_qty, "sku": selected_sku}
                                    )
                                    conn.execute(
                                        text("""
                                        INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes)
                                        VALUES (:ts, :sku, 'STOCK_OUT (Write-Off)', :qty, :notes)
                                        """),
                                        {"ts": datetime.now(), "sku": selected_sku, "qty": -units_qty, "notes": out_reason}
                                    )
                                st.toast(f"✅ Written off -{units_qty}x {sku_data['name']}.", icon="📤")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Stock OUT Failed: {err}")
                    else:
                        st.error("Database not connected.")
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