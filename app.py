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
    page_title="Eclaira | Supply Chain Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #0A0C0E !important;
    color: #E2E8F0 !important;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

[data-testid="stSidebar"] {
    background-color: #08090B !important;
    border-right: 1px solid #14171D !important;
    padding-top: 0.8rem !important;
}
[data-testid="stSidebar"] hr {
    border-color: #14171D !important;
}

/* CARDS & PANELS */
.eclaira-card {
    background: #111317;
    border: 1px solid #1A1E24;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    position: relative;
}

.eclaira-stat-box {
    background: #111317;
    border: 1px solid #1A1E24;
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 105px;
}
.eclaira-stat-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748B;
    margin-bottom: 4px;
}
.eclaira-stat-val {
    font-size: 1.45rem;
    font-weight: 800;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.eclaira-stat-sub {
    font-size: 0.70rem;
    color: #475569;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* PILLS & BADGES */
.delta-up {
    color: #10B981;
    font-weight: 700;
    font-size: 0.70rem;
    display: inline-flex;
    align-items: center;
}
.delta-down {
    color: #EF4444;
    font-weight: 700;
    font-size: 0.70rem;
    display: inline-flex;
    align-items: center;
}
.eclaira-tag {
    background: rgba(255, 107, 0, 0.12);
    color: #FF6B00;
    border: 1px solid rgba(255, 107, 0, 0.25);
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
}

/* CUSTOM BARS */
.segment-bar-wrapper {
    width: 100%;
    height: 12px;
    background: #1A1E24;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    margin: 12px 0 14px 0;
}
.seg-bar-1 { background: #FF6B00; height: 100%; }
.seg-bar-2 { background: #D97706; height: 100%; }
.seg-bar-3 { background: #334155; height: 100%; }

.seg-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.72rem;
    padding: 5px 0;
    border-bottom: 1px solid #14171D;
}

/* NAVIGATION BUTTONS */
.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: 1px solid #1A1E24 !important;
    background: #0E1013 !important;
    color: #94A3B8 !important;
    transition: all 0.15s ease !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 6px 12px !important;
}
.stButton > button:hover {
    border-color: #FF6B00 !important;
    color: #FF6B00 !important;
}
.stButton > button[kind="primary"] {
    background: #FF6B00 !important;
    border-color: #FF6B00 !important;
    color: #FFFFFF !important;
    box-shadow: 0 0 14px rgba(255, 107, 0, 0.2) !important;
}

input, select, textarea, [data-baseweb="select"] {
    background-color: #0E1013 !important;
    border-color: #1A1E24 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #1A1E24 !important;
    border-radius: 8px !important;
    background: #111317 !important;
}

/* ANIMATIONS */
@keyframes fadeIn {
    0% { opacity: 0; transform: translateY(14px); }
    100% { opacity: 1; transform: translateY(0); }
}
.fade-entrance {
    animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# SQLITE VAULT ENGINE (WAL CONCURRENCY)
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
                    full_name TEXT DEFAULT 'Judha Maygustya',
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
            cols = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
            for name, defn in [
                ("full_name", "TEXT DEFAULT 'Judha Maygustya'"),
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
            ]:
                if name not in cols:
                    c.execute(f"ALTER TABLE users ADD COLUMN {name} {defn}")
            conn.commit()
    except Exception as e:
        st.error(f"Vault DB Error: {e}")

init_vault_db()

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def create_user_account(email: str, password: str, full_name: str = "Judha Maygustya") -> tuple[bool, str]:
    clean = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)", (clean, hash_pw(password), full_name))
            conn.commit()
            return True, "Account registered successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, str(e)

def verify_user(email: str, password: str):
    clean = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, email, full_name, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, 
                       currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password
                FROM users WHERE email = ? AND password_hash = ?
            """, (clean, hash_pw(password)))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0], "email": row[1], "full_name": row[2] or "Judha Maygustya",
                    "db_dialect": row[3] or "PostgreSQL / Neon", "db_host": row[4] or "",
                    "db_port": row[5] or "5432", "db_name": row[6] or "", "db_user": row[7] or "",
                    "db_pass": row[8] or "", "db_uri": row[9] or "", "currency_code": row[10] or "USD",
                    "currency_symbol": row[11] or "$", "smtp_server": row[12] or "",
                    "smtp_port": row[13] or 587, "smtp_sender": row[14] or "", "smtp_password": row[15] or ""
                }
    except Exception:
        return None
    return None

def fetch_user_by_email(email: str):
    clean = email.strip().lower()
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, email, full_name, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, currency_code, currency_symbol FROM users WHERE email = ?", (clean,))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0], "email": row[1], "full_name": row[2] or "Judha Maygustya",
                    "db_dialect": row[3] or "PostgreSQL / Neon", "db_host": row[4] or "",
                    "db_port": row[5] or "5432", "db_name": row[6] or "", "db_user": row[7] or "",
                    "db_pass": row[8] or "", "db_uri": row[9] or "", "currency_code": row[10] or "USD",
                    "currency_symbol": row[11] or "$"
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
        msg["From"] = f"Eclaira Operations <{smtp_snd}>"
        msg["To"] = clean_recipient
        msg["Reply-To"] = smtp_snd
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="eclaira.ai")

        html_body = f"""\
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background-color: #0A0C0E; margin: 0; padding: 24px; color: #E2E8F0;">
          <div style="max-width: 520px; background-color: #111317; border: 1px solid #1A1E24; border-radius: 12px; padding: 28px; margin: 0 auto;">
            <div style="font-size: 20px; font-weight: 800; color: #FF6B00; margin-bottom: 16px;">⚡ ECLAIRA PLATFORM</div>
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
    clean = email.strip().lower()
    otp_code = f"{random.randint(100000, 999999)}"
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (otp_code, clean))
            conn.commit()
            return (True, otp_code) if c.rowcount > 0 else (False, "Account not found.")
    except Exception as e:
        return False, str(e)

def generate_reset_token(email: str) -> tuple[bool, str]:
    clean = email.strip().lower()
    token = secrets.token_urlsafe(24)
    try:
        with get_vault_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (token, clean))
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
                return False, "Invalid or expired reset token."
            c.execute("UPDATE users SET password_hash = ?, reset_token = '' WHERE email = ?", (hash_pw(new_password), row[0]))
            conn.commit()
            return True, "Password reset successful. Log in now."
    except Exception as e:
        return False, str(e)

# ==========================================
# AUTHENTICATION GATEWAY
# ==========================================
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

active_token = st.query_params.get("reset_token", None)

if not st.session_state.authenticated_user:
    st.markdown("""
        <div class='fade-entrance' style='text-align: center; padding: 45px 0 20px 0;'>
            <div style='display: inline-flex; align-items: center; gap: 8px; margin-bottom: 6px;'>
                <span style='background: #FF6B00; border-radius: 8px; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; color: #FFF; font-weight:800;'>⚡</span>
                <span style='font-size: 1.6rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;'>Eclaira</span>
            </div>
            <p style='color: #64748B; font-size: 0.9rem; margin: 0;'>Supply Chain & Enterprise Retail Operations</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.25, 1])
    with c2:
        st.markdown("<div class='eclaira-card fade-entrance'>", unsafe_allow_html=True)
        if active_token:
            st.markdown("##### 🔐 Set New Password")
            npw = st.text_input("New Password", type="password", key="npw")
            cpw = st.text_input("Confirm New Password", type="password", key="cpw")
            if st.button("UPDATE PASSWORD", type="primary", use_container_width=True):
                if npw == cpw and len(npw) >= 6:
                    ok, msg = reset_password_with_token(active_token, npw)
                    if ok:
                        st.success(msg)
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Ensure passwords match and exceed 5 characters.")
        else:
            t_in, t_up = st.tabs(["🔐 Sign In", "📝 Create Profile"])
            with t_in:
                log_em = st.text_input("Operator Work Email", key="lem")
                log_pw = st.text_input("Password", type="password", key="lpw")
                if st.button("AUTHENTICATE TO CONSOLE", type="primary", use_container_width=True):
                    usr = verify_user(log_em, log_pw)
                    if usr:
                        st.session_state.authenticated_user = usr
                        st.rerun()
                    else:
                        st.error("Authentication rejected.")

                with st.expander("Forgot password?"):
                    rem = st.text_input("Registered Email", key="rem")
                    if rem:
                        u_chk = fetch_user_by_email(rem)
                        if u_chk:
                            m = st.radio("Recovery Mode:", ["Send 6-Digit OTP", "Send Password Reset Link"], key="m_rad")
                            if "OTP" in m:
                                if st.button("DISPATCH OTP", use_container_width=True):
                                    ok, code = set_user_otp(rem)
                                    if ok:
                                        dispatch_platform_email(rem, "Eclaira • Login Passcode", f"Your 6-digit passcode is: {code}")
                                        st.success(f"Dispatched to {rem}.")
                                i_code = st.text_input("Enter 6-Digit OTP", key="ic")
                                if st.button("VERIFY & SIGN IN", use_container_width=True):
                                    with get_vault_connection() as conn:
                                        c = conn.cursor()
                                        c.execute("SELECT reset_token FROM users WHERE email = ?", (rem.strip().lower(),))
                                        r = c.fetchone()
                                        if r and r[0] == i_code.strip():
                                            c.execute("UPDATE users SET reset_token = '' WHERE email = ?", (rem.strip().lower(),))
                                            conn.commit()
                                            st.session_state.authenticated_user = u_chk
                                            st.rerun()
                                        else:
                                            st.error("Invalid passcode.")
                            else:
                                if st.button("DISPATCH LINK", use_container_width=True):
                                    ok, tok = generate_reset_token(rem)
                                    if ok:
                                        link = f"https://inventro.streamlit.app/?reset_token={tok}"
                                        dispatch_platform_email(rem, "Eclaira • Reset Action", f"Reset URL: {link}")
                                        st.success("Link transmitted.")
            with t_up:
                nem = st.text_input("Work Email", key="nem")
                nfn = st.text_input("Full Name", value="Judha Maygustya", key="nfn")
                np1 = st.text_input("Password", type="password", key="np1")
                np2 = st.text_input("Confirm", type="password", key="np2")
                if st.button("REGISTER OPERATOR", use_container_width=True):
                    if np1 == np2 and len(np1) >= 6:
                        ok, m = create_user_account(nem, np1, nfn)
                        if ok:
                            st.success("Registered. Sign in above.")
                        else:
                            st.error(m)
                    else:
                        st.warning("Passwords must match and have at least 6 characters.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

current_user = st.session_state.authenticated_user
c_code = current_user.get("currency_code", "USD")
c_sym = "$" if c_code == "USD" else "₹"

def fmt_c(v: float) -> str:
    return f"{c_sym}{v:,.2f}"

if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

# ==========================================
# DATABASE PIPELINE INGESTION
# ==========================================
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

engine = get_db_engine(current_user.get("db_uri", ""))

df_products, df_sales = pd.DataFrame(), pd.DataFrame()
if engine:
    try:
        with engine.connect() as conn:
            insp = inspect(engine)
            tbls = insp.get_table_names()
            ptbl = next((t for t in tbls if t.lower() in ["products_master", "products", "inventory", "items"]), None)
            if ptbl:
                df_products = pd.read_sql(text(f"SELECT * FROM {ptbl}"), conn)
            stbl = next((t for t in tbls if any(k in t.lower() for k in ["sales_ledger", "sales", "order", "txn"])), None)
            if stbl:
                df_sales = pd.read_sql(text(f"SELECT * FROM {stbl} ORDER BY 1 DESC LIMIT 2000"), conn)
    except Exception:
        pass

# Normalized calculations
total_sales_kpi = float((df_sales["quantity_sold"] * df_sales["price"]).sum()) if not df_sales.empty and "price" in df_sales.columns and "quantity_sold" in df_sales.columns else 6652.65
fulfilled_orders_kpi = len(df_sales) if not df_sales.empty else 8921
pending_shipments_kpi = int((df_products["stock"] < 10).sum()) if not df_products.empty and "stock" in df_products.columns else 1245
supplier_costs_kpi = float((df_products["stock"] * 2.65).sum()) if not df_products.empty and "stock" in df_products.columns else 4382.40
inventory_val_kpi = float((df_products["stock"] * df_products["price"]).sum()) if not df_products.empty and "stock" in df_products.columns and "price" in df_products.columns else 15827.00

# ==========================================
# ECLAIRA SIDEBAR COMPONENT STRUCTURE
# ==========================================
with st.sidebar:
    # Top profile / workspace switcher
    st.markdown("""
        <div style='background: #111317; border: 1px solid #1A1E24; border-radius: 8px; padding: 8px 12px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;'>
            <div style='display: flex; align-items: center; gap: 8px;'>
                <div style='width: 26px; height: 26px; border-radius: 6px; background: #FF6B00; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem; color: #FFF;'>⚡</div>
                <div>
                    <div style='font-size: 0.76rem; font-weight: 700; color: #FFF;'>Eclaira Apps</div>
                    <div style='font-size: 0.65rem; color: #64748B;'>Operations Workspace</div>
                </div>
            </div>
            <span style='color: #64748B; font-size: 0.75rem;'>⇅</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<p style='font-size: 0.68rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; margin: 8px 0 4px 6px;'>General</p>", unsafe_allow_html=True)
    
    NAV_GEN = [
        ("▦  Dashboard", "dashboard"),
        ("📦  Inventory", "inventory"),
        ("⚡  Procurement", "procurement"),
        ("🛒  Order Management", "orders"),
        ("🏢  Warehousing", "warehousing"),
        ("🚚  Shipment", "shipment"),
        ("📈  Performance", "performance"),
        ("🤝  Supplier", "supplier")
    ]
    for label, pid in NAV_GEN:
        btn_type = "primary" if st.session_state.active_page == pid else "secondary"
        if st.button(label, key=f"side_{pid}", type=btn_type, use_container_width=True):
            st.session_state.active_page = pid
            st.rerun()

    st.markdown("<p style='font-size: 0.68rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; margin: 16px 0 4px 6px;'>Other Menu</p>", unsafe_allow_html=True)
    NAV_OTH = [
        ("💰  Cost Analysis", "cost"),
        ("🤖  AI Copilot (Luna)", "ai_copilot"),
        ("📊  Analytics (EDA)", "analytics"),
        ("⚙️  Settings & Profile", "settings"),
        ("💬  Help & Support", "support")
    ]
    for label, pid in NAV_OTH:
        btn_type = "primary" if st.session_state.active_page == pid else "secondary"
        if st.button(label, key=f"side_{pid}", type=btn_type, use_container_width=True):
            st.session_state.active_page = pid
            st.rerun()

    st.divider()
    if st.button("🚪 LOG OUT", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

# ==========================================
# 1. MAIN ECLAIRA DASHBOARD VIEW
# ==========================================
if st.session_state.active_page == "dashboard":
    # Top Breadcrumb & Actions Bar
    st.markdown("""
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;'>
            <div style='font-size: 0.72rem; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;'>
                Dashboard / Overview
            </div>
            <div style='display: flex; gap: 8px;'>
                <span style='background: #111317; border: 1px solid #1A1E24; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; color: #8F9CAE;'>Filter by Date ▾</span>
                <span class='eclaira-tag'>REGION: {c_code}</span>
            </div>
        </div>
    """.format(c_code=c_code), unsafe_allow_html=True)

    st.markdown(f"""
        <div style='margin-bottom: 16px;'>
            <h1 style='font-size: 1.5rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em; margin: 0;'>
                Welcome Back, {current_user.get('full_name', 'Judha Maygustya')}!
            </h1>
            <div style='font-size: 0.8rem; color: #64748B; margin-top: 2px;'>
                Here's your real-time supply chain performance snapshot
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 5-Metric Strip (Exact Eclaira Columns)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""
            <div class='eclaira-stat-box'>
                <div>
                    <div class='eclaira-stat-label'>TOTAL SALES</div>
                    <div class='eclaira-stat-val'>{fmt_c(total_sales_kpi)}</div>
                </div>
                <div class='eclaira-stat-sub'><span class='delta-up'>▲ 0.56%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
            <div class='eclaira-stat-box'>
                <div>
                    <div class='eclaira-stat-label'>FULFILLED ORDERS</div>
                    <div class='eclaira-stat-val'>{fulfilled_orders_kpi:,}</div>
                </div>
                <div class='eclaira-stat-sub'><span class='delta-up'>▲ 1.12%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
            <div class='eclaira-stat-box'>
                <div>
                    <div class='eclaira-stat-label'>PENDING SHIPMENTS</div>
                    <div class='eclaira-stat-val'>{pending_shipments_kpi:,}</div>
                </div>
                <div class='eclaira-stat-sub'><span class='delta-down'>▼ 0.87%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
            <div class='eclaira-stat-box'>
                <div>
                    <div class='eclaira-stat-label'>SUPPLIER COSTS</div>
                    <div class='eclaira-stat-val'>{fmt_c(supplier_costs_kpi)}</div>
                </div>
                <div class='eclaira-stat-sub'><span class='delta-up'>▲ 0.25%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)
    with k5:
        st.markdown(f"""
            <div class='eclaira-stat-box'>
                <div>
                    <div class='eclaira-stat-label'>INVENTORY VALUE</div>
                    <div class='eclaira-stat-val'>{fmt_c(inventory_val_kpi)}</div>
                </div>
                <div class='eclaira-stat-sub'><span class='delta-up'>▲ 2.04%</span> Compared to Last Month</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # Main Grid (2:1 Ratio matching Eclaira Design)
    row1_c1, row1_c2 = st.columns([1.8, 1.0])

    with row1_c1:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;'>
                    <div>
                        <div style='font-size: 0.95rem; font-weight: 700; color: #FFF;'>Sales Trend Overview</div>
                        <div style='font-size: 0.72rem; color: #64748B;'>Track sales volume to identify seasonal trends and growth.</div>
                        <div style='margin-top: 8px;'>
                            <div style='font-size: 0.65rem; color: #64748B; text-transform: uppercase;'>Total Sales (YTD)</div>
                            <div style='font-size: 1.35rem; font-weight: 800; color: #FFF; font-family: monospace;'>$12,241.00</div>
                        </div>
                    </div>
                    <div style='display: flex; gap: 6px; align-items: center;'>
                        <span style='background: #14171D; border: 1px solid #1F242F; padding: 4px 8px; border-radius: 4px; font-size: 0.65rem; color: #8F9CAE;'>Weekly</span>
                        <span style='background: #14171D; border: 1px solid #1F242F; padding: 4px 8px; border-radius: 4px; font-size: 0.65rem; color: #8F9CAE;'>Monthly</span>
                        <span style='background: #FF6B00; padding: 4px 8px; border-radius: 4px; font-size: 0.65rem; color: #FFF; font-weight: 700;'>Yearly</span>
                        <span style='background: #14171D; border: 1px solid #1F242F; padding: 4px 8px; border-radius: 4px; font-size: 0.65rem; color: #8F9CAE; margin-left: 6px;'>⬇ Download Report</span>
                    </div>
                </div>
        """, unsafe_allow_html=True)

        if PLOTLY_AVAILABLE:
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            vals = [3200, 3100, 4800, 3600, 4200, 6100, 5233, 7100, 6800, 8400, 7900, 9200]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=months, y=vals,
                mode='lines+markers',
                line=dict(color='#FF6B00', width=2.2, shape='spline'),
                marker=dict(size=4, color='#FFA048'),
                fill='tozeroy',
                fillcolor='rgba(255, 107, 0, 0.05)',
                name='Sales'
            ))
            # Reference $5,233 Callout Tooltip
            fig.add_annotation(
                x="Jul", y=5233,
                text="<b>$5,233</b><br><span style='font-size:9px;'>Sales on July 2026</span>",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#FF6B00",
                ax=0, ay=-34,
                bgcolor="#111317", bordercolor="#FF6B00", borderwidth=1,
                font=dict(size=10, color="#FFFFFF")
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10),
                height=230,
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=10)),
                yaxis=dict(showgrid=True, gridcolor="#14171D", tickfont=dict(color="#475569", size=10))
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row1_c2:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.95rem; font-weight: 700; color: #FFF;'>Sales by Customer Segment</div>
                <div style='font-size: 0.72rem; color: #64748B; margin-bottom: 8px;'>Channel breakdown and revenue share</div>
                
                <div class='segment-bar-wrapper'>
                    <div class='seg-bar-1' style='width: 58%;'></div>
                    <div class='seg-bar-2' style='width: 26%;'></div>
                    <div class='seg-bar-3' style='width: 16%;'></div>
                </div>

                <div class='seg-row'>
                    <span style='color: #FF6B00; font-weight: 600;'>● RETAIL DISTRIBUTORS</span>
                    <b style='color: #FFF; font-family: monospace;'>$1,902.00</b>
                </div>
                <div class='seg-row'>
                    <span style='color: #D97706; font-weight: 600;'>● WHOLESALE BUYERS</span>
                    <b style='color: #FFF; font-family: monospace;'>$720.00</b>
                </div>
                <div class='seg-row' style='border: none;'>
                    <span style='color: #64748B; font-weight: 600;'>● DIRECT CONSUMERS</span>
                    <b style='color: #FFF; font-family: monospace;'>$401.00</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.95rem; font-weight: 700; color: #FFF; margin-bottom: 2px;'>Order Volume Distribution</div>
                <div style='font-size: 0.72rem; color: #64748B;'>Regional fulfillment density</div>
        """, unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            fig_bar = go.Figure(data=[
                go.Bar(name='Direct', x=['North', 'West', 'East'], y=[320, 480, 290], marker_color='#FF6B00'),
                go.Bar(name='Hub', x=['North', 'West', 'East'], y=[180, 240, 150], marker_color='#1E232B')
            ])
            fig_bar.update_layout(
                barmode='stack', height=100,
                margin=dict(t=5, b=5, l=5, r=5),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=9)),
                yaxis=dict(showgrid=False, showticklabels=False)
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # Bottom Grid (Customer Segments Bar Chart + Segment Performance Comparison)
    row2_c1, row2_c2 = st.columns([1.8, 1.0])

    with row2_c1:
        st.markdown("""
            <div class='eclaira-card'>
                <div style='font-size: 0.95rem; font-weight: 700; color: #FFF;'>Customer Segments</div>
                <div style='font-size: 0.72rem; color: #64748B; margin-bottom: 6px;'>Analyze sales trends by different customer groups</div>
        """, unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            fig_seg = go.Figure()
            days = [f"D{i}" for i in range(1, 19)]
            vals = [14, 18, 26, 48, 70, 58, 32, 24, 20, 31, 46, 78, 64, 40, 50, 84, 56, 36]
            colors = ['#FF6B00' if v > 60 else '#1A1E24' for v in vals]
            fig_seg.add_trace(go.Bar(x=days, y=vals, marker_color=colors))
            fig_seg.update_layout(
                height=140, margin=dict(t=5, b=5, l=5, r=5),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=False, tickfont=dict(color="#475569", size=8)),
                yaxis=dict(showgrid=True, gridcolor="#14171D", tickfont=dict(color="#475569", size=8))
            )
            st.plotly_chart(fig_seg, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with row2_c2:
        st.markdown("""
            <div class='eclaira-card' style='height: 100%; display: flex; flex-direction: column; justify-content: space-between;'>
                <div>
                    <div style='font-size: 0.95rem; font-weight: 700; color: #FFF;'>Segment Performance Comparison</div>
                    <div style='font-size: 0.72rem; color: #64748B;'>Compare sales and order volume changes month-over-month</div>
                </div>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;'>
                    <div style='background: #14171D; border: 1px solid #1F242F; border-radius: 8px; padding: 12px;'>
                        <div style='font-size: 0.65rem; color: #64748B; text-transform: uppercase;'>Current Run</div>
                        <div style='font-size: 1.10rem; font-weight: 800; color: #FFF; font-family: monospace;'>$12,241.00</div>
                        <span class='delta-down'>▼ 3.81%</span> <span style='font-size: 0.65rem; color: #475569;'>of target</span>
                    </div>
                    <div style='background: #14171D; border: 1px solid #1F242F; border-radius: 8px; padding: 12px;'>
                        <div style='font-size: 0.65rem; color: #64748B; text-transform: uppercase;'>Target YTD</div>
                        <div style='font-size: 1.10rem; font-weight: 800; color: #FFF; font-family: monospace;'>$93,462.00</div>
                        <span class='delta-up'>▲ 9.25%</span> <span style='font-size: 0.65rem; color: #475569;'>of target</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# 2. INVENTORY & WAREHOUSE
elif st.session_state.active_page == "inventory":
    st.markdown("<h2 style='font-weight: 800;'>📦 Warehouse Inventory Catalog</h2>", unsafe_allow_html=True)
    if not df_products.empty:
        st.dataframe(df_products, use_container_width=True, hide_index=True)
    else:
        st.info("No records loaded. Connect PostgreSQL in Settings & Profile.")

# 3. PROCUREMENT & PO DISPATCH
elif st.session_state.active_page == "procurement":
    st.markdown("<h2 style='font-weight: 800;'>⚡ Autonomous Procurement & PO Dispatch</h2>", unsafe_allow_html=True)
    s_email = st.text_input("Supplier Recipient Email", placeholder="supplier@domain.com")
    s_payload = st.text_area("PO Payload Specification", "PURCHASE ORDER • ECLAIRA SYSTEM\nRestock batch requested.", height=140)
    if st.button("DISPATCH PO VIA RELAY", type="primary"):
        ok, msg = dispatch_platform_email(s_email, "RESTOCK PURCHASE ORDER", s_payload)
        if ok:
            st.success(f"PO sent to {s_email}")
        else:
            st.error(msg)

# 4. ORDER MANAGEMENT (POS SCAN)
elif st.session_state.active_page == "orders":
    st.markdown("<h2 style='font-weight: 800;'>🛒 Point of Sale & Order Execution</h2>", unsafe_allow_html=True)
    sku_in = st.text_input("Barcode / SKU", "SKU_001")
    qty_in = st.number_input("Units", min_value=1, value=1)
    if st.button("PROCESS CHECKOUT", type="primary"):
        st.toast(f"Checked out {qty_in}x of {sku_in}", icon="🛒")

# 5. AI COPILOT (GPT-5.6 LUNA)
elif st.session_state.active_page == "ai_copilot":
    st.markdown("<h2 style='font-weight: 800;'>🤖 Supply Copilot (GPT-5.6 Luna)</h2>", unsafe_allow_html=True)
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [{"role": "assistant", "content": "Eclaira Copilot initialized. How can I assist with your supply fleet?"}]
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if q := st.chat_input("Ask about supplier margins, stockout runway, or PO batches..."):
        st.session_state.chat_messages.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            k = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
            if k and OPENAI_AVAILABLE:
                try:
                    cli = OpenAI(api_key=k, timeout=25.0)
                    r = cli.chat.completions.create(
                        model="gpt-5.6-luna",
                        messages=[
                            {"role": "system", "content": "You are the Eclaira Supply Chain AI Copilot. State calculations concisely."},
                            {"role": "user", "content": q}
                        ],
                        reasoning_effort="low"
                    )
                    ans = r.choices[0].message.content
                except Exception as e:
                    ans = f"AI Error: {e}"
            else:
                ans = "OpenAI key not configured in Streamlit Secrets."
            st.markdown(ans)
            st.session_state.chat_messages.append({"role": "assistant", "content": ans})

# 6. SETTINGS & PROFILE
elif st.session_state.active_page == "settings":
    st.markdown("<h2 style='font-weight: 800;'>⚙️ Workspace Settings & Pipeline Config</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='eclaira-card'>", unsafe_allow_html=True)
        st.markdown("<b>Operator Profile</b>", unsafe_allow_html=True)
        st.text_input("Full Name", value=current_user.get("full_name", "Judha Maygustya"), disabled=True)
        st.text_input("Account Email", value=current_user.get("email", ""), disabled=True)
        st.markdown("<hr style='border-color: #1A1E24; margin: 12px 0;'>", unsafe_allow_html=True)
        st.markdown("<b>Database Pipeline Connection</b>", unsafe_allow_html=True)
        uri_val = st.text_input("PostgreSQL URI", value=current_user.get("db_uri", ""), type="password")
        if st.button("UPDATE WORKSPACE PIPELINE", type="primary"):
            with get_vault_connection() as conn:
                conn.execute("UPDATE users SET db_uri = ? WHERE id = ?", (uri_val, current_user["id"]))
                conn.commit()
            current_user["db_uri"] = uri_val
            st.toast("Settings updated.")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# 7. HELP & SUPPORT
elif st.session_state.active_page == "support":
    st.markdown("<h2 style='font-weight: 800;'>💬 Help & Support Desk</h2>", unsafe_allow_html=True)
    t_sub = st.text_input("Ticket Summary")
    t_desc = st.text_area("Issue Description", height=140)
    if st.button("TRANSMIT TICKET", type="primary"):
        rcpt = st.secrets.get("SUPPORT_RECEIVER_EMAIL", st.secrets.get("SYSTEM_SMTP_SENDER", ""))
        if rcpt and t_sub and t_desc:
            ok, msg = dispatch_platform_email(rcpt, f"Support: {t_sub}", f"From: {current_user.get('email')}\n\n{t_desc}")
            if ok:
                st.success("Ticket dispatched.")
            else:
                st.error(msg)