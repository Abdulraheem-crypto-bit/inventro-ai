import os
import re
import math
import json
import random
import secrets
import smtplib
import sqlite3
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from email.utils import make_msgid, formatdate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ==========================================
# PAGE CONFIGURATION & ECLAIRA OBSIDIAN THEME
# ==========================================
st.set_page_config(
    page_title="inventro.ai | Supply Chain OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background-color: #0D0F12 !important;
    color: #E6EDF3 !important;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

[data-testid="stSidebar"] {
    background-color: #090B0E !important;
    border-right: 1px solid #181C24 !important;
    padding-top: 1rem !important;
}
[data-testid="stSidebar"] hr {
    border-color: #181C24 !important;
}

/* ECLAIRA OBSIDIAN CARDS */
.eclaira-card {
    background: #13161C;
    border: 1px solid #1C222C;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 14px;
    position: relative;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.eclaira-card:hover {
    border-color: #293241;
}

.eclaira-kpi-card {
    background: #13161C;
    border: 1px solid #1C222C;
    border-radius: 12px;
    padding: 16px 18px;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.eclaira-kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6C7A8E;
    margin-bottom: 6px;
}
.eclaira-kpi-value {
    font-size: 1.55rem;
    font-weight: 800;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.eclaira-kpi-sub {
    font-size: 0.72rem;
    color: #5C6777;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* PILLS & BADGES */
.badge-up {
    color: #10B981;
    font-weight: 700;
    font-size: 0.72rem;
    display: inline-flex;
    align-items: center;
}
.badge-down {
    color: #EF4444;
    font-weight: 700;
    font-size: 0.72rem;
    display: inline-flex;
    align-items: center;
}
.badge-orange {
    background: rgba(255, 107, 0, 0.15);
    color: #FF8A3D;
    border: 1px solid rgba(255, 107, 0, 0.35);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
}

/* SECTION HEADERS */
.eclaira-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    margin: 0;
}
.eclaira-subtitle {
    font-size: 0.82rem;
    color: #6C7A8E;
    margin-top: 2px;
    margin-bottom: 18px;
}

/* SEGMENT BARS */
.segment-bar-container {
    width: 100%;
    height: 14px;
    background: #1C222C;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    margin: 14px 0 16px 0;
}
.seg-fill-1 { background: #FF6B00; height: 100%; }
.seg-fill-2 { background: #FFA048; height: 100%; }
.seg-fill-3 { background: #475569; height: 100%; }

.seg-legend-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.76rem;
    padding: 6px 0;
    border-bottom: 1px solid #181D26;
}

/* BUTTON OVERRIDES */
.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: 1px solid #202633 !important;
    background: #14171E !important;
    color: #C2CDDB !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    border-color: #FF6B00 !important;
    color: #FF8A3D !important;
}
.stButton > button[kind="primary"] {
    background: #FF6B00 !important;
    border-color: #FF7D1A !important;
    color: #FFFFFF !important;
    box-shadow: 0 0 16px rgba(255, 107, 0, 0.25) !important;
}

input, select, textarea, [data-baseweb="select"] {
    background-color: #12151B !important;
    border-color: #1E2430 !important;
    color: #E6EDF3 !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #1C222C !important;
    border-radius: 10px !important;
    background: #13161C !important;
}

/* OPENING KEYFRAME ANIMATIONS */
@keyframes entrance {
    0% { opacity: 0; transform: translateY(18px); }
    100% { opacity: 1; transform: translateY(0); }
}
.auth-anim {
    animation: entrance 0.75s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# CURRENCY LOCALIZATION
# ==========================================
CURRENCY_PROFILES = {
    "USD": {"symbol": "$", "code": "USD", "label": "United States (USD - $)", "rate_multiplier": 1.0},
    "INR": {"symbol": "₹", "code": "INR", "label": "India (INR - ₹)", "rate_multiplier": 83.5},
    "AED": {"symbol": "AED ", "code": "AED", "label": "UAE (AED - د.إ)", "rate_multiplier": 3.67},
    "EUR": {"symbol": "€", "code": "EUR", "label": "Europe (EUR - €)", "rate_multiplier": 0.92},
    "GBP": {"symbol": "£", "code": "GBP", "label": "UK (GBP - £)", "rate_multiplier": 0.78}
}

# ==========================================
# SQLITE VAULT (WAL CONCURRENCY)
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
                    currency_code TEXT DEFAULT 'USD',
                    currency_symbol TEXT DEFAULT '$',
                    smtp_server TEXT DEFAULT '',
                    smtp_port INTEGER DEFAULT 587,
                    smtp_sender TEXT DEFAULT '',
                    smtp_password TEXT DEFAULT '',
                    reset_token TEXT DEFAULT '',
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
                ("db_uri", "TEXT DEFAULT ''"),
                ("currency_code", "TEXT DEFAULT 'USD'"),
                ("currency_symbol", "TEXT DEFAULT '$'"),
                ("smtp_server", "TEXT DEFAULT ''"),
                ("smtp_port", "INTEGER DEFAULT 587"),
                ("smtp_sender", "TEXT DEFAULT ''"),
                ("smtp_password", "TEXT DEFAULT ''"),
                ("reset_token", "TEXT DEFAULT ''")
            ]
            for col, col_type in migration_fields:
                if col not in existing_cols:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            conn.commit()
    except Exception as err:
        st.error(f"Vault Init Notice: {err}")

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
            return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, f"Error: {e}"

def verify_user(email: str, password: str):
    clean_email = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, email, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, 
                       currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password
                FROM users WHERE email = ? AND password_hash = ?
            """, (clean_email, hash_pw(password)))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0], "email": row[1], "db_dialect": row[2] or "PostgreSQL / Neon",
                    "db_host": row[3] or "", "db_port": row[4] or "5432", "db_name": row[5] or "",
                    "db_user": row[6] or "", "db_pass": row[7] or "", "db_uri": row[8] or "",
                    "currency_code": row[9] or "USD", "currency_symbol": row[10] or "$",
                    "smtp_server": row[11] or "", "smtp_port": row[12] or 587,
                    "smtp_sender": row[13] or "", "smtp_password": row[14] or ""
                }
    except Exception:
        return None
    return None

def fetch_user_by_email(email: str):
    clean_email = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, email, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password FROM users WHERE email = ?", (clean_email,))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0], "email": row[1], "db_dialect": row[2] or "PostgreSQL / Neon",
                    "db_host": row[3] or "", "db_port": row[4] or "5432", "db_name": row[5] or "",
                    "db_user": row[6] or "", "db_pass": row[7] or "", "db_uri": row[8] or "",
                    "currency_code": row[9] or "USD", "currency_symbol": row[10] or "$",
                    "smtp_server": row[11] or "", "smtp_port": row[12] or 587,
                    "smtp_sender": row[13] or "", "smtp_password": row[14] or ""
                }
    except Exception:
        return None
    return None

def dispatch_platform_email(recipient: str, subject: str, body_text: str) -> tuple[bool, str]:
    smtp_srv = st.secrets.get("SYSTEM_SMTP_SERVER", os.environ.get("SYSTEM_SMTP_SERVER", ""))
    smtp_prt = st.secrets.get("SYSTEM_SMTP_PORT", os.environ.get("SYSTEM_SMTP_PORT", 587))
    smtp_snd = st.secrets.get("SYSTEM_SMTP_SENDER", os.environ.get("SYSTEM_SMTP_SENDER", ""))
    smtp_pwd = st.secrets.get("SYSTEM_SMTP_PASSWORD", os.environ.get("SYSTEM_SMTP_PASSWORD", ""))

    if not (smtp_srv and smtp_snd and smtp_pwd):
        return False, "System Email Service Not Configured in Secrets."

    try:
        clean_recipient = recipient.strip()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"inventro.ai Operations <{smtp_snd}>"
        msg["To"] = clean_recipient
        msg["Reply-To"] = smtp_snd
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="inventro.ai")

        html_body = f"""\
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background-color: #0D0F12; margin: 0; padding: 24px; color: #E6EDF3;">
          <div style="max-width: 520px; background-color: #13161C; border: 1px solid #1C222C; border-radius: 14px; padding: 28px; margin: 0 auto;">
            <div style="font-size: 20px; font-weight: 800; color: #FF6B00; margin-bottom: 16px;">⚡ INVENTRO.AI</div>
            <div style="font-size: 14px; line-height: 1.6; color: #CBD5E1; white-space: pre-line;">{body_text}</div>
          </div>
        </body>
        </html>"""
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(smtp_srv, int(smtp_prt), timeout=15)
        server.starttls()
        server.login(smtp_snd, smtp_pwd)
        server.send_message(msg)
        server.quit()
        return True, f"Sent to {clean_recipient}."
    except Exception as e:
        return False, str(e)

def set_user_otp(email: str) -> tuple[bool, str]:
    clean_email = email.strip().lower()
    otp_code = f"{random.randint(100000, 999999)}"
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (otp_code, clean_email))
            conn.commit()
            return (True, otp_code) if c.rowcount > 0 else (False, "Account not found.")
    except Exception as e:
        return False, str(e)

def generate_reset_token(email: str) -> tuple[bool, str]:
    clean_email = email.strip().lower()
    token = secrets.token_urlsafe(24)
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (token, clean_email))
            conn.commit()
            return (True, token) if c.rowcount > 0 else (False, "Account not found.")
    except Exception as e:
        return False, str(e)

def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE reset_token = ? AND reset_token != ''", (token.strip(),))
            row = c.fetchone()
            if not row:
                return False, "Invalid or expired token."
            c.execute("UPDATE users SET password_hash = ?, reset_token = '' WHERE email = ?", (hash_pw(new_password), row[0]))
            conn.commit()
            return True, f"Password reset successful. Log in now."
    except Exception as e:
        return False, str(e)

def save_user_credentials(user_id: int, dialect: str, host: str, port: str, dbname: str, user: str, pwd: str, uri: str, curr_code: str, curr_sym: str):
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users SET db_dialect = ?, db_host = ?, db_port = ?, db_name = ?, db_user = ?, db_pass = ?, db_uri = ?,
                    currency_code = ?, currency_symbol = ? WHERE id = ?
            """, (dialect, host, port, dbname, user, pwd, uri, curr_code, curr_sym, user_id))
            conn.commit()
    except Exception as e:
        st.error(f"Save error: {e}")

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

query_params = st.query_params
active_reset_token = query_params.get("reset_token", None)

if not st.session_state.authenticated_user:
    st.markdown("""
        <div class='auth-anim' style='text-align: center; padding: 50px 0 20px 0;'>
            <div style='display: inline-flex; align-items: center; gap: 8px; margin-bottom: 8px;'>
                <span style='background: #FF6B00; border-radius: 8px; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; color: #FFF;'>⚡</span>
                <span style='font-size: 1.6rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;'>inventro.ai</span>
            </div>
            <p style='color: #6C7A8E; font-size: 0.95rem; margin: 0;'>Supply Chain & Retail Operations Operating System</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.25, 1])
    with c2:
        st.markdown("<div class='eclaira-card auth-anim'>", unsafe_allow_html=True)
        if active_reset_token:
            st.markdown("##### 🔐 Set New Password")
            new_pw = st.text_input("New Password", type="password", key="npw")
            conf_pw = st.text_input("Confirm New Password", type="password", key="cpw")
            if st.button("UPDATE PASSWORD", type="primary", use_container_width=True):
                if new_pw == conf_pw and len(new_pw) >= 6:
                    ok, msg = reset_password_with_token(active_reset_token, new_pw)
                    if ok:
                        st.success(msg)
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Check inputs (min 6 chars, match).")
        else:
            tab_in, tab_up = st.tabs(["🔐 Sign In", "📝 Register"])
            with tab_in:
                login_email = st.text_input("Operator Email", key="log_em")
                login_pass = st.text_input("Password", type="password", key="log_pw")
                if st.button("AUTHENTICATE TO CONSOLE", type="primary", use_container_width=True):
                    usr = verify_user(login_email, login_pass)
                    if usr:
                        st.session_state.authenticated_user = usr
                        st.toast(f"Authenticated: {login_email}", icon="⚡")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

                with st.expander("Forgot password?"):
                    rec_mail = st.text_input("Registered Email", key="rec_m")
                    if rec_mail:
                        u_chk = fetch_user_by_email(rec_mail)
                        if u_chk:
                            mthd = st.radio("Delivery Method:", ["OTP to Email", "Reset Link to Email"], key="mthd_rad")
                            if "OTP" in mthd:
                                if st.button("SEND OTP", use_container_width=True):
                                    ok, code = set_user_otp(rec_mail)
                                    if ok:
                                        dispatch_platform_email(rec_mail, "inventro.ai • Login Passcode", f"Your 6-digit login passcode is: {code}")
                                        st.success(f"OTP sent to {rec_mail}.")
                                in_otp = st.text_input("Enter 6-digit OTP", key="in_otp_b")
                                if st.button("VERIFY & SIGN IN", use_container_width=True):
                                    with get_vault_connection() as conn:
                                        c = conn.cursor()
                                        c.execute("SELECT reset_token FROM users WHERE email = ?", (rec_mail.strip().lower(),))
                                        row = c.fetchone()
                                        if row and row[0] == in_otp.strip():
                                            c.execute("UPDATE users SET reset_token = '' WHERE email = ?", (rec_mail.strip().lower(),))
                                            conn.commit()
                                            st.session_state.authenticated_user = u_chk
                                            st.rerun()
                                        else:
                                            st.error("Invalid code.")
                            else:
                                if st.button("SEND RESET LINK", use_container_width=True):
                                    ok, tok = generate_reset_token(rec_mail)
                                    if ok:
                                        link = f"https://inventro.streamlit.app/?reset_token={tok}"
                                        dispatch_platform_email(rec_mail, "inventro.ai • Password Reset", f"Reset link: {link}")
                                        st.success("Link transmitted.")
            with tab_up:
                up_em = st.text_input("Work Email", key="up_em")
                up_p1 = st.text_input("Password", type="password", key="up_p1")
                up_p2 = st.text_input("Confirm", type="password", key="up_p2")
                if st.button("CREATE OPERATOR ACCOUNT", use_container_width=True):
                    if up_p1 == up_p2 and len(up_p1) >= 6:
                        ok, msg = create_user_account(up_em, up_p1)
                        if ok:
                            st.success("Account created. Please log in.")
                        else:
                            st.error(msg)
                    else:
                        st.warning("Ensure passwords match (min 6 chars).")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

current_user = st.session_state.authenticated_user

# Currency Localization
user_curr_code = current_user.get("currency_code", "USD")
active_currency = CURRENCY_PROFILES.get(user_curr_code, CURRENCY_PROFILES["USD"])
c_sym = active_currency["symbol"]
c_code = active_currency["code"]

def format_currency(val: float) -> str:
    return f"{c_sym}{val:,.2f}"

if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

# ==========================================
# SCHEMA RESOLUTION & INGESTION
# ==========================================
COLUMN_SYNONYMS = {
    "sku": ["sku", "product_id", "productid", "item_id", "itemcode", "id", "barcode"],
    "name": ["name", "product_name", "productname", "item_name", "title", "product"],
    "category": ["category", "cat", "department", "dept", "product_type", "type"],
    "stock": ["stock", "current_stock", "qty", "quantity", "inventory", "on_hand"],
    "lead_time": ["lead_time", "leadtime", "lead_days", "delivery_days"],
    "moq": ["moq", "min_order_qty", "minimum_order"],
    "pack_size": ["pack_size", "packsize", "case_size", "multiplier"],
    "vendor": ["vendor", "supplier", "vendor_name", "supplier_name"],
    "email": ["email", "vendor_email", "contact_email"],
    "expiry_days": ["expiry_days", "shelf_life", "expiry", "days_to_expire"],
    "price": ["price", "unit_price", "cost", "mrp", "retail_price", "rate"],
    "quantity_sold": ["quantity_sold", "qty_sold", "units_sold", "sales", "volume"],
    "transaction_date": ["transaction_date", "timestamp", "date", "created_at"]
}

def clean_str(s: str) -> str:
    return re.sub(r'[\s_\-]+', '', str(s)).lower()

def resolve_and_normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if df.empty:
        return df, {}
    norm = df.copy()
    mapping = {}
    clean_cols = {clean_str(c): c for c in df.columns}

    for k, syns in COLUMN_SYNONYMS.items():
        for s in syns:
            cs = clean_str(s)
            if cs in clean_cols:
                orig = clean_cols[cs]
                mapping[k] = orig
                norm[k] = df[orig]
                break

    for num_col, def_val in [("stock", 0), ("lead_time", 2), ("moq", 1), ("pack_size", 1), ("expiry_days", 30), ("price", 45.0), ("quantity_sold", 1)]:
        if num_col in norm.columns:
            cleaned = norm[num_col].astype(str).str.replace(r"[^\d.-]", "", regex=True)
            norm[num_col] = pd.to_numeric(cleaned, errors="coerce").fillna(def_val)
        else:
            norm[num_col] = def_val

    for str_col, def_val in [("sku", "SKU_001"), ("name", "Item"), ("category", "Retail"), ("vendor", "Primary Supplier"), ("email", "")]:
        if str_col not in norm.columns:
            norm[str_col] = def_val
        else:
            norm[str_col] = norm[str_col].fillna(def_val)

    return norm, mapping

def sanitize_db_uri(raw_uri: str) -> str:
    if not raw_uri or not raw_uri.strip():
        return ""
    clean = raw_uri.strip()
    if clean.startswith("postgres://"):
        clean = clean.replace("postgres://", "postgresql://", 1)
    try:
        p = urlparse(clean)
        q = parse_qs(p.query)
        if "postgresql" in p.scheme:
            q["sslmode"] = ["require"]
        return urlunparse(p._replace(query=urlencode(q, doseq=True)))
    except Exception:
        return clean

@st.cache_resource(show_spinner=False)
def get_db_engine(uri: str):
    s = sanitize_db_uri(uri)
    if not s:
        return None
    try:
        args = {"connect_timeout": 12} if "postgresql" in s else {}
        eng = create_engine(s, pool_pre_ping=True, pool_recycle=300, connect_args=args)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception:
        return None

# ==========================================
# ECLAIRA STYLE SIDEBAR NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("""
        <div style='display: flex; align-items: center; justify-content: space-between; padding: 6px 4px 14px 4px; border-bottom: 1px solid #181D26; margin-bottom: 14px;'>
            <div style='display: flex; align-items: center; gap: 9px;'>
                <div style='width: 30px; height: 30px; border-radius: 7px; background: #FF6B00; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem; color: #FFF;'>⚡</div>
                <div>
                    <div style='font-weight: 800; font-size: 0.92rem; color: #FFF;'>inventro.ai</div>
                    <div style='font-size: 0.68rem; color: #6C7A8E;'>Supply Chain Hub</div>
                </div>
            </div>
            <span class='badge-orange'>v2.4</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<p style='font-size: 0.68rem; font-weight: 700; color: #505B6C; text-transform: uppercase; letter-spacing: 0.08em; margin: 12px 0 6px 4px;'>General</p>", unsafe_allow_html=True)
    
    NAV_GENERAL = [
        ("▦  Dashboard", "dashboard"),
        ("📦  Inventory", "catalog"),
        ("⚡  Procurement & PO", "po_dispatch"),
        ("🛒  Order Management (POS)", "pos_scan"),
        ("📋  Transactions", "recent_tx"),
        ("🛡️  Risk & Compliance", "risk_gov")
    ]
    for label, pid in NAV_GENERAL:
        btn_type = "primary" if st.session_state.active_page == pid else "secondary"
        if st.button(label, key=f"nav_{pid}", type=btn_type, use_container_width=True):
            st.session_state.active_page = pid
            st.rerun()

    st.markdown("<p style='font-size: 0.68rem; font-weight: 700; color: #505B6C; text-transform: uppercase; letter-spacing: 0.08em; margin: 16px 0 6px 4px;'>Other Menu</p>", unsafe_allow_html=True)
    NAV_OTHER = [
        ("🤖  AI Copilot (Luna)", "ai_copilot"),
        ("🔬  Data Report (EDA)", "eda_report"),
        ("🔌  Database Terminal", "db_terminal"),
        ("💬  Help & Support", "support"),
        ("⚙️  Settings & Profile", "profile")
    ]
    for label, pid in NAV_OTHER:
        btn_type = "primary" if st.session_state.active_page == pid else "secondary"
        if st.button(label, key=f"nav_{pid}", type=btn_type, use_container_width=True):
            st.session_state.active_page = pid
            st.rerun()

    st.divider()
    db_uri_val = current_user.get("db_uri", "")
    engine = get_db_engine(db_uri_val) if db_uri_val else None
    if engine:
        st.markdown("<span style='font-size: 0.72rem; color: #10B981; font-weight: 600;'>● Postgres Live</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='font-size: 0.72rem; color: #F59E0B; font-weight: 600;'>○ Standby Offline</span>", unsafe_allow_html=True)

    if st.button("SIGN OUT", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

# ==========================================
# FETCH DATA & COMPUTE ABC-XYZ
# ==========================================
raw_products, raw_sales, raw_movements = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
if engine:
    try:
        with engine.connect() as conn:
            insp = inspect(engine)
            tbls = insp.get_table_names()
            p_tbl = next((t for t in tbls if t.lower() in ["products_master", "products", "inventory", "items"]), None)
            if p_tbl:
                raw_products = pd.read_sql(text(f"SELECT * FROM {p_tbl}"), conn)
            s_tbl = next((t for t in tbls if any(k in t.lower() for k in ["sales_ledger", "sales", "order", "txn"])), None)
            if s_tbl:
                raw_sales = pd.read_sql(text(f"SELECT * FROM {s_tbl} ORDER BY 1 DESC LIMIT 2000"), conn)
            m_tbl = next((t for t in tbls if any(k in t.lower() for k in ["stock_movements", "movement", "audit"])), None)
            if m_tbl:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {m_tbl} ORDER BY 1 DESC LIMIT 50"), conn)
    except Exception:
        pass

df_products, prod_map = resolve_and_normalize(raw_products)
df_sales, sales_map = resolve_and_normalize(raw_sales)

# Analytics calculation
def compute_analytics(p_df: pd.DataFrame, s_df: pd.DataFrame) -> pd.DataFrame:
    if p_df.empty:
        return pd.DataFrame()
    m = p_df.copy()
    if not s_df.empty and "sku" in s_df.columns and "quantity_sold" in s_df.columns:
        v = s_df.groupby("sku")["quantity_sold"].agg(
            daily_velocity="mean",
            daily_volatility=lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.5,
            total_sold="sum"
        ).reset_index()
        m = m.merge(v, on="sku", how="left")
    else:
        m["daily_velocity"] = 1.2
        m["daily_volatility"] = 0.5
        m["total_sold"] = 0

    m["daily_velocity"] = m["daily_velocity"].fillna(1.2).clip(lower=0.1)
    m["daily_volatility"] = m["daily_volatility"].fillna(0.5).clip(lower=0.1)
    m["total_sold"] = m["total_sold"].fillna(0)

    Z = 1.65
    m["safety_stock"] = np.ceil(Z * m["daily_volatility"] * np.sqrt(m["lead_time"].astype(float))).astype(int)
    m["rop"] = np.ceil((m["daily_velocity"] * m["lead_time"].astype(float)) + m["safety_stock"]).astype(int)
    m["reorder_status"] = np.where(m["stock"] <= m["rop"], "RESTOCK NEEDED", "HEALTHY")
    m["expiry_risk"] = np.where(m["expiry_days"] <= 7, "HIGH EXPIRY RISK", "STABLE")

    def calc_po(r):
        if r["reorder_status"] == "RESTOCK NEEDED":
            deficit = max(0, (2 * r["rop"]) - r["stock"])
            pk = max(1, int(r.get("pack_size", 1)))
            b = math.ceil(deficit / pk) * pk
            return max(int(r.get("moq", 1)), b)
        return 0

    m["suggested_po_qty"] = m.apply(calc_po, axis=1)
    return m

analytics_df = compute_analytics(df_products, df_sales)

# Dynamic aggregated values
total_sales_val = float((df_sales["quantity_sold"] * df_sales["price"]).sum()) if not df_sales.empty and "price" in df_sales.columns else 6652.65
fulfilled_orders = len(df_sales) if not df_sales.empty else 8921
pending_shipments = int((analytics_df["reorder_status"] == "RESTOCK NEEDED").sum()) if not analytics_df.empty else 1245
supplier_costs = float((analytics_df["suggested_po_qty"] * analytics_df["price"]).sum()) if not analytics_df.empty else 4382.40
inventory_val = float((analytics_df["stock"] * analytics_df["price"]).sum()) if not analytics_df.empty else 15827.00

# ==========================================
# PAGE ROUTER
# ==========================================

# 1. ECLAIRA REPRODUCED DASHBOARD
if st.session_state.active_page == "dashboard":
    # Top breadcrumb & welcome
    st.markdown("""
        <div style='font-size: 0.72rem; color: #5B6675; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px;'>
            Dashboard / Overview
        </div>
    """, unsafe_allow_html=True)
    
    op_name = current_user.get('email', '').split('@')[0].capitalize()
    st.markdown(f"""
        <div style='display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px;'>
            <div>
                <h1 class='eclaira-title'>Welcome Back, {op_name}!</h1>
                <div class='eclaira-subtitle'>Here's your real-time supply chain performance snapshot</div>
            </div>
            <div style='display: flex; gap: 8px;'>
                <span class='badge-orange'>REGION: {c_code}</span>
                <span style='background: #13161C; border: 1px solid #1C222C; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; color: #8F9CAE;'>Filter by Date ▾</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 5-Stat Strip
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""
            <div class='eclaira-kpi-card'>
                <div>
                    <div class='eclaira-kpi-label'>Total Sales</div>
                    <div class='eclaira-kpi-value'>{format_currency(total_sales_val)}</div>
                </div>
                <div class='eclaira-kpi-sub'><span class='badge-up'>▲ 0.56%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
            <div class='eclaira-kpi-card'>
                <div>
                    <div class='eclaira-kpi-label'>Fulfilled Orders</div>
                    <div class='eclaira-kpi-value'>{fulfilled_orders:,}</div>
                </div>
                <div class='eclaira-kpi-sub'><span class='badge-up'>▲ 1.12%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
            <div class='eclaira-kpi-card'>
                <div>
                    <div class='eclaira-kpi-label'>Pending Shipments</div>
                    <div class='eclaira-kpi-value'>{pending_shipments:,}</div>
                </div>
                <div class='eclaira-kpi-sub'><span class='badge-down'>▼ 0.87%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
            <div class='eclaira-kpi-card'>
                <div>
                    <div class='eclaira-kpi-label'>Supplier Costs</div>
                    <div class='eclaira-kpi-value'>{format_currency(supplier_costs)}</div>
                </div>
                <div class='eclaira-kpi-sub'><span class='badge-up'>▲ 0.25%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k5:
        st.markdown(f"""
            <div class='eclaira-kpi-card'>
                <div>
                    <div class='eclaira-kpi-label'>Inventory Value</div>
                    <div class='eclaira-kpi-value'>{format_currency(inventory_val)}</div>
                </div>
                <div class='eclaira-kpi-sub'><span class='badge-up'>▲ 2.04%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Main Chart Row (Sales Trend Overview + Sales by Customer Segment)
    m_col1, m_col2 = st.columns([1.75, 1.0])

    with m_col1:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>
                    <div>
                        <div style='font-size: 0.92rem; font-weight: 700; color: #FFF;'>Sales Trend Overview</div>
                        <div style='font-size: 0.72rem; color: #5B6675;'>Track sales volume to identify seasonal trends and growth.</div>
                    </div>
                    <span style='background: #181D26; border: 1px solid #232A36; padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; color: #94A3B8;'>Download Report ▾</span>
                </div>
        """, unsafe_allow_html=True)

        if PLOTLY_AVAILABLE:
            # Generate continuous curved line graph matching Eclaira palette
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            trend_values = [3200, 3100, 4800, 3600, 4200, 6100, 5233, 7100, 6800, 8400, 7900, 9200]
            
            fig = go.Figure()
            # Area fill with glowing Eclaira orange accent
            fig.add_trace(go.Scatter(
                x=months, y=trend_values,
                mode='lines+markers',
                line=dict(color='#FF6B00', width=2.5, shape='spline'),
                marker=dict(size=4, color='#FFA048'),
                fill='tozeroy',
                fillcolor='rgba(255, 107, 0, 0.08)',
                name='Volume'
            ))
            # Callout point at July ($5,233)
            fig.add_annotation(
                x="Jul", y=5233,
                text="<b>$5,233</b><br><span style='font-size:9px;'>Sales on July 2026</span>",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#FF6B00",
                ax=0, ay=-36,
                bgcolor="#1C222C", bordercolor="#FF6B00", borderwidth=1,
                font=dict(size=10, color="#FFFFFF")
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=260,
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#5B6675", size=10)),
                yaxis=dict(showgrid=True, gridcolor="#181D26", tickfont=dict(color="#5B6675", size=10))
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with m_col2:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.92rem; font-weight: 700; color: #FFF; margin-bottom: 4px;'>Sales by Customer Segment</div>
                <div style='font-size: 0.72rem; color: #5B6675;'>Channel breakdown & wholesale share</div>
                
                <div class='segment-bar-container'>
                    <div class='seg-fill-1' style='width: 58%;'></div>
                    <div class='seg-fill-2' style='width: 27%;'></div>
                    <div class='seg-fill-3' style='width: 15%;'></div>
                </div>

                <div class='seg-legend-row'>
                    <span style='color: #FF6B00;'>● RETAIL DISTRIBUTORS</span>
                    <b style='color: #FFF; font-family: monospace;'>$1,902.00</b>
                </div>
                <div class='seg-legend-row'>
                    <span style='color: #FFA048;'>● WHOLESALE BUYERS</span>
                    <b style='color: #FFF; font-family: monospace;'>$720.00</b>
                </div>
                <div class='seg-legend-row' style='border: none;'>
                    <span style='color: #94A3B8;'>● DIRECT CONSUMERS</span>
                    <b style='color: #FFF; font-family: monospace;'>$401.00</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.92rem; font-weight: 700; color: #FFF; margin-bottom: 2px;'>Order Volume Distribution</div>
                <div style='font-size: 0.72rem; color: #5B6675;'>Regional fulfillment density</div>
        """, unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            fig_bar = go.Figure(data=[
                go.Bar(name='Direct', x=['North', 'West', 'East'], y=[320, 480, 290], marker_color='#FF6B00'),
                go.Bar(name='Hub', x=['North', 'West', 'East'], y=[180, 240, 150], marker_color='#252C38')
            ])
            fig_bar.update_layout(
                barmode='stack', height=110,
                margin=dict(t=5, b=5, l=5, r=5),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#5B6675", size=9)),
                yaxis=dict(showgrid=False, showticklabels=False)
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # Bottom Row (Customer Segments Bar Chart + Segment Performance Comparison)
    b_col1, b_col2 = st.columns([1.75, 1.0])

    with b_col1:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.92rem; font-weight: 700; color: #FFF;'>Customer Segments</div>
                <div style='font-size: 0.72rem; color: #5B6675; margin-bottom: 10px;'>Analyze sales trends by different customer groups</div>
        """, unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            fig_hist = go.Figure()
            days = [f"D{i}" for i in range(1, 19)]
            y_vals = [12, 14, 25, 42, 68, 55, 30, 22, 18, 29, 44, 75, 62, 38, 48, 80, 52, 34]
            colors = ['#FF6B00' if v > 60 else '#202632' for v in y_vals]
            fig_hist.add_trace(go.Bar(x=days, y=y_vals, marker_color=colors))
            fig_hist.update_layout(
                height=150, margin=dict(t=5, b=5, l=5, r=5),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#5B6675", size=8)),
                yaxis=dict(showgrid=True, gridcolor="#181D26", tickfont=dict(color="#5B6675", size=8))
            )
            st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with b_col2:
        st.markdown("""
            <div class='eclaira-card' style='height: 100%; display: flex; flex-direction: column; justify-content: space-between;'>
                <div>
                    <div style='font-size: 0.92rem; font-weight: 700; color: #FFF;'>Segment Performance Comparison</div>
                    <div style='font-size: 0.72rem; color: #5B6675;'>Compare sales and order volume changes month-over-month</div>
                </div>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px;'>
                    <div style='background: #181D26; border-radius: 8px; padding: 12px;'>
                        <div style='font-size: 0.68rem; color: #6C7A8E; text-transform: uppercase;'>Current Run</div>
                        <div style='font-size: 1.15rem; font-weight: 800; color: #FFF; font-family: monospace;'>$12,241.00</div>
                        <span class='badge-down'>▼ 3.81%</span>
                    </div>
                    <div style='background: #181D26; border-radius: 8px; padding: 12px;'>
                        <div style='font-size: 0.68rem; color: #6C7A8E; text-transform: uppercase;'>Target YTD</div>
                        <div style='font-size: 1.15rem; font-weight: 800; color: #FFF; font-family: monospace;'>$93,462.00</div>
                        <span class='badge-up'>▲ 9.25%</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# 2. INVENTORY CATALOG
elif st.session_state.active_page == "catalog":
    st.markdown("<h1 class='eclaira-title'>📦 Warehouse Inventory Catalog</h1><div class='eclaira-subtitle'>Stock positions and reorder limits</div>", unsafe_allow_html=True)
    if not analytics_df.empty:
        s_box = st.text_input("Search catalog...", placeholder="Filter by SKU or description...")
        filt = analytics_df.copy()
        if s_box:
            filt = filt[filt["name"].str.contains(s_box, case=False) | filt["sku"].str.contains(s_box, case=False)]
        cols = ["sku", "name", "category", "stock", "lead_time", "rop", "reorder_status", "suggested_po_qty", "vendor"]
        st.dataframe(filt[[c for c in cols if c in filt.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("Catalog empty. Connect your database pipeline.")

# 3. PO DISPATCH
elif st.session_state.active_page == "po_dispatch":
    st.markdown("<h1 class='eclaira-title'>⚡ Autonomous Purchase Order Dispatch</h1><div class='eclaira-subtitle'>Replenishment orders triggered by inventory breaches</div>", unsafe_allow_html=True)
    if not analytics_df.empty:
        po_lines = analytics_df[analytics_df["suggested_po_qty"] > 0]
        if po_lines.empty:
            st.success("All SKU levels healthy. No PO orders required.")
        else:
            sel_v = st.selectbox("Select Supplier", po_lines["vendor"].unique())
            v_data = po_lines[po_lines["vendor"] == sel_v]
            target_em = v_data["email"].iloc[0] if "email" in v_data.columns else ""
            rcpt_em = st.text_input("Supplier Recipient Email", value=target_em)
            po_body = f"PURCHASE ORDER • INVENTRO.AI RELAY\nSupplier: {sel_v}\n" + "-"*40 + "\n"
            for _, r in v_data.iterrows():
                po_body += f"{r['sku']:<10} | {r['name'][:18]:<18} | Qty: {r['suggested_po_qty']}\n"
            st.text_area("PO Payload", value=po_body, height=160)
            if st.button("DISPATCH RESTOCK PO", type="primary"):
                ok, m = dispatch_platform_email(rcpt_em, f"RESTOCK PO - {sel_v}", po_body)
                if ok:
                    st.success(f"PO sent to {rcpt_em}")
                else:
                    st.error(m)
    else:
        st.info("No data available.")

# 4. ORDER MANAGEMENT (POS SCAN)
elif st.session_state.active_page == "pos_scan":
    st.markdown("<h1 class='eclaira-title'>🛒 POS Checkout & Stock Intake</h1><div class='eclaira-subtitle'>Register transactions and shipments</div>", unsafe_allow_html=True)
    if not analytics_df.empty:
        c1, c2 = st.columns([1.2, 1.0])
        with c1:
            sel_sku = st.selectbox("SKU", analytics_df["sku"].tolist())
            row = analytics_df[analytics_df["sku"] == sel_sku].iloc[0]
            act = st.radio("Type:", ["Sale (POS)", "Stock IN (Receive)"], horizontal=True)
            u = st.number_input("Units", min_value=1, value=1)
            st.caption(f"Item: {row['name']} | Current Stock: {row['stock']}")
            if st.button("COMMIT RECORD", type="primary", use_container_width=True):
                if engine:
                    try:
                        with engine.begin() as conn:
                            if "Sale" in act:
                                conn.execute(text(f"UPDATE products_master SET stock = stock - :u WHERE sku = :s AND stock >= :u"), {"u": u, "s": sel_sku})
                            else:
                                conn.execute(text(f"UPDATE products_master SET stock = stock + :u WHERE sku = :s"), {"u": u, "s": sel_sku})
                        st.success("Committed.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Commit error: {err}")
        with c2:
            st.markdown("<b>Recent Movements</b>", unsafe_allow_html=True)
            if not raw_movements.empty:
                st.dataframe(raw_movements.head(6), use_container_width=True, hide_index=True)
    else:
        st.info("Catalog empty.")

# 5. RECENT TRANSACTIONS
elif st.session_state.active_page == "recent_tx":
    st.markdown("<h1 class='eclaira-title'>📋 Recent Fleet Transactions</h1>", unsafe_allow_html=True)
    if not df_sales.empty:
        st.dataframe(df_sales.head(30), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions logged.")

# 6. RISK & COMPLIANCE
elif st.session_state.active_page == "risk_gov":
    st.markdown("<h1 class='eclaira-title'>🛡️ Risk Radar & Compliance</h1>", unsafe_allow_html=True)
    if not analytics_df.empty:
        exp = analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"]
        st.dataframe(exp, use_container_width=True, hide_index=True)
    else:
        st.info("No risks detected.")

# 7. AI COPILOT (GPT-5.6 LUNA)
elif st.session_state.active_page == "ai_copilot":
    st.markdown("<h1 class='eclaira-title'>🤖 Supply Copilot (GPT-5.6 Luna)</h1><div class='eclaira-subtitle'>AI diagnostic agent for inventory Runway and Pareto distribution</div>", unsafe_allow_html=True)
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [{"role": "assistant", "content": f"Ready. How can I assist with your supply fleet?"}]
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if p := st.chat_input("Ask about stockouts, supplier SLA, or PO calculation..."):
        st.session_state.chat_messages.append({"role": "user", "content": p})
        with st.chat_message("user"):
            st.markdown(p)
        with st.chat_message("assistant"):
            k = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
            if k and OPENAI_AVAILABLE:
                try:
                    cli = OpenAI(api_key=k, timeout=25.0)
                    resp = cli.chat.completions.create(
                        model="gpt-5.6-luna",
                        messages=[
                            {"role": "system", "content": f"You are the autonomous AI Copilot for inventro.ai. Answer concisely using currency {c_code}."},
                            {"role": "user", "content": p}
                        ],
                        reasoning_effort="low"
                    )
                    ans = resp.choices[0].message.content
                except Exception as e:
                    ans = f"AI Error: {e}"
            else:
                ans = "OpenAI key not configured in Streamlit Secrets."
            st.markdown(ans)
            st.session_state.chat_messages.append({"role": "assistant", "content": ans})

# 8. DATA REPORT (EDA)
elif st.session_state.active_page == "eda_report":
    st.markdown("<h1 class='eclaira-title'>🔬 14-Point EDA Telemetry</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Total Catalog SKUs", len(df_products))
    c2.metric("Total Sales Records", len(df_sales))

# 9. DB TERMINAL
elif st.session_state.active_page == "db_terminal":
    st.markdown("<h1 class='eclaira-title'>🔌 Direct Relational SQL Terminal</h1>", unsafe_allow_html=True)
    q = st.text_area("SQL Statement", placeholder="SELECT * FROM products_master LIMIT 5;")
    if st.button("RUN QUERY"):
        if engine and q:
            try:
                with engine.connect() as conn:
                    st.dataframe(pd.read_sql(text(q), conn), use_container_width=True)
            except Exception as e:
                st.error(str(e))

# 10. HELP & SUPPORT
elif st.session_state.active_page == "support":
    st.markdown("<h1 class='eclaira-title'>💬 Operator Help & Issue Desk</h1><div class='eclaira-subtitle'>Submit tickets directly to the engineering team</div>", unsafe_allow_html=True)
    sub = st.text_input("Issue Summary")
    desc = st.text_area("Description")
    if st.button("TRANSMIT TICKET", type="primary"):
        rec = st.secrets.get("SUPPORT_RECEIVER_EMAIL", st.secrets.get("SYSTEM_SMTP_SENDER", ""))
        if rec and sub and desc:
            ok, m = dispatch_platform_email(rec, f"Support Ticket: {sub}", f"From: {current_user.get('email')}\n\n{desc}")
            if ok:
                st.success("Ticket transmitted.")
            else:
                st.error(m)

# 11. SETTINGS & PROFILE
elif st.session_state.active_page == "profile":
    st.markdown("<h1 class='eclaira-title'>⚙️ Operator Settings & Vault</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='eclaira-card'>", unsafe_allow_html=True)
        st.markdown("<b>Currency Format</b>", unsafe_allow_html=True)
        sel_c = st.selectbox("Select Currency", list(CURRENCY_PROFILES.keys()), index=list(CURRENCY_PROFILES.keys()).index(user_curr_code))
        st.markdown("<hr style='border-color: #1E2430; margin: 12px 0;'>", unsafe_allow_html=True)
        st.markdown("<b>Database Connection URI</b>", unsafe_allow_html=True)
        u_uri = st.text_input("Postgres / Neon URI", value=current_user.get("db_uri", ""), type="password")
        if st.button("SAVE CONFIGURATION", type="primary"):
            save_user_credentials(current_user["id"], "PostgreSQL / Neon", "", "5432", "", "", "", u_uri, sel_c, CURRENCY_PROFILES[sel_c]["symbol"])
            current_user["currency_code"] = sel_c
            current_user["currency_symbol"] = CURRENCY_PROFILES[sel_c]["symbol"]
            current_user["db_uri"] = u_uri
            st.toast("Saved configuration.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='eclaira-card'><b>Active Session</b><br><br>Operator: <code>{current_user.get('email')}</code><br>Vault Engine: SQLite 3 (WAL Mode)<br>Status: Protected</div>", unsafe_allow_html=True)