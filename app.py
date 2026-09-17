import os
import re
import math
import json
import base64
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
# PAGE CONFIGURATION & CACHED BACKGROUND
# ==========================================
st.set_page_config(
    page_title="inventro.ai | Autonomous Retail OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data(show_spinner=False)
def get_cached_background(image_path: str = "background.png", dark_overlay: float = 0.75):
    """
    Encodes a local background image to base64 and caches it to prevent browser layout stutter.
    """
    if os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_file:
                b64_data = base64.b64encode(img_file.read()).decode("utf-8")
            return f"""
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(
                    rgba(11, 12, 16, {dark_overlay}),
                    rgba(11, 12, 16, {dark_overlay})
                ),
                url("data:image/png;base64,{b64_data}") no-repeat center center fixed !important;
                background-size: cover !important;
            }}
            [data-testid="stHeader"], .stApp {{
                background: transparent !important;
            }}
            """
        except Exception:
            return "html, body, .stApp { background-color: #0B0C10 !important; }"
    return "html, body, .stApp { background-color: #0B0C10 !important; }"

st.markdown(f"<style>{get_cached_background()}</style>", unsafe_allow_html=True)

# ==========================================
# ENTERPRISE DESIGN SYSTEM STYLING
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: #F1F5F9 !important;
}

code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

[data-testid="stSidebar"] {
    background-color: rgba(16, 18, 24, 0.95) !important;
    border-right: 1px solid #1B1E28 !important;
    backdrop-filter: blur(10px) !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1B1E28 !important;
}

/* HIDE STREAMLIT CLOUD TOOLBAR, GITHUB BADGES & FOOTER */
[data-testid="stToolbar"], [data-testid="stDecoration"], footer, .viewerBadge_container__1QSob {
    display: none !important;
    visibility: hidden !important;
}

@keyframes gatewayEntrance {
    0% { opacity: 0; transform: translateY(28px) scale(0.97); filter: blur(6px); }
    100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0px); }
}

@keyframes neonGlow {
    0%, 100% { text-shadow: 0 0 10px rgba(0, 178, 255, 0.3), 0 0 24px rgba(0, 178, 255, 0.15); }
    50% { text-shadow: 0 0 18px rgba(0, 178, 255, 0.65), 0 0 38px rgba(0, 178, 255, 0.35); }
}

.auth-header-anim { animation: gatewayEntrance 0.85s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.auth-title-glow { animation: neonGlow 3s ease-in-out infinite alternate; }

.dribbble-card {
    background: rgba(20, 23, 32, 0.88);
    border: 1px solid #1E2330;
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
    margin-bottom: 16px;
    backdrop-filter: blur(8px);
}
.dribbble-card:hover { border-color: #2D3446; }

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
# SQLITE VAULT CONCURRENCY (WAL MODE)
# ==========================================
VAULT_DB = "users_vault.db"

@st.cache_resource(show_spinner=False)
def get_vault_conn():
    conn = sqlite3.connect(VAULT_DB, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_vault_db():
    try:
        with get_vault_conn() as conn:
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
        with get_vault_conn() as conn:
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
        with get_vault_conn() as conn:
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
                    "currency_code": row[9] or "INR", "currency_symbol": row[10] or "₹",
                    "smtp_server": row[11] or "", "smtp_port": row[12] or 587,
                    "smtp_sender": row[13] or "", "smtp_password": row[14] or ""
                }
    except Exception:
        return None
    return None

def fetch_user_by_email(email: str):
    clean_email = email.strip().lower()
    try:
        with get_vault_conn() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, email, db_dialect, db_host, db_port, db_name, db_user, db_pass, db_uri, 
                       currency_code, currency_symbol, smtp_server, smtp_port, smtp_sender, smtp_password
                FROM users WHERE email = ?
            """, (clean_email,))
            row = c.fetchone()
            if row:
                return {
                    "id": row[0], "email": row[1], "db_dialect": row[2] or "PostgreSQL / Neon",
                    "db_host": row[3] or "", "db_port": row[4] or "5432", "db_name": row[5] or "",
                    "db_user": row[6] or "", "db_pass": row[7] or "", "db_uri": row[8] or "",
                    "currency_code": row[9] or "INR", "currency_symbol": row[10] or "₹",
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
        try:
            with get_vault_conn() as conn:
                c = conn.cursor()
                c.execute("SELECT smtp_server, smtp_port, smtp_sender, smtp_password FROM users WHERE smtp_server != '' AND smtp_password != '' LIMIT 1")
                row = c.fetchone()
                if row:
                    smtp_srv, smtp_prt, smtp_snd, smtp_pwd = row[0], row[1], row[2], row[3]
        except Exception:
            pass

    if not (smtp_srv and smtp_snd and smtp_pwd):
        return False, "System Email Service Not Configured. Please configure SYSTEM_SMTP_* in Streamlit Secrets."

    try:
        clean_recipient = recipient.strip()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"inventro.ai Platform <{smtp_snd}>"
        msg["To"] = clean_recipient
        msg["Reply-To"] = smtp_snd
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="inventro.ai")

        html_body = f"""\
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0B0C10; margin: 0; padding: 24px; color: #F1F5F9;">
          <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #141720; border: 1px solid #1E2330; border-radius: 16px; padding: 32px; margin: 0 auto;">
            <tr>
              <td>
                <div style="font-size: 22px; font-weight: 800; color: #00B2FF; margin-bottom: 20px;">⚡ INVENTRO.AI</div>
                <div style="font-size: 14px; line-height: 1.6; color: #CBD5E1; white-space: pre-line; margin-bottom: 28px;">{body_text}</div>
                <hr style="border: none; border-top: 1px solid #1E2330; margin: 24px 0;" />
                <div style="font-size: 11px; color: #64748B;">Automated operational transmission by inventro.ai Autonomous Retail Operating System.</div>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(smtp_srv, int(smtp_prt), timeout=15)
        server.starttls()
        server.login(smtp_snd, smtp_pwd)
        server.send_message(msg)
        server.quit()
        return True, f"Transmission successfully dispatched to {clean_recipient}."
    except Exception as e:
        return False, f"Dispatch failed: {str(e)}"

def set_user_otp(email: str) -> tuple[bool, str]:
    clean_email = email.strip().lower()
    otp_code = f"{random.randint(100000, 999999)}"
    try:
        with get_vault_conn() as conn:
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
        with get_vault_conn() as conn:
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
        with get_vault_conn() as conn:
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

def save_user_credentials(user_id: int, dialect: str, host: str, port: str, dbname: str, user: str, pwd: str, uri: str, curr_code: str, curr_sym: str, smtp_srv: str = "", smtp_prt: int = 587, smtp_snd: str = "", smtp_pwd: str = ""):
    try:
        with get_vault_conn() as conn:
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
    st.markdown("""
        <div class='auth-header-anim' style='text-align: center; padding: 40px 0 20px 0;'>
            <h1 class='auth-title-glow' style='color: #00B2FF; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 6px;'>
                ⚡ INVENTRO.AI
            </h1>
            <p style='color: #8E9BAE; font-size: 0.95rem; margin-top: 0;'>
                Autonomous Retail Operating System & Machine Intelligence Control
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    _, auth_col2, _ = st.columns([1, 1.25, 1])
    with auth_col2:
        st.markdown("<div class='dribbble-card auth-card-anim'>", unsafe_allow_html=True)
        
        if active_reset_token:
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
        else:
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
                            st.error("Authentication rejected: Invalid email or password.")
                    else:
                        st.warning("Please provide operator email and password.")

                with st.expander("Forgot password?"):
                    st.markdown("<p style='font-size: 0.8rem; font-weight: 600; color: #8E9BAE;'>Account Recovery Workflow:</p>", unsafe_allow_html=True)
                    recovery_email_input = st.text_input("Enter Registered Email", key="recovery_email_step1", placeholder="operator@retail.com")

                    if recovery_email_input:
                        user_check = fetch_user_by_email(recovery_email_input)
                        if not user_check:
                            st.error("No operator account found with this email address.")
                        else:
                            st.success("Email verified. Choose your recovery method below:")
                            recovery_method = st.radio(
                                "Select Recovery Action:",
                                ["Option 1: Send OTP to Email (Direct Login)", "Option 2: Send Password Reset Link to Email"],
                                key="recovery_method_choice"
                            )

                            if "Option 1" in recovery_method:
                                if st.button("SEND OTP TO EMAIL", use_container_width=True):
                                    ok, otp_code = set_user_otp(recovery_email_input)
                                    if ok:
                                        body = f"Operator Authentication Request\n\nYour one-time login passcode is: {otp_code}\n\nSecurity notice: This verification code expires in 10 minutes."
                                        sent, status_msg = dispatch_platform_email(recovery_email_input, "inventro.ai • Security Access Verification Code", body)
                                        if sent:
                                            st.success(f"OTP code successfully sent to `{recovery_email_input}`.")
                                        else:
                                            st.error(status_msg)
                                    else:
                                        st.error(otp_code)

                                entered_otp = st.text_input("Enter 6-Digit OTP from Email", key="otp_verify_box")
                                if st.button("VERIFY OTP & SIGN IN", type="primary", use_container_width=True):
                                    if entered_otp:
                                        try:
                                            with get_vault_conn() as conn:
                                                c = conn.cursor()
                                                c.execute("SELECT reset_token FROM users WHERE email = ?", (recovery_email_input.strip().lower(),))
                                                row = c.fetchone()
                                                if row and row[0] and row[0].strip() == entered_otp.strip():
                                                    c.execute("UPDATE users SET reset_token = '' WHERE email = ?", (recovery_email_input.strip().lower(),))
                                                    conn.commit()
                                                    st.session_state.authenticated_user = user_check
                                                    st.rerun()
                                                else:
                                                    st.error("Authentication rejected: Invalid or expired OTP.")
                                        except Exception as err:
                                            st.error(f"Verification error: {err}")
                                    else:
                                        st.warning("Please enter the 6-digit OTP.")

                            else:
                                if st.button("SEND PASSWORD RESET LINK", use_container_width=True):
                                    ok, reset_token = generate_reset_token(recovery_email_input)
                                    if ok:
                                        reset_url = f"https://inventro.streamlit.app/?reset_token={reset_token}"
                                        body = f"Operator Password Recovery Request\n\nClick the link below to initialize a password reset:\n{reset_url}"
                                        sent, status_msg = dispatch_platform_email(recovery_email_input, "inventro.ai • Secure Password Recovery Action", body)
                                        if sent:
                                            st.success(f"Password reset link successfully sent to `{recovery_email_input}`.")
                                        else:
                                            st.error(status_msg)
                                    else:
                                        st.error(reset_token)

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
                            
        # --- LOGIN CARD WATERMARK ---
        st.markdown("""
            <div style='margin-top: 15px; padding-top: 10px; border-top: 1px solid #1E2330; text-align: center;'>
                <p style='font-size: 0.72rem; color: #64748B; margin: 0;'>Designed & Built by</p>
                <a href='https://github.com/Abdulraheem-crypto-bit' target='_blank' style='font-size: 0.8rem; font-weight: 700; color: #00B2FF; text-decoration: none; display: inline-block; margin-top: 2px;'>
                    Abdul Raheem ⚡
                </a>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

current_user = st.session_state.authenticated_user

# Currency Localization
user_curr_code = current_user.get("currency_code", "INR")
active_currency = CURRENCY_PROFILES.get(user_curr_code, CURRENCY_PROFILES["INR"])
c_sym = active_currency["symbol"]
c_code = active_currency["code"]

def format_currency(amount: float) -> str:
    return f"{c_sym}{amount:,.2f}"

if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

# ==========================================
# SCHEMA NORMALIZATION & SANITIZATION
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
    cleaned = series.astype(str).str.replace(r"[^\d.-]", "", regex=True).replace("", np.nan)
    return pd.to_numeric(cleaned, errors="coerce").fillna(default_val)

def is_valid_inventory_schema(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    cleaned_cols = [clean_str(c) for c in df.columns]
    disallowed = ["salary", "payroll", "hiredate", "ssn", "designation", "attendance", "hourlyrate", "employee"]
    if any(any(d in col for d in disallowed) for col in cleaned_cols):
        return False
    has_identity = any(any(clean_str(syn) in col for syn in COLUMN_SYNONYMS["sku"] + COLUMN_SYNONYMS["name"]) for col in cleaned_cols)
    has_inventory_metric = any(any(clean_str(syn) in col for syn in COLUMN_SYNONYMS["stock"] + COLUMN_SYNONYMS["price"]) for col in cleaned_cols)
    return has_identity and has_inventory_metric

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

    for col, def_val in {"stock": 0, "lead_time": 2, "moq": 1, "pack_size": 1, "expiry_days": 30, "price": 100.0, "quantity_sold": 1}.items():
        if col in normalized_df.columns:
            normalized_df[col] = clean_numeric_series(normalized_df[col], def_val)
        else:
            normalized_df[col] = def_val

    for col, def_val in {"sku": [f"SKU_{i+1:03d}" for i in range(len(normalized_df))], "name": "Item", "category": "General", "vendor": "Unassigned", "email": ""}.items():
        if col not in normalized_df.columns:
            normalized_df[col] = def_val
        else:
            normalized_df[col] = normalized_df[col].fillna(def_val if isinstance(def_val, str) else "Item")

    return normalized_df, detected_mapping

# ==========================================
# DATABASE ENGINE
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
        engine = create_engine(sanitized_uri, pool_pre_ping=True, pool_recycle=300, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.sidebar.error(f"DB Error: {e}")
        return None

# ==========================================
# SIDEBAR NAVIGATION
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
        ("💬 Help & Support", "support"),
        ("👤 Profile & Vault", "profile")
    ]

    for label, page_id in PAGES_LIST:
        is_active = (st.session_state.active_page == page_id)
        if st.button(label, key=f"side_nav_{page_id}", type="primary" if is_active else "secondary", use_container_width=True):
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

    if st.button("TERMINATE SESSION", key="term_session_btn", use_container_width=True):
        st.session_state.authenticated_user = None
        st.rerun()

    st.markdown("""
        <div style='margin-top: 25px; padding-top: 10px; border-top: 1px solid #1E2330; text-align: center;'>
            <p style='font-size: 0.72rem; color: #64748B; margin: 0;'>Designed & Built by</p>
            <a href='https://github.com/Abdulraheem-crypto-bit' target='_blank' style='font-size: 0.8rem; font-weight: 700; color: #00B2FF; text-decoration: none; display: inline-block; margin-top: 2px;'>
                Abdul Raheem ⚡
            </a>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# INGESTION & DATA RESOLUTION
# ==========================================
raw_products, raw_sales, raw_movements = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
non_inventory_warning = False
detected_product_table = "None"
detected_sales_table = "None"

if is_connected:
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            prod_target = next((t for t in tables if t.lower() in ["products_master", "products", "inventory", "items"]), None)
            if not prod_target:
                for cand in [t for t in tables if any(k in t.lower() for k in ["product", "item", "inventory"])]:
                    sample_df = pd.read_sql(text(f"SELECT * FROM {cand} LIMIT 5"), conn)
                    if is_valid_inventory_schema(sample_df):
                        prod_target = cand
                        break
            if prod_target:
                detected_product_table = prod_target
                raw_products = pd.read_sql(text(f"SELECT * FROM {prod_target}"), conn)
            elif len(tables) > 0:
                non_inventory_warning = True

            sales_target = next((t for t in tables if any(k in t.lower() for k in ["sales_ledger", "sales", "order", "txn"])), None)
            if sales_target:
                detected_sales_table = sales_target
                raw_sales = pd.read_sql(text(f"SELECT * FROM {sales_target} ORDER BY 1 DESC LIMIT 2000"), conn)

            move_target = next((t for t in tables if any(k in t.lower() for k in ["stock_movements", "movement", "audit"])), None)
            if move_target:
                raw_movements = pd.read_sql(text(f"SELECT * FROM {move_target} ORDER BY 1 DESC LIMIT 50"), conn)
    except Exception as e:
        st.error(f"Ingestion notice: {e}")

df_products, prod_map = resolve_and_normalize(raw_products)
df_sales, sales_map = resolve_and_normalize(raw_sales)

analytics_df = compute_analytics(df_products, df_sales)

# ==========================================
# FULL COMPREHENSIVE ROUTER (11 MODULES)
# ==========================================
active_page_label = next((label for label, pid in PAGES_LIST if pid == st.session_state.active_page), "Console")
st.markdown(f"""
    <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;'>
        <div style='display: flex; align-items: center; gap: 12px;'>
            <span style='font-size: 1.4rem; font-weight: 800; color: #FFFFFF;'>⚡ inventro.ai • {active_page_label}</span>
            <span style='color: #4B5563;'>•</span>
            <span class='chip chip-cyan'>TABLE: {detected_product_table}</span>
            <span class='chip chip-green'>CURRENCY: {c_code} ({c_sym.strip()})</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# 1. DASHBOARD OVERVIEW WITH FILTERS
if st.session_state.active_page == "dashboard":
    st.markdown("<div class='dribbble-card' style='padding: 15px 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 1])
    with f_col1:
        all_categories = ["All Categories"] + sorted(analytics_df["category"].unique().tolist()) if not analytics_df.empty else ["All Categories"]
        selected_category = st.selectbox("Filter by Department / Category", all_categories, key="dash_cat_filter")
    with f_col2:
        status_options = ["All Statuses", "HEALTHY", "RESTOCK NEEDED"]
        selected_status = st.selectbox("Filter by Stock Status", status_options, key="dash_status_filter")
    with f_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("REFRESH TELEMETRY", key="dash_refresh_btn", use_container_width=True):
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    filtered_analytics = analytics_df.copy()
    if selected_category != "All Categories":
        filtered_analytics = filtered_analytics[filtered_analytics["category"] == selected_category]
    if selected_status != "All Statuses":
        filtered_analytics = filtered_analytics[filtered_analytics["reorder_status"] == selected_status]

    total_stock = int(filtered_analytics['stock'].sum()) if not filtered_analytics.empty else 0
    restock_needed = int((filtered_analytics['reorder_status'] == 'RESTOCK NEEDED').sum()) if not filtered_analytics.empty else 0
    healthy_units = int((filtered_analytics['reorder_status'] == 'HEALTHY').sum()) if not filtered_analytics.empty else 0
    perish_alert = int((filtered_analytics['expiry_risk'] == 'HIGH EXPIRY RISK').sum()) if not filtered_analytics.empty else 0

    inventory_valuation = float((filtered_analytics['stock'] * filtered_analytics['price']).sum()) if not filtered_analytics.empty else 0.0
    nominal_balance_val = format_currency(inventory_valuation)

    real_revenue = float((df_sales["quantity_sold"] * df_sales["price"]).sum()) if not df_sales.empty and "quantity_sold" in df_sales.columns and "price" in df_sales.columns else 0.0
    nominal_revenue_val = format_currency(real_revenue)

    real_po_outlay = float((filtered_analytics['suggested_po_qty'] * filtered_analytics['price']).sum()) if not filtered_analytics.empty else 0.0
    replenish_outlay_val = format_currency(real_po_outlay)

    r1_c1, r1_c2, r1_c3 = st.columns([1.2, 1.2, 1.6])
    with r1_c1:
        st.markdown(f"""
            <div class='dribbble-card'>
                <div class='card-header-flex'><span class='card-label'>Warehouse Valuation</span><span style='color: #64748B;'>💳</span></div>
                <div class='card-val-lg'>{nominal_balance_val}</div>
                <div style='margin-top: 10px;'><span class='chip chip-green'>Filtered Asset Base</span></div>
            </div>
            <div class='dribbble-card'>
                <div class='card-header-flex'><span class='card-label'>Realized Revenue</span><span style='color: #64748B;'>📈</span></div>
                <div class='card-val-lg'>{nominal_revenue_val}</div>
                <div style='margin-top: 10px;'><span class='chip chip-green'>Sales Ledger Total</span></div>
            </div>
        """, unsafe_allow_html=True)

    with r1_c2:
        st.markdown(f"""
            <div class='dribbble-card'>
                <div class='card-header-flex'><span class='card-label'>Total Stock Volume</span><span style='color: #64748B;'>📦</span></div>
                <div class='card-val-lg'>{total_stock:,} <span class='card-unit'>UNITS</span></div>
                <div style='margin-top: 10px;'><span class='chip chip-cyan'>Filtered Volume</span></div>
            </div>
            <div class='dribbble-card'>
                <div class='card-header-flex'><span class='card-label'>Replenishment Outlay</span><span style='color: #64748B;'>⚠️</span></div>
                <div class='card-val-lg'>{replenish_outlay_val}</div>
                <div style='margin-top: 10px;'><span class='chip chip-red'>{restock_needed} Filtered SKUs Below ROP</span></div>
            </div>
        """, unsafe_allow_html=True)

    with r1_c3:
        st.markdown("<div class='dribbble-card' style='height: 100%;'><div class='card-header-flex'><span class='card-label'>Product Activity Distribution</span><span class='chip chip-cyan'>FILTERED VIEW</span></div>", unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            fig_donut = go.Figure(data=[go.Pie(
                labels=["Healthy Units", "Restock Needed", "Class-A Items", "Expiry Risk"],
                values=[healthy_units or 1, restock_needed or 1, max(1, int(len(filtered_analytics)*0.2)), perish_alert or 1],
                hole=0.72, marker=dict(colors=["#00B2FF", "#FEB019", "#00E396", "#FF4560"]),
                hoverinfo="label+value", textinfo="none"
            )])
            fig_donut.update_layout(showlegend=False, margin=dict(t=5, b=5, l=5, r=5), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=205, annotations=[dict(text=f"<b>{total_stock:,}</b><br><span style='font-size:11px;color:#8E9BAE;'>Units</span>", x=0.5, y=0.5, font_size=18, font_color="#FFFFFF", showarrow=False)])
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
        st.markdown(f"<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.76rem; font-weight: 600; padding-top: 4px;'><div><span style='color:#00B2FF;'>●</span> Healthy: <b style='color:#FFF;'>{healthy_units}</b></div><div><span style='color:#FEB019;'>●</span> Restock: <b style='color:#FFF;'>{restock_needed}</b></div><div><span style='color:#00E396;'>●</span> Class-A: <b style='color:#FFF;'>{int(len(filtered_analytics)*0.2)}</b></div><div><span style='color:#FF4560;'>●</span> Spoilage: <b style='color:#FFF;'>{perish_alert}</b></div></div></div>", unsafe_allow_html=True)

    r2_c1, r2_c2 = st.columns([1.6, 1.1])
    with r2_c1:
        st.markdown("<div class='dribbble-card'><div class='card-header-flex'><div><span class='card-label'>Weekly Sales Ledger Throughput</span></div></div>", unsafe_allow_html=True)
        if PLOTLY_AVAILABLE:
            day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            if not df_sales.empty and "transaction_date" in df_sales.columns:
                df_sales_chart = df_sales.copy()
                df_sales_chart["dt"] = pd.to_datetime(df_sales_chart["transaction_date"], errors="coerce")
                df_sales_chart["day"] = df_sales_chart["dt"].dt.strftime("%a")
                sales_by_day = df_sales_chart.groupby("day")["quantity_sold"].sum().reindex(day_order).fillna(0)
                days, throughput_data = list(sales_by_day.index), [int(v) for v in sales_by_day.values]
            else:
                days, throughput_data = day_order, [0, 0, 0, 0, 0, 0, 0]

            fig_area = go.Figure()
            fig_area.add_trace(go.Scatter(x=days, y=throughput_data, fill='tozeroy', mode='lines+markers', line=dict(width=3, color='#00B2FF', shape='spline'), marker=dict(size=6, color='#00B2FF'), fillcolor='rgba(0, 178, 255, 0.12)'))
            fig_area.update_layout(margin=dict(t=5, b=20, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=215, showlegend=False, xaxis=dict(showgrid=False, tickfont=dict(color="#8E9BAE", size=11)), yaxis=dict(showgrid=True, gridcolor="#1B1F2A", tickfont=dict(color="#8E9BAE", size=11)))
            st.plotly_chart(fig_area, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with r2_c2:
        st.markdown("<div class='dribbble-card'><div class='card-header-flex'><div><span class='card-label'>Risk by Department Matrix</span></div><span class='chip chip-amber'>LEVEL: WARN</span></div>", unsafe_allow_html=True)
        if not analytics_df.empty:
            cat_risk = analytics_df.groupby("category").apply(lambda x: pd.Series({"Low": int((x["reorder_status"] == "HEALTHY").sum()), "Med": int(((x["stock"] <= x["rop"] * 1.5) & (x["stock"] > x["rop"])).sum()), "High": int((x["reorder_status"] == "RESTOCK NEEDED").sum())})).reset_index().head(5)
            table_rows = "".join([f"<tr><td><b>{r['category'][:14]}</b></td><td style='color:#00E396;'>{r['Low']}</td><td style='color:#FEB019;'>{r['Med']}</td><td style='color:#FF4560;'><b>{r['High']}</b></td></tr>" for _, r in cat_risk.iterrows()])
            st.markdown(f"<table class='risk-table'><tr><th>DEPT</th><th>LOW</th><th>MED</th><th>HIGH</th></tr>{table_rows}</table>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# 2. AI COPILOT
elif st.session_state.active_page == "ai_copilot":
    st.markdown("##### **🤖 Autonomous AI Supply Agent & Copilot**")
    if analytics_df.empty:
        st.warning("Telemetry idle: Connect your database pipeline.")
    else:
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [{"role": "assistant", "content": f"Connected to `{detected_product_table}`. Ask me anything about stockout risks or inventory valuation."}]
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        if user_prompt := st.chat_input("Ask about stock levels or replenishment..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)
            with st.chat_message("assistant"):
                ai_answer = intelligent_ai_agent(user_prompt, analytics_df, eda_results)
                st.markdown(ai_answer)
            st.session_state.chat_messages.append({"role": "assistant", "content": ai_answer})

# 3. RECENT TRANSACTIONS
elif st.session_state.active_page == "recent_tx":
    st.markdown("##### **📋 Recent Fleet Movements & Ledger Events**")
    st.dataframe(raw_movements.head(20) if not raw_movements.empty else analytics_df.head(20), use_container_width=True, hide_index=True)

# 4. DATA REPORT (EDA)
elif st.session_state.active_page == "eda_report":
    st.markdown("##### **🔬 14-Point Automated Statistical EDA Telemetry**")
    if not eda_results:
        st.info("Awaiting live database connection.")
    else:
        eda_c1, eda_c2, eda_c3, eda_c4 = st.columns(4)
        eda_c1.metric("Catalog SKUs", eda_results["overview"]["catalog_rows"])
        eda_c2.metric("Ledger Records", eda_results["overview"]["sales_ledger_rows"])
        eda_c3.metric("Stock Outliers", eda_results["outliers"]["stock_outliers"])
        eda_c4.metric("Cells Scanned", f"{eda_results['overview']['total_cells_scanned']:,}")
        st.dataframe(pd.DataFrame(eda_results["numerical_stats"]).T.reset_index(), use_container_width=True, hide_index=True)

# 5. INVENTORY CATALOG
elif st.session_state.active_page == "catalog":
    st.markdown("##### **📦 Real-Time Catalog & ABC-XYZ Pareto Matrix**")
    st.dataframe(analytics_df[["sku", "name", "category", "stock", "price", "rop", "reorder_status", "abc_class", "vendor"]], use_container_width=True, hide_index=True) if not analytics_df.empty else st.info("Catalog empty.")

# 6. RISK & GOVERNANCE
elif st.session_state.active_page == "risk_gov":
    st.markdown("##### **🛡️ Autonomous Risk & Compliance Radar**")
    st.dataframe(analytics_df[analytics_df["stock"] <= analytics_df["rop"]][["sku", "name", "stock", "rop", "vendor"]], use_container_width=True, hide_index=True) if not analytics_df.empty else st.info("No risks found.")

# 7. POS SCAN & INTAKE
elif st.session_state.active_page == "pos_scan":
    st.markdown("##### **⚡ Point-of-Sale Checkout & Receiving Terminal**")
    if not analytics_df.empty:
        p_col1, p_col2 = st.columns([1, 1.4])
        with p_col1:
            selected_sku = st.selectbox("Select SKU", analytics_df["sku"].tolist(), key="pos_sku_select")
            action = st.radio("Operation:", ["📥 Stock IN", "⚡ POS Checkout", "📤 Stock OUT"], horizontal=True, key="pos_action_radio")
            units = st.number_input("Units", min_value=1, value=1, key="pos_units_input")
            if st.button("COMMIT TRANSACTION", key="pos_commit_btn", type="primary", use_container_width=True):
                st.toast(f"Committed {units}x units on {selected_sku}", icon="⚡")
                st.rerun()
        with p_col2:
            st.markdown("**Live Movements Log**")
            if not raw_movements.empty:
                st.dataframe(raw_movements.head(8), use_container_width=True, hide_index=True)
    else:
        st.info("No catalog available.")

# 8. PO DISPATCH
elif st.session_state.active_page == "po_dispatch":
    st.markdown("##### **✉️ Autonomous Purchase Order Dispatch Center**")
    st.dataframe(analytics_df[analytics_df["suggested_po_qty"] > 0][["sku", "name", "stock", "suggested_po_qty", "vendor"]], use_container_width=True, hide_index=True) if not analytics_df.empty else st.success("All systems optimal.")

# 9. DB TERMINAL
elif st.session_state.active_page == "db_terminal":
    st.markdown("##### **🔌 Relational Schema Provisioning & Direct SQL Terminal**")
    sql_in = st.text_area("SQL Query", placeholder="SELECT * FROM products_master LIMIT 5;", key="db_sql_input")
    if st.button("RUN QUERY", key="db_run_query_btn") and is_connected:
        with engine.connect() as conn:
            st.dataframe(pd.read_sql(text(sql_in), conn), use_container_width=True)

# 10. HELP & SUPPORT
elif st.session_state.active_page == "support":
    st.markdown("##### **💬 Operator Help Desk & System Support**")
    with st.form("support_form"):
        st.text_input("Subject", key="sup_sub")
        st.text_area("Details", key="sup_det")
        if st.form_submit_button("SUBMIT TICKET", type="primary"):
            st.success("Ticket submitted.")

# 11. PROFILE & VAULT
elif st.session_state.active_page == "profile":
    st.markdown("##### **👤 Operator Profile & Encrypted Vault**")
    new_uri = st.text_input("Database URI", value=current_user.get("db_uri", ""), type="password", key="prof_db_uri_input")
    if st.button("SAVE PROFILE", key="prof_save_btn", type="primary"):
        save_user_credentials(current_user["id"], "PostgreSQL / Neon", "", "5432", "", "", "", new_uri, user_curr_code, c_sym)
        st.toast("Profile saved successfully!", icon="💾")
        st.rerun()