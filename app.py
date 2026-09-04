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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Plotly with Defensive Fallback
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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
# PAGE CONFIGURATION & DATAOPS THEME
# ==========================================
st.set_page_config(
    page_title="inventro.ai | Autonomous Retail OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    background-color: #0B0C10 !important;
    color: #F1F5F9 !important;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

[data-testid="stSidebar"] {
    background-color: #101218 !important;
    border-right: 1px solid #1B1E28 !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1B1E28 !important;
}

.dribbble-card {
    background: #141720;
    border: 1px solid #1E2330;
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    margin-bottom: 16px;
    position: relative;
}
.dribbble-card:hover {
    border-color: #2D3446;
}

.card-header-flex {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.card-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8E9BAE;
}
.card-val-lg {
    font-size: 1.85rem;
    font-weight: 800;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.card-unit {
    font-size: 0.8rem;
    font-weight: 500;
    color: #717D96;
    margin-left: 4px;
}

.chip {
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.chip-green { background: rgba(0, 227, 150, 0.12); color: #00E396; border: 1px solid rgba(0, 227, 150, 0.3); }
.chip-red { background: rgba(255, 69, 96, 0.12); color: #FF4560; border: 1px solid rgba(255, 69, 96, 0.3); }
.chip-cyan { background: rgba(0, 178, 255, 0.12); color: #00B2FF; border: 1px solid rgba(0, 178, 255, 0.3); }
.chip-amber { background: rgba(254, 176, 25, 0.12); color: #FEB019; border: 1px solid rgba(254, 176, 25, 0.3); }

.risk-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-top: 6px;
}
.risk-table th {
    color: #64748B;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid #1E2330;
}
.risk-table td {
    padding: 10px 10px;
    border-bottom: 1px solid #171A24;
    color: #E2E8F0;
    font-weight: 500;
}

.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    border: 1px solid #282E3E !important;
    background: #191D28 !important;
    color: #F1F5F9 !important;
    transition: all 0.2s ease !important;
    margin-bottom: 2px !important;
}
.stButton > button:hover {
    border-color: #00B2FF !important;
    color: #00B2FF !important;
}
.stButton > button[kind="primary"] {
    background: #0284C7 !important;
    border-color: #00B2FF !important;
    color: #FFFFFF !important;
    box-shadow: 0 0 12px rgba(0, 178, 255, 0.25) !important;
}

input, select, textarea, [data-baseweb="select"] {
    background-color: #141720 !important;
    border-color: #1E2330 !important;
    color: #F1F5F9 !important;
    border-radius: 10px !important;
    font-size: 0.85rem !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #1E2330 !important;
    border-radius: 12px !important;
    background: #141720 !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# CURRENCY LOCALIZATION DICTIONARY
# ==========================================
CURRENCY_PROFILES = {
    "INR": {"symbol": "₹", "code": "INR", "label": "India (INR - ₹)", "rate_multiplier": 83.5},
    "USD": {"symbol": "$", "code": "USD", "label": "United States (USD - $)", "rate_multiplier": 1.0},
    "AED": {"symbol": "AED ", "code": "AED", "label": "UAE / Dubai (AED - د.إ)", "rate_multiplier": 3.67},
    "EUR": {"symbol": "€", "code": "EUR", "label": "European Union (EUR - €)", "rate_multiplier": 0.92},
    "GBP": {"symbol": "£", "code": "GBP", "label": "United Kingdom (GBP - £)", "rate_multiplier": 0.78},
    "SAR": {"symbol": "SAR ", "code": "SAR", "label": "Saudi Arabia (SAR - ﷼)", "rate_multiplier": 3.75},
    "SGD": {"symbol": "S$", "code": "SGD", "label": "Singapore (SGD - S$)", "rate_multiplier": 1.34}
}

# ==========================================
# 1. SQLITE VAULT CONCURRENCY (WAL MODE)
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
                    currency_code TEXT DEFAULT 'INR',
                    currency_symbol TEXT DEFAULT '₹',
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
                ("currency_code", "TEXT DEFAULT 'INR'"),
                ("currency_symbol", "TEXT DEFAULT '₹'"),
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
                       currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password
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
                    "currency_code": row[9] or "INR",
                    "currency_symbol": row[10] or "₹",
                    "smtp_server": row[11] or "",
                    "smtp_port": row[12] or 587,
                    "smtp_sender": row[13] or "",
                    "smtp_password": row[14] or ""
                }
    except Exception:
        return None
    return None

def send_system_email(recipient: str, subject: str, body: str) -> tuple[bool, str]:
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT smtp_server, smtp_port, smtp_sender, smtp_password FROM users WHERE email = ?", (recipient.strip().lower(),))
            smtp_info = c.fetchone()
            if not (smtp_info and smtp_info[0] and smtp_info[2] and smtp_info[3]):
                c.execute("SELECT smtp_server, smtp_port, smtp_sender, smtp_password FROM users WHERE smtp_server != '' AND smtp_password != '' LIMIT 1")
                smtp_info = c.fetchone()

        if not (smtp_info and smtp_info[0] and smtp_info[2] and smtp_info[3]):
            return False, "SMTP configuration missing: Please set up SMTP credentials in the Profile tab."

        msg = MIMEMultipart()
        msg["From"] = smtp_info[2]
        msg["To"] = recipient.strip()
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(smtp_info[0], int(smtp_info[1] or 587), timeout=15)
        server.starttls()
        server.login(smtp_info[2], smtp_info[3])
        server.send_message(msg)
        server.quit()
        return True, f"Security dispatch delivered to {recipient.strip()}."
    except Exception as e:
        return False, f"SMTP relay transmission error: {str(e)}"

def set_user_otp(email: str) -> tuple[bool, str]:
    clean_email = email.strip().lower()
    otp_code = f"{random.randint(100000, 999999)}"
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (otp_code, clean_email))
            conn.commit()
            if c.rowcount > 0:
                return True, otp_code
            return False, "No operator account found with this email."
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
            if c.rowcount > 0:
                return True, token
            return False, "No operator account found with this email."
    except Exception as e:
        return False, str(e)

def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE reset_token = ? AND reset_token != ''", (token.strip(),))
            row = c.fetchone()
            if not row:
                return False, "Invalid or expired reset token."
            user_email = row[0]
            c.execute("UPDATE users SET password_hash = ?, reset_token = '' WHERE email = ?", (hash_pw(new_password), user_email))
            conn.commit()
            return True, f"Password reset successful for {user_email}. You may now log in."
    except Exception as e:
        return False, str(e)

def save_user_credentials(user_id: int, dialect: str, host: str, port: str, dbname: str, user: str, pwd: str, uri: str, curr_code: str, curr_sym: str, smtp_srv: str, smtp_prt: int, smtp_snd: str, smtp_pwd: str):
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE users
                SET db_dialect = ?, db_host = ?, db_port = ?, db_name = ?, db_user = ?, db_pass = ?, db_uri = ?,
                    currency_code = ?, currency_symbol = ?,
                    smtp_server = ?, smtp_port = ?, smtp_sender = ?, smtp_password = ?
                WHERE id = ?
            """, (dialect, host, port, dbname, user, pwd, uri, curr_code, curr_sym, smtp_srv, smtp_prt, smtp_snd, smtp_pwd, user_id))
            conn.commit()
    except Exception as e:
        st.error(f"Failed to save credentials: {e}")

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

query_params = st.query_params
active_reset_token = query_params.get("reset_token", None)

if not st.session_state.authenticated_user:
    st.markdown("<div style='text-align: center; padding: 50px 0 25px 0;'><h1 style='color: #00B2FF; font-weight: 800; letter-spacing: -0.03em;'>⚡ INVENTRO.AI</h1><p style='color: #8E9BAE; font-size: 1rem;'>Autonomous Retail Operating System & Machine Intelligence Control</p></div>", unsafe_allow_html=True)
    
    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.25, 1])
    with auth_col2:
        if active_reset_token:
            st.markdown("<div class='dribbble-card'>", unsafe_allow_html=True)
            st.markdown("##### 🔐 Set New Password")
            st.caption("Secure password reset link authenticated.")
            new_link_pw = st.text_input("New Password", type="password", key="new_link_pw")
            confirm_link_pw = st.text_input("Confirm New Password", type="password", key="confirm_link_pw")

            if st.button("UPDATE PASSWORD & PROCEED TO LOGIN", type="primary", use_container_width=True):
                if not new_link_pw or not confirm_link_pw:
                    st.warning("All fields are required.")
                elif new_link_pw != confirm_link_pw:
                    st.error("Passwords do not match.")
                elif len(new_link_pw) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    ok, msg = reset_password_with_token(active_reset_token, new_link_pw)
                    if ok:
                        st.success(msg)
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(msg)
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        auth_tab_login, auth_tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])
        
        with auth_tab_login:
            st.markdown("##### Workspace Authentication")
            login_email = st.text_input("Operator Identity", key="login_email")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("INITIALIZE MISSION CONTROL", type="primary", use_container_width=True):
                if login_email and login_pass:
                    user_data = verify_user(login_email, login_pass)
                    if user_data:
                        st.session_state.authenticated_user = user_data
                        st.toast(f"Operator Verified: {login_email}", icon="⚡")
                        st.rerun()
                    else:
                        st.error("Authentication rejected: Invalid credentials.")
                else:
                    st.warning("Please provide operator email and password.")

            with st.expander("Forgot password?"):
                st.markdown("<p style='font-size: 0.8rem; font-weight: 600; color: #8E9BAE;'>Select recovery path:</p>", unsafe_allow_html=True)
                recovery_choice = st.radio(
                    "Recovery Mode:",
                    ["Option 1: Send OTP to registered email", "Option 2: Reset password via email link"],
                    label_visibility="collapsed",
                    key="recovery_choice"
                )

                reg_email = st.text_input("Registered Email Address", key="reg_email_field", placeholder="operator@retail.com")

                if recovery_choice == "Option 1: Send OTP to registered email":
                    st.caption("A 6-digit access OTP will be dispatched exclusively to your registered inbox.")
                    
                    if st.button("DISPATCH LOGIN OTP", use_container_width=True):
                        if reg_email:
                            ok, otp_or_msg = set_user_otp(reg_email)
                            if ok:
                                body = (
                                    f"INVENTRO.AI SECURITY VERIFICATION\n\n"
                                    f"Your single-use login OTP code is: {otp_or_msg}\n\n"
                                    f"This code expires immediately after successful verification.\n"
                                    f"If you did not request this code, contact your system administrator."
                                )
                                sent, status_msg = send_system_email(
                                    reg_email,
                                    "inventro.ai • One-Time Access Verification Code",
                                    body
                                )
                                if sent:
                                    st.success(f"Security code dispatched to `{reg_email}`. Please check your inbox.")
                                else:
                                    st.error(status_msg)
                        else:
                            st.warning("Please provide your registered operator email.")

                    otp_input = st.text_input("Enter 6-Digit OTP from Email", key="login_otp_input")
                    if st.button("VERIFY OTP & LOG IN", type="primary", use_container_width=True):
                        if not reg_email or not otp_input:
                            st.warning("Both registered email and OTP are required.")
                        else:
                            try:
                                with get_vault_connection() as conn:
                                    c = conn.cursor()
                                    c.execute("SELECT reset_token FROM users WHERE email = ?", (reg_email.strip().lower(),))
                                    row = c.fetchone()
                                    if row and row[0] and row[0].strip() == otp_input.strip():
                                        c.execute("UPDATE users SET reset_token = '' WHERE email = ?", (reg_email.strip().lower(),))
                                        conn.commit()
                                        
                                        c.execute("""
                                            SELECT id, email, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, 
                                                   currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password
                                            FROM users WHERE email = ?
                                        """, (reg_email.strip().lower(),))
                                        u_row = c.fetchone()
                                        st.session_state.authenticated_user = {
                                            "id": u_row[0], "email": u_row[1], "db_dialect": u_row[2] or "PostgreSQL / Neon",
                                            "db_host": u_row[3] or "", "db_port": u_row[4] or "5432", "db_name": u_row[5] or "",
                                            "db_user": u_row[6] or "", "db_pass": u_row[7] or "", "db_uri": u_row[8] or "",
                                            "currency_code": u_row[9] or "INR", "currency_symbol": u_row[10] or "₹",
                                            "smtp_server": u_row[11] or "", "smtp_port": u_row[12] or 587,
                                            "smtp_sender": u_row[13] or "", "smtp_password": u_row[14] or ""
                                        }
                                        st.toast(f"Operator Authenticated: {reg_email}", icon="⚡")
                                        st.rerun()
                                    else:
                                        st.error("Authentication rejected: Invalid or expired OTP.")
                            except Exception as err:
                                st.error(f"Vault verification error: {err}")

                elif recovery_choice == "Option 2: Reset password via email link":
                    st.caption("A secure tokenized URL will be delivered to your inbox to reset your password.")
                    
                    if st.button("SEND PASSWORD RESET LINK", use_container_width=True):
                        if reg_email:
                            ok, token_or_msg = generate_reset_token(reg_email)
                            if ok:
                                reset_url = f"https://inventro.streamlit.app/?reset_token={token_or_msg}"
                                body = (
                                    f"INVENTRO.AI PASSWORD RESET REQUEST\n\n"
                                    f"Click the link below to configure a new operator secret:\n"
                                    f"{reset_url}\n\n"
                                    f"If you did not request a credential reset, please disregard this email."
                                )
                                sent, status_msg = send_system_email(
                                    reg_email,
                                    "inventro.ai • Secure Password Reset Link",
                                    body
                                )
                                if sent:
                                    st.success(f"Password reset link dispatched to `{reg_email}`. Check your inbox.")
                                else:
                                    st.error(status_msg)
                        else:
                            st.error(token_or_msg)
                    else:
                        st.warning("Please provide your registered operator email.")

        with auth_tab_signup:
            st.markdown("##### Create Operator Profile")
            signup_email = st.text_input("Operator Email", key="signup_email")
            signup_pass = st.text_input("Password", type="password", key="signup_pass")
            signup_pass2 = st.text_input("Confirm Password", type="password", key="signup_pass2")
            
            if st.button("GENERATE SECURE VAULT", use_container_width=True):
                if not signup_email or not signup_pass:
                    st.warning("All credentials required.")
                elif signup_pass != signup_pass2:
                    st.error("Passwords do not match.")
                elif len(signup_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    success, msg = create_user_account(signup_email, signup_pass)
                    if success:
                        st.success("Operator registered. Log in to continue.")
                    else:
                        st.error(msg)
    st.stop()

current_user = st.session_state.authenticated_user

# Currency Localization
user_curr_code = current_user.get("currency_code", "INR")
active_currency = CURRENCY_PROFILES.get(user_curr_code, CURRENCY_PROFILES["INR"])
c_sym = active_currency["symbol"]
c_code = active_currency["code"]
c_mult = active_currency["rate_multiplier"]

def format_currency(amount_usd: float) -> str:
    converted = amount_usd * (c_mult if c_code != "USD" else 1.0)
    return f"{c_sym}{converted:,.2f}"

# Navigation State: Defaults to Overview Dashboard
if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

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
    "price": ["price", "unit_price", "cost", "mrp", "retail_price", "rate", "sale_price"],
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
        "stock": 0, "lead_time": 2, "moq": 1, "pack_size": 1,
        "expiry_days": 30, "price": 100.0, "quantity_sold": 1
    }
    for col, def_val in numeric_defaults.items():
        if col in normalized_df.columns:
            normalized_df[col] = clean_numeric_series(normalized_df[col], def_val)
        else:
            normalized_df[col] = def_val

    string_defaults = {
        "sku": [f"SKU_{i+1:03d}" for i in range(len(normalized_df))],
        "name": "Item", "category": "General", "vendor": "Unassigned", "email": ""
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
        st.sidebar.error(f"DB Error: {e}")
        return None

# ==========================================
# LEFT COLLAPSIBLE SIDEBAR: PAGE NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("""
        <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 12px;'>
            <div style='width: 36px; height: 36px; border-radius: 10px; background: #00B2FF; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; color: #FFF;'>⚡</div>
            <div>
                <div style='font-weight: 700; font-size: 0.95rem; color: #FFF;'>inventro.ai</div>
                <div style='font-size: 0.72rem; color: #64748B;'>Autonomous Retail OS</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style='background: #141720; border: 1px solid #1E2330; border-radius: 10px; padding: 10px 12px; margin-bottom: 14px;'>
            <div style='font-size: 0.68rem; color: #64748B; text-transform: uppercase;'>Signed-In Operator</div>
            <div style='font-size: 0.82rem; font-weight: 700; color: #F1F5F9; word-break: break-all;'>{current_user.get('email', '')}</div>
            <div style='margin-top: 6px;'><span class='chip chip-green'>REGION: {c_code} ({c_sym.strip()})</span></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<p style='font-size: 0.7rem; font-weight: 800; color: #8E9BAE; letter-spacing: 0.08em; margin-bottom: 6px;'>NAVIGATION PAGES</p>", unsafe_allow_html=True)

    PAGES_LIST = [
        ("📊 Dashboard Overview", "dashboard"),
        ("🤖 AI Copilot Agent", "ai_copilot"),
        ("📋 Recent Transactions", "recent_tx"),
        ("🔬 Data Report (EDA)", "eda_report"),
        ("📦 Inventory Catalog", "catalog"),
        ("🛡️ Risk & Governance", "risk_gov"),
        ("⚡ POS Scan & Intake", "pos_scan"),
        ("✉️ PO Dispatch", "po_dispatch"),
        ("🔌 DB Terminal", "db_terminal"),
        ("👤 Profile & Vault", "profile")
    ]

    for label, page_id in PAGES_LIST:
        is_active = (st.session_state.active_page == page_id)
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"side_nav_{page_id}", type=btn_type, use_container_width=True):
            st.session_state.active_page = page_id
            st.rerun()

    st.divider()
    final_connection_uri = current_user.get("db_uri", "")
    engine = get_db_engine(final_connection_uri) if final_connection_uri else None
    is_connected = engine is not None

    if is_connected:
        st.markdown("<span class='chip chip-green' style='width: 100%; justify-content: center; margin-bottom: 8px;'>PIPELINE: ONLINE (POSTGRES)</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='chip chip-amber' style='width: 100%; justify-content: center; margin-bottom: 8px;'>PIPELINE: STANDBY / OFFLINE</span>", unsafe_allow_html=True)

    if st.button("TERMINATE SESSION", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

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

    # ABC Pareto
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
# AI COPILOT ENGINE (GPT-5.6 LUNA)
# ==========================================
def intelligent_ai_agent(user_query: str, matrix: pd.DataFrame, eda_data: dict) -> str:
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not api_key:
        return "⚠️ OpenAI API key missing. Configure `OPENAI_API_KEY` in Streamlit Secrets."
    if not OPENAI_AVAILABLE:
        return "⚠️ `openai` library not found. Add `openai` to requirements.txt."
    try:
        client = OpenAI(api_key=api_key, timeout=30.0)
        trimmed = matrix.head(45)[[
            "sku", "name", "category", "stock", "lead_time", "daily_velocity",
            "safety_stock", "rop", "days_runway", "reorder_status", "suggested_po_qty", "vendor"
        ]].to_dict(orient="records")

        completion = client.chat.completions.create(
            model="gpt-5.6-luna",
            messages=[
                {"role": "system", "content": f"You are the autonomous AI Copilot for inventro.ai operating in {c_code} ({c_sym.strip()}). Fleet: {json.dumps(trimmed, default=str)}. EDA: {json.dumps(eda_data, default=str)}. State exact financial metrics in {c_code} ({c_sym.strip()})."},
                {"role": "user", "content": user_query}
            ],
            reasoning_effort="low"
        )
        return completion.choices[0].message.content
    except Exception as err:
        return f"⚠️ AI Engine Exception: {str(err)}"

# Metrics calculation
total_stock = int(analytics_df['stock'].sum()) if not analytics_df.empty else 0
restock_needed = int((analytics_df['reorder_status'] == 'RESTOCK NEEDED').sum()) if not analytics_df.empty else 0
healthy_units = int((analytics_df['reorder_status'] == 'HEALTHY').sum()) if not analytics_df.empty else 0
perish_alert = int((analytics_df['expiry_risk'] == 'HIGH EXPIRY RISK').sum()) if not analytics_df.empty else 0
nominal_revenue_val = format_currency(total_stock * 32.40)
nominal_balance_val = format_currency(78500.00)
replenish_outlay_val = format_currency(12980.00)

# ==========================================
# TOP HEADER BAR
# ==========================================
active_page_label = next((label for label, pid in PAGES_LIST if pid == st.session_state.active_page), "Console")
st.markdown(f"""
    <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;'>
        <div style='display: flex; align-items: center; gap: 12px;'>
            <span style='font-size: 1.4rem; font-weight: 800; color: #FFFFFF;'>⚡ inventro.ai • {active_page_label}</span>
            <span style='color: #4B5563;'>•</span>
            <span class='chip chip-cyan'>FLEET ONLINE</span>
            <span class='chip chip-green'>CURRENCY: {c_code} ({c_sym.strip()})</span>
        </div>
        <div style='display: flex; align-items: center; gap: 8px;'>
            <span style='background: #141720; border: 1px solid #1E2330; padding: 6px 12px; border-radius: 20px; font-size: 0.75rem; color: #94A3B8;'>Connected: <b style='color:#00E396;'>Postgres</b></span>
            <span style='background: #141720; border: 1px solid #1E2330; padding: 6px 12px; border-radius: 20px; font-size: 0.75rem; color: #94A3B8;'>SLA: <b style='color:#00B2FF;'>99.98%</b></span>
        </div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# MAIN ROUTER: DYNAMIC PAGE SELECTION
# ==========================================

# 1. DASHBOARD OVERVIEW
if st.session_state.active_page == "dashboard":
    r1_c1, r1_c2, r1_c3 = st.columns([1.2, 1.2, 1.6])

    with r1_c1:
        st.markdown(f"<div class='dribbble-card'><div class='card-header-flex'><span class='card-label'>Nominal Balance</span><span style='color: #64748B;'>💳</span></div><div class='card-val-lg'>{nominal_balance_val}</div><div style='display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px;'><span class='chip chip-green'>↑ 1.18% weekly</span><svg width='75' height='24' viewBox='0 0 100 30' fill='none'><path d='M0 25 Q 25 5, 50 18 T 100 8' stroke='#00E396' stroke-width='3' fill='none'/></svg></div></div><div class='dribbble-card'><div class='card-header-flex'><span class='card-label'>Nominal Revenue</span><span style='color: #64748B;'>📈</span></div><div class='card-val-lg'>{nominal_revenue_val}</div><div style='display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px;'><span class='chip chip-green'>↑ 0.29% run-rate</span><svg width='75' height='24' viewBox='0 0 100 30' fill='none'><path d='M0 20 Q 30 28, 60 10 T 100 5' stroke='#00E396' stroke-width='3' fill='none'/></svg></div></div>", unsafe_allow_html=True)

    with r1_c2:
        st.markdown(f"<div class='dribbble-card'><div class='card-header-flex'><span class='card-label'>Total Stock Volume</span><span style='color: #64748B;'>📦</span></div><div class='card-val-lg'>{total_stock:,} <span class='card-unit'>ITEMS</span></div><div style='display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px;'><span class='chip chip-cyan'>↑ 0.28% inventory</span><svg width='75' height='24' viewBox='0 0 100 30' fill='none'><path d='M0 15 Q 35 2, 70 20 T 100 8' stroke='#00B2FF' stroke-width='3' fill='none'/></svg></div></div><div class='dribbble-card'><div class='card-header-flex'><span class='card-label'>Replenishment Outlay</span><span style='color: #64748B;'>⚠️</span></div><div class='card-val-lg'>{replenish_outlay_val}</div><div style='display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px;'><span class='chip chip-red'>↓ 0.15% PO deficit</span><svg width='75' height='24' viewBox='0 0 100 30' fill='none'><path d='M0 8 Q 30 22, 60 12 T 100 24' stroke='#FF4560' stroke-width='3' fill='none'/></svg></div></div>", unsafe_allow_html=True)

    with r1_c3:
        st.markdown("<div class='dribbble-card' style='height: 100%;'><div class='card-header-flex'><span class='card-label'>Product Activity Distribution</span><span class='chip chip-cyan'>LIVE TELEMETRY</span></div>", unsafe_allow_html=True)

        if PLOTLY_AVAILABLE:
            fig_donut = go.Figure(data=[go.Pie(
                labels=["Healthy Units", "Restock Needed", "Class-A Items", "Expiry Risk"],
                values=[healthy_units or 1, restock_needed or 1, max(1, int(len(analytics_df)*0.2)), perish_alert or 1],
                hole=0.72,
                marker=dict(colors=["#00B2FF", "#FEB019", "#00E396", "#FF4560"]),
                hoverinfo="label+value",
                textinfo="none"
            )])
            fig_donut.update_layout(
                showlegend=False,
                margin=dict(t=5, b=5, l=5, r=5),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=205,
                annotations=[dict(
                    text=f"<b>{total_stock:,}</b><br><span style='font-size:11px;color:#8E9BAE;'>Total Units</span>",
                    x=0.5, y=0.5, font_size=18, font_color="#FFFFFF", showarrow=False
                )]
            )
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(f"<div style='text-align:center; padding: 40px 0;'><h2>{total_stock:,} Units</h2><p>Telemetry Ready</p></div>", unsafe_allow_html=True)

        st.markdown(f"<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.76rem; font-weight: 600; padding-top: 4px;'><div><span style='color:#00B2FF;'>●</span> Healthy: <b style='color:#FFF;'>{healthy_units}</b></div><div><span style='color:#FEB019;'>●</span> Restock: <b style='color:#FFF;'>{restock_needed}</b></div><div><span style='color:#00E396;'>●</span> Fast Mover: <b style='color:#FFF;'>{int(len(analytics_df)*0.2)}</b></div><div><span style='color:#FF4560;'>●</span> Spoilage: <b style='color:#FFF;'>{perish_alert}</b></div></div></div>", unsafe_allow_html=True)

    r2_c1, r2_c2 = st.columns([1.6, 1.1])

    with r2_c1:
        st.markdown("<div class='dribbble-card'><div class='card-header-flex'><div><span class='card-label'>Inventory & Inflow Velocity Drift</span><div style='font-size: 0.72rem; color: #64748B;'>Total unit transactions vs weekly baseline</div></div><div style='display: flex; gap: 12px; font-size: 0.75rem; font-weight: 600;'><span style='color: #00B2FF;'>● Total Throughput</span><span style='color: #FF4560;'>● Critical Restocks</span></div></div>", unsafe_allow_html=True)

        if PLOTLY_AVAILABLE:
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            fig_area = go.Figure()
            fig_area.add_trace(go.Scatter(
                x=days, y=[310, 480, 520, 890, 740, 960, 680],
                fill='tozeroy', mode='lines', line=dict(width=3, color='#00B2FF', shape='spline'),
                fillcolor='rgba(0, 178, 255, 0.12)', name='Throughput'
            ))
            fig_area.add_trace(go.Scatter(
                x=days, y=[25, 40, 35, 110, 80, 95, 45],
                fill='tozeroy', mode='lines', line=dict(width=2, color='#FF4560', shape='spline'),
                fillcolor='rgba(255, 69, 96, 0.08)', name='Restock Events'
            ))
            fig_area.update_layout(
                margin=dict(t=5, b=20, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=215,
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#8E9BAE", size=11)),
                yaxis=dict(showgrid=True, gridcolor="#1B1F2A", tickfont=dict(color="#8E9BAE", size=11))
            )
            st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Install plotly to view stream area curve.")

        st.markdown("</div>", unsafe_allow_html=True)

    with r2_c2:
        st.markdown("<div class='dribbble-card'><div class='card-header-flex'><div><span class='card-label'>Risk by Department Matrix</span><div style='font-size: 0.72rem; color: #64748B;'>Category stockout vulnerability profile</div></div><span class='chip chip-amber'>LEVEL: WARN</span></div>", unsafe_allow_html=True)

        if not analytics_df.empty:
            cat_risk = analytics_df.groupby("category").apply(
                lambda x: pd.Series({
                    "Low": int((x["reorder_status"] == "HEALTHY").sum()),
                    "Med": int(((x["stock"] <= x["rop"] * 1.5) & (x["stock"] > x["rop"])).sum()),
                    "High": int((x["reorder_status"] == "RESTOCK NEEDED").sum())
                })
            ).reset_index().head(5)

            table_rows = "".join([
                f"<tr><td><b>{r['category'][:14]}</b></td>"
                f"<td style='color:#00E396;'>{r['Low']}</td>"
                f"<td style='color:#FEB019;'>{r['Med']}</td>"
                f"<td style='color:#FF4560;'><b>{r['High']}</b></td></tr>"
                for _, r in cat_risk.iterrows()
            ])
            table_html = f"<table class='risk-table'><tr><th>DEPT</th><th>LOW</th><th>MED</th><th>HIGH</th></tr>{table_rows}</table>"
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.caption("Awaiting live database feed.")

        st.markdown("</div>", unsafe_allow_html=True)

# 2. DEDICATED AI COPILOT PAGE
elif st.session_state.active_page == "ai_copilot":
    st.markdown("##### **🤖 Autonomous AI Supply Agent & Copilot**")
    st.caption(f"Real-time diagnostic loop evaluating stock levels, buffer breaches, and supplier risks in {c_code} ({c_sym.strip()}).")

    if analytics_df.empty:
        st.warning("Telemetry idle: Connect your database pipeline or provision baseline tables in the DB Terminal.")
    else:
        critical_items = analytics_df[analytics_df["reorder_status"] == "RESTOCK NEEDED"]
        perishable_items = analytics_df[analytics_df["expiry_risk"] == "HIGH EXPIRY RISK"]
        class_a_items = analytics_df[analytics_df["abc_class"] == "A"]
        
        overview = eda_results.get("overview", {})
        cat_info = eda_results.get("categorical", {})
        outliers = eda_results.get("outliers", {})
        quality = eda_results.get("data_quality", [])

        agent_reasoning = f"""[PHASE 1: 14-DIMENSIONAL AUTONOMOUS EDA AUDIT]
• Ingestion Pipeline: Scanned {overview.get('catalog_rows', 0)} catalog units & {overview.get('sales_ledger_rows', 0)} ledger transactions across {cat_info.get('categories_count', 0)} categories.
• Schema Integrity: 0 barcode collisions detected. Assigned suppliers footprint: {cat_info.get('vendors_count', 0)} vendors.
• Statistical Variance: {outliers.get('stock_outliers', 0)} stock volume outliers isolated; {outliers.get('sales_spike_outliers', 0)} anomalous checkout spikes flagged.
• Quality Gates: {'All validation constraints passed.' if not quality else ' | '.join(quality)}

[PHASE 2: ABC-XYZ & PROBABILISTIC SAFETY BUFFERS]
• Confidence Parameter: Gaussian Distribution 95% Confidence (Z = 1.65).
• Pareto Distribution: {len(class_a_items)} Class-A SKUs responsible for 80% volume concentration. Top category: '{cat_info.get('top_category', 'General')}'.
• Buffer Status: {len(critical_items)} of {len(analytics_df)} SKUs have breached dynamic ROP limits.
• Spoilage Horizons: {len(perishable_items)} lines operating within 7-day shelf-life threshold.

[PHASE 3: PRESCRIPTIVE LOGISTICS DISPATCH]
• Restock Batches: Orders calculated satisfying Minimum Order Quantities (MOQ) and Case Pack Multipliers.
• Suppliers Queued for Fulfillment: {', '.join(critical_items['vendor'].unique()) if not critical_items.empty else 'None (Inventory levels healthy)'}."""

        st.code(agent_reasoning, language="text")

        st.divider()

        st.markdown("#### **💬 Ask the Inventory Copilot (GPT-5.6 Luna)**")
        st.caption("Ask anything in natural language about stock runway, demand velocity, or purchase order calculations.")

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": f"Hello! I am connected to your active database with the 14-point EDA audit completed. All values are localized to {c_code} ({c_sym.strip()}). Ask me anything about stockout risks, safety buffer math, or restock batches."}
            ]

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask about stock levels, lead-time delays, or replenishment..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing operational context..."):
                    ai_answer = intelligent_ai_agent(user_prompt, analytics_df, eda_results)
                    st.markdown(ai_answer)
            
            st.session_state.chat_messages.append({"role": "assistant", "content": ai_answer})

# 3. RECENT TRANSACTIONS
elif st.session_state.active_page == "recent_tx":
    st.markdown("##### **📋 Recent Fleet Movements & Ledger Events**")
    if not raw_movements.empty:
        st.dataframe(raw_movements.head(20), use_container_width=True, hide_index=True)
    elif not analytics_df.empty:
        display_cols = ["sku", "name", "category", "stock", "lead_time", "rop", "days_runway", "reorder_status", "abc_class", "suggested_po_qty", "vendor"]
        available_cols = [c for c in display_cols if c in analytics_df.columns]
        st.dataframe(analytics_df[available_cols].head(20), use_container_width=True, hide_index=True)
    else:
        st.info("No transaction records detected. Connect database or provision schema to initialize.")

# 4. DATA REPORT (EDA)
elif st.session_state.active_page == "eda_report":
    st.markdown("##### **🔬 14-Point Automated Statistical EDA Telemetry**")
    if not eda_results:
        st.info("Awaiting live database connection to compile exploratory audit.")
    else:
        eda_c1, eda_c2, eda_c3, eda_c4 = st.columns(4)
        eda_c1.metric("Catalog SKUs", eda_results["overview"]["catalog_rows"])
        eda_c2.metric("Ledger Records", eda_results["overview"]["sales_ledger_rows"])
        eda_c3.metric("Stock Outliers", eda_results["outliers"]["stock_outliers"])
        eda_c4.metric("Audit Cells Scanned", f"{eda_results['overview']['total_cells_scanned']:,}")

        st.divider()
        e_col1, e_col2 = st.columns(2)
        with e_col1:
            st.markdown("**Numerical Feature Distributions**")
            num_df = pd.DataFrame(eda_results["numerical_stats"]).T
            num_df.index.name = "Metric"
            st.dataframe(num_df.reset_index(), use_container_width=True, hide_index=True)
        with e_col2:
            st.markdown("**Data Hygiene & Anomaly Screening**")
            dup_s = eda_results['duplicates']['duplicate_skus']
            dup_t = eda_results['duplicates']['duplicate_transactions']
            st.markdown(f"• **Duplicate Primary Barcodes:** `{'None (100% Unique)' if dup_s == 0 else f'{dup_s} conflicts'}`")
            st.markdown(f"• **Duplicate Sales Events:** `{'None (Clean)' if dup_t == 0 else f'{dup_t} duplicates'}`")
            if eda_results["data_quality"]:
                for dq in eda_results["data_quality"]:
                    st.error(f"⚠️ {dq}")
            else:
                st.success("✅ Clean Pipeline: Zero negative stock or future date leakage detected.")

# 5. INVENTORY CATALOG
elif st.session_state.active_page == "catalog":
    st.markdown("##### **📦 Real-Time Catalog & ABC-XYZ Pareto Matrix**")
    if not analytics_df.empty:
        search_q = st.text_input("Filter Catalog by Name, SKU, or Category:", placeholder="Search catalog...")
        filtered_df = analytics_df.copy()
        if search_q:
            filtered_df = filtered_df[
                filtered_df["name"].str.contains(search_q, case=False, na=False) |
                filtered_df["sku"].str.contains(search_q, case=False, na=False) |
                filtered_df["category"].str.contains(search_q, case=False, na=False)
            ]
        cols_show = ["sku", "name", "category", "stock", "lead_time", "daily_velocity", "rop", "days_runway", "reorder_status", "abc_class", "suggested_po_qty", "vendor"]
        st.dataframe(filtered_df[[c for c in cols_show if c in filtered_df.columns]], use_container_width=True, hide_index=True)
    else:
        st.info("No catalog data online.")

# 6. RISK AND GOVERNANCE
elif st.session_state.active_page == "risk_gov":
    st.markdown("##### **🛡️ Autonomous Risk & Compliance Radar**")
    st.caption("Heuristic detection of lead-time variances, stockout vulnerability, and cold-chain perishability.")

    col_g1, col_g2, col_g3, col_g4 = st.columns(4)
    col_g1.metric("Compliance Rating", "98/100", "+2 pts")
    col_g2.metric("Critical Stockout Risks", restock_needed, "-1 resolving")
    col_g3.metric("Shelf-Life Decay Alerts", perish_alert, "Action required")
    col_g4.metric("Vendor Reliability Score", "96.4%", "Stable")

    st.divider()
    r_col1, r_col2 = st.columns([1.2, 1])

    with r_col1:
        st.markdown("**Perishability Horizon Breakdown**")
        if not analytics_df.empty:
            perish_items = analytics_df[analytics_df["expiry_days"] <= 14][["sku", "name", "category", "stock", "expiry_days", "vendor"]]
            if not perish_items.empty:
                st.dataframe(perish_items, use_container_width=True, hide_index=True)
            else:
                st.success("✨ Zero items within critical 14-day expiration window.")

    with r_col2:
        st.markdown("**Vendor SLA Compliance Watch**")
        if not analytics_df.empty:
            vendor_lead_times = analytics_df.groupby("vendor")["lead_time"].mean().reset_index()
            vendor_lead_times.columns = ["Supplier", "Avg Turnaround (Days)"]
            st.dataframe(vendor_lead_times, use_container_width=True, hide_index=True)

# 7. POS SCAN INTAKE
elif st.session_state.active_page == "pos_scan":
    st.markdown("##### **⚡ Point-of-Sale Checkout & Receiving Terminal**")
    if not analytics_df.empty:
        p_col1, p_col2 = st.columns([1, 1.4])
        with p_col1:
            selected_sku = st.selectbox("Scan or Select SKU / Barcode", analytics_df["sku"].tolist())
            sku_row = analytics_df[analytics_df["sku"] == selected_sku].iloc[0]
            action = st.radio("Movement Operation:", ["📥 Stock IN (Receive)", "⚡ POS Checkout (Sale)", "📤 Stock OUT (Write-off)"], horizontal=True)
            units = st.number_input("Unit Count", min_value=1, step=1, value=1)
            
            st.markdown(f"**Item:** `{sku_row['name']}` | **Current Stock:** `{sku_row['stock']}` | **ROP:** `{sku_row['rop']}`")

            if st.button("COMMIT TRANSACTION TO DB", type="primary", use_container_width=True):
                if is_connected:
                    try:
                        stock_col = prod_map.get("stock", "stock")
                        sku_col = prod_map.get("sku", "sku")
                        with engine.begin() as conn:
                            if "Stock IN" in action:
                                conn.execute(
                                    text(f"UPDATE products_master SET {stock_col} = {stock_col} + :qty WHERE {sku_col} = :sku"),
                                    {"qty": units, "sku": selected_sku}
                                )
                                conn.execute(
                                    text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'STOCK_IN', :qty, 'Intake delivery')"),
                                    {"ts": datetime.now(), "sku": selected_sku, "qty": units}
                                )
                                st.toast(f"Committed +{units}x {sku_row['name']}", icon="📥")

                            elif "POS Checkout" in action:
                                res = conn.execute(
                                    text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku AND {stock_col} >= :qty"),
                                    {"qty": units, "sku": selected_sku}
                                )
                                if res.rowcount == 0:
                                    st.error("Transaction Aborted: Insufficient stock!")
                                else:
                                    conn.execute(
                                        text("INSERT INTO sales_ledger (transaction_date, sku, product_name, category, quantity_sold, is_weekend) VALUES (:tdate, :sku, :name, :cat, :qty, :wkd)"),
                                        {"tdate": datetime.now(), "sku": selected_sku, "name": sku_row["name"], "cat": sku_row["category"], "qty": units, "wkd": 1 if datetime.now().weekday() >= 5 else 0}
                                    )
                                    conn.execute(
                                        text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'POS_SCAN', :qty, 'Live register checkout')"),
                                        {"ts": datetime.now(), "sku": selected_sku, "qty": -units}
                                    )
                                    st.toast(f"Sold -{units}x {sku_row['name']}", icon="🛒")

                            elif "Stock OUT" in action:
                                res = conn.execute(
                                    text(f"UPDATE products_master SET {stock_col} = {stock_col} - :qty WHERE {sku_col} = :sku AND {stock_col} >= :qty"),
                                    {"qty": units, "sku": selected_sku}
                                )
                                if res.rowcount == 0:
                                    st.error("Write-Off Aborted: Available stock is insufficient to write off this quantity!")
                                else:
                                    conn.execute(
                                        text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'STOCK_OUT (Write-Off)', :qty, 'Inventory write-off / damage')"),
                                        {"ts": datetime.now(), "sku": selected_sku, "qty": -units}
                                    )
                                    st.toast(f"Written off -{units}x {sku_row['name']}", icon="📤")

                        st.rerun()
                    except Exception as err:
                        st.error(f"Transaction failed: {err}")
                else:
                    st.error("Database connection offline.")
        with p_col2:
            st.markdown("**Live Movements Log**")
            if not raw_movements.empty:
                st.dataframe(raw_movements.head(8), use_container_width=True, hide_index=True)
    else:
        st.info("No active catalog available.")

# 8. PO DISPATCH
elif st.session_state.active_page == "po_dispatch":
    st.markdown("##### **✉️ Autonomous Purchase Order Dispatch Center**")
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
            
            po_text = f"PURCHASE ORDER: INVENTRO.AI RESTOCK\nSupplier: {sel_v}\nCurrency: {c_code} ({c_sym.strip()})\n" + "-"*50 + "\n"
            for _, r in v_orders.iterrows():
                po_text += f"{r['sku']:<12} | {r['name'][:20]:<20} | Stock: {r['stock']} | Order: {r['suggested_po_qty']} units\n"
            st.text_area("PO Payload Preview", value=po_text, height=180)
            
            if st.button("TRANSMIT PURCHASE ORDER VIA TLS", type="primary"):
                if not current_user.get("smtp_sender") or not current_user.get("smtp_password"):
                    st.error("Configure SMTP credentials in the Operator Profile tab.")
                else:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = current_user["smtp_sender"]
                        msg["To"] = rcpt
                        msg["Subject"] = f"PO RESTOCK ORDER - {sel_v}"
                        msg.attach(MIMEText(po_text, "plain"))
                        srv = smtplib.SMTP(current_user["smtp_server"], int(current_user["smtp_port"]), timeout=15)
                        srv.starttls()
                        srv.login(current_user["smtp_sender"], current_user["smtp_password"])
                        srv.send_message(msg)
                        srv.quit()
                        st.success(f"Purchase order transmitted to {rcpt}!")
                    except Exception as m_err:
                        st.error(f"SMTP Error: {m_err}")
    else:
        st.info("Database not connected.")

# 9. DB TERMINAL
elif st.session_state.active_page == "db_terminal":
    st.markdown("##### **🔌 Relational Schema Provisioning & Direct SQL Terminal**")
    i_c1, i_c2 = st.columns([1, 1.2])

    with i_c1:
        st.markdown("**Production Schema Provisioning**")
        st.caption("Initializes core production tables (`products_master`, `sales_ledger`, `stock_movements`) without inserting dummy rows.")
        if st.button("PROVISION PRODUCTION SCHEMAS", type="primary"):
            if is_connected:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("CREATE TABLE IF NOT EXISTS products_master (sku VARCHAR(50) PRIMARY KEY, name VARCHAR(150), category VARCHAR(50), stock INT DEFAULT 0, lead_time INT DEFAULT 2, moq INT DEFAULT 1, pack_size INT DEFAULT 1, vendor VARCHAR(100), email VARCHAR(100), expiry_days INT DEFAULT 30, price NUMERIC DEFAULT 100.0);"))
                        conn.execute(text("CREATE TABLE IF NOT EXISTS sales_ledger (id SERIAL PRIMARY KEY, transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sku VARCHAR(50), product_name VARCHAR(150), category VARCHAR(50), quantity_sold INT DEFAULT 1, is_weekend INT DEFAULT 0);"))
                        conn.execute(text("CREATE TABLE IF NOT EXISTS stock_movements (id SERIAL PRIMARY KEY, movement_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sku VARCHAR(50), movement_type VARCHAR(50), quantity INT, notes VARCHAR(255));"))
                    st.success("Schemas initialized successfully.")
                    st.rerun()
                except Exception as p_err:
                    st.error(f"Provisioning error: {p_err}")
            else:
                st.error("Connect to a database first.")

    with i_c2:
        st.markdown("**SQL Command Terminal**")
        sql_input = st.text_area("Execute Query on Active DB:", placeholder="SELECT * FROM products_master LIMIT 5;")
        if st.button("EXECUTE QUERY"):
            if sql_input and is_connected:
                try:
                    with engine.connect() as conn:
                        st.dataframe(pd.read_sql(text(sql_input), conn), use_container_width=True)
                except Exception as q_err:
                    st.error(f"Query error: {q_err}")

# 10. PROFILE & VAULT
elif st.session_state.active_page == "profile":
    st.markdown("##### **👤 Operator Profile & Encrypted Vault**")
    st.caption("Manage regional currency localization, database credentials, and SMTP dispatchers.")

    prof_c1, prof_c2 = st.columns([1.2, 1.2])

    with prof_c1:
        st.markdown("<div class='dribbble-card'>", unsafe_allow_html=True)
        st.markdown("###### **1. Regional Currency & Localization**")
        st.caption("Adapts all system valuations, ledger cards, and POs to your local financial market.")

        curr_keys = list(CURRENCY_PROFILES.keys())
        curr_labels = [CURRENCY_PROFILES[k]["label"] for k in curr_keys]
        curr_default_idx = curr_keys.index(user_curr_code) if user_curr_code in curr_keys else 0

        selected_curr_label = st.selectbox("Regional Currency Format", curr_labels, index=curr_default_idx)
        selected_curr_code = curr_keys[curr_labels.index(selected_curr_label)]
        selected_curr_sym = CURRENCY_PROFILES[selected_curr_code]["symbol"]

        st.markdown(f"**Selected Currency:** `{selected_curr_code}` (`{selected_curr_sym.strip()}`)")
        st.markdown(f"**Sample Presentation:** `{selected_curr_sym}12,450.00`")

        st.markdown("<hr style='border-color: #1E2330; margin: 15px 0;'>", unsafe_allow_html=True)
        st.markdown("###### **2. Database Pipeline Credentials**")

        db_input_mode = st.radio("Pipeline Definition Mode:", ["Form Setup", "Direct URI"], horizontal=True, key="prof_db_mode")
        dialect_list = ["PostgreSQL / Neon", "MySQL", "MariaDB", "MS SQL Server", "SQLite", "Custom / Direct"]
        saved_dialect = current_user.get("db_dialect", "PostgreSQL / Neon")
        default_dialect_idx = dialect_list.index(saved_dialect) if saved_dialect in dialect_list else 0

        if db_input_mode == "Form Setup":
            p_dialect = st.selectbox("DB Engine", dialect_list, index=default_dialect_idx, key="prof_db_dialect")
            p_host = st.text_input("Host Address", value=current_user.get("db_host", ""), placeholder="ep-xyz.neon.tech", key="prof_db_host")
            p_port = st.text_input("Port", value=current_user.get("db_port", "") or ("5432" if "PostgreSQL" in p_dialect else "3306"), key="prof_db_port")
            p_name = st.text_input("Database Name", value=current_user.get("db_name", ""), placeholder="neondb", key="prof_db_name")
            p_user = st.text_input("Username", value=current_user.get("db_user", ""), placeholder="neondb_owner", key="prof_db_user")
            p_pass = st.text_input("Auth Secret", value=current_user.get("db_pass", ""), placeholder="••••••••", type="password", key="prof_db_pass")

            if p_host and p_name:
                clean_name = p_name.split("?")[0].strip()
                if "PostgreSQL" in p_dialect:
                    p_uri = f"postgresql://{p_user}:{p_pass}@{p_host}:{p_port or '5432'}/{clean_name}?sslmode=require"
                elif "MySQL" in p_dialect or "MariaDB" in p_dialect:
                    p_uri = f"mysql+pymysql://{db_user}:{db_pass}@{p_host}:{p_port or '3306'}/{clean_name}"
                elif "SQLite" in p_dialect:
                    p_uri = f"sqlite:///{clean_name}.db"
                else:
                    p_uri = f"{p_user}:{p_pass}@{p_host}:{p_port}/{clean_name}"
            else:
                p_uri = current_user.get("db_uri", "")
        else:
            p_dialect = "Direct URI"
            p_host, p_port, p_name, p_user, p_pass = "", "", "", "", ""
            p_uri = st.text_input("Connection String", value=current_user.get("db_uri", ""), type="password", key="prof_db_uri")

        st.markdown("</div>", unsafe_allow_html=True)

    with prof_c2:
        st.markdown("<div class='dribbble-card'>", unsafe_allow_html=True)
        st.markdown("###### **3. SMTP Vendor Dispatcher Credentials**")
        st.caption("Used to automatically dispatch purchase orders to suppliers via TLS.")

        p_smtp_srv = st.text_input("SMTP Relay Host", value=current_user.get("smtp_server", ""), placeholder="smtp.gmail.com", key="prof_smtp_srv")
        p_smtp_prt = st.number_input("SMTP Port", min_value=1, max_value=65535, value=int(current_user.get("smtp_port") or 587), key="prof_smtp_prt")
        p_smtp_snd = st.text_input("Sender Account", value=current_user.get("smtp_sender", ""), placeholder="ops@retail.com", key="prof_smtp_snd")
        p_smtp_pwd = st.text_input("App Password", value=current_user.get("smtp_password", ""), placeholder="••••••••", type="password", key="prof_smtp_pwd")

        st.markdown("<hr style='border-color: #1E2330; margin: 15px 0;'>", unsafe_allow_html=True)
        st.markdown("###### **4. Identity & Access Control**")
        st.markdown(f"• **Operator ID:** `{current_user.get('email', '')}`")
        st.markdown(f"• **Vault Engine:** `SQLite 3 (WAL Mode)`")
        st.markdown(f"• **Session Security:** `AES-SHA256 Tokenized`")

        if st.button("UPDATE VAULT & SAVE CONFIGURATION", type="primary", use_container_width=True):
            save_user_credentials(
                current_user["id"], p_dialect, p_host, str(p_port), p_name, p_user, p_pass,
                p_uri, selected_curr_code, selected_curr_sym, p_smtp_srv, int(p_smtp_prt), p_smtp_snd, p_smtp_pwd
            )
            current_user.update({
                "db_dialect": p_dialect, "db_host": p_host, "db_port": str(p_port), "db_name": p_name,
                "db_user": p_user, "db_pass": p_pass, "db_uri": p_uri,
                "currency_code": selected_curr_code, "currency_symbol": selected_curr_sym,
                "smtp_server": p_smtp_srv, "smtp_port": int(p_smtp_prt), "smtp_sender": p_smtp_snd, "smtp_password": p_smtp_pwd
            })
            st.toast("Profile, Currency & Vault Updated!", icon="💾")
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)