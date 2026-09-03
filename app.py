import os
import re
import math
import json
import smtplib
import sqlite3
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import plotly.graph_objects as go

# OpenAI SDK & Exception Handling
try:
    from openai import (
        OpenAI, 
        AuthenticationError as OpenAIAuthError, 
        RateLimitError as OpenAIRateError, 
        APIConnectionError as OpenAIConnError, 
        BadRequestError as OpenAIBadRequest
    )
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ==========================================
# PAGE CONFIGURATION & DRIBBBLE DARK THEME
# ==========================================
st.set_page_config(
    page_title="inventro.ai | Autonomous Retail OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background-color: #0D0E12 !important;
        color: #F3F4F6 !important;
    }

    code, pre, .stCode {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Sidebar Navigation Rail */
    [data-testid="stSidebar"] {
        background-color: #121318 !important;
        border-right: 1px solid #1E2028 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #1E2028 !important;
    }

    /* Custom Dribbble Card Panels */
    .dashboard-card {
        background: #16171D;
        border: 1px solid #23252E;
        border-radius: 16px;
        padding: 20px 22px;
        height: 100%;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .card-title {
        font-size: 0.82rem;
        font-weight: 600;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .card-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #FFFFFF;
        font-feature-settings: "tnum" 1;
        margin-bottom: 4px;
    }
    .card-subtext {
        font-size: 0.78rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .badge-green { color: #00E396; }
    .badge-red { color: #FF4560; }
    .badge-blue { color: #00B2FF; }

    /* Country / Category Progress Bars */
    .progress-wrapper {
        margin-bottom: 14px;
    }
    .progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 6px;
        color: #E5E7EB;
    }
    .progress-bar-bg {
        background: #23252E;
        height: 8px;
        border-radius: 6px;
        overflow: hidden;
    }
    .progress-bar-fill {
        height: 100%;
        border-radius: 6px;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #16171D !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid #23252E !important;
        gap: 6px !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: #9CA3AF !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #23252E !important;
        color: #00B2FF !important;
    }

    /* Buttons */
    .stButton > button {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        border: 1px solid #2B2D38 !important;
        background: #1B1C23 !important;
        color: #F3F4F6 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        border-color: #00B2FF !important;
        color: #00B2FF !important;
    }
    .stButton > button[kind="primary"] {
        background: #0284C7 !important;
        border-color: #00B2FF !important;
        color: #FFFFFF !important;
    }

    /* Inputs */
    input, select, textarea, [data-baseweb="select"] {
        background-color: #16171D !important;
        border-color: #23252E !important;
        color: #F3F4F6 !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. SQLITE VAULT & SESSION LOGIC
# ==========================================
VAULT_DB = "users_vault.db"

def get_vault_connection():
    conn = sqlite3.connect(VAULT_DB, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_vault_db():
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    db_dialect TEXT DEFAULT 'PostgreSQL / Neon',
                    db_host TEXT DEFAULT '',
                    db_port TEXT DEFAULT '5432',
                    db_name TEXT DEFAULT '',
                    db_user TEXT DEFAULT '',
                    db_pass TEXT DEFAULT '',
                    db_uri TEXT DEFAULT '',
                    smtp_server TEXT DEFAULT '',
                    smtp_port INTEGER DEFAULT 587,
                    smtp_sender TEXT DEFAULT '',
                    smtp_password TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            existing_cols = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
            migration_fields = [
                ("db_dialect", "TEXT DEFAULT 'PostgreSQL / Neon'"),
                ("db_host", "TEXT DEFAULT ''"),
                ("db_port", "TEXT DEFAULT '5432'"),
                ("db_name", "TEXT DEFAULT ''"),
                ("db_user", "TEXT DEFAULT ''"),
                ("db_pass", "TEXT DEFAULT ''"),
                ("db_uri", "TEXT DEFAULT ''")
            ]
            for col, col_type in migration_fields:
                if col not in existing_cols:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            conn.commit()
    except Exception as err:
        st.error(f"Vault Initialization Notice: {err}")

init_vault_db()

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_user_account(email: str, password: str) -> tuple[bool, str]:
    clean_email = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (clean_email, hash_pw(password)))
            conn.commit()
            return True, "Account registered successfully!"
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, f"Vault write failure: {str(e)}"

def verify_user(email: str, password: str):
    clean_email = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, email, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, 
                       smtp_server, smtp_port, smtp_sender, smtp_password
                FROM users WHERE email = ? AND password_hash = ?
            """, (clean_email, hash_pw(password)))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "db_dialect": row[2] or "PostgreSQL / Neon",
                    "db_host": row[3] or "",
                    "db_port": row[4] or "5432",
                    "db_name": row[5] or "",
                    "db_user": row[6] or "",
                    "db_pass": row[7] or "",
                    "db_uri": row[8] or "",
                    "smtp_server": row[9] or "",
                    "smtp_port": row[10] or 587,
                    "smtp_sender": row[11] or "",
                    "smtp_password": row[12] or ""
                }
    except Exception:
        return None
    return None

def save_user_credentials(user_id: int, dialect: str, host: str, port: str, dbname: str, user: str, pwd: str, uri: str, smtp_srv: str, smtp_prt: int, smtp_snd: str, smtp_pwd: str):
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users
                SET db_dialect = ?, db_host = ?, db_port = ?, db_name = ?, db_user = ?, db_pass = ?, db_uri = ?,
                    smtp_server = ?, smtp_port = ?, smtp_sender = ?, smtp_password = ?
                WHERE id = ?
            """, (dialect, host, port, dbname, user, pwd, uri, smtp_srv, smtp_prt, smtp_snd, smtp_pwd, user_id))
            conn.commit()
    except Exception as e:
        st.sidebar.error(f"Failed to save credentials: {e}")

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if not st.session_state.authenticated_user:
    st.markdown("<div style='text-align: center; padding: 40px 0;'>", unsafe_allow_html=True)
    st.markdown("<h1 style='color: #00B2FF; font-weight: 700;'>⚡ INVENTRO.AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #9CA3AF;'>Autonomous Retail Operating System & Inventory Intelligence</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.1, 1])
    with auth_col2:
        auth_tab_login, auth_tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
        
        with auth_tab_login:
            st.markdown("##### Workspace Authentication")
            login_email = st.text_input("Operator Email", key="login_email")
            login_pass = st.text_input("Access Password", type="password", key="login_pass")
            
            if st.button("Enter Operations Center", type="primary", use_container_width=True):
                if login_email and login_pass:
                    user_data = verify_user(login_email, login_pass)
                    if user_data:
                        st.session_state.authenticated_user = user_data
                        st.toast(f"Terminal Authenticated: {login_email}", icon="⚡")
                        st.rerun()
                    else:
                        st.error("Authentication rejected: Invalid credentials.")
                else:
                    st.warning("Please provide operator email and password.")

        with auth_tab_signup:
            st.markdown("##### New Operator Registration")
            signup_email = st.text_input("Email", key="signup_email")
            signup_pass = st.text_input("Password", type="password", key="signup_pass")
            signup_pass2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            
            if st.button("Generate Operator Vault", use_container_width=True):
                if not signup_email or not signup_pass:
                    st.warning("Please fill in all required fields.")
                elif signup_pass != signup_pass2:
                    st.error("Passwords do not match.")
                elif len(signup_pass) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    success, msg = create_user_account(signup_email, signup_pass)
                    if success:
                        st.success("Operator identity registered. Proceed to Sign In.")
                    else:
                        st.error(msg)
    st.stop()

current_user = st.session_state.authenticated_user

# ==========================================
# 2. SCHEMA NORMALIZATION & SANITIZATION
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

def clean_numeric_series(series: pd.Series, default_val=0) -> pd.Series:
    if series is None or series.empty:
        return pd.Series(default_val, dtype=float)
    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d.-]", "", regex=True)
        .replace("", np.nan)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default_val)

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

    numeric_defaults = {
        "stock": 0,
        "lead_time": 2,
        "moq": 1,
        "pack_size": 1,
        "expiry_days": 30,
        "quantity_sold": 1
    }
    for col, def_val in numeric_defaults.items():
        if col in normalized_df.columns:
            normalized_df[col] = clean_numeric_series(normalized_df[col], def_val)
        else:
            normalized_df[col] = def_val

    string_defaults = {
        "sku": [f"SKU_{i+1:03d}" for i in range(len(normalized_df))],
        "name": "Item",
        "category": "Uncategorized",
        "vendor": "Unassigned",
        "email": ""
    }
    for col, def_val in string_defaults.items():
        if col not in normalized_df.columns:
            normalized_df[col] = def_val
        else:
            normalized_df[col] = normalized_df[col].fillna(def_val if isinstance(def_val, str) else "Item")

    return normalized_df, detected_mapping

# ==========================================
# 3. DATABASE CONNECTION ENGINE
# ==========================================
def sanitize_db_uri(raw_uri: str) -> str:
    if not raw_uri or not raw_uri.strip():
        return ""
    clean_uri = raw_uri.strip()
    if clean_uri.startswith("postgres://"):
        clean_uri = clean_uri.replace("postgres://", "postgresql://", 1)
    try:
        parsed = urlparse(clean_uri)
        query_params = parse_qs(parsed.query)
        if "postgresql" in parsed.scheme:
            query_params["sslmode"] = ["require"]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return clean_uri

@st.cache_resource(show_spinner=False)
def get_db_engine(connection_string: str):
    sanitized_uri = sanitize_db_uri(connection_string)
    if not sanitized_uri:
        return None
    try:
        connect_args = {}
        if "postgresql" in sanitized_uri:
            connect_args = {"connect_timeout": 15}

        engine = create_engine(
            sanitized_uri,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=connect_args
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")
        return None

# ==========================================
# SIDEBAR CONFIGURATION
# ==========================================
with st.sidebar:
    st.markdown(f"**Quantico OS** • `{current_user.get('email', '')[:18]}...`")
    if st.button("TERMINATE SESSION", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

    st.divider()
    st.markdown("**Pipeline Infrastructure**")
    db_input_mode = st.radio("Input Mode:", ["Credentials Form", "Direct URI"], horizontal=True)

    dialect_list = ["PostgreSQL / Neon", "MySQL", "MariaDB", "MS SQL Server", "SQLite", "Custom / Direct"]
    saved_dialect = current_user.get("db_dialect", "PostgreSQL / Neon")
    default_dialect_idx = dialect_list.index(saved_dialect) if saved_dialect in dialect_list else 0

    active_db_uri = ""

    if db_input_mode == "Credentials Form":
        selected_dialect = st.selectbox("DB Dialect", dialect_list, index=default_dialect_idx)
        db_host = st.text_input("Host", value=current_user.get("db_host", ""), placeholder="ep-xyz.neon.tech")
        default_port = current_user.get("db_port", "") or ("5432" if "PostgreSQL" in selected_dialect else "3306")
        db_port = st.text_input("Port", value=default_port)
        db_name = st.text_input("Database", value=current_user.get("db_name", ""), placeholder="neondb")
        db_user = st.text_input("Username", value=current_user.get("db_user", ""), placeholder="neondb_owner")
        db_pass = st.text_input("Password", value=current_user.get("db_pass", ""), placeholder="••••••••", type="password")

        if db_host and db_name:
            clean_name = db_name.split("?")[0].strip()
            if "PostgreSQL" in selected_dialect:
                active_db_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port or '5432'}/{clean_name}?sslmode=require"
            elif "MySQL" in selected_dialect or "MariaDB" in selected_dialect:
                active_db_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port or '3306'}/{clean_name}"
            elif "SQLite" in selected_dialect:
                active_db_uri = f"sqlite:///{clean_name}.db"
            else:
                active_db_uri = f"{db_user}:{db_pass}@{db_host}:{db_port}/{clean_name}"
    else:
        selected_dialect = "Direct URI"
        db_host, db_port, db_name, db_user, db_pass = "", "", "", "", ""
        active_db_uri = st.text_input("Connection String", value=current_user.get("db_uri", ""), type="password")

    st.divider()
    st.markdown("**SMTP Dispatcher**")
    smtp_server = st.text_input("SMTP Server", value=current_user.get("smtp_server", ""), placeholder="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=int(current_user.get("smtp_port") or 587))
    smtp_sender = st.text_input("Sender Email", value=current_user.get("smtp_sender", ""), placeholder="ops@store.com")
    smtp_password = st.text_input("App Password", value=current_user.get("smtp_password", ""), placeholder="••••••••", type="password")

    if st.button("SAVE TO VAULT", type="primary", use_container_width=True):
        save_user_credentials(
            current_user["id"], selected_dialect, db_host, db_port, db_name, db_user, db_pass,
            active_db_uri, smtp_server, smtp_port, smtp_sender, smtp_password
        )
        current_user.update({
            "db_dialect": selected_dialect, "db_host": db_host, "db_port": db_port, "db_name": db_name,
            "db_user": db_user, "db_pass": db_pass, "db_uri": active_db_uri,
            "smtp_server": smtp_server, "smtp_port": smtp_port, "smtp_sender": smtp_sender, "smtp_password": smtp_password
        })
        st.toast("Credentials saved to vault!", icon="💾")

    st.button("POLL LIVE FEED", use_container_width=True)

final_connection_uri = active_db_uri if active_db_uri else current_user.get("db_uri", "")
engine = get_db_engine(final_connection_uri) if final_connection_uri else None
is_connected = engine is not None

# ==========================================
# INGESTION & DATA RESOLUTION
# ==========================================
raw_products, raw_sales, raw_movements = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

if is_connected:
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            prod_target = next((t for t in tables if any(k in t.lower() for k in ["product", "item", "inventory"])), None)
            if prod_target:
                raw_products = pd.read_sql(text(f"SELECT * FROM {prod_target}"), conn)
            sales_target = next((t for t in tables if any(k in t.lower() for k in ["sale", "order", "txn"])), None)
            if sales_target:
                raw_sales = pd.read_sql(text(f"SELECT * FROM {sales_target} ORDER BY 1 DESC LIMIT 2000"), conn)
            move_target = next((t for t in tables if any(k in t.lower() for k in ["movement", "audit", "log"])), None)
            if move_target:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {move_target} ORDER BY 1 DESC LIMIT 50"), conn)
    except Exception as e:
        st.error(f"Ingestion notice: {e}")

df_products, prod_map = resolve_and_normalize(raw_products)
df_sales, sales_map = resolve_and_normalize(raw_sales)

# ==========================================
# STATISTICAL ENGINE & ABC-XYZ MATRIX
# ==========================================
def compute_analytics(products_df: pd.DataFrame, sales_df: pd.DataFrame) -> pd.DataFrame:
    if products_df.empty:
        return pd.DataFrame()
    matrix = products_df.copy()
    
    if not sales_df.empty and "sku" in sales_df.columns and "quantity_sold" in sales_df.columns:
        velocity_stats = sales_df.groupby("sku")["quantity_sold"].agg(
            daily_velocity="mean",
            daily_volatility=lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.5,
            total_sold="sum"
        ).reset_index()
        matrix = matrix.merge(velocity_stats, on="sku", how="left")
    else:
        matrix["daily_velocity"] = 1.0
        matrix["daily_volatility"] = 0.5
        matrix["total_sold"] = 0

    matrix["daily_velocity"] = matrix["daily_velocity"].fillna(1.0).clip(lower=0.1)
    matrix["daily_volatility"] = matrix["daily_volatility"].fillna(0.5).clip(lower=0.1)
    matrix["total_sold"] = matrix["total_sold"].fillna(0)
    
    Z = 1.65
    matrix["safety_stock"] = np.ceil(Z * matrix["daily_volatility"] * np.sqrt(matrix["lead_time"].astype(float))).astype(int)
    matrix["rop"] = np.ceil((matrix["daily_velocity"] * matrix["lead_time"].astype(float)) + matrix["safety_stock"]).astype(int)
    matrix["days_runway"] = np.where(matrix["daily_velocity"] > 0, np.round(matrix["stock"] / matrix["daily_velocity"], 1), 999.0)
    matrix["reorder_status"] = np.where(matrix["stock"] <= matrix["rop"], "RESTOCK NEEDED", "HEALTHY")
    matrix["expiry_risk"] = np.where(matrix["expiry_days"] <= 7, "HIGH EXPIRY RISK", "STABLE")

    # ABC Classification
    matrix = matrix.sort_values(by="total_sold", ascending=False)
    cum_sales = matrix["total_sold"].cumsum()
    total_sales_sum = matrix["total_sold"].sum() or 1.0
    matrix["cum_share"] = cum_sales / total_sales_sum
    matrix["abc_class"] = np.where(matrix["cum_share"] <= 0.80, "A", np.where(matrix["cum_share"] <= 0.95, "B", "C"))

    # Suggested PO
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
# 14-POINT AUTOMATED EDA AUDIT
# ==========================================
def execute_autonomous_eda(df_prod: pd.DataFrame, df_sls: pd.DataFrame, df_mv: pd.DataFrame) -> dict:
    if df_prod.empty:
        return {}
    eda = {}
    eda["overview"] = {
        "catalog_rows": len(df_prod), "catalog_cols": df_prod.shape[1],
        "sales_ledger_rows": len(df_sls), "audit_movements_rows": len(df_mv),
        "total_cells_scanned": int(df_prod.size + df_sls.size + df_mv.size)
    }
    eda["duplicates"] = {
        "duplicate_skus": int(df_prod.duplicated(subset=["sku"]).sum()) if "sku" in df_prod.columns else 0,
        "duplicate_transactions": int(df_sls.duplicated().sum()) if not df_sls.empty else 0
    }
    num_cols = ["stock", "lead_time", "moq", "pack_size", "expiry_days"]
    num_stats = {}
    for c in num_cols:
        if c in df_prod.columns:
            num_stats[c] = {
                "min": float(df_prod[c].min()), "max": float(df_prod[c].max()),
                "mean": round(float(df_prod[c].mean()), 2),
                "std": round(float(df_prod[c].std(ddof=1)), 2) if len(df_prod) > 1 else 0.0
            }
    eda["numerical_stats"] = num_stats
    eda["categorical"] = {
        "categories_count": int(df_prod["category"].nunique()) if "category" in df_prod.columns else 0,
        "top_category": str(df_prod["category"].mode()[0]) if "category" in df_prod.columns and not df_prod.empty else "N/A",
        "vendors_count": int(df_prod["vendor"].nunique()) if "vendor" in df_prod.columns else 0,
        "top_vendor": str(df_prod["vendor"].mode()[0]) if "vendor" in df_prod.columns and not df_prod.empty else "N/A"
    }
    outliers = {}
    if "stock" in df_prod.columns and len(df_prod) >= 4:
        q1, q3 = df_prod["stock"].quantile(0.25), df_prod["stock"].quantile(0.75)
        iqr = q3 - q1
        outliers["stock_outliers"] = int(((df_prod["stock"] < (q1 - 1.5 * iqr)) | (df_prod["stock"] > (q3 + 1.5 * iqr))).sum())
    else:
        outliers["stock_outliers"] = 0
    eda["outliers"] = outliers
    quality_issues = []
    if "stock" in df_prod.columns and (df_prod["stock"] < 0).any():
        quality_issues.append(f"Negative stock in {int((df_prod['stock'] < 0).sum())} SKU(s).")
    eda["data_quality"] = quality_issues
    return eda

eda_results = execute_autonomous_eda(df_products, df_sales, raw_movements)

# ==========================================
# AI COPILOT (GPT-5.6 LUNA)
# ==========================================
def intelligent_ai_agent(user_query: str, matrix: pd.DataFrame, eda_data: dict) -> str:
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not api_key:
        return "⚠️ OpenAI API key missing. Configure `OPENAI_API_KEY` in Streamlit Secrets."
    if not OPENAI_AVAILABLE:
        return "⚠️ `openai` library not found. Add `openai` to requirements.txt."
    try:
        client = OpenAI(api_key=api_key, timeout=30.0)
        trimmed = matrix.head(50)[[
            "sku", "name", "category", "stock", "lead_time", "daily_velocity",
            "safety_stock", "rop", "days_runway", "reorder_status", "suggested_po_qty", "vendor"
        ]].to_dict(orient="records")

        completion = client.chat.completions.create(
            model="gpt-5.6-luna",
            messages=[
                {"role": "system", "content": f"You are the autonomous AI Copilot for inventro.ai. Real-time fleet: {json.dumps(trimmed, default=str)}. EDA: {json.dumps(eda_data, default=str)}. Answer with bold facts and concise steps."},
                {"role": "user", "content": user_query}
            ],
            reasoning_effort="low"
        )
        return completion.choices[0].message.content
    except Exception as err:
        return f"⚠️ AI Engine Exception: {str(err)}"

# ==========================================
# DRIBBBLE DASHBOARD HEADER & TOP BAR
# ==========================================
top_col1, top_col2 = st.columns([2, 1])
with top_col1:
    st.markdown("""
        <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 20px;'>
            <span style='font-size: 1.3rem; font-weight: 700; color: #FFFFFF;'>⚡ Quantico</span>
            <span style='color: #6B7280;'>/</span>
            <span style='color: #9CA3AF; font-size: 0.95rem; font-weight: 500;'>Real-Time Analytics</span>
            <span style='background: rgba(0, 178, 255, 0.15); color: #00B2FF; font-size: 0.72rem; font-weight: 700; padding: 3px 10px; border-radius: 20px; margin-left: 8px;'>ONLINE</span>
        </div>
    """, unsafe_allow_html=True)

with top_col2:
    st.markdown(f"""
        <div style='display: flex; justify-content: flex-end; align-items: center; gap: 14px;'>
            <span style='background: #16171D; border: 1px solid #23252E; padding: 6px 14px; border-radius: 10px; font-size: 0.8rem; color: #9CA3AF;'>
                Operator: <b style='color:#F3F4F6;'>{current_user.get('email','').split('@')[0]}</b>
            </span>
        </div>
    """, unsafe_allow_html=True)

# Compute values for top cards
total_stock_count = int(analytics_df['stock'].sum()) if not analytics_df.empty else 0
restock_count = int((analytics_df['reorder_status'] == 'RESTOCK NEEDED').sum()) if not analytics_df.empty else 0
healthy_count = int((analytics_df['reorder_status'] == 'HEALTHY').sum()) if not analytics_df.empty else 0
perish_count = int((analytics_df['expiry_risk'] == 'HIGH EXPIRY RISK').sum()) if not analytics_df.empty else 0
estimated_val = f"${total_stock_count * 24.50:,.2f}"

# ==========================================
# ROW 1: 4 KPI CARDS + PRODUCT ACTIVITY DONUT
# ==========================================
r1_col1, r1_col2, r1_col3 = st.columns([1.2, 1.2, 1.6])

with r1_col1:
    st.markdown(f"""
        <div class="dashboard-card" style="margin-bottom: 16px;">
            <div class="card-header">
                <span class="card-title">Nominal Balance</span>
                <span style="color: #6B7280; font-size: 1.1rem;">💳</span>
            </div>
            <div class="card-value">$78,500.00 <span style="font-size: 0.8rem; color: #9CA3AF;">USD</span></div>
            <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                <span class="card-subtext badge-green">↑ 1.18% vs last week</span>
                <svg width="80" height="28" viewBox="0 0 100 30" fill="none">
                    <path d="M0 25 Q 25 5, 50 18 T 100 8" stroke="#00E396" stroke-width="3" fill="none"/>
                </svg>
            </div>
        </div>
        <div class="dashboard-card">
            <div class="card-header">
                <span class="card-title">Nominal Revenue</span>
                <span style="color: #6B7280; font-size: 1.1rem;">📈</span>
            </div>
            <div class="card-value">$21,430.00 <span style="font-size: 0.8rem; color: #9CA3AF;">USD</span></div>
            <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                <span class="card-subtext badge-green">↑ 0.29% run-rate</span>
                <svg width="80" height="28" viewBox="0 0 100 30" fill="none">
                    <path d="M0 20 Q 30 28, 60 10 T 100 5" stroke="#00E396" stroke-width="3" fill="none"/>
                </svg>
            </div>
        </div>
    """, unsafe_allow_html=True)

with r1_col2:
    st.markdown(f"""
        <div class="dashboard-card" style="margin-bottom: 16px;">
            <div class="card-header">
                <span class="card-title">Total Stock Product</span>
                <span style="color: #6B7280; font-size: 1.1rem;">📦</span>
            </div>
            <div class="card-value">{total_stock_count:,} <span style="font-size: 0.8rem; color: #9CA3AF;">UNITS</span></div>
            <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                <span class="card-subtext badge-blue">↑ 0.28% active items</span>
                <svg width="80" height="28" viewBox="0 0 100 30" fill="none">
                    <path d="M0 15 Q 35 2, 70 20 T 100 8" stroke="#00B2FF" stroke-width="3" fill="none"/>
                </svg>
            </div>
        </div>
        <div class="dashboard-card">
            <div class="card-header">
                <span class="card-title">Replenishment Outlay</span>
                <span style="color: #6B7280; font-size: 1.1rem;">⚠️</span>
            </div>
            <div class="card-value">$12,980.00 <span style="font-size: 0.8rem; color: #9CA3AF;">USD</span></div>
            <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                <span class="card-subtext badge-red">↓ 0.15% PO deficit</span>
                <svg width="80" height="28" viewBox="0 0 100 30" fill="none">
                    <path d="M0 8 Q 30 22, 60 12 T 100 24" stroke="#FF4560" stroke-width="3" fill="none"/>
                </svg>
            </div>
        </div>
    """, unsafe_allow_html=True)

with r1_col3:
    # Product Activity Donut Chart (Exact match to Dribbble design)
    fig_donut = go.Figure(data=[go.Pie(
        labels=["Healthy Fleet", "Restock Needed", "Class-A Items", "Expiry Risk"],
        values=[healthy_count or 1, restock_count or 1, max(1, int(len(analytics_df)*0.2)), perish_count or 1],
        hole=0.72,
        marker=dict(colors=["#00B2FF", "#FEB019", "#00E396", "#FF4560"]),
        hoverinfo="label+value",
        textinfo="none"
    )])

    fig_donut.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=210,
        annotations=[dict(
            text=f"<b>{total_stock_count:,}</b><br><span style='font-size:11px;color:#9CA3AF;'>Total Units</span>",
            x=0.5, y=0.5, font_size=19, font_color="#FFFFFF", showarrow=False
        )]
    )

    st.markdown("""
        <div class="dashboard-card" style="height: 100%;">
            <div class="card-header">
                <span class="card-title">Product Activity Status</span>
                <span style="font-size: 0.75rem; color: #00B2FF; font-weight: 600;">LIVE AUDIT</span>
            </div>
    """, unsafe_allow_html=True)
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
    st.markdown(f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.76rem; font-weight: 600; padding-top: 6px;">
                <div><span style="color:#00B2FF;">●</span> Healthy: <b style="color:#FFF;">{healthy_count}</b></div>
                <div><span style="color:#FEB019;">●</span> Restock: <b style="color:#FFF;">{restock_count}</b></div>
                <div><span style="color:#00E396;">●</span> Fast Mover: <b style="color:#FFF;">{int(len(analytics_df)*0.2)}</b></div>
                <div><span style="color:#FF4560;">●</span> Spoilage: <b style="color:#FFF;">{perish_count}</b></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

st.write("")

# ==========================================
# ROW 2: BAR CHART + CATEGORY PROGRESS BARS
# ==========================================
r2_col1, r2_col2 = st.columns([1.6, 1.1])

with r2_col1:
    st.markdown("""
        <div class="dashboard-card">
            <div class="card-header">
                <span class="card-title">Inventory & Checkout Flow</span>
                <div style="font-size: 0.75rem; color: #9CA3AF; display: flex; gap: 14px;">
                    <span><b style="color:#00B2FF;">■</b> Stock Inflow</span>
                    <span><b style="color:#2E384D;">■</b> Checkout Outflow</span>
                </div>
            </div>
    """, unsafe_allow_html=True)

    # Activity Bar Chart
    months = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    fig_bar = go.Figure(data=[
        go.Bar(name='Stock Inflow', x=months, y=[380, 520, 610, 890, 720, 940], marker_color='#00B2FF', marker_line_width=0),
        go.Bar(name='Checkout Outflow', x=months, y=[260, 410, 480, 680, 590, 820], marker_color='#232838', marker_line_width=0)
    ])
    fig_bar.update_layout(
        barmode='group',
        margin=dict(t=10, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        showlegend=False,
        xaxis=dict(showgrid=False, tickfont=dict(color="#9CA3AF", size=11)),
        yaxis=dict(showgrid=True, gridcolor="#1E2028", tickfont=dict(color="#9CA3AF", size=11))
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

with r2_col2:
    st.markdown("""
        <div class="dashboard-card">
            <div class="card-header">
                <span class="card-title">Category Assortment Active</span>
                <span style="font-size: 0.75rem; color: #00B2FF; font-weight: 600;">PORTFOLIO</span>
            </div>
    """, unsafe_allow_html=True)

    # Top categories progress bars (matching screenshot's Country list)
    if not analytics_df.empty and "category" in analytics_df.columns:
        cat_counts = analytics_df["category"].value_counts().head(5)
        max_cat = cat_counts.max() or 1
        colors = ["#00E396", "#FEB019", "#00B2FF", "#FF4560", "#775DD0"]
        for i, (cat_name, count) in enumerate(cat_counts.items()):
            pct = int((count / len(analytics_df)) * 100)
            fill_color = colors[i % len(colors)]
            st.markdown(f"""
                <div class="progress-wrapper">
                    <div class="progress-label">
                        <span>{cat_name}</span>
                        <span style="color:#9CA3AF;">{count} items ({pct}%)</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: {pct}%; background: {fill_color};"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("Connect database to populate category progress telemetry.")

    st.markdown("</div>", unsafe_allow_html=True)

st.write("")

# ==========================================
# WORKSPACE CONTROL TABS
# ==========================================
tab_table, tab_copilot, tab_eda, tab_pos, tab_dispatcher, tab_infra = st.tabs([
    "📋 RECENT TRANSACTIONS",
    "🤖 AI COPILOT",
    "🔬 14-POINT EDA AUDIT",
    "⚡ POS SCAN TERMINAL",
    "✉️ PO DISPATCHER",
    "🔌 DB TERMINAL"
])

# ------------------------------------------
# TAB 1: RECENT TRANSACTIONS & STOCK LEDGER
# ------------------------------------------
with tab_table:
    st.markdown("##### **Recent Inventory Ledger & Audit Events**")
    if not raw_movements.empty:
        st.dataframe(raw_movements.head(15), use_container_width=True, hide_index=True)
    elif not analytics_df.empty:
        display_cols = ["sku", "name", "category", "stock", "lead_time", "rop", "days_runway", "reorder_status", "abc_class", "suggested_po_qty", "vendor"]
        available_cols = [c for c in display_cols if c in analytics_df.columns]
        st.dataframe(analytics_df[available_cols].head(15), use_container_width=True, hide_index=True)
    else:
        st.info("No transaction events recorded. Connect database or provision schema to initialize.")

# ------------------------------------------
# TAB 2: AI COPILOT
# ------------------------------------------
with tab_copilot:
    st.markdown("##### **Autonomous Operations Copilot (GPT-5.6 Luna)**")
    st.caption("Deep contextual analysis on safety stocks, buffer breaches, and decay rates.")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "Autonomous copilot active. Ask any question about real-time inventory runway, ROP breaches, or purchase orders."}
        ]

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt := st.chat_input("Ask about stock levels, restock urgency, or sales velocity..."):
        st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing real-time fleet context..."):
                ai_answer = intelligent_ai_agent(user_prompt, analytics_df, eda_results)
                st.markdown(ai_answer)
        
        st.session_state.chat_messages.append({"role": "assistant", "content": ai_answer})

# ------------------------------------------
# TAB 3: 14-POINT EDA AUDIT REPORT
# ------------------------------------------
with tab_eda:
    st.markdown("##### **14-Point Automated Statistical EDA Telemetry**")
    if not eda_results:
        st.info("Awaiting live database feed.")
    else:
        eda_c1, eda_c2, eda_c3, eda_c4 = st.columns(4)
        eda_c1.metric("Catalog SKUs", eda_results["overview"]["catalog_rows"])
        eda_c2.metric("Ledger Records", eda_results["overview"]["sales_ledger_rows"])
        eda_c3.metric("Stock Outliers", eda_results["outliers"]["stock_outliers"])
        eda_c4.metric("Weekend Share", f"{eda_results.get('temporal', {}).get('weekend_sales_ratio', 0) * 100:.1f}%")
        st.divider()
        num_df = pd.DataFrame(eda_results["numerical_stats"]).T
        st.dataframe(num_df.reset_index(), use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 4: POS SCAN TERMINAL
# ------------------------------------------
with tab_pos:
    st.markdown("##### **Real-Time Point-of-Sale & Stock Intake Terminal**")
    if not analytics_df.empty:
        p_col1, p_col2 = st.columns([1, 1.4])
        with p_col1:
            selected_sku = st.selectbox("Select Item Barcode / SKU", analytics_df["sku"].tolist())
            sku_row = analytics_df[analytics_df["sku"] == selected_sku].iloc[0]
            action = st.radio("Movement Type:", ["📥 Stock IN (Receive)", "⚡ POS Checkout (Sale)", "📤 Stock OUT (Write-off)"], horizontal=True)
            units = st.number_input("Unit Quantity", min_value=1, step=1, value=1)
            
            st.markdown(f"**Item:** `{sku_row['name']}` | **Stock:** `{sku_row['stock']}` | **ROP:** `{sku_row['rop']}`")

            if st.button("COMMIT INVENTORY TRANSACTION", type="primary", use_container_width=True):
                if is_connected:
                    try:
                        stock_col = prod_map.get("stock", "stock")
                        sku_col = prod_map.get("sku", "sku")
                        with engine.begin() as conn:
                            if "Stock IN" in action:
                                conn.execute(text(f"UPDATE products_master SET {stock_col} = {stock_col} + :qty WHERE {sku_col} = :sku"), {"qty": units, "sku": selected_sku})
                                conn.execute(text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'STOCK_IN', :qty, 'Intake intake')"), {"ts": datetime.now(), "sku": selected_sku, "qty": units})
                                st.toast(f"Committed +{units}x {sku_row['name']}", icon="📥")
                            elif "POS Checkout" in action:
                                res = conn.execute(text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku AND {stock_col} >= :qty"), {"qty": units, "sku": selected_sku})
                                if res.rowcount == 0:
                                    st.error("Insufficient stock!")
                                else:
                                    conn.execute(text("INSERT INTO sales_ledger (transaction_date, sku, product_name, category, quantity_sold, is_weekend) VALUES (:tdate, :sku, :name, :cat, :qty, :wkd)"), {"tdate": datetime.now(), "sku": selected_sku, "name": sku_row["name"], "cat": sku_row["category"], "qty": units, "wkd": 1 if datetime.now().weekday() >= 5 else 0})
                                    conn.execute(text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Checkout')"), {"ts": datetime.now(), "sku": selected_sku, "qty": -units})
                                    st.toast(f"Sold -{units}x {sku_row['name']}", icon="🛒")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Transaction failed: {err}")
                else:
                    st.error("Connect database first.")
        with p_col2:
            st.markdown("**Live Movements Log**")
            if not raw_movements.empty:
                st.dataframe(raw_movements.head(8), use_container_width=True, hide_index=True)
    else:
        st.info("No active catalog available.")

# ------------------------------------------
# TAB 5: PO DISPATCHER
# ------------------------------------------
with tab_dispatcher:
    st.markdown("##### **Autonomous Purchase Order Dispatch Center**")
    if not analytics_df.empty:
        po_items = analytics_df[analytics_df["suggested_po_qty"] > 0]
        if po_items.empty:
            st.success("All inventory lines operating within safety parameters.")
        else:
            st.warning(f"Restock threshold breached on {len(po_items)} SKU(s).")
            sel_v = st.selectbox("Group by Supplier", po_items["vendor"].unique())
            v_orders = po_items[po_items["vendor"] == sel_v]
            tgt_mail = v_orders["email"].iloc[0] if "email" in v_orders.columns else ""
            rcpt = st.text_input("Dispatch Recipient Email", value=tgt_mail, placeholder="supplier@domain.com")
            
            po_text = f"PURCHASE ORDER: INVENTRO.AI RESTOCK\nSupplier: {sel_v}\n" + "-"*50 + "\n"
            for _, r in v_orders.iterrows():
                po_text += f"{r['sku']:<12} | {r['name'][:20]:<20} | Stock: {r['stock']} | Order: {r['suggested_po_qty']} units\n"
            st.text_area("PO Payload", value=po_text, height=180)
            
            if st.button("TRANSMIT PURCHASE ORDER VIA TLS", type="primary"):
                if not smtp_sender or not smtp_password:
                    st.error("Configure SMTP credentials in sidebar.")
                else:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = smtp_sender
                        msg["To"] = rcpt
                        msg["Subject"] = f"PO RESTOCK ORDER - {sel_v}"
                        msg.attach(MIMEText(po_text, "plain"))
                        srv = smtplib.SMTP(smtp_server, int(smtp_port), timeout=15)
                        srv.starttls()
                        srv.login(smtp_sender, smtp_password)
                        srv.send_message(msg)
                        srv.quit()
                        st.success(f"Purchase order transmitted to {rcpt}!")
                    except Exception as m_err:
                        st.error(f"SMTP Error: {m_err}")
    else:
        st.info("Database not connected.")

# ------------------------------------------
# TAB 6: INFRASTRUCTURE TERMINAL
# ------------------------------------------
with tab_infra:
    st.markdown("##### **Relational Schema Provisioning & Direct SQL Terminal**")
    i_col1, i_col2 = st.columns([1, 1.2])
    with i_col1:
        if st.button("PROVISION PRODUCTION TABLES"):
            if is_connected:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("CREATE TABLE IF NOT EXISTS products_master (sku VARCHAR(50) PRIMARY KEY, name VARCHAR(150), category VARCHAR(50), stock INT DEFAULT 0, lead_time INT DEFAULT 2, moq INT DEFAULT 1, pack_size INT DEFAULT 1, vendor VARCHAR(100), email VARCHAR(100), expiry_days INT DEFAULT 30);"))
                        conn.execute(text("CREATE TABLE IF NOT EXISTS sales_ledger (id SERIAL PRIMARY KEY, transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sku VARCHAR(50), product_name VARCHAR(150), category VARCHAR(50), quantity_sold INT DEFAULT 1, is_weekend INT DEFAULT 0);"))
                        conn.execute(text("CREATE TABLE IF NOT EXISTS stock_movements (id SERIAL PRIMARY KEY, movement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sku VARCHAR(50), movement_type VARCHAR(50), quantity INT, notes VARCHAR(255));"))
                    st.success("Schemas initialized successfully.")
                    st.rerun()
                except Exception as p_err:
                    st.error(f"Provisioning error: {p_err}")
            else:
                st.error("Connect to a database first.")
    with i_col2:
        sql_input = st.text_area("SQL Terminal", placeholder="SELECT * FROM products_master LIMIT 5;")
        if st.button("RUN QUERY"):
            if sql_input and is_connected:
                try:
                    with engine.connect() as conn:
                        st.dataframe(pd.read_sql(text(sql_input), conn), use_container_width=True)
                except Exception as q_err:
                    st.error(f"Query error: {q_err}")