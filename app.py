import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
import numpy as np
import traceback
import json
import hashlib
from io import BytesIO
import base64
import time
import random
import re
from collections import defaultdict
import secrets
import os
warnings.filterwarnings('ignore')

def run_migration_if_needed():
    """Run Migration.py if the database does not exist or is empty."""
    db_path = os.path.join(os.path.dirname(__file__), "duckdb", "business.db")
    if not os.path.exists(db_path):
        print("📦 Database not found – running Migration.py...")
        os.system(f"{sys.executable} Migration.py")
    else:
        # Check if the main table exists
        try:
            conn = duckdb.connect(db_path)
            conn.execute("SELECT 1 FROM dashboard_data LIMIT 1")
            conn.close()
        except:
            print("⚠️ Main table missing – running Migration.py...")
            conn.close()
            os.system(f"{sys.executable} Migration.py")

# Call it
run_migration_if_needed()


# ============================================================================
# AUTHENTICATION MODULE (Integrated)
# ============================================================================

# Password hashing
def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    combined = salt + password
    hash_obj = hashlib.sha256(combined.encode())
    return salt + ":" + hash_obj.hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hashed version."""
    try:
        salt, hash_val = hashed.split(":")
        combined = salt + password
        return hashlib.sha256(combined.encode()).hexdigest() == hash_val
    except:
        return False

# Default users
DEFAULT_USERS = {
    "admin": {
        "password": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
        "name": "System Administrator",
        "role": "admin",
        "email": "admin@uniquepharma.com",
        "created": "2026-01-01",
        "last_login": None,
        "active": True,
        "permissions": ["all"]
    },
    "manager": {
        "password": "6b8f9d7c6a4b8c1a2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z",
        "name": "Pharma Manager",
        "role": "manager",
        "email": "manager@uniquepharma.com",
        "created": "2026-01-01",
        "last_login": None,
        "active": True,
        "permissions": ["view_all", "export_data", "view_suppliers"]
    },
    "analyst": {
        "password": "f7c3bc1d808e04732adf679965ccc34ca7ae3441a90c51e7e5c7d9e1f3f3e0d9",
        "name": "Data Analyst",
        "role": "analyst",
        "email": "analyst@uniquepharma.com",
        "created": "2026-01-01",
        "last_login": None,
        "active": True,
        "permissions": ["view_dashboard", "view_reports", "export_data"]
    }
}

class UserManager:
    """Handle user authentication and management."""
    
    def __init__(self):
        self.users_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
        self.users = self._load_users()
        self._ensure_default_users()
    
    def _load_users(self) -> dict:
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def _ensure_default_users(self):
        changed = False
        for username, user_data in DEFAULT_USERS.items():
            if username not in self.users:
                self.users[username] = user_data
                changed = True
        if changed:
            self._save_users()
    
    def authenticate(self, username: str, password: str):
        if username not in self.users:
            return False, None
        
        user = self.users[username]
        if not user.get('active', True):
            return False, None
        
        stored_hash = user.get('password', '')
        if verify_password(password, stored_hash):
            user['last_login'] = datetime.now().isoformat()
            self._save_users()
            return True, user
        
        return False, None
    
    def create_user(self, username: str, password: str, name: str, email: str, 
                   role: str = "analyst", permissions: list = None) -> bool:
        if username in self.users:
            return False
        if permissions is None:
            permissions = ["view_dashboard"]
        self.users[username] = {
            "password": hash_password(password),
            "name": name,
            "role": role,
            "email": email,
            "created": datetime.now().isoformat(),
            "last_login": None,
            "active": True,
            "permissions": permissions
        }
        self._save_users()
        return True
    
    def update_user(self, username: str, **kwargs) -> bool:
        if username not in self.users:
            return False
        for key, value in kwargs.items():
            if key != 'password' and key != 'username':
                self.users[username][key] = value
        if 'password' in kwargs:
            self.users[username]['password'] = hash_password(kwargs['password'])
        self._save_users()
        return True
    
    def delete_user(self, username: str) -> bool:
        if username == 'admin':
            return False
        if username in self.users:
            del self.users[username]
            self._save_users()
            return True
        return False
    
    def list_users(self):
        if not self.users:
            return pd.DataFrame()
        data = []
        for username, user in self.users.items():
            data.append({
                'Username': username,
                'Name': user.get('name', ''),
                'Role': user.get('role', ''),
                'Email': user.get('email', ''),
                'Active': user.get('active', True),
                'Last Login': user.get('last_login', 'Never'),
                'Created': user.get('created', '')
            })
        return pd.DataFrame(data)

class SessionManager:
    """Handle user session state."""
    
    SESSION_EXPIRY_HOURS = 8
    
    @staticmethod
    def init_session():
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'username' not in st.session_state:
            st.session_state.username = None
        if 'login_time' not in st.session_state:
            st.session_state.login_time = None
    
    @staticmethod
    def login(username: str, user_data: dict):
        st.session_state.authenticated = True
        st.session_state.user = user_data
        st.session_state.username = username
        st.session_state.login_time = datetime.now()
    
    @staticmethod
    def logout():
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.username = None
        st.session_state.login_time = None
        st.cache_data.clear()
    
    @staticmethod
    def is_authenticated() -> bool:
        if not st.session_state.authenticated:
            return False
        if st.session_state.login_time:
            expiry = st.session_state.login_time + timedelta(
                hours=SessionManager.SESSION_EXPIRY_HOURS
            )
            if datetime.now() > expiry:
                SessionManager.logout()
                return False
        return True

class PermissionManager:
    """Handle user permissions."""
    
    ROLE_PERMISSIONS = {
        'admin': ['all'],
        'manager': ['view_all', 'export_data', 'view_suppliers', 'view_stock'],
        'analyst': ['view_dashboard', 'view_reports', 'export_data'],
        'viewer': ['view_dashboard']
    }
    
    @staticmethod
    def has_permission(user_data: dict, permission: str) -> bool:
        if not user_data:
            return False
        perms = user_data.get('permissions', [])
        if 'all' in perms:
            return True
        role = user_data.get('role', 'viewer')
        role_perms = PermissionManager.ROLE_PERMISSIONS.get(role, [])
        return permission in perms or permission in role_perms
    
    @staticmethod
    def get_available_pages(user_data: dict) -> list:
        all_pages = [
            "📊 Executive Dashboard",
            "📈 Sales Analytics",
            "🔄 Returns Analysis",
            "📊 Net Sales Analysis",
            "📋 Year Comparison",
            "🔮 Demand Forecast",
            "🏆 Performance Ranking",
            "📦 Product Portfolio",
            "📦 Stock Analysis",
            "📦 Purchase Analysis",
            "🏢 Supplier Performance",
            "🎯 FOC Analysis"
        ]
        if not user_data:
            return ["📊 Executive Dashboard"]
        perms = user_data.get('permissions', [])
        role = user_data.get('role', 'viewer')
        if 'all' in perms or role == 'admin':
            return all_pages
        if role == 'manager':
            return all_pages
        if role == 'analyst':
            return all_pages
        return ["📊 Executive Dashboard", "📈 Sales Analytics", "📦 Stock Analysis"]

# ============================================================================
# LOGIN UI
# ============================================================================

def render_login_page():
    """Render professional login page."""
    
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #0a0e1a 0%, #1a1030 50%, #0d1528 100%);
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .login-container {
            max-width: 420px;
            margin: 0 auto;
            padding: 40px 32px;
            background: rgba(20, 27, 45, 0.9);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 25px 80px rgba(0,0,0,0.6);
            animation: fadeInUp 0.6s ease-out;
            position: relative;
            overflow: hidden;
        }
        .login-container::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 20%, rgba(0,102,204,0.05), transparent 60%);
            pointer-events: none;
        }
        .login-container::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #0066CC, #7b5ea7, #22c55e);
            border-radius: 3px 3px 0 0;
        }
        .login-logo {
            text-align: center;
            margin-bottom: 32px;
            position: relative;
            z-index: 1;
        }
        .login-logo .icon {
            font-size: 3rem;
            display: block;
            margin-bottom: 8px;
        }
        .login-logo h1 {
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #0066CC, #7b5ea7, #22c55e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .login-logo .subtitle {
            color: #8899bb;
            font-size: 0.8rem;
            letter-spacing: 2px;
            margin-top: 4px;
            font-weight: 300;
        }
        .login-logo .version {
            color: #667799;
            font-size: 0.6rem;
            letter-spacing: 1px;
            margin-top: 2px;
        }
        .login-form .stTextInput input {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 12px !important;
            color: #e8edf5 !important;
            padding: 12px 16px !important;
            font-size: 0.95rem !important;
            transition: all 0.3s ease !important;
        }
        .login-form .stTextInput input:focus {
            border-color: #0066CC !important;
            box-shadow: 0 0 0 3px rgba(0,102,204,0.15) !important;
            background: rgba(255,255,255,0.08) !important;
        }
        .login-form .stTextInput input::placeholder {
            color: #667799 !important;
        }
        .login-form .stButton button {
            background: linear-gradient(135deg, #0066CC, #0052a3) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            width: 100% !important;
            transition: all 0.3s ease !important;
            margin-top: 8px !important;
        }
        .login-form .stButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 32px rgba(0,102,204,0.3) !important;
            background: linear-gradient(135deg, #0077EE, #0066CC) !important;
        }
        .login-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 12px;
            padding: 12px 16px;
            color: #ef4444;
            font-size: 0.85rem;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: shake 0.5s ease-out;
        }
        .login-footer {
            text-align: center;
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.05);
            position: relative;
            z-index: 1;
        }
        .login-footer .text {
            color: #667799;
            font-size: 0.7rem;
        }
        .security-badge {
            display: flex;
            justify-content: center;
            gap: 16px;
            margin-top: 12px;
            position: relative;
            z-index: 1;
        }
        .security-badge span {
            color: #667799;
            font-size: 0.6rem;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            20% { transform: translateX(-10px); }
            40% { transform: translateX(10px); }
            60% { transform: translateX(-6px); }
            80% { transform: translateX(6px); }
        }
        @media (max-width: 480px) {
            .login-container { padding: 24px 16px; margin: 16px; }
            .login-logo h1 { font-size: 1.4rem; }
        }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="login-logo">
                <span class="icon">🏢</span>
                <h1>UNIQUE PHARMA</h1>
                <div class="subtitle">ENTERPRISE PHARMACEUTICAL INTELLIGENCE</div>
                <div class="version">KINSHASA · GOMA · LUBUMBASHI</div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username"
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            
            submitted = st.form_submit_button("🔐 Sign In")
            
            if submitted:
                if username and password:
                    user_manager = UserManager()
                    success, user_data = user_manager.authenticate(username, password)
                    if success:
                        SessionManager.login(username, user_data)
                        st.rerun()
                    else:
                        st.markdown("""
                        <div class="login-error">
                            ❌ Invalid username or password. Please try again.
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="login-error">
                        ⚠️ Please enter both username and password.
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="text-align: center; margin-top: 12px; position: relative; z-index: 1;">
            <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 8px 12px; display: inline-block;">
                <span style="color: #667799; font-size: 0.7rem;">Demo Credentials: </span>
                <span style="color: #8899bb; font-size: 0.7rem; margin: 0 8px;">
                    <strong>admin</strong> / <strong>admin</strong>
                </span>
                <span style="color: #667799; font-size: 0.7rem;">•</span>
                <span style="color: #8899bb; font-size: 0.7rem; margin: 0 8px;">
                    <strong>manager</strong> / <strong>manager123</strong>
                </span>
            </div>
        </div>
        <div class="security-badge">
            <span>🔒 Encrypted</span>
            <span>🛡️ Secure</span>
            <span>⚡ SSL</span>
        </div>
        <div class="login-footer">
            <div class="text">
                © 2026 Unique Pharma · Enterprise Edition v11.0
            </div>
        </div>
        </div>
        """, unsafe_allow_html=True)

def render_user_profile():
    """Render user profile and settings."""
    if not SessionManager.is_authenticated():
        return
    
    user_data = st.session_state.user
    username = st.session_state.username
    
    st.markdown("### 👤 User Profile")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style="background: #1a2236; border-radius: 16px; padding: 20px; border: 1px solid #2a3450;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="background: linear-gradient(135deg, #0066CC, #7b5ea7); width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; color: white; font-weight: bold;">
                    {username[0].upper()}
                </div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #e8edf5;">{user_data.get('name', username)}</div>
                    <div style="font-size: 0.8rem; color: #8899bb;">@{username}</div>
                    <div style="display: flex; gap: 8px; margin-top: 4px;">
                        <span style="background: rgba(0,102,204,0.2); color: #0066CC; padding: 2px 12px; border-radius: 12px; font-size: 0.7rem; font-weight: 500;">
                            {user_data.get('role', 'viewer').upper()}
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 User Information")
        info_data = {
            "Username": username,
            "Name": user_data.get('name', ''),
            "Email": user_data.get('email', ''),
            "Role": user_data.get('role', ''),
            "Last Login": user_data.get('last_login', 'Never'),
            "Created": user_data.get('created', ''),
            "Active": "✅ Yes" if user_data.get('active', True) else "❌ No"
        }
        for key, value in info_data.items():
            st.text(f"{key}: {value}")
    
    with col2:
        st.markdown("### 🔐 Security Settings")
        
        with st.expander("Change Password", expanded=False):
            with st.form("change_password_form"):
                current = st.text_input("Current Password", type="password")
                new = st.text_input("New Password", type="password")
                confirm = st.text_input("Confirm New Password", type="password")
                if st.form_submit_button("Update Password"):
                    if current and new and confirm:
                        if new == confirm:
                            if len(new) >= 6:
                                user_manager = UserManager()
                                success, _ = user_manager.authenticate(username, current)
                                if success:
                                    user_manager.update_user(username, password=new)
                                    st.success("✅ Password updated successfully!")
                                    st.rerun()
                                else:
                                    st.error("❌ Current password is incorrect.")
                            else:
                                st.error("❌ Password must be at least 6 characters.")
                        else:
                            st.error("❌ New passwords do not match.")
                    else:
                        st.error("❌ Please fill in all fields.")
        
        st.markdown("### 📱 Session Information")
        login_time = st.session_state.login_time
        if login_time:
            st.text(f"Session Started: {login_time.strftime('%Y-%m-%d %H:%M:%S')}")
            expiry = login_time + timedelta(hours=SessionManager.SESSION_EXPIRY_HOURS)
            st.text(f"Session Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            SessionManager.logout()
            st.rerun()

def render_admin_panel():
    """Render admin user management panel."""
    if not SessionManager.is_authenticated():
        return
    
    user_data = st.session_state.user
    if user_data.get('role') != 'admin' and 'all' not in user_data.get('permissions', []):
        st.warning("⚠️ Admin access required.")
        return
    
    st.markdown("### 👥 User Management")
    
    user_manager = UserManager()
    users_df = user_manager.list_users()
    
    if not users_df.empty:
        st.dataframe(users_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### ➕ Create New User")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("create_user_form"):
            new_username = st.text_input("Username", placeholder="Enter username")
            new_password = st.text_input("Password", type="password", placeholder="Min 6 characters")
            new_name = st.text_input("Full Name", placeholder="Enter full name")
            if st.form_submit_button("Create User"):
                if new_username and new_password and new_name:
                    if len(new_password) >= 6:
                        if user_manager.create_user(
                            new_username, new_password, new_name, "", "analyst"
                        ):
                            st.success(f"✅ User {new_username} created successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Username already exists.")
                    else:
                        st.error("❌ Password must be at least 6 characters.")
                else:
                    st.error("❌ Please fill in all required fields.")
    
    with col2:
        st.markdown("### 🗑️ Delete User")
        users_list = list(user_manager.users.keys())
        users_list = [u for u in users_list if u != 'admin']
        if users_list:
            delete_user = st.selectbox("Select user to delete", users_list)
            if st.button("Delete User", type="primary"):
                if user_manager.delete_user(delete_user):
                    st.success(f"✅ User {delete_user} deleted successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete user.")
        else:
            st.info("No other users to delete.")

# ============================================================================
# PAGE CONFIG
# ============================================================================

# Initialize session
SessionManager.init_session()

# Check authentication
if not SessionManager.is_authenticated():
    render_login_page()
    st.stop()

st.set_page_config(
    page_title="UNIQUE PHARMA - KINSHASA, GOMA & LUBUMBASHI",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

DB_PATH = r"C:\Users\User\Desktop\Dashboard Working\duckdb\business.db"

class DatabaseConnection:
    """Centralized database connection management."""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
        return cls._instance
    
    def get_connection(self):
        if self._connection is None:
            self._connection = duckdb.connect(DB_PATH)
            self._connection.execute("PRAGMA memory_limit='4GB'")
        return self._connection

_db = DatabaseConnection()

@st.cache_resource
def get_connection():
    return _db.get_connection()


# ============================================================================
# DATE FILTER FUNCTIONS
# ============================================================================

def get_date_range_options():
    conn = get_connection()
    try:
        result = conn.execute("""
            SELECT MIN(Month) as min_date, MAX(Month) as max_date
            FROM dashboard_data
        """).fetchone()
        if result and result[0] and result[1]:
            min_date = pd.to_datetime(result[0])
            max_date = pd.to_datetime(result[1])
            options = {
                'All': (min_date, max_date),
                'Last 3 Months': (max_date - pd.DateOffset(months=3), max_date),
                'Last 6 Months': (max_date - pd.DateOffset(months=6), max_date),
                'Last 12 Months': (max_date - pd.DateOffset(months=12), max_date),
                'Year to Date': (pd.Timestamp(year=max_date.year, month=1, day=1), max_date),
                'Custom': None
            }
            return options, min_date, max_date
        return None, None, None
    except Exception as e:
        st.error(f"Error getting date range options: {e}")
        return None, None, None

def apply_date_filter(df, start_date=None, end_date=None, period_type='All'):
    if df is None or df.empty:
        return df
    date_col = None
    for col in ['Month', 'Sale_Date', 'Purchase_Date', 'Return_Date', 'Date']:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_col = col
                break
    if date_col is None:
        if 'Month_Label' in df.columns:
            try:
                df['_date_temp'] = pd.to_datetime(df['Month_Label'] + '-01')
                date_col = '_date_temp'
            except:
                pass
    if date_col is None:
        return df
    options, min_date, max_date = get_date_range_options()
    if options is None:
        return df
    if period_type == 'Custom':
        if start_date is not None:
            df = df[df[date_col] >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df[date_col] <= pd.to_datetime(end_date)]
    elif period_type in options and options[period_type] is not None:
        start_dt, end_dt = options[period_type]
        df = df[df[date_col] >= start_dt]
        df = df[df[date_col] <= end_dt]
    return df

def create_date_filter_sidebar():
    st.sidebar.markdown("### 📅 Date Period Filter")
    options, min_date, max_date = get_date_range_options()
    if options is None:
        st.sidebar.warning("No date data available")
        return None, None, None
    period_types = list(options.keys())
    default_period = 'All' if 'All' in period_types else period_types[0]
    if 'date_period_type' not in st.session_state:
        st.session_state.date_period_type = default_period
    selected_period = st.sidebar.selectbox(
        "Time Period",
        period_types,
        index=period_types.index(st.session_state.date_period_type) if st.session_state.date_period_type in period_types else 0,
        key="date_period_select"
    )
    start_date = None
    end_date = None
    if selected_period == 'Custom' and min_date and max_date:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=min_date.date(), min_value=min_date.date(), max_value=max_date.date())
        with col2:
            end_date = st.date_input("End Date", value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())
        if start_date and end_date and start_date > end_date:
            st.sidebar.error("Start date cannot be after end date!")
            start_date = end_date
    elif selected_period in options and options[selected_period] is not None:
        start_dt, end_dt = options[selected_period]
        start_date = start_dt.date() if hasattr(start_dt, 'date') else start_dt
        end_date = end_dt.date() if hasattr(end_dt, 'date') else end_dt
        st.sidebar.caption(f"📅 {start_dt.strftime('%b %d, %Y')} - {end_dt.strftime('%b %d, %Y')}")
    st.session_state.date_period_type = selected_period
    return start_date, end_date, selected_period

def create_year_quarter_filter():
    st.sidebar.markdown("### 📊 Year / Quarter Filter")
    conn = get_connection()
    try:
        years = conn.execute("SELECT DISTINCT Year FROM dashboard_data ORDER BY Year DESC").df()
        year_options = ['All'] + years['Year'].astype(str).tolist() if not years.empty else ['All']
        if 'filter_year' not in st.session_state:
            st.session_state.filter_year = 'All'
        if 'filter_quarter' not in st.session_state:
            st.session_state.filter_quarter = 'All'
        selected_year = st.sidebar.selectbox("Year", year_options, 
                                            index=year_options.index(st.session_state.filter_year) if st.session_state.filter_year in year_options else 0,
                                            key="filter_year_select")
        if selected_year != 'All':
            quarters = conn.execute("SELECT DISTINCT Quarter FROM dashboard_data WHERE Year = ? ORDER BY Quarter", [int(selected_year)]).df()
            quarter_options = ['All'] + quarters['Quarter'].astype(str).tolist() if not quarters.empty else ['All']
        else:
            quarter_options = ['All', '1', '2', '3', '4']
        selected_quarter = st.sidebar.selectbox("Quarter", quarter_options,
                                                index=quarter_options.index(st.session_state.filter_quarter) if st.session_state.filter_quarter in quarter_options else 0,
                                                key="filter_quarter_select")
        st.session_state.filter_year = selected_year
        st.session_state.filter_quarter = selected_quarter
        return selected_year, selected_quarter
    except Exception as e:
        st.sidebar.error(f"Error loading year/quarter data: {e}")
        return 'All', 'All'

# ============================================================================
# STOCK RETRIEVAL HELPERS
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_latest_stock_per_item(branch="All", location="All", product_group="All", 
                              division="All", item_code="All", item_name="All", supplier="All"):
    conn = get_connection()
    conditions = []
    params = []
    if branch != "All":
        conditions.append("LOWER(s.Branch_Location) = LOWER(?)")
        params.append(branch)
    if location != "All":
        conditions.append("LOWER(s.File_Location) = LOWER(?)")
        params.append(location)
    if product_group != "All":
        conditions.append("LOWER(im.Product_Group) = LOWER(?)")
        params.append(product_group)
    if division != "All":
        conditions.append("LOWER(im.Division) = LOWER(?)")
        params.append(division)
    if item_code != "All":
        conditions.append("UPPER(s.Item_Number) = UPPER(?)")
        params.append(item_code)
    if item_name != "All":
        conditions.append("UPPER(s.Item_Name) = UPPER(?)")
        params.append(item_name)
    if supplier != "All":
        conditions.append("UPPER(s.Item_Number) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))")
        params.append(supplier)
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        WITH latest_stock AS (
            SELECT Item_Number, Branch_Location, MAX(Month_End_Date) AS Latest_Date
            FROM stock_unpivoted GROUP BY Item_Number, Branch_Location
        )
        SELECT s.Item_Number AS Item_Code, s.Item_Name, s.Branch_Location AS Branch,
               s.File_Location AS Location, s.Stock_Qty AS Current_Stock_Qty,
               im.Product_Group, im.Division
        FROM stock_unpivoted s
        JOIN latest_stock l ON s.Item_Number = l.Item_Number AND s.Branch_Location = l.Branch_Location AND s.Month_End_Date = l.Latest_Date
        LEFT JOIN item_master im ON UPPER(s.Item_Number) = UPPER(im.Item_Code)
        WHERE {where_clause}
    """
    df = conn.execute(query, params).df()
    return df

# ============================================================================
# DATA LOADERS
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_filter_options():
    conn = get_connection()
    try:
        years = conn.execute("SELECT DISTINCT Year FROM yearly_summary ORDER BY Year DESC").df()
        year_options = ["All"] + [str(int(y)) for y in years['Year'].tolist()] if not years.empty else ["All"]
    except:
        year_options = ["All"]
    try:
        branches = conn.execute("SELECT DISTINCT Branch FROM location_master ORDER BY Branch").df()
        branch_options = ["All"] + branches['Branch'].tolist() if not branches.empty else ["All"]
    except:
        branch_options = ["All"]
    try:
        locations = conn.execute("SELECT DISTINCT Location FROM location_master ORDER BY Location").df()
        location_options = ["All"] + locations['Location'].tolist() if not locations.empty else ["All"]
    except:
        location_options = ["All"]
    try:
        product_groups = conn.execute("SELECT DISTINCT Product_Group FROM item_master ORDER BY Product_Group").df()
        pg_options = ["All"] + product_groups['Product_Group'].tolist() if not product_groups.empty else ["All"]
    except:
        pg_options = ["All"]
    try:
        divisions = conn.execute("SELECT DISTINCT Division FROM item_master ORDER BY Division").df()
        div_options = ["All"] + divisions['Division'].tolist() if not divisions.empty else ["All"]
    except:
        div_options = ["All"]
    try:
        item_codes = conn.execute("SELECT DISTINCT Item_Code FROM item_master ORDER BY Item_Code").df()
        code_options = ["All"] + item_codes['Item_Code'].tolist() if not item_codes.empty else ["All"]
    except:
        code_options = ["All"]
    try:
        item_names = conn.execute("SELECT DISTINCT Item_Name FROM item_master ORDER BY Item_Name").df()
        name_options = ["All"] + item_names['Item_Name'].tolist() if not item_names.empty else ["All"]
    except:
        name_options = ["All"]
    try:
        suppliers = conn.execute("SELECT DISTINCT Supplier FROM supplier_purchase_summary ORDER BY Supplier").df()
        supplier_options = ["All"] + suppliers['Supplier'].tolist() if not suppliers.empty else ["All"]
    except:
        supplier_options = ["All"]
    try:
        vendors = conn.execute("SELECT DISTINCT Vendor FROM purchase_all ORDER BY Vendor").df()
        vendor_options = ["All"] + vendors['Vendor'].tolist() if not vendors.empty else ["All"]
    except:
        vendor_options = ["All"]
    return {
        'years': year_options, 'branches': branch_options, 'locations': location_options,
        'product_groups': pg_options, 'divisions': div_options,
        'item_codes': code_options, 'item_names': name_options,
        'suppliers': supplier_options, 'vendors': vendor_options
    }

@st.cache_data(ttl=300, show_spinner=False)
def load_all_data(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
    conn = get_connection()
    result = {}
    use_global = (branch == "All" and location == "All")
    
    def get_supplier_items():
        if supplier != "All":
            items_df = conn.execute("SELECT Item_Code FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?)", [supplier]).df()
            return items_df['Item_Code'].tolist() if not items_df.empty else []
        return []
    
    supplier_items = get_supplier_items()
    
    # Monthly Summary
    monthly_conditions = []; monthly_params = []
    if year != "All":
        monthly_conditions.append("Year = ?"); monthly_params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            monthly_conditions.append("Month_Num = ?"); monthly_params.append(month_num)
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            monthly_conditions.append("Quarter = ?"); monthly_params.append(q)
    monthly_where = " AND ".join(monthly_conditions) if monthly_conditions else "1=1"
    monthly_query = f"""
        SELECT Month_Label, Year, Month_Num, Total_Sales, Total_Qty, Total_Transactions,
               Total_Returns, Total_Return_Qty, Total_Return_Transactions,
               Total_Net, Total_Net_Qty, Total_Net_Transactions,
               Active_Products, Active_Branches
        FROM monthly_summary WHERE {monthly_where} ORDER BY Year, Month_Num
    """
    try:
        result['monthly_data'] = conn.execute(monthly_query, monthly_params).df()
    except Exception as e:
        st.error(f"Error loading monthly_data: {e}")
        result['monthly_data'] = pd.DataFrame()
    
    # Yearly Summary
    yearly_conditions = []; yearly_params = []
    if year != "All":
        yearly_conditions.append("Year = ?"); yearly_params.append(int(year))
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            yearly_conditions.append("Quarter = ?"); yearly_params.append(q)
    yearly_where = " AND ".join(yearly_conditions) if yearly_conditions else "1=1"
    yearly_query = f"""
        SELECT Year, SUM(Total_Sales) as Total_Sales, SUM(Total_Qty) as Total_Qty,
               SUM(Total_Transactions) as Total_Transactions, SUM(Total_Returns) as Total_Returns,
               SUM(Total_Return_Qty) as Total_Return_Qty, SUM(Total_Return_Transactions) as Total_Return_Transactions,
               SUM(Total_Net) as Total_Net, SUM(Total_Net_Qty) as Total_Net_Qty,
               SUM(Total_Net_Transactions) as Total_Net_Transactions
        FROM monthly_summary WHERE {yearly_where} GROUP BY Year ORDER BY Year DESC
    """
    try:
        result['yearly_data'] = conn.execute(yearly_query, yearly_params).df()
    except Exception as e:
        st.error(f"Error loading yearly_data: {e}")
        result['yearly_data'] = pd.DataFrame()
    
    # Branch Performance
    branch_conditions = []; branch_params = []
    if year != "All":
        branch_conditions.append("Year = ?"); branch_params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            branch_conditions.append("Month_Num = ?"); branch_params.append(month_num)
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            branch_conditions.append("Quarter = ?"); branch_params.append(q)
    if branch != "All":
        branch_conditions.append("Branch = ?"); branch_params.append(branch)
    if location != "All":
        branch_conditions.append("Location = ?"); branch_params.append(location)
    if supplier != "All" and supplier_items:
        supplier_branches_query = """
            SELECT DISTINCT Branch FROM branch_item_summary 
            WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))
        """
        supplier_branches_df = conn.execute(supplier_branches_query, [supplier]).df()
        supplier_branches = supplier_branches_df['Branch'].tolist() if not supplier_branches_df.empty else []
        if supplier_branches:
            placeholders = ','.join(['?'] * len(supplier_branches))
            branch_conditions.append(f"Branch IN ({placeholders})")
            branch_params.extend(supplier_branches)
        else:
            result['branch_performance'] = pd.DataFrame()
    branch_where = " AND ".join(branch_conditions) if branch_conditions else "1=1"
    branch_query = f"""
        SELECT Branch, SUM(Sales_Amount) as Total_Sales, SUM(Qty_Sold) as Total_Qty,
               SUM(Sales_Transactions) as Total_Transactions, SUM(Return_Amount) as Total_Returns,
               SUM(Return_Transactions) as Return_Transactions, SUM(Net_Amount) as Total_Net,
               SUM(Net_Transactions) as Net_Transactions, SUM(Unique_Products) as Unique_Products
        FROM branch_monthly_summary WHERE {branch_where} GROUP BY Branch ORDER BY Total_Sales DESC
    """
    try:
        result['branch_performance'] = conn.execute(branch_query, branch_params).df()
        if not result['branch_performance'].empty:
            result['branch_performance']['Avg_Transaction_Value'] = (
                result['branch_performance']['Total_Sales'] / 
                result['branch_performance']['Total_Transactions'].replace(0, np.nan)
            ).fillna(0)
    except Exception as e:
        st.error(f"Error loading branch_performance: {e}")
        result['branch_performance'] = pd.DataFrame()
    
    # Category Performance
    cat_conditions = []; cat_params = []
    if year != "All":
        cat_conditions.append("Year = ?"); cat_params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            cat_conditions.append("Month_Num = ?"); cat_params.append(month_num)
    if product_group != "All":
        cat_conditions.append("Product_Group = ?"); cat_params.append(product_group)
    if supplier != "All" and supplier_items:
        supplier_pg_query = """
            SELECT DISTINCT Product_Group FROM item_master 
            WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))
            AND Product_Group IS NOT NULL AND Product_Group != ''
        """
        supplier_pg_df = conn.execute(supplier_pg_query, [supplier]).df()
        supplier_pgs = supplier_pg_df['Product_Group'].tolist() if not supplier_pg_df.empty else []
        if supplier_pgs:
            placeholders = ','.join(['?'] * len(supplier_pgs))
            cat_conditions.append(f"Product_Group IN ({placeholders})")
            cat_params.extend(supplier_pgs)
        else:
            result['category_performance'] = pd.DataFrame()
    cat_where = " AND ".join(cat_conditions) if cat_conditions else "1=1"
    cat_query = f"""
        SELECT Product_Group, SUM(Sales_Amount) as Total_Sales, SUM(Qty_Sold) as Total_Qty,
               SUM(Sales_Transactions) as Total_Transactions, SUM(Return_Amount) as Total_Returns,
               SUM(Unique_Products) as Unique_Products
        FROM category_monthly_summary WHERE {cat_where} GROUP BY Product_Group ORDER BY Total_Sales DESC
    """
    try:
        result['category_performance'] = conn.execute(cat_query, cat_params).df()
    except Exception as e:
        st.error(f"Error loading category_performance: {e}")
        result['category_performance'] = pd.DataFrame()
    
    # Item Performance
    item_conditions = []; item_params = []
    if product_group != "All":
        item_conditions.append("Product_Group = ?"); item_params.append(product_group)
    if division != "All":
        item_conditions.append("Division = ?"); item_params.append(division)
    if item_code != "All":
        item_conditions.append("UPPER(Item_Code) = UPPER(?)"); item_params.append(item_code)
    if item_name != "All":
        item_conditions.append("UPPER(Item_Name) = UPPER(?)"); item_params.append(item_name)
    if supplier != "All" and supplier_items:
        item_conditions.append("UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))")
        item_params.append(supplier)
    item_where = " AND ".join(item_conditions) if item_conditions else "1=1"
    item_query = f"""
        SELECT Item_Code, Item_Name, Product_Group, Brand_Name, Division,
               Total_Sales, Total_Qty, Total_Transactions, Total_Returns, Total_Net
        FROM item_total_summary WHERE {item_where} ORDER BY Total_Sales DESC
    """
    try:
        result['item_performance'] = conn.execute(item_query, item_params).df()
    except Exception as e:
        st.error(f"Error loading item_performance: {e}")
        result['item_performance'] = pd.DataFrame()
    
    # Monthly Item Data
    item_monthly_conditions = []
    item_monthly_params = []
    if year != "All":
        item_monthly_conditions.append("Year = ?")
        item_monthly_params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            item_monthly_conditions.append("Month_Num = ?")
            item_monthly_params.append(month_num)
    if product_group != "All":
        item_monthly_conditions.append("Product_Group = ?")
        item_monthly_params.append(product_group)
    if division != "All":
        item_monthly_conditions.append("Division = ?")
        item_monthly_params.append(division)
    if item_code != "All":
        item_monthly_conditions.append("UPPER(Item_Code) = UPPER(?)")
        item_monthly_params.append(item_code)
    if item_name != "All":
        item_monthly_conditions.append("UPPER(Item_Name) = UPPER(?)")
        item_monthly_params.append(item_name)
    if supplier != "All" and supplier_items:
        item_monthly_conditions.append("UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))")
        item_monthly_params.append(supplier)
    if not use_global:
        if branch != "All":
            item_monthly_conditions.append("Branch = ?")
            item_monthly_params.append(branch)
        if location != "All":
            item_monthly_conditions.append("Location = ?")
            item_monthly_params.append(location)
    item_monthly_where = " AND ".join(item_monthly_conditions) if item_monthly_conditions else "1=1"
    if use_global:
        item_monthly_query = f"""
            SELECT Month_Label, Year, Month_Num, Item_Code, Item_Name, Product_Group, Division,
                   Sales_Amount, Qty_Sold, Sales_Transactions,
                   Return_Amount, Qty_Returned, Return_Transactions,
                   Net_Amount, Net_Qty, Net_Transactions
            FROM item_monthly_summary WHERE {item_monthly_where} ORDER BY Year, Month_Num, Item_Name
        """
    else:
        item_monthly_query = f"""
            SELECT Month_Label, Year, Month_Num, Item_Code, Item_Name, Product_Group, Division,
                   Sales_Amount, Qty_Sold, Sales_Transactions,
                   Return_Amount, Qty_Returned, Return_Transactions,
                   Net_Amount, Net_Qty, Net_Transactions
            FROM branch_item_monthly_summary WHERE {item_monthly_where} ORDER BY Year, Month_Num, Item_Name
        """
    try:
        result['item_monthly_data'] = conn.execute(item_monthly_query, item_monthly_params).df()
    except Exception as e:
        st.warning(f"Error loading item_monthly_data: {e}")
        result['item_monthly_data'] = pd.DataFrame()
    
    # Monthly Growth
    if not result['monthly_data'].empty:
        df = result['monthly_data'].sort_values(['Year', 'Month_Num'])
        df['Sales_Growth'] = df['Total_Sales'].pct_change() * 100
        df['Qty_Growth'] = df['Total_Qty'].pct_change() * 100
        df['Transaction_Growth'] = df['Total_Transactions'].pct_change() * 100
        result['monthly_growth'] = df
    else:
        result['monthly_growth'] = pd.DataFrame()
    
    # Quarterly Performance
    q_conditions = []; q_params = []
    if year != "All":
        q_conditions.append("Year = ?"); q_params.append(int(year))
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            q_conditions.append("Quarter = ?"); q_params.append(q)
    if branch != "All":
        q_conditions.append("Branch = ?"); q_params.append(branch)
    if location != "All":
        q_conditions.append("Location = ?"); q_params.append(location)
    if supplier != "All" and supplier_items:
        supplier_branches_query = """
            SELECT DISTINCT Branch FROM branch_item_summary 
            WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))
        """
        supplier_branches_df = conn.execute(supplier_branches_query, [supplier]).df()
        supplier_branches = supplier_branches_df['Branch'].tolist() if not supplier_branches_df.empty else []
        if supplier_branches:
            placeholders = ','.join(['?'] * len(supplier_branches))
            q_conditions.append(f"Branch IN ({placeholders})")
            q_params.extend(supplier_branches)
        else:
            result['quarterly_performance'] = pd.DataFrame()
    q_where = " AND ".join(q_conditions) if q_conditions else "1=1"
    q_query = f"""
        SELECT Quarter, Year, SUM(Sales_Amount) as Total_Sales, SUM(Qty_Sold) as Total_Qty,
               SUM(Sales_Transactions) as Total_Transactions, SUM(Return_Amount) as Total_Returns,
               SUM(Net_Amount) as Total_Net
        FROM branch_monthly_summary WHERE {q_where} GROUP BY Quarter, Year ORDER BY Year, Quarter
    """
    try:
        result['quarterly_performance'] = conn.execute(q_query, q_params).df()
    except Exception as e:
        st.error(f"Error loading quarterly_performance: {e}")
        result['quarterly_performance'] = pd.DataFrame()
    
    return result

# ============================================================================
# FOC DATA LOADER
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_foc_data(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
    conn = get_connection()
    result = {}
    
    def get_supplier_condition():
        if supplier != "All":
            return f" AND UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER('{supplier}'))"
        return ""
    
    supplier_condition = get_supplier_condition()
    
    foc_conditions = []
    foc_params = []
    if year != "All":
        foc_conditions.append("Year = ?"); foc_params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            foc_conditions.append("Month_Num = ?"); foc_params.append(month_num)
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            foc_conditions.append("Quarter = ?"); foc_params.append(q)
    if branch != "All":
        foc_conditions.append("Branch = ?"); foc_params.append(branch)
    if location != "All":
        foc_conditions.append("Location = ?"); foc_params.append(location)
    if item_code != "All":
        foc_conditions.append("UPPER(Item_Code) = UPPER(?)"); foc_params.append(item_code)
    if item_name != "All":
        foc_conditions.append("UPPER(Item_Name) = UPPER(?)"); foc_params.append(item_name)
    if product_group != "All":
        foc_conditions.append("Product_Group = ?"); foc_params.append(product_group)
    if division != "All":
        foc_conditions.append("Division = ?"); foc_params.append(division)
    foc_where = " AND ".join(foc_conditions) if foc_conditions else "1=1"
    
    try:
        query = f"""
            SELECT Item_Code, Item_Name, Product_Group, Division, Branch, Location,
                   Total_Qty_Sold, Total_FOC_Qty, Paid_Qty, Total_Transactions,
                   FOC_Transactions, Avg_FOC_Per_Transaction, FOC_Percentage
            FROM foc_sales_summary WHERE {foc_where} {supplier_condition} ORDER BY Total_FOC_Qty DESC
        """
        result['foc_sales_summary'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_sales_summary: {e}")
        result['foc_sales_summary'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Month_Label, Year, Month_Num, Quarter,
                   Total_Qty, Total_FOC_Qty, Paid_Qty,
                   Total_Revenue, FOC_Revenue_Value,
                   FOC_Pct, FOC_Value_Pct, FOC_Transactions, Total_Transactions
            FROM foc_sales_monthly WHERE {foc_where} {supplier_condition} ORDER BY Year, Month_Num
        """
        result['foc_monthly'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_monthly: {e}")
        result['foc_monthly'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Purchase_Type, Branch, Vendor, Item_Code, Item_Name,
                   Total_Purchase_Qty, Total_FOC_Qty, Total_Amount,
                   FOC_Transactions, Avg_FOC_Per_Transaction, FOC_Percentage
            FROM foc_purchase_summary WHERE {foc_where} {supplier_condition} ORDER BY Total_FOC_Qty DESC
        """
        result['foc_purchase_summary'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_purchase_summary: {e}")
        result['foc_purchase_summary'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Purchase_Type, Month_Label, Year, Month_Num, Quarter,
                   Total_Qty, Total_FOC_Qty, Total_Amount,
                   FOC_Transactions, FOC_Percentage
            FROM foc_purchase_monthly WHERE {foc_where} {supplier_condition} ORDER BY Year, Month_Num
        """
        result['foc_purchase_monthly'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_purchase_monthly: {e}")
        result['foc_purchase_monthly'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Sale_Date, Branch, Item_Code, Item_Name,
                   Quantity, Free_Qty, Amount_USD, anomaly_type
            FROM foc_sales_outliers WHERE {foc_where} {supplier_condition} ORDER BY Free_Qty DESC
        """
        result['foc_outliers'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_outliers: {e}")
        result['foc_outliers'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Branch, Location, Unique_Products_With_FOC, Total_Qty_Sold,
                   Total_FOC_Qty, Paid_Qty, FOC_Transactions,
                   Overall_FOC_Pct, Avg_FOC_When_Present
            FROM foc_sales_by_branch WHERE {foc_where} {supplier_condition} ORDER BY Total_FOC_Qty DESC
        """
        result['foc_by_branch'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_by_branch: {e}")
        result['foc_by_branch'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Product_Group, Total_Qty_Sold, Total_FOC_Qty,
                   Paid_Qty, FOC_Transactions, FOC_Percentage,
                   Total_Revenue, FOC_Revenue_Value, FOC_Value_Pct
            FROM foc_sales_by_group WHERE 1=1 {supplier_condition.replace('Item_Code', 'Item_Code')} ORDER BY Total_FOC_Qty DESC
        """
        result['foc_by_group'] = conn.execute(query).df()
    except Exception as e:
        st.warning(f"Error loading foc_by_group: {e}")
        result['foc_by_group'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Month_Label, Year, Month_Num, Quarter,
                   Total_Qty, FOC_Qty, Paid_Qty,
                   FOC_Pct, Total_Revenue, FOC_Revenue, FOC_Value_Pct,
                   FOC_MA_3, FOC_MA_6
            FROM foc_demand_impact WHERE 1=1 ORDER BY Year, Month_Num
        """
        result['foc_demand_impact'] = conn.execute(query).df()
    except Exception as e:
        st.warning(f"Error loading foc_demand_impact: {e}")
        result['foc_demand_impact'] = pd.DataFrame()
    
    try:
        query = f"""
            SELECT Data_Type, Item_Code, Item_Name, Product_Group,
                   Branch, Total_FOC_Qty, FOC_Pct,
                   FOC_Severity, Recommendation
            FROM foc_recommendations WHERE {foc_where} {supplier_condition} ORDER BY FOC_Pct DESC
        """
        result['foc_recommendations'] = conn.execute(query, foc_params).df()
    except Exception as e:
        st.warning(f"Error loading foc_recommendations: {e}")
        result['foc_recommendations'] = pd.DataFrame()
    
    return result

# ============================================================================
# PURCHASE DATA LOADER
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_purchase_data(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All", vendor="All", purchase_type="All"):
    conn = get_connection()
    query = """
        SELECT Purchase_Date, Purchase_Type, Branch, Vendor, Item_Code, Item_Name,
               Qty, Amount_USD, Supplier_Rate, Country, Carrier,
               Shipping_Lead_Time, Unit, FOC_Qty
        FROM purchase_all_clean WHERE Purchase_Date IS NOT NULL
    """
    params = []
    if year != "All":
        query += " AND EXTRACT(YEAR FROM Purchase_Date) = ?"
        params.append(int(year))
    if month != "All":
        month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                     "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        month_num = month_map.get(month)
        if month_num:
            query += " AND EXTRACT(MONTH FROM Purchase_Date) = ?"
            params.append(month_num)
    if period != "All":
        quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
        q = quarter_map.get(period)
        if q:
            query += " AND EXTRACT(QUARTER FROM Purchase_Date) = ?"
            params.append(q)
    if branch != "All":
        query += " AND Branch = ?"
        params.append(branch)
    if location != "All":
        query += " AND Branch IN (SELECT Branch FROM location_master WHERE Location = ?)"
        params.append(location)
    if item_code != "All":
        query += " AND UPPER(Item_Code) = UPPER(?)"
        params.append(item_code)
    elif item_name != "All":
        query += " AND UPPER(Item_Name) = UPPER(?)"
        params.append(item_name)
    if product_group != "All" or division != "All":
        query += " AND Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
        if product_group != "All":
            query += " AND LOWER(Product_Group) = LOWER(?)"
            params.append(product_group)
        if division != "All":
            query += " AND LOWER(Division) = LOWER(?)"
            params.append(division)
        query += ")"
    if supplier != "All":
        query += " AND UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))"
        params.append(supplier)
    if vendor != "All":
        query += " AND Vendor = ?"
        params.append(vendor)
    if purchase_type != "All":
        query += " AND Purchase_Type = ?"
        params.append(purchase_type)
    query += " ORDER BY Purchase_Date DESC"
    try:
        df = conn.execute(query, params).df()
        return df
    except Exception as e:
        st.error(f"Error loading purchase data: {e}")
        return pd.DataFrame()

# ============================================================================
# SUPPLIER DATA LOADER
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_supplier_data(year, month, period, branch, location, product_group, division, item_code, item_name, supplier="All"):
    conn = get_connection()
    result = {}
    
    query_summary = """
        SELECT Supplier, Total_Products_Purchased as Unique_Products,
               Total_Purchase_Amount as Total_Sales,
               Total_Purchase_Qty as Total_Qty, Total_Transactions,
               Total_Purchase_Amount as Total_Purchase_Spend,
               Total_Purchase_Qty as Total_Purchase_Qty,
               Avg_Unit_Cost as Avg_Purchase_Price,
               Countries as Product_Groups
        FROM supplier_purchase_summary WHERE 1=1
    """
    params = []
    if supplier != "All":
        query_summary += " AND UPPER(Supplier) = UPPER(?)"
        params.append(supplier)
    query_summary += " ORDER BY Total_Purchase_Amount DESC"
    try:
        result['supplier_summary'] = conn.execute(query_summary, params).df()
    except Exception as e:
        st.warning(f"Error loading supplier_summary: {e}")
        result['supplier_summary'] = pd.DataFrame()
    
    query_perf = """
        SELECT Supplier_Name, Total_POs, Unique_Items,
               Total_Ordered_Qty, Total_Invoiced_Value,
               Avg_Unit_Price, Closed_POs, Open_POs,
               Avg_PO_Age_Days, Total_Advance_Paid, Total_Outstanding_Balance
        FROM supplier_performance WHERE 1=1
    """
    params_perf = []
    if supplier != "All":
        query_perf += " AND UPPER(Supplier_Name) = UPPER(?)"
        params_perf.append(supplier)
    query_perf += " ORDER BY Total_Invoiced_Value DESC"
    try:
        result['supplier_performance'] = conn.execute(query_perf, params_perf).df()
    except Exception as e:
        st.warning(f"Error loading supplier_performance: {e}")
        result['supplier_performance'] = pd.DataFrame()
    
    query_risk = """
        SELECT Supplier, Product_Count, Total_Revenue, Total_Qty,
               Product_Groups, Primary_Product_Count,
               High_Risk_Products, Medium_Risk_Products, Low_Risk_Products,
               Risk_Level, Primary_Supplier_Status
        FROM supplier_risk_analysis WHERE 1=1
    """
    params_risk = []
    if supplier != "All":
        query_risk += " AND UPPER(Supplier) = UPPER(?)"
        params_risk.append(supplier)
    query_risk += " ORDER BY Total_Revenue DESC"
    try:
        result['supplier_risk'] = conn.execute(query_risk, params_risk).df()
    except Exception as e:
        st.warning(f"Error loading supplier_risk: {e}")
        result['supplier_risk'] = pd.DataFrame()
    
    query_mapping = """
        SELECT Item_Code, Item_Name, Product_Group, Division, Brand_Name,
               Supplier, Total_Purchase_Qty as Purchase_Qty,
               Total_Purchase_Amount as Purchase_Spend,
               Avg_Unit_Cost, Transaction_Count, Countries_Sourced
        FROM supplier_purchase_by_item WHERE 1=1
    """
    params_mapping = []
    if supplier != "All":
        query_mapping += " AND UPPER(Supplier) = UPPER(?)"
        params_mapping.append(supplier)
    if product_group != "All":
        query_mapping += " AND LOWER(Product_Group) = LOWER(?)"
        params_mapping.append(product_group)
    if division != "All":
        query_mapping += " AND LOWER(Division) = LOWER(?)"
        params_mapping.append(division)
    if item_code != "All":
        query_mapping += " AND UPPER(Item_Code) = UPPER(?)"
        params_mapping.append(item_code)
    if item_name != "All":
        query_mapping += " AND UPPER(Item_Name) = UPPER(?)"
        params_mapping.append(item_name)
    query_mapping += " ORDER BY Supplier, Total_Purchase_Amount DESC"
    try:
        result['supplier_product_mapping'] = conn.execute(query_mapping, params_mapping).df()
    except Exception as e:
        st.warning(f"Error loading supplier_product_mapping: {e}")
        result['supplier_product_mapping'] = pd.DataFrame()
    
    query_perf_prod = """
        SELECT Supplier, Item_Code, Item_Name, Product_Group, Division,
               Is_Primary_Supplier, Total_Sales, Total_Qty, Total_Transactions,
               Purchase_Spend, Purchase_Qty, Avg_Purchase_Price
        FROM supplier_product_performance WHERE 1=1
    """
    params_perf_prod = []
    if supplier != "All":
        query_perf_prod += " AND UPPER(Supplier) = UPPER(?)"
        params_perf_prod.append(supplier)
    if product_group != "All":
        query_perf_prod += " AND LOWER(Product_Group) = LOWER(?)"
        params_perf_prod.append(product_group)
    if division != "All":
        query_perf_prod += " AND LOWER(Division) = LOWER(?)"
        params_perf_prod.append(division)
    if item_code != "All":
        query_perf_prod += " AND UPPER(Item_Code) = UPPER(?)"
        params_perf_prod.append(item_code)
    if item_name != "All":
        query_perf_prod += " AND UPPER(Item_Name) = UPPER(?)"
        params_perf_prod.append(item_name)
    query_perf_prod += " ORDER BY Total_Sales DESC"
    try:
        result['supplier_product_performance'] = conn.execute(query_perf_prod, params_perf_prod).df()
    except Exception as e:
        st.warning(f"Error loading supplier_product_performance: {e}")
        result['supplier_product_performance'] = pd.DataFrame()
    
    query_demand = """
        SELECT Supplier, Total_Items, Total_Revenue, Total_Qty,
               Avg_Stability, Stable_Items, Variable_Items,
               Primary_Products, Avg_Purchase_Price, Product_Groups
        FROM supplier_demand_forecast WHERE 1=1
    """
    params_demand = []
    if supplier != "All":
        query_demand += " AND UPPER(Supplier) = UPPER(?)"
        params_demand.append(supplier)
    if product_group != "All" or division != "All":
        query_demand += " AND Supplier IN (SELECT DISTINCT Supplier FROM supplier_product_mapping WHERE 1=1"
        if product_group != "All":
            query_demand += " AND LOWER(Product_Group) = LOWER(?)"
            params_demand.append(product_group)
        if division != "All":
            query_demand += " AND LOWER(Division) = LOWER(?)"
            params_demand.append(division)
        query_demand += ")"
    query_demand += " ORDER BY Total_Revenue DESC"
    try:
        result['supplier_demand_forecast'] = conn.execute(query_demand, params_demand).df()
    except Exception as e:
        st.warning(f"Error loading supplier_demand_forecast: {e}")
        result['supplier_demand_forecast'] = pd.DataFrame()
    
    return result

# ============================================================================
# SAFETY STOCK HELPERS
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_safety_stock_by_item(branch="All", location="All", product_group="All", 
                              division="All", item_code="All", supplier="All"):
    conn = get_connection()
    query = """
        SELECT Item_Code, Item_Name, Product_Group, Primary_Supplier,
               Supplier_Location, Lead_Time, Avg_Daily_Demand_Qty,
               Avg_Daily_Demand_Value, Demand_Stability_Index,
               Safety_Stock_Qty, Safety_Stock_Value, Reorder_Point_Qty,
               Reorder_Point_Value, Current_Stock, Short_Excess,
               Lead_Time_Category, Demand_Category
        FROM safety_stock_by_item WHERE 1=1
    """
    params = []
    if branch != "All":
        query += " AND LOWER(Supplier_Location) = LOWER(?)"
        params.append(branch)
    if location != "All":
        query += " AND LOWER(Supplier_Location) = LOWER(?)"
        params.append(location)
    if product_group != "All":
        query += " AND LOWER(Product_Group) = LOWER(?)"
        params.append(product_group)
    if division != "All":
        query += " AND Division = ?"
        params.append(division)
    if item_code != "All":
        query += " AND UPPER(Item_Code) = UPPER(?)"
        params.append(item_code)
    if supplier != "All":
        query += " AND UPPER(Primary_Supplier) = UPPER(?)"
        params.append(supplier)
    query += " ORDER BY Safety_Stock_Qty DESC"
    try:
        df = conn.execute(query, params).df()
        return df
    except Exception as e:
        st.error(f"Error loading safety stock data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_safety_stock_summary():
    conn = get_connection()
    try:
        df = conn.execute("SELECT * FROM safety_stock_summary ORDER BY Total_Safety_Stock_Qty DESC").df()
        return df
    except Exception as e:
        return pd.DataFrame()

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

if "page" not in st.session_state:
    st.session_state.page = "📊 Executive Dashboard"
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "accent_color" not in st.session_state:
    st.session_state.accent_color = "#0066CC"
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Monthly"
if "view_type" not in st.session_state:
    st.session_state.view_type = "💰 Value"
if "chart_type" not in st.session_state:
    st.session_state.chart_type = "Bar"
if "show_ma" not in st.session_state:
    st.session_state.show_ma = True
if "top_n" not in st.session_state:
    st.session_state.top_n = 10
if "top_bottom_mode" not in st.session_state:
    st.session_state.top_bottom_mode = "Top"
if "n_selection" not in st.session_state:
    st.session_state.n_selection = 10
if "top_transactions_n" not in st.session_state:
    st.session_state.top_transactions_n = 100
if "forecast_method" not in st.session_state:
    st.session_state.forecast_method = "MA_3"
if "vendor" not in st.session_state:
    st.session_state.vendor = "All"
if "purchase_type" not in st.session_state:
    st.session_state.purchase_type = "All"
if "show_forecast_confidence" not in st.session_state:
    st.session_state.show_forecast_confidence = True
if "show_anomalies" not in st.session_state:
    st.session_state.show_anomalies = True
if "comparison_mode" not in st.session_state:
    st.session_state.comparison_mode = "Year-over-Year"
if "show_stock_alerts" not in st.session_state:
    st.session_state.show_stock_alerts = True
if "dashboard_layout" not in st.session_state:
    st.session_state.dashboard_layout = "Standard"
if "show_predictions" not in st.session_state:
    st.session_state.show_predictions = True
if "forecast_horizon" not in st.session_state:
    st.session_state.forecast_horizon = 6
if "confidence_interval" not in st.session_state:
    st.session_state.confidence_interval = 95
if "show_trend_line" not in st.session_state:
    st.session_state.show_trend_line = True
if "show_seasonality" not in st.session_state:
    st.session_state.show_seasonality = True
if "comparison_periods" not in st.session_state:
    st.session_state.comparison_periods = 3
if "year" not in st.session_state:
    st.session_state.year = "All"
if "month" not in st.session_state:
    st.session_state.month = "All"
if "period" not in st.session_state:
    st.session_state.period = "All"
if "branch" not in st.session_state:
    st.session_state.branch = "All"
if "location" not in st.session_state:
    st.session_state.location = "All"
if "item_code" not in st.session_state:
    st.session_state.item_code = "All"
if "item_name" not in st.session_state:
    st.session_state.item_name = "All"
if "product_group" not in st.session_state:
    st.session_state.product_group = "All"
if "division" not in st.session_state:
    st.session_state.division = "All"
if "supplier" not in st.session_state:
    st.session_state.supplier = "All"
if "date_period_type" not in st.session_state:
    st.session_state.date_period_type = "All"
if "date_start" not in st.session_state:
    st.session_state.date_start = None
if "date_end" not in st.session_state:
    st.session_state.date_end = None
if "filter_year" not in st.session_state:
    st.session_state.filter_year = "All"
if "filter_quarter" not in st.session_state:
    st.session_state.filter_quarter = "All"
if "ui_compact_mode" not in st.session_state:
    st.session_state.ui_compact_mode = False
if "ui_show_tooltips" not in st.session_state:
    st.session_state.ui_show_tooltips = True
if "ui_animation_speed" not in st.session_state:
    st.session_state.ui_animation_speed = "Normal"
if "ui_color_blind_mode" not in st.session_state:
    st.session_state.ui_color_blind_mode = False
if "show_advanced_analytics" not in st.session_state:
    st.session_state.show_advanced_analytics = False
if "show_prediction_intervals" not in st.session_state:
    st.session_state.show_prediction_intervals = True
if "show_correlation_matrix" not in st.session_state:
    st.session_state.show_correlation_matrix = False
if "show_outlier_analysis" not in st.session_state:
    st.session_state.show_outlier_analysis = True
if "show_market_share" not in st.session_state:
    st.session_state.show_market_share = True
if "export_format" not in st.session_state:
    st.session_state.export_format = "CSV"
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 300

# ============================================================================
# PROFESSIONAL CSS
# ============================================================================

def load_css(theme, accent):
    bg = "#0a0e1a" if theme == "dark" else "#f4f6f9"
    card_bg = "#141b2d" if theme == "dark" else "#ffffff"
    card_bg_alt = "#1a2236" if theme == "dark" else "#f8f9fa"
    text = "#e8edf5" if theme == "dark" else "#1a2332"
    text_secondary = "#8899bb" if theme == "dark" else "#6b7a8f"
    border = "#2a3450" if theme == "dark" else "#e4e7ed"
    shadow = "0 4px 24px rgba(0,0,0,0.4)" if theme == "dark" else "0 4px 24px rgba(0,0,0,0.06)"
    
    if st.session_state.ui_color_blind_mode:
        accent = "#0077BB"
        color_palette = """#0077BB, #EE7733, #009988, #CC3311, #33BBEE, #EE3377, #BBBBBB, #000000"""
    else:
        color_palette = """#0066CC, #22c55e, #f59e0b, #ef4444, #8b5cf6, #3b82f6, #ec4899, #14b8a6"""
    
    return f"""
    <style>
        .stApp {{ background-color: {bg}; color: {text}; transition: all 0.3s ease; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: #0d1528; border-radius: 3px; }}
        ::-webkit-scrollbar-thumb {{ background: #2a3450; border-radius: 3px; transition: all 0.3s ease; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {accent}; }}
        .main-header {{ font-size: 2.4rem; font-weight: 700; background: linear-gradient(135deg, {accent}, #7b5ea7, #22c55e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding: 0.5rem 0 0.2rem 0; letter-spacing: -0.5px; animation: fadeInDown 0.8s ease-out; }}
        .sub-header {{ font-size: 1rem; color: {text_secondary}; margin-bottom: 1.5rem; font-weight: 400; animation: fadeInUp 0.6s ease-out; }}
        .section-title {{ font-size: 1.5rem; font-weight: 600; color: {text}; margin: 28px 0 16px 0; display: flex; align-items: center; gap: 12px; animation: slideInLeft 0.6s ease-out; }}
        .section-title::after {{ content: ''; flex: 1; height: 2px; background: linear-gradient(90deg, {accent}, transparent); border-radius: 2px; }}
        .kpi-card {{ background: {card_bg}; border-radius: 16px; padding: 20px 24px; border: 1px solid {border}; box-shadow: {shadow}; height: 100%; position: relative; overflow: hidden; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); cursor: pointer; animation: fadeInUp 0.6s ease-out forwards; opacity: 0; }}
        .kpi-card:nth-child(1) {{ animation-delay: 0.05s; }}
        .kpi-card:nth-child(2) {{ animation-delay: 0.10s; }}
        .kpi-card:nth-child(3) {{ animation-delay: 0.15s; }}
        .kpi-card:nth-child(4) {{ animation-delay: 0.20s; }}
        .kpi-card:nth-child(5) {{ animation-delay: 0.25s; }}
        .kpi-card:nth-child(6) {{ animation-delay: 0.30s; }}
        .kpi-card:nth-child(7) {{ animation-delay: 0.35s; }}
        .kpi-card:nth-child(8) {{ animation-delay: 0.40s; }}
        .kpi-card:hover {{ transform: translateY(-4px) scale(1.01); box-shadow: 0 12px 48px rgba(0,0,0,0.5); border-color: {accent}66; }}
        .kpi-card::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, {accent}, #7b5ea7, #22c55e); animation: shimmer 3s infinite; background-size: 200% 100%; }}
        .kpi-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.8px; color: {text_secondary}; font-weight: 600; position: relative; z-index: 1; }}
        .kpi-value {{ font-size: 2.2rem; font-weight: 700; color: {text}; margin: 4px 0; font-feature-settings: "tnum"; letter-spacing: -0.5px; position: relative; z-index: 1; }}
        .kpi-previous {{ font-size: 0.75rem; color: {text_secondary}; margin-top: 2px; position: relative; z-index: 1; }}
        .kpi-delta {{ font-size: 0.75rem; font-weight: 600; padding: 2px 12px; border-radius: 12px; display: inline-block; margin-left: 6px; animation: countUp 0.8s ease-out; }}
        .kpi-delta.positive {{ color: #22c55e; background: #22c55e22; border: 1px solid #22c55e44; }}
        .kpi-delta.negative {{ color: #ef4444; background: #ef444422; border: 1px solid #ef444444; }}
        .kpi-delta.neutral {{ color: {text_secondary}; background: {text_secondary}22; border: 1px solid {text_secondary}44; }}
        .kpi-icon {{ position: absolute; top: 12px; right: 16px; font-size: 2rem; opacity: 0.12; z-index: 0; transition: all 0.4s ease; }}
        .kpi-card:hover .kpi-icon {{ opacity: 0.25; transform: scale(1.1) rotate(-5deg); }}
        .glass-card {{ background: rgba(20, 27, 45, 0.7); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 16px; padding: 20px 24px; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 8px 32px rgba(0,0,0,0.3); transition: all 0.4s ease; }}
        .forecast-kpi-card {{ background: linear-gradient(145deg, #141b2d, #1a2236); border-radius: 16px; padding: 18px 20px; border: 1px solid #2a3450; box-shadow: 0 8px 32px rgba(0,0,0,0.3); transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); animation: fadeInUp 0.6s ease-out forwards; opacity: 0; position: relative; overflow: hidden; cursor: pointer; }}
        .forecast-kpi-card:hover {{ transform: translateY(-6px) scale(1.02); box-shadow: 0 16px 48px rgba(0,0,0,0.5); border-color: #0066CC66; animation: glowPulse 2s infinite; }}
        .forecast-kpi-card .label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1.5px; color: #8899bb; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .forecast-kpi-card .value {{ font-size: 1.8rem; font-weight: 700; color: #e8edf5; margin: 6px 0 2px 0; font-feature-settings: "tnum"; animation: countUp 0.8s ease-out forwards; }}
        .forecast-kpi-card .sub {{ font-size: 0.7rem; color: #667799; display: flex; align-items: center; gap: 6px; }}
        .forecast-kpi-card .icon {{ position: absolute; top: 12px; right: 16px; font-size: 2rem; opacity: 0.15; transition: all 0.4s ease; }}
        .purchase-card {{ background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 14px 18px; border: 1px solid #2a3450; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); animation: fadeInUp 0.6s ease-out forwards; position: relative; overflow: hidden; }}
        .purchase-card:hover {{ transform: translateY(-3px); border-color: {accent}44; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }}
        .purchase-card .purchase-label {{ font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.8px; color: {text_secondary}; font-weight: 500; }}
        .purchase-card .purchase-value {{ font-size: 1.4rem; font-weight: 700; color: {text}; margin-top: 2px; font-feature-settings: "tnum"; }}
        .foc-card {{ background: linear-gradient(145deg, #1a1030, #2a1a40); border-radius: 12px; padding: 16px 20px; border: 1px solid #8b5cf644; transition: all 0.3s ease; }}
        .foc-card:hover {{ border-color: #8b5cf6; transform: translateY(-2px); box-shadow: 0 8px 32px rgba(139, 92, 246, 0.15); }}
        .foc-card .foc-label {{ font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.8px; color: #8899bb; font-weight: 500; }}
        .foc-card .foc-value {{ font-size: 1.6rem; font-weight: 700; color: #8b5cf6; margin-top: 2px; }}
        .foc-card .foc-sub {{ font-size: 0.7rem; color: #667799; }}
        .section-divider {{ display: flex; align-items: center; margin: 32px 0 24px 0; animation: slideInLeft 0.8s ease-out; }}
        .section-divider .line {{ flex: 1; height: 2px; background: linear-gradient(90deg, {accent}, #7b5ea7, transparent); border-radius: 2px; position: relative; overflow: hidden; }}
        .section-divider .title {{ font-size: 1.2rem; font-weight: 600; color: #e8edf5; padding: 0 16px 0 0; background: #0a0e1a; white-space: nowrap; display: flex; align-items: center; gap: 10px; }}
        .table-container {{ background: {card_bg_alt}; border-radius: 16px; padding: 20px; border: 1px solid {border}; margin-top: 16px; animation: fadeInUp 0.6s ease-out; }}
        .table-container .table-header {{ font-size: 1rem; font-weight: 600; color: {text}; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
        .drug-table-container {{ background: {card_bg_alt}; border-radius: 16px; padding: 20px; border: 1px solid {border}; }}
        .drug-table-header {{ font-size: 1rem; font-weight: 600; color: {text}; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
        .drug-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {border}; font-size: 0.85rem; transition: all 0.2s ease; }}
        .drug-row:hover {{ background: {card_bg}; border-radius: 6px; padding-left: 8px; padding-right: 8px; }}
        .drug-name {{ color: {text}; flex: 1; }}
        .drug-sales {{ color: #22c55e; font-weight: 600; font-feature-settings: "tnum"; }}
        .drug-rank {{ color: {text_secondary}; margin-right: 12px; font-weight: 300; width: 30px; }}
        .insight-card {{ background: {card_bg}; border-radius: 12px; padding: 16px 20px; border: 1px solid {border}; margin-bottom: 16px; transition: all 0.3s ease; }}
        .insight-card:hover {{ border-color: {accent}44; }}
        .insight-green {{ border-left: 4px solid #22c55e; }}
        .insight-yellow {{ border-left: 4px solid #f59e0b; }}
        .insight-red {{ border-left: 4px solid #ef4444; }}
        .insight-blue {{ border-left: 4px solid {accent}; }}
        .insight-purple {{ border-left: 4px solid #8b5cf6; }}
        .progress-bar-container {{ background: {card_bg_alt}; border-radius: 20px; height: 10px; overflow: hidden; margin-top: 8px; }}
        .progress-bar-fill {{ height: 100%; border-radius: 20px; transition: width 0.5s ease; }}
        .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #22c55e; margin-right: 8px; animation: pulse 2s infinite; }}
        .product-tag {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.65rem; font-weight: 500; margin-right: 4px; }}
        .product-tag-group {{ background: {accent}33; color: {accent}; }}
        .product-tag-division {{ background: #22c55e33; color: #22c55e; }}
        .severity-critical {{ color: #ef4444; background: #ef444422; border: 1px solid #ef444444; }}
        .severity-high {{ color: #f59e0b; background: #f59e0b22; border: 1px solid #f59e0b44; }}
        .severity-moderate {{ color: #3b82f6; background: #3b82f622; border: 1px solid #3b82f644; }}
        .severity-low {{ color: #22c55e; background: #22c55e22; border: 1px solid #22c55e44; }}
        .footer {{ font-size: 0.75rem; color: {text_secondary}; text-align: center; padding: 1.5rem 0 0.5rem 0; border-top: 1px solid {border}; margin-top: 2rem; animation: fadeInUp 0.8s ease-out; }}
        @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(40px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes fadeInDown {{ from {{ opacity: 0; transform: translateY(-30px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes slideInLeft {{ from {{ opacity: 0; transform: translateX(-40px); }} to {{ opacity: 1; transform: translateX(0); }} }}
        @keyframes slideInRight {{ from {{ opacity: 0; transform: translateX(40px); }} to {{ opacity: 1; transform: translateX(0); }} }}
        @keyframes countUp {{ from {{ opacity: 0; transform: scale(0.5); }} to {{ opacity: 1; transform: scale(1); }} }}
        @keyframes shimmer {{ 0% {{ background-position: -200% center; }} 100% {{ background-position: 200% center; }} }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
        @keyframes glowPulse {{ 0%, 100% {{ box-shadow: 0 0 20px rgba(0,102,204,0.1); }} 50% {{ box-shadow: 0 0 40px rgba(0,102,204,0.3); }} }}
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        .stDeployButton {{ display: none; }}
        .stDataFrame {{ border-radius: 12px; overflow: hidden; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; background: {card_bg_alt}; border-radius: 12px; padding: 4px; }}
        .stTabs [data-baseweb="tab"] {{ border-radius: 8px; padding: 6px 16px; color: {text_secondary}; font-weight: 500; font-size: 0.85rem; border: none; transition: all 0.3s ease; }}
        .stTabs [aria-selected="true"] {{ background: {accent}; color: white; }}
        .stPlotlyChart {{ height: 100% !important; min-height: 500px !important; }}
        .stPlotlyChart > div {{ height: 100% !important; min-height: 500px !important; }}
        .stPlotlyChart .plotly {{ height: 100% !important; min-height: 500px !important; }}
    </style>
    """

# ============================================================================
# SIDEBAR RENDERER
# ============================================================================

def render_sidebar(options):
    with st.sidebar:
        # Company Logo / Header
        st.markdown("""
        <div style="text-align: center; padding: 0.5rem 0; animation: fadeInDown 0.6s ease-out;">
            <div style="font-size: 2.2rem; font-weight: 700; background: linear-gradient(135deg, #0066CC, #7b5ea7, #22c55e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; letter-spacing: -0.5px;">UNIQUE PHARMA</div>
            <div style="font-size: 0.65rem; color: #8899bb; letter-spacing: 3px; font-weight: 300; margin-top: 2px;">KINSHASA · GOMA · LUBUMBASHI</div>
            <div style="font-size: 0.55rem; color: #667799; letter-spacing: 1px; margin-top: 4px;">ENTERPRISE PHARMACEUTICAL INTELLIGENCE</div>
        </div>
        """, unsafe_allow_html=True)
        
        # User info
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.03); border-radius: 12px; padding: 12px 16px; margin: 8px 0 16px 0; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: linear-gradient(135deg, #0066CC, #7b5ea7); width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; color: white; font-weight: bold;">
                    {st.session_state.username[0].upper()}
                </div>
                <div>
                    <div style="font-size: 0.85rem; font-weight: 600; color: #e8edf5;">{st.session_state.user.get('name', st.session_state.username)}</div>
                    <div style="font-size: 0.6rem; color: #8899bb;">{st.session_state.user.get('role', 'viewer').upper()}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Navigation
        all_pages = [
            "📊 Executive Dashboard",
            "📈 Sales Analytics",
            "🔄 Returns Analysis",
            "📊 Net Sales Analysis",
            "📋 Year Comparison",
            "🔮 Demand Forecast",
            "🏆 Performance Ranking",
            "📦 Product Portfolio",
            "📦 Stock Analysis",
            "📦 Purchase Analysis",
            "🏢 Supplier Performance",
            "🎯 FOC Analysis"
        ]
        
        available_pages = PermissionManager.get_available_pages(st.session_state.user)
        
        if 'admin' in st.session_state.user.get('role', '') or 'all' in st.session_state.user.get('permissions', []):
            available_pages.append("👤 My Profile")
            available_pages.append("⚙️ Admin Panel")
        
        selected = st.radio("Navigation", available_pages, index=available_pages.index(st.session_state.page) if st.session_state.page in available_pages else 0)
        if selected != st.session_state.page:
            st.session_state.page = selected
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Time Filters
        st.markdown("### ⏱️ Time Filters")
        col1, col2 = st.columns(2)
        with col1:
            idx = options['years'].index(st.session_state.year) if st.session_state.year in options['years'] else 0
            new_year = st.selectbox("Year", options['years'], index=idx, key="year_select")
            if new_year != st.session_state.year:
                st.session_state.year = new_year
                st.cache_data.clear()
                st.rerun()
        with col2:
            months = ["All", "January", "February", "March", "April", "May", "June", 
                     "July", "August", "September", "October", "November", "December"]
            idx = months.index(st.session_state.month) if st.session_state.month in months else 0
            new_month = st.selectbox("Month", months, index=idx, key="month_select")
            if new_month != st.session_state.month:
                st.session_state.month = new_month
                st.cache_data.clear()
                st.rerun()
        
        periods = ["All", "Q1 (Jan-Mar)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dec)"]
        idx = periods.index(st.session_state.period) if st.session_state.period in periods else 0
        new_period = st.selectbox("Quarter", periods, index=idx, key="period_select")
        if new_period != st.session_state.period:
            st.session_state.period = new_period
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        create_date_filter_sidebar()
        st.markdown("---")
        
        # Location Filters
        st.markdown("### 📍 Location")
        col1, col2 = st.columns(2)
        with col1:
            idx = options['branches'].index(st.session_state.branch) if st.session_state.branch in options['branches'] else 0
            new_branch = st.selectbox("Branch", options['branches'], index=idx, key="branch_select")
            if new_branch != st.session_state.branch:
                st.session_state.branch = new_branch
                st.cache_data.clear()
                st.rerun()
        with col2:
            idx = options['locations'].index(st.session_state.location) if st.session_state.location in options['locations'] else 0
            new_location = st.selectbox("Location", options['locations'], index=idx, key="location_select")
            if new_location != st.session_state.location:
                st.session_state.location = new_location
                st.cache_data.clear()
                st.rerun()
        st.markdown("---")
        
        # Product Filters
        st.markdown("### 📦 Product")
        col1, col2 = st.columns(2)
        with col1:
            idx = options['product_groups'].index(st.session_state.product_group) if st.session_state.product_group in options['product_groups'] else 0
            new_pg = st.selectbox("Product Group", options['product_groups'], index=idx, key="pg_select")
            if new_pg != st.session_state.product_group:
                st.session_state.product_group = new_pg
                st.cache_data.clear()
                st.rerun()
        with col2:
            idx = options['divisions'].index(st.session_state.division) if st.session_state.division in options['divisions'] else 0
            new_div = st.selectbox("Division", options['divisions'], index=idx, key="div_select")
            if new_div != st.session_state.division:
                st.session_state.division = new_div
                st.cache_data.clear()
                st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            idx = options['item_codes'].index(st.session_state.item_code) if st.session_state.item_code in options['item_codes'] else 0
            new_code = st.selectbox("Item Code", options['item_codes'], index=idx, key="code_select")
            if new_code != st.session_state.item_code:
                st.session_state.item_code = new_code
                st.cache_data.clear()
                st.rerun()
        with col2:
            idx = options['item_names'].index(st.session_state.item_name) if st.session_state.item_name in options['item_names'] else 0
            new_name = st.selectbox("Item Name", options['item_names'], index=idx, key="name_select")
            if new_name != st.session_state.item_name:
                st.session_state.item_name = new_name
                st.cache_data.clear()
                st.rerun()
        st.markdown("---")
        
        # Supplier Filter
        st.markdown("### 🏢 Supplier")
        idx = options['suppliers'].index(st.session_state.supplier) if st.session_state.supplier in options['suppliers'] else 0
        new_supplier = st.selectbox("Supplier", options['suppliers'], index=idx, key="supplier_select")
        if new_supplier != st.session_state.supplier:
            st.session_state.supplier = new_supplier
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        
        # View Settings
        st.markdown("### 👁️ View Settings")
        view_modes = ["Monthly", "Quarterly", "Yearly"]
        idx = view_modes.index(st.session_state.view_mode) if st.session_state.view_mode in view_modes else 0
        new_mode = st.selectbox("View Mode", view_modes, index=idx, key="mode_select")
        if new_mode != st.session_state.view_mode:
            st.session_state.view_mode = new_mode
            st.cache_data.clear()
            st.rerun()
        
        chart_types = ["Bar", "Line", "Area"]
        idx = chart_types.index(st.session_state.chart_type) if st.session_state.chart_type in chart_types else 0
        st.session_state.chart_type = st.selectbox("Chart Type", chart_types, index=idx, key="chart_select")
        st.session_state.show_ma = st.checkbox("Show Moving Average", value=st.session_state.show_ma)
        st.markdown("---")
        
        # UI Settings
        st.markdown("### ⚙️ UI Settings")
        st.session_state.ui_compact_mode = st.checkbox("Compact Mode", value=st.session_state.ui_compact_mode)
        st.session_state.ui_color_blind_mode = st.checkbox("Color Blind Mode", value=st.session_state.ui_color_blind_mode)
        st.markdown("---")
        
        st.session_state.show_advanced_analytics = st.checkbox("🔬 Advanced Analytics", value=st.session_state.show_advanced_analytics)
        
        st.markdown("---")
        if st.button("🔄 Reset All Filters", use_container_width=True):
            for key in ['year', 'month', 'period', 'branch', 'location', 'item_code', 'item_name', 
                       'product_group', 'division', 'supplier', 'vendor', 'purchase_type', 
                       'date_period_type', 'filter_year', 'filter_quarter']:
                st.session_state[key] = "All"
            st.session_state.date_start = None
            st.session_state.date_end = None
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        
        st.markdown("---")
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.75rem; color: #8899bb; padding: 4px 8px;">
            <span class="status-dot"></span> 
            <span>Live</span>
            <span style="margin-left: auto;">v11.0</span>
        </div>
        """, unsafe_allow_html=True)

# ============================================================================
# KPI HELPER
# ============================================================================

def get_filter_context(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
    parts = []
    if year != "All" and month != "All":
        parts.append(f"{year} ({month})")
    elif year != "All" and period != "All":
        parts.append(f"{year} ({period})")
    elif year != "All":
        parts.append(f"{year}")
    elif month != "All" and period != "All":
        parts.append(f"{month} - {period}")
    elif month != "All":
        parts.append(f"{month}")
    elif period != "All":
        parts.append(f"{period}")
    else:
        parts.append("All Time")
    if branch != "All" and location != "All":
        parts.append(f"{branch} - {location}")
    elif branch != "All":
        parts.append(f"{branch}")
    elif location != "All":
        parts.append(f"{location}")
    if supplier != "All":
        parts.append(f"Supplier: {supplier}")
    if item_name != "All" and item_code != "All":
        parts.append(f"{item_name} ({item_code})")
    elif item_name != "All":
        parts.append(f"{item_name}")
    elif item_code != "All":
        parts.append(f"Item {item_code}")
    if product_group != "All" and division != "All":
        parts.append(f"{product_group} - {division}")
    elif product_group != "All":
        parts.append(f"{product_group}")
    elif division != "All":
        parts.append(f"{division}")
    return " | ".join(parts) if parts else "All Data"

def executive_kpi(label, current_value, prev_value=None, prefix="", suffix="", format=",.0f", icon="📊", 
                  is_value=True, filter_context=None, show_context=True, color=None):
    if current_value is None or pd.isna(current_value):
        current_value = 0
    if prev_value is None or pd.isna(prev_value):
        prev_value = 0
    if format == ",.2f":
        formatted_current = f"{current_value:{format}}" if current_value > 0 else "0"
        formatted_prev = f"{prev_value:{format}}" if prev_value > 0 else "0"
    else:
        formatted_current = f"{current_value:{format}}" if current_value > 0 else "0"
        formatted_prev = f"{prev_value:{format}}" if prev_value > 0 else "0"
    delta = None
    delta_class = "neutral"
    if prev_value > 0:
        delta = ((current_value - prev_value) / prev_value) * 100
        delta_class = "positive" if delta > 0 else "negative" if delta < 0 else "neutral"
    delta_html = f'<span class="kpi-delta {delta_class}">{delta:+.1f}%</span>' if delta is not None else ""
    if show_context and filter_context:
        display_label = f"{label} <span style='font-weight:300; font-size:0.6rem; color:#8899bb;'>({filter_context})</span>"
    else:
        display_label = label
    color_style = f"color: {color};" if color else ""
    html = f"""
    <div class="kpi-card">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{display_label}</div>
        <div class="kpi-value" style="{color_style}">{prefix}{formatted_current}{suffix}</div>
        <div class="kpi-previous">Previous: {prefix}{formatted_prev}{suffix} {delta_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ============================================================================
# CHART CREATOR
# ============================================================================

def create_chart(df, x_col, y_col, title, color, y_label, chart_type="Bar", show_ma=False, is_value=True, height=400,
                 show_confidence=False, confidence_data=None, show_trend=False, trend_color="#f59e0b"):
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return None
    label_format = '${:,.0f}' if is_value else '{:,.0f}'
    fig = go.Figure()
    show_text = len(df) <= 15
    
    if chart_type == "Bar":
        fig.add_trace(go.Bar(
            x=df[x_col], y=df[y_col],
            marker_color=color,
            text=df[y_col].apply(lambda x: label_format.format(x) if x > 0 and show_text else ''),
            textposition='outside' if show_text else 'none',
            textfont=dict(size=10 if len(df) > 15 else 12),
            name='Value', opacity=0.85,
            hovertemplate=f'<b>%{{x}}</b><br>{y_label}: %{{y:,.0f}}<extra></extra>'
        ))
    elif chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col],
            mode='lines+markers' + ('+text' if show_text else ''),
            line=dict(color=color, width=3),
            marker=dict(size=8, color=color),
            text=df[y_col].apply(lambda x: label_format.format(x) if x > 0 and show_text else ''),
            textposition='top center', textfont=dict(size=10),
            name='Value', fill='tozeroy',
            fillcolor=f'rgba{tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (0.1,)}',
            hovertemplate=f'<b>%{{x}}</b><br>{y_label}: %{{y:,.0f}}<extra></extra>'
        ))
    else:
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col],
            mode='lines' + ('+text' if show_text else ''),
            line=dict(color=color, width=2),
            text=df[y_col].apply(lambda x: label_format.format(x) if x > 0 and show_text else ''),
            textposition='top center', textfont=dict(size=10),
            fill='tozeroy',
            fillcolor=f'rgba{tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (0.3,)}',
            name='Value',
            hovertemplate=f'<b>%{{x}}</b><br>{y_label}: %{{y:,.0f}}<extra></extra>'
        ))
    
    if show_ma and len(df) > 3:
        ma = df[y_col].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df[x_col], y=ma,
            mode='lines',
            line=dict(color='#f59e0b', width=2, dash='dash'),
            name='3-Period MA',
            hovertemplate=f'<b>%{{x}}</b><br>MA(3): %{{y:,.0f}}<extra></extra>'
        ))
    
    if show_trend and len(df) > 2:
        x_vals = np.arange(len(df))
        y_vals = df[y_col].values
        slope, intercept = np.polyfit(x_vals, y_vals, 1)
        trend_vals = slope * x_vals + intercept
        fig.add_trace(go.Scatter(
            x=df[x_col], y=trend_vals,
            mode='lines',
            line=dict(color=trend_color, width=2, dash='dot'),
            name='Trend Line',
            hovertemplate=f'<b>%{{x}}</b><br>Trend: %{{y:,.0f}}<extra></extra>'
        ))
    
    x_angle = -45 if len(df) > 10 else 0
    fig.update_layout(
        title=title, height=height,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=50, b=60 if len(df) > 10 else 50),
        xaxis={'title': 'Period', 'tickangle': x_angle, 'tickfont': {'size': 10}},
        yaxis={'title': y_label, 'tickformat': ',.0f'},
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=10)),
        bargap=0.15,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ============================================================================
# KPI CALCULATOR
# ============================================================================

def calculate_all_kpis(yearly_data, current_year, prev_year, is_value, view_type_label, year_filter="All"):
    def get_val_for_year(df, col, year_val):
        if df is None or df.empty or col not in df.columns:
            return 0
        year_data = df[df['Year'] == year_val]
        if year_data.empty:
            return 0
        return year_data[col].iloc[0] if not year_data[col].empty else 0
    def get_total_all_years(df, col):
        if df is None or df.empty or col not in df.columns:
            return 0
        return df[col].sum() if not df[col].empty else 0
    
    if view_type_label == "💰 Value":
        sales_col = 'Total_Sales'
        returns_col = 'Total_Returns'
        net_col = 'Total_Net'
        qty_col = 'Total_Qty'
        trans_col = 'Total_Transactions'
        return_qty_col = 'Total_Return_Qty'
        return_trans_col = 'Total_Return_Transactions'
        net_qty_col = 'Total_Net_Qty'
        net_trans_col = 'Total_Net_Transactions'
        is_value = True
    elif view_type_label == "📦 Quantity":
        sales_col = 'Total_Qty'
        returns_col = 'Total_Return_Qty'
        net_col = 'Total_Net_Qty'
        qty_col = 'Total_Qty'
        trans_col = 'Total_Transactions'
        return_qty_col = 'Total_Return_Qty'
        return_trans_col = 'Total_Return_Transactions'
        net_qty_col = 'Total_Net_Qty'
        net_trans_col = 'Total_Net_Transactions'
        is_value = False
    else:
        sales_col = 'Total_Transactions'
        returns_col = 'Total_Return_Transactions'
        net_col = 'Total_Net_Transactions'
        qty_col = 'Total_Qty'
        trans_col = 'Total_Transactions'
        return_qty_col = 'Total_Return_Qty'
        return_trans_col = 'Total_Return_Transactions'
        net_qty_col = 'Total_Net_Qty'
        net_trans_col = 'Total_Net_Transactions'
        is_value = False
    
    if year_filter == "All":
        sales_cy = {'amount': get_total_all_years(yearly_data, sales_col), 'qty': get_total_all_years(yearly_data, qty_col), 'trans': get_total_all_years(yearly_data, trans_col)}
        if prev_year:
            sales_py = {'amount': get_val_for_year(yearly_data, sales_col, prev_year), 'qty': get_val_for_year(yearly_data, qty_col, prev_year), 'trans': get_val_for_year(yearly_data, trans_col, prev_year)}
        else:
            sales_py = {'amount': 0, 'qty': 0, 'trans': 0}
    else:
        sales_cy = {'amount': get_val_for_year(yearly_data, sales_col, current_year), 'qty': get_val_for_year(yearly_data, qty_col, current_year), 'trans': get_val_for_year(yearly_data, trans_col, current_year)}
        if prev_year:
            sales_py = {'amount': get_val_for_year(yearly_data, sales_col, prev_year), 'qty': get_val_for_year(yearly_data, qty_col, prev_year), 'trans': get_val_for_year(yearly_data, trans_col, prev_year)}
        else:
            sales_py = {'amount': 0, 'qty': 0, 'trans': 0}
    
    if year_filter == "All":
        returns_cy = {'amount': get_total_all_years(yearly_data, returns_col), 'qty': get_total_all_years(yearly_data, return_qty_col), 'trans': get_total_all_years(yearly_data, return_trans_col)}
        if prev_year:
            returns_py = {'amount': get_val_for_year(yearly_data, returns_col, prev_year), 'qty': get_val_for_year(yearly_data, return_qty_col, prev_year), 'trans': get_val_for_year(yearly_data, return_trans_col, prev_year)}
        else:
            returns_py = {'amount': 0, 'qty': 0, 'trans': 0}
    else:
        returns_cy = {'amount': get_val_for_year(yearly_data, returns_col, current_year), 'qty': get_val_for_year(yearly_data, return_qty_col, current_year), 'trans': get_val_for_year(yearly_data, return_trans_col, current_year)}
        if prev_year:
            returns_py = {'amount': get_val_for_year(yearly_data, returns_col, prev_year), 'qty': get_val_for_year(yearly_data, return_qty_col, prev_year), 'trans': get_val_for_year(yearly_data, return_trans_col, prev_year)}
        else:
            returns_py = {'amount': 0, 'qty': 0, 'trans': 0}
    
    if year_filter == "All":
        net_cy = {'amount': get_total_all_years(yearly_data, net_col), 'qty': get_total_all_years(yearly_data, net_qty_col), 'trans': get_total_all_years(yearly_data, net_trans_col)}
        if prev_year:
            net_py = {'amount': get_val_for_year(yearly_data, net_col, prev_year), 'qty': get_val_for_year(yearly_data, net_qty_col, prev_year), 'trans': get_val_for_year(yearly_data, net_trans_col, prev_year)}
        else:
            net_py = {'amount': 0, 'qty': 0, 'trans': 0}
    else:
        net_cy = {'amount': get_val_for_year(yearly_data, net_col, current_year), 'qty': get_val_for_year(yearly_data, net_qty_col, current_year), 'trans': get_val_for_year(yearly_data, net_trans_col, current_year)}
        if prev_year:
            net_py = {'amount': get_val_for_year(yearly_data, net_col, prev_year), 'qty': get_val_for_year(yearly_data, net_qty_col, prev_year), 'trans': get_val_for_year(yearly_data, net_trans_col, prev_year)}
        else:
            net_py = {'amount': 0, 'qty': 0, 'trans': 0}
    
    return_rate_cy = (returns_cy['amount'] / sales_cy['amount'] * 100) if sales_cy['amount'] > 0 else 0
    return_rate_py = (returns_py['amount'] / sales_py['amount'] * 100) if sales_py['amount'] > 0 else 0
    avg_trans_cy = (sales_cy['amount'] / sales_cy['trans']) if sales_cy['trans'] > 0 else 0
    avg_trans_py = (sales_py['amount'] / sales_py['trans']) if sales_py['trans'] > 0 else 0
    sales_val = sales_cy['amount']; sales_prev = sales_py['amount']; returns_val = returns_cy['amount']; returns_prev = returns_py['amount']; net_val = net_cy['amount']; net_prev = net_py['amount']
    
    return {
        'sales': {'current': sales_val, 'previous': sales_prev, 'amount': sales_cy['amount'], 'qty': sales_cy['qty'], 
                  'trans': sales_cy['trans'], 'prev_amount': sales_py['amount'], 'prev_qty': sales_py['qty'], 
                  'prev_trans': sales_py['trans']},
        'returns': {'current': returns_val, 'previous': returns_prev, 'amount': returns_cy['amount'], 
                    'qty': returns_cy['qty'], 'trans': returns_cy['trans'], 'prev_amount': returns_py['amount'], 
                    'prev_qty': returns_py['qty'], 'prev_trans': returns_py['trans']},
        'net': {'current': net_val, 'previous': net_prev, 'amount': net_cy['amount'], 'qty': net_cy['qty'], 
                'trans': net_cy['trans'], 'prev_amount': net_py['amount'], 'prev_qty': net_py['qty'], 
                'prev_trans': net_py['trans']},
        'rates': {'return_rate': {'current': return_rate_cy, 'previous': return_rate_py}, 'avg_transaction': {'current': avg_trans_cy, 'previous': avg_trans_py}}
    }

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.markdown(load_css(st.session_state.theme, st.session_state.accent_color), unsafe_allow_html=True)
    
    options = load_filter_options()
    
    year = st.session_state.year
    month = st.session_state.month
    period = st.session_state.period
    branch = st.session_state.branch
    location = st.session_state.location
    item_code = st.session_state.item_code
    item_name = st.session_state.item_name
    product_group = st.session_state.product_group
    division = st.session_state.division
    supplier = st.session_state.supplier
    vendor = st.session_state.vendor
    purchase_type = st.session_state.purchase_type
    
    date_period_type = st.session_state.date_period_type
    date_start = st.session_state.date_start
    date_end = st.session_state.date_end
    
    compact_class = "compact-mode" if st.session_state.ui_compact_mode else ""
    color_blind_class = "color-blind-mode" if st.session_state.ui_color_blind_mode else ""
    st.markdown(f'<div class="{compact_class} {color_blind_class}">', unsafe_allow_html=True)
    
    # ========================================================================
    # PAGE ROUTING
    # ========================================================================
    
    if st.session_state.page == "👤 My Profile":
        render_user_profile()
        return
    
    elif st.session_state.page == "⚙️ Admin Panel":
        render_admin_panel()
        return
    
    # Load data for dashboard pages
    with st.spinner("Loading data..."):
        data = load_all_data(
            year, month, period, branch, location, 
            item_code, item_name, product_group, division, supplier
        )
        monthly_data = data.get('monthly_data', pd.DataFrame())
        yearly_data = data.get('yearly_data', pd.DataFrame())
        item_monthly_data = data.get('item_monthly_data', pd.DataFrame())
        branch_performance = data.get('branch_performance', pd.DataFrame())
        category_performance = data.get('category_performance', pd.DataFrame())
        monthly_growth = data.get('monthly_growth', pd.DataFrame())
        quarterly_performance = data.get('quarterly_performance', pd.DataFrame())
        item_performance = data.get('item_performance', pd.DataFrame())
    
    if date_period_type != 'All' or date_start or date_end:
        monthly_data = apply_date_filter(monthly_data, date_start, date_end, date_period_type)
        monthly_growth = apply_date_filter(monthly_growth, date_start, date_end, date_period_type)
        quarterly_performance = apply_date_filter(quarterly_performance, date_start, date_end, date_period_type)
        item_monthly_data = apply_date_filter(item_monthly_data, date_start, date_end, date_period_type)
    
    render_sidebar(options)
    
    filter_context = get_filter_context(
        year, month, period, branch, location, 
        item_code, item_name, product_group, division, supplier
    )
    
    st.markdown(f'<div class="main-header">🏢 {st.session_state.page}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header"><span style="color:#8899bb;">Filter: {filter_context}</span></div>', unsafe_allow_html=True)
    
    view_type_label = st.session_state.view_type
    is_value = view_type_label == "💰 Value"
    
    available_years = yearly_data['Year'].unique().tolist() if not yearly_data.empty else []
    available_years.sort(reverse=True)
    
    if year != "All":
        current_year = int(year)
    else:
        current_year = max(available_years) if available_years else datetime.now().year
    
    if current_year in available_years:
        prev_years = [y for y in available_years if y < current_year]
        prev_year = max(prev_years) if prev_years else None
    else:
        prev_year = None
    
    kpis = calculate_all_kpis(yearly_data, current_year, prev_year, is_value, view_type_label, year)

        
    # ========================================================================
    # EXECUTIVE DASHBOARD (Sample)
    # ========================================================================
    if st.session_state.page == "📊 Executive Dashboard":
        st.markdown("### 🎯 Executive Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "💰" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Total Sales" if view_type_label == "💰 Value" else "Total Quantity" if view_type_label == "📦 Quantity" else "Transactions"
            executive_kpi(label, kpis['sales']['current'], kpis['sales']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        with col2:
            executive_kpi("Transactions", kpis['sales']['trans'], kpis['sales']['prev_trans'], icon="📋", is_value=True, filter_context=filter_context, show_context=True)
        with col3:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "🔄" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Returns" if view_type_label == "💰 Value" else "Return Qty" if view_type_label == "📦 Quantity" else "Return Trans"
            executive_kpi(label, kpis['returns']['current'], kpis['returns']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        with col4:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "📊" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Net Sales" if view_type_label == "💰 Value" else "Net Qty" if view_type_label == "📦 Quantity" else "Net Trans"
            executive_kpi(label, kpis['net']['current'], kpis['net']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        
        st.success(f"👋 Welcome back, {st.session_state.user.get('name', st.session_state.username)}! Your dashboard is ready.")
        
       
        # KPI Row 2
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            executive_kpi("Return Rate", kpis['rates']['return_rate']['current'], kpis['rates']['return_rate']['previous'], suffix="%", format=".2f", icon="📊", is_value=True, filter_context=filter_context, show_context=True)
        with col2:
            executive_kpi("Return Transactions", kpis['returns']['trans'], kpis['returns']['prev_trans'], icon="📋", is_value=True, filter_context=filter_context, show_context=True)
        with col3:
            executive_kpi("Net Transactions", kpis['net']['trans'], kpis['net']['prev_trans'], icon="📋", is_value=True, filter_context=filter_context, show_context=True)
        with col4:
            executive_kpi("Avg Transaction", kpis['rates']['avg_transaction']['current'], kpis['rates']['avg_transaction']['previous'], prefix="$" if view_type_label == "💰 Value" else "", format=".2f" if view_type_label == "💰 Value" else ",.0f", icon="💳", is_value=True, filter_context=filter_context, show_context=True)
        
        st.markdown("---")
        
        # Drug Performance Ranking
        st.markdown("### 🏆 Drug Performance Ranking")
        col_mode1, col_mode2 = st.columns([1, 2])
        with col_mode1:
            top_bottom = st.radio("Mode", options=["Top", "Bottom"], index=0 if st.session_state.top_bottom_mode == "Top" else 1, horizontal=True, key="top_bottom_radio_exec")
            st.session_state.top_bottom_mode = top_bottom
        with col_mode2:
            n_options = [5, 10, 16, 20, 29, 50, 100, 200]
            n_selected = st.select_slider("Number of Drugs", options=n_options, value=st.session_state.n_selection, key="n_slider_exec")
            st.session_state.n_selection = n_selected
        
        st.markdown("#### View Type")
        view_col1, view_col2, view_col3 = st.columns(3)
        with view_col1:
            if st.button("💰 Value", use_container_width=True, type="primary" if st.session_state.view_type == "💰 Value" else "secondary"):
                st.session_state.view_type = "💰 Value"; st.rerun()
        with view_col2:
            if st.button("📦 Qty", use_container_width=True, type="primary" if st.session_state.view_type == "📦 Quantity" else "secondary"):
                st.session_state.view_type = "📦 Quantity"; st.rerun()
        with view_col3:
            if st.button("📋 Trans", use_container_width=True, type="primary" if st.session_state.view_type == "📋 Transactions" else "secondary"):
                st.session_state.view_type = "📋 Transactions"; st.rerun()
        
        st.markdown("---")
        
        if not item_performance.empty:
            if view_type_label == "💰 Value":
                value_col = 'Total_Sales'; col_label = "Sales Amount"; prefix = "$"
            elif view_type_label == "📦 Quantity":
                value_col = 'Total_Qty'; col_label = "Qty Sold"; prefix = ""
            else:
                value_col = 'Total_Transactions'; col_label = "Transactions"; prefix = ""
            
            drug_performance = item_performance[['Item_Name', value_col, 'Product_Group', 'Division', 'Brand_Name']].copy()
            drug_performance = drug_performance.sort_values(value_col, ascending=False)
            total_value = drug_performance[value_col].sum()
            drug_performance['Percentage'] = (drug_performance[value_col] / total_value * 100) if total_value > 0 else 0
            
            if st.session_state.top_bottom_mode == "Top":
                selected_drugs = drug_performance.head(st.session_state.n_selection).copy(); rank_label = "Top"
            else:
                selected_drugs = drug_performance.tail(st.session_state.n_selection).copy(); selected_drugs = selected_drugs.sort_values(value_col, ascending=False); rank_label = "Bottom"
            
            selected_drugs['Rank'] = range(1, len(selected_drugs) + 1)
            selected_total = selected_drugs[value_col].sum()
            selected_pct = (selected_total / total_value * 100) if total_value > 0 else 0
            insight_color = "#22c55e" if selected_pct > 50 else "#f59e0b" if selected_pct > 30 else "#ef4444"
            insight_text = "Strong concentration" if selected_pct > 50 else "Moderate concentration" if selected_pct > 30 else "Low concentration"
            remaining_pct = 100 - selected_pct
            
            st.markdown(f"""
            <div class="insight-card insight-{insight_text.lower().replace(' ', '-')}">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <div>
                        <span style="font-size: 0.8rem; color: #8899bb;">{rank_label} {st.session_state.n_selection} Drugs Performance</span>
                        <div style="font-size: 1.6rem; font-weight: 700; color: #e8edf5; margin-top: 2px;">{prefix}{selected_total:,.0f}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-size: 0.8rem; color: #8899bb;">of Total {col_label}</span>
                        <div style="font-size: 1.6rem; font-weight: 700; color: {insight_color};">{selected_pct:.1f}%</div>
                        <span style="font-size: 0.7rem; color: #8899bb;">Total: {prefix}{total_value:,.0f}</span>
                    </div>
                </div>
                <div style="margin-top: 10px;">
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" style="width: {min(selected_pct, 100)}%; background: {insight_color};"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 4px;">
                        <span style="font-size: 0.7rem; color: {insight_color};">{insight_text} • {selected_pct:.1f}%</span>
                        <span style="font-size: 0.7rem; color: #8899bb;">Remaining {remaining_pct:.1f}% from other drugs</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="drug-table-container">
                <div class="drug-table-header">
                    <span>{rank_label} {st.session_state.n_selection} Drugs By Total {col_label}</span>
                    <span>Filter: {filter_context}</span>
                </div>
            """, unsafe_allow_html=True)
            
            display_drugs = selected_drugs[['Rank', 'Item_Name', value_col, 'Percentage', 'Product_Group', 'Division']].copy()
            display_drugs['Value'] = display_drugs[value_col].apply(lambda x: f'{prefix}{x:,.0f}')
            display_drugs['Percentage'] = display_drugs['Percentage'].apply(lambda x: f'{x:.1f}%')
            display_drugs = display_drugs.rename(columns={'Item_Name': 'Drug Name', 'Percentage': '% of Total', 'Product_Group': 'Product Group', 'Division': 'Division'})
            display_drugs = display_drugs[['Rank', 'Drug Name', 'Product Group', 'Division', 'Value', '% of Total']]
            st.dataframe(display_drugs, use_container_width=True, height=400, hide_index=True)
            
            csv_data = selected_drugs[['Rank', 'Item_Name', value_col, 'Percentage', 'Product_Group', 'Division']].copy()
            csv_data.columns = ['Rank', 'Drug', col_label, 'Percentage', 'Product Group', 'Division']
            csv = csv_data.to_csv(index=False)
            st.download_button("📥 Download Drugs Data", csv, f"drugs_performance_{rank_label.lower()}_{st.session_state.n_selection}.csv", "text/csv")
        
        st.markdown("---")
        
        # Top Drug Transactions
        st.markdown("### 💊 Top Drug Transactions")
        if not item_performance.empty:
            col_n1, col_n2 = st.columns([2, 1])
            with col_n1:
                n_value = st.slider("Number of Drugs to Display", min_value=1, max_value=1000, value=st.session_state.top_transactions_n, step=1, key="top_transactions_slider_exec")
                st.session_state.top_transactions_n = n_value
            with col_n2:
                st.markdown(f"""
                <div style="background: #1a2236; border-radius: 12px; padding: 16px; border: 1px solid #2a3450; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                    <span style="font-size: 0.7rem; color: #8899bb;">Showing Top</span>
                    <span style="font-size: 1.8rem; font-weight: 700; color: #e8edf5;">{n_value}</span>
                    <span style="font-size: 0.7rem; color: #8899bb;">Drugs</span>
                </div>
                """, unsafe_allow_html=True)
            
            drug_transactions = item_performance[['Item_Name', 'Total_Qty', 'Total_Sales', 'Total_Returns', 'Total_Net']].copy()
            drug_transactions = drug_transactions.sort_values('Total_Sales', ascending=False)
            top_n_drugs = drug_transactions.head(n_value).copy()
            top_n_drugs['Rank'] = range(1, len(top_n_drugs) + 1)
            top_n_drugs = top_n_drugs[['Rank', 'Item_Name', 'Total_Qty', 'Total_Sales', 'Total_Returns', 'Total_Net']]
            top_n_drugs.columns = ['Rank', 'Drug Name', 'Transaction Qty', 'Sales', 'Sales Return', 'Net Sales']
            
            st.markdown(f"""
            <div class="table-container">
                <div class="table-header">
                    <span>Top {n_value} Drug Transactions</span>
                    <span class="badge">Filter: {filter_context}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            display_df = top_n_drugs.copy()
            display_df['Sales'] = display_df['Sales'].apply(lambda x: f'${x:,.2f}')
            display_df['Sales Return'] = display_df['Sales Return'].apply(lambda x: f'${x:,.2f}')
            display_df['Net Sales'] = display_df['Net Sales'].apply(lambda x: f'${x:,.2f}')
            display_df['Transaction Qty'] = display_df['Transaction Qty'].apply(lambda x: f'{x:,.0f}')
            st.dataframe(display_df, use_container_width=True, height=300, hide_index=True)
            
            csv_data = top_n_drugs.copy()
            csv = csv_data.to_csv(index=False)
            st.download_button("📥 Download Top Drug Transactions", csv, f"top_drug_transactions_{n_value}.csv", "text/csv")
            
            total_sales = top_n_drugs['Sales'].sum(); total_returns = top_n_drugs['Sales Return'].sum(); total_net = top_n_drugs['Net Sales'].sum(); total_qty = top_n_drugs['Transaction Qty'].sum()
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px;">
                <div style="background: #1a2236; border-radius: 12px; padding: 12px 16px; border: 1px solid #2a3450; text-align: center;">
                    <span style="font-size: 0.7rem; color: #8899bb;">Total Sales</span>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #22c55e;">${total_sales:,.2f}</div>
                </div>
                <div style="background: #1a2236; border-radius: 12px; padding: 12px 16px; border: 1px solid #2a3450; text-align: center;">
                    <span style="font-size: 0.7rem; color: #8899bb;">Total Returns</span>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #ef4444;">${total_returns:,.2f}</div>
                </div>
                <div style="background: #1a2236; border-radius: 12px; padding: 12px 16px; border: 1px solid #2a3450; text-align: center;">
                    <span style="font-size: 0.7rem; color: #8899bb;">Net Sales</span>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #3b82f6;">${total_net:,.2f}</div>
                </div>
                <div style="background: #1a2236; border-radius: 12px; padding: 12px 16px; border: 1px solid #2a3450; text-align: center;">
                    <span style="font-size: 0.7rem; color: #8899bb;">Total Quantity</span>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #f59e0b;">{total_qty:,.0f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Top & Bottom Branches
        st.markdown("### 🏢 Top & Bottom Branches")
        if not branch_performance.empty:
            col_top_branches, col_bottom_branches = st.columns(2)
            with col_top_branches:
                st.markdown("#### 🏆 Top Branches")
                top_branches = branch_performance.head(10)
                for idx, row in top_branches.iterrows():
                    branch_name = row['Branch']; sales = row['Total_Sales']; rank = idx + 1
                    st.markdown(f"""
                    <div class="branch-row">
                        <div style="display: flex; align-items: center; flex: 1;">
                            <span class="branch-rank">#{rank}</span>
                            <span class="branch-name">{branch_name}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="branch-value">${sales:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            with col_bottom_branches:
                st.markdown("#### 📉 Bottom Branches")
                bottom_branches = branch_performance.tail(10).sort_values('Total_Sales', ascending=True)
                for idx, row in bottom_branches.iterrows():
                    branch_name = row['Branch']; sales = row['Total_Sales']; rank = len(branch_performance) - idx
                    st.markdown(f"""
                    <div class="branch-row">
                        <div style="display: flex; align-items: center; flex: 1;">
                            <span class="branch-rank">#{rank}</span>
                            <span class="branch-name">{branch_name}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="branch-value" style="color: #ef4444;">${sales:,.0f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Executive Performance Charts
        st.markdown("### 📊 Executive Performance Charts")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("#### 📈 Sales Trend")
            if not monthly_data.empty:
                if view_type_label == "💰 Value":
                    y_col = 'Total_Sales'; y_label = 'Revenue ($)'
                elif view_type_label == "📦 Quantity":
                    y_col = 'Total_Qty'; y_label = 'Quantity'
                else:
                    y_col = 'Total_Transactions'; y_label = 'Transactions'
                fig = create_chart(monthly_data, 'Month_Label', y_col, 'Monthly Sales Trend', st.session_state.accent_color, y_label, st.session_state.chart_type, st.session_state.show_ma, is_value, height=350, show_trend=st.session_state.show_trend_line)
                if fig: st.plotly_chart(fig, use_container_width=True)
        with col_chart2:
            st.markdown("#### 📊 Quarterly Performance")
            if not quarterly_performance.empty:
                if view_type_label == "💰 Value":
                    y_col = 'Total_Sales'; y_label = 'Revenue ($)'
                elif view_type_label == "📦 Quantity":
                    y_col = 'Total_Qty'; y_label = 'Quantity'
                else:
                    y_col = 'Total_Transactions'; y_label = 'Transactions'
                quarterly_performance['Quarter_Label'] = quarterly_performance.apply(lambda row: f"Q{row['Quarter']} {row['Year']}", axis=1)
                fig = px.bar(quarterly_performance, x='Quarter_Label', y=y_col, title='Quarterly Performance', color=y_col, color_continuous_scale='Blues', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=40), xaxis_title='Quarter', yaxis_title=y_label, showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        
        col_chart3, col_chart4 = st.columns(2)
        with col_chart3:
            st.markdown("#### 🏢 Branch Performance")
            if not branch_performance.empty:
                fig = px.bar(branch_performance.head(15), x='Total_Sales', y='Branch', orientation='h', title='Top 15 Branches by Sales', color='Total_Sales', color_continuous_scale='Greens', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20), xaxis_title='Sales ($)', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        with col_chart4:
            st.markdown("#### 📦 Product Category Performance")
            if not category_performance.empty:
                fig = px.pie(category_performance.head(10), values='Total_Sales', names='Product_Group', title='Sales by Product Category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20))
                fig.update_traces(textposition='inside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        
        col_chart5, col_chart6 = st.columns(2)
        with col_chart5:
            st.markdown("#### 📈 Monthly Growth Rate")
            if not monthly_growth.empty and 'Sales_Growth' in monthly_growth.columns:
                growth_data = monthly_growth[['Month_Label', 'Sales_Growth']].dropna()
                if not growth_data.empty:
                    colors_growth = ['#22c55e' if x >= 0 else '#ef4444' for x in growth_data['Sales_Growth']]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=growth_data['Month_Label'], y=growth_data['Sales_Growth'], marker_color=colors_growth, text=growth_data['Sales_Growth'].apply(lambda x: f'{x:+.1f}%'), textposition='outside', textfont=dict(size=9)))
                    fig.add_hline(y=0, line_dash="dash", line_color="#8899bb", line_width=1)
                    fig.update_layout(title='Monthly Sales Growth Rate', height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=40), xaxis_title='Month', yaxis_title='Growth (%)', showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        with col_chart6:
            st.markdown("#### 📊 Sales vs Returns")
            if not monthly_data.empty:
                if view_type_label == "💰 Value":
                    sales_col = 'Total_Sales'; returns_col = 'Total_Returns'; prefix = '$'
                elif view_type_label == "📦 Quantity":
                    sales_col = 'Total_Qty'; returns_col = 'Total_Return_Qty'; prefix = ''
                else:
                    sales_col = 'Total_Transactions'; returns_col = 'Total_Return_Transactions'; prefix = ''
                fig = go.Figure()
                fig.add_trace(go.Bar(x=monthly_data['Month_Label'], y=monthly_data[sales_col], name='Sales', marker_color=st.session_state.accent_color, opacity=0.7, text=monthly_data[sales_col].apply(lambda x: f'{prefix}{x:,.0f}'), textposition='outside', textfont=dict(size=8)))
                fig.add_trace(go.Bar(x=monthly_data['Month_Label'], y=monthly_data[returns_col], name='Returns', marker_color='#ef4444', opacity=0.7, text=monthly_data[returns_col].apply(lambda x: f'{prefix}{x:,.0f}'), textposition='outside', textfont=dict(size=8)))
                fig.update_layout(title='Sales vs Returns Comparison', height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=40), xaxis_title='Month', yaxis_title='Value', barmode='group', legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Top & Bottom Products
        col_top_products, col_bottom_products = st.columns(2)
        with col_top_products:
            st.markdown("### 🏆 Top Products")
            if not item_performance.empty:
                if view_type_label == "💰 Value": value_col = 'Total_Sales'
                elif view_type_label == "📦 Quantity": value_col = 'Total_Qty'
                else: value_col = 'Total_Transactions'
                top_items = item_performance.nlargest(st.session_state.top_n, value_col)[['Item_Name', value_col]]
                top_items.columns = ['Item', 'Value']
                fig = px.bar(top_items, x='Value', y='Item', orientation='h', title=f'Top {st.session_state.top_n} Products', color='Value', color_continuous_scale='Greens', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20), xaxis_title='Sales' if view_type_label == "💰 Value" else 'Quantity' if view_type_label == "📦 Quantity" else 'Transactions', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        with col_bottom_products:
            st.markdown("### 📉 Bottom Products")
            if not item_performance.empty:
                if view_type_label == "💰 Value": value_col = 'Total_Sales'
                elif view_type_label == "📦 Quantity": value_col = 'Total_Qty'
                else: value_col = 'Total_Transactions'
                bottom_items = item_performance.nsmallest(st.session_state.top_n, value_col)[['Item_Name', value_col]]
                bottom_items.columns = ['Item', 'Value']
                fig = px.bar(bottom_items, x='Value', y='Item', orientation='h', title=f'Bottom {st.session_state.top_n} Products', color='Value', color_continuous_scale='Reds', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20), xaxis_title='Sales' if view_type_label == "💰 Value" else 'Quantity' if view_type_label == "📦 Quantity" else 'Transactions', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # PAGE 2: SALES ANALYTICS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📈 Sales Analytics":
        st.markdown("### 📈 Sales Analytics")
        st.caption("Comprehensive sales performance with decision insights")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "💰" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Total Sales" if view_type_label == "💰 Value" else "Total Quantity" if view_type_label == "📦 Quantity" else "Transactions"
            executive_kpi(label, kpis['sales']['current'], kpis['sales']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        with col2:
            executive_kpi("Total Quantity", kpis['sales']['qty'], kpis['sales']['prev_qty'], icon="📦", is_value=False, filter_context=filter_context, show_context=True)
        with col3:
            executive_kpi("Transactions", kpis['sales']['trans'], kpis['sales']['prev_trans'], icon="📋", is_value=True, filter_context=filter_context, show_context=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 Sales Trend")
            if view_type_label == "💰 Value":
                y_col = 'Total_Sales'; y_label = 'Revenue ($)'
            elif view_type_label == "📦 Quantity":
                y_col = 'Total_Qty'; y_label = 'Quantity'
            else:
                y_col = 'Total_Transactions'; y_label = 'Transactions'
            fig = create_chart(monthly_data, 'Month_Label', y_col, 'Sales Trend', st.session_state.accent_color, y_label, st.session_state.chart_type, st.session_state.show_ma, is_value, show_trend=st.session_state.show_trend_line)
            if fig: st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### 📊 Sales by Branch")
            if not branch_performance.empty:
                fig = px.pie(branch_performance.head(10), values='Total_Sales', names='Branch', title='Sales Distribution by Branch', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.markdown(f"### 📋 {st.session_state.view_mode} Sales by Item")
        use_global = (branch == "All" and location == "All")
        if use_global:
            pivot_data = item_monthly_data[['Item_Code', 'Item_Name', 'Month_Label', 'Sales_Amount', 'Qty_Sold', 'Sales_Transactions']].copy() if not item_monthly_data.empty else pd.DataFrame()
        else:
            conn = get_connection()
            conditions = []; params = []
            if year != "All": conditions.append("Year = ?"); params.append(int(year))
            if month != "All":
                month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,"July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
                month_num = month_map.get(month)
                if month_num: conditions.append("Month_Num = ?"); params.append(month_num)
            if period != "All":
                quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
                q = quarter_map.get(period)
                if q: conditions.append("Quarter = ?"); params.append(q)
            if branch != "All": conditions.append("Branch = ?"); params.append(branch)
            if location != "All": conditions.append("Location = ?"); params.append(location)
            if product_group != "All": conditions.append("Product_Group = ?"); params.append(product_group)
            if division != "All": conditions.append("Division = ?"); params.append(division)
            if item_code != "All": conditions.append("UPPER(Item_Code) = UPPER(?)"); params.append(item_code)
            if item_name != "All": conditions.append("UPPER(Item_Name) = UPPER(?)"); params.append(item_name)
            if supplier != "All": conditions.append("UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))"); params.append(supplier)
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT Item_Code, Item_Name, Month_Label,
                       SUM(Sales_Amount) as Sales_Amount,
                       SUM(Qty_Sold) as Qty_Sold,
                       SUM(Sales_Transactions) as Sales_Transactions
                FROM branch_item_monthly_analysis
                WHERE {where_clause}
                GROUP BY Item_Code, Item_Name, Month_Label
                ORDER BY Item_Name, Month_Label
            """
            try: pivot_data = conn.execute(query, params).df()
            except: pivot_data = pd.DataFrame()
            
        
        def build_pivot_table(df, value_col, prefix=""):
            if df.empty: return pd.DataFrame()
            pivot = df.pivot_table(index=['Item_Code', 'Item_Name'], columns='Month_Label', values=value_col, aggfunc='sum', fill_value=0)
            pivot = pivot.reindex(sorted(pivot.columns), axis=1)
            pivot['Total'] = pivot.sum(axis=1)
            pivot = pivot.sort_values('Total', ascending=False).reset_index()
            numeric_cols = pivot.select_dtypes(include=['float64', 'int64']).columns
            for col in numeric_cols:
                pivot[col] = pivot[col].apply(lambda x: f'{prefix}{x:,.0f}' if x > 0 else '-')
            return pivot
        
        tab_val, tab_qty, tab_trans = st.tabs(["💰 Sales Value", "📦 Sales Qty", "📋 Sales Transactions"])
        with tab_val:
            if not pivot_data.empty:
                pivot_val = build_pivot_table(pivot_data, 'Sales_Amount', '$')
                st.dataframe(pivot_val, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_val.to_csv(index=False)
                st.download_button("📥 Download CSV (Value)", csv, "sales_item_value.csv", "text/csv")
            else: st.info("No data available")
        with tab_qty:
            if not pivot_data.empty:
                pivot_qty = build_pivot_table(pivot_data, 'Qty_Sold', '')
                st.dataframe(pivot_qty, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_qty.to_csv(index=False)
                st.download_button("📥 Download CSV (Qty)", csv, "sales_item_qty.csv", "text/csv")
            else: st.info("No data available")
        with tab_trans:
            if not pivot_data.empty:
                pivot_trans = build_pivot_table(pivot_data, 'Sales_Transactions', '')
                st.dataframe(pivot_trans, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_trans.to_csv(index=False)
                st.download_button("📥 Download CSV (Transactions)", csv, "sales_item_trans.csv", "text/csv")
            else: st.info("No data available")
        
        st.markdown("---")
        
        st.markdown("### 📊 Average Sales Analysis")
        if not item_performance.empty:
            avg_data = item_performance[['Item_Name', 'Total_Sales', 'Total_Qty', 'Total_Transactions']].copy()
            avg_data = avg_data.sort_values('Total_Sales', ascending=False)
            top10 = avg_data.head(10)
            if not top10.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=top10['Item_Name'], y=top10['Total_Sales'], name='Total Sales ($)', marker_color=st.session_state.accent_color))
                fig.add_trace(go.Bar(x=top10['Item_Name'], y=top10['Total_Qty'], name='Total Qty', marker_color='#22c55e'))
                fig.add_trace(go.Bar(x=top10['Item_Name'], y=top10['Total_Transactions'], name='Total Trans', marker_color='#f59e0b'))
                fig.update_layout(title='Top 10 Items by Total Sales', height=400, template='plotly_dark', xaxis={'tickangle': -45}, barmode='group', legend=dict(orientation='h', yanchor='bottom', y=1.02))
                st.plotly_chart(fig, use_container_width=True)
                
                display_avg = avg_data.copy()
                display_avg['Total_Sales'] = display_avg['Total_Sales'].apply(lambda x: f'${x:,.2f}')
                display_avg['Total_Qty'] = display_avg['Total_Qty'].apply(lambda x: f'{x:,.1f}')
                display_avg['Total_Transactions'] = display_avg['Total_Transactions'].apply(lambda x: f'{x:,.1f}')
                st.dataframe(display_avg, use_container_width=True, height=300, hide_index=True, column_config={"Item_Name": "Item", "Total_Sales": "Total Sales ($)", "Total_Qty": "Total Qty", "Total_Transactions": "Total Trans"})
                csv_avg = avg_data.to_csv(index=False)
                st.download_button("📥 Download Average Sales CSV", csv_avg, "avg_sales.csv", "text/csv")

    # ========================================================================
    # PAGE 3: RETURNS ANALYSIS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "🔄 Returns Analysis":
        st.markdown("### 🔄 Returns Analysis")
        st.caption("Monitor return trends and identify problem areas")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "🔄" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Returns" if view_type_label == "💰 Value" else "Return Qty" if view_type_label == "📦 Quantity" else "Return Trans"
            executive_kpi(label, kpis['returns']['current'], kpis['returns']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        with col2:
            executive_kpi("Return Quantity", kpis['returns']['qty'], kpis['returns']['prev_qty'], icon="📦", is_value=False, filter_context=filter_context, show_context=True)
        with col3:
            executive_kpi("Return Rate", kpis['rates']['return_rate']['current'], kpis['rates']['return_rate']['previous'], suffix="%", format=".2f", icon="📊", is_value=True, filter_context=filter_context, show_context=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 Returns Trend")
            if view_type_label == "💰 Value":
                y_col = 'Total_Returns'; y_label = 'Returns ($)'
            elif view_type_label == "📦 Quantity":
                y_col = 'Total_Return_Qty'; y_label = 'Quantity'
            else:
                y_col = 'Total_Return_Transactions'; y_label = 'Transactions'
            fig = create_chart(monthly_data, 'Month_Label', y_col, 'Returns Trend', '#ef4444', y_label, st.session_state.chart_type, st.session_state.show_ma, is_value, show_trend=st.session_state.show_trend_line)
            if fig: st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### 📊 Returns by Branch")
            if not branch_performance.empty:
                fig = px.bar(branch_performance.head(10), x='Branch', y='Total_Returns', title='Returns by Branch', color='Total_Returns', color_continuous_scale='Reds', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=30), showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.markdown(f"### 📋 {st.session_state.view_mode} Returns by Item")
        use_global = (branch == "All" and location == "All")
        if use_global:
            pivot_data = item_monthly_data[['Item_Code', 'Item_Name', 'Month_Label', 'Return_Amount', 'Qty_Returned', 'Return_Transactions']].copy() if not item_monthly_data.empty else pd.DataFrame()
        else:
            conn = get_connection()
            conditions = []; params = []
            if year != "All": conditions.append("Year = ?"); params.append(int(year))
            if month != "All":
                month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,"July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
                month_num = month_map.get(month)
                if month_num: conditions.append("Month_Num = ?"); params.append(month_num)
            if period != "All":
                quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
                q = quarter_map.get(period)
                if q: conditions.append("Quarter = ?"); params.append(q)
            if branch != "All": conditions.append("Branch = ?"); params.append(branch)
            if location != "All": conditions.append("Location = ?"); params.append(location)
            if product_group != "All": conditions.append("Product_Group = ?"); params.append(product_group)
            if division != "All": conditions.append("Division = ?"); params.append(division)
            if item_code != "All": conditions.append("UPPER(Item_Code) = UPPER(?)"); params.append(item_code)
            if item_name != "All": conditions.append("UPPER(Item_Name) = UPPER(?)"); params.append(item_name)
            if supplier != "All": conditions.append("UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))"); params.append(supplier)
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT Item_Code, Item_Name, Month_Label,
                       SUM(Return_Amount) as Return_Amount,
                       SUM(Qty_Returned) as Qty_Returned,
                       SUM(Return_Transactions) as Return_Transactions
                FROM branch_item_monthly_analysis
                WHERE {where_clause}
                GROUP BY Item_Code, Item_Name, Month_Label
                ORDER BY Item_Name, Month_Label
            """
            try: pivot_data = conn.execute(query, params).df()
            except: pivot_data = pd.DataFrame()
            
        
        def build_pivot_table(df, value_col, prefix=""):
            if df.empty: return pd.DataFrame()
            pivot = df.pivot_table(index=['Item_Code', 'Item_Name'], columns='Month_Label', values=value_col, aggfunc='sum', fill_value=0)
            pivot = pivot.reindex(sorted(pivot.columns), axis=1)
            pivot['Total'] = pivot.sum(axis=1)
            pivot = pivot.sort_values('Total', ascending=False).reset_index()
            numeric_cols = pivot.select_dtypes(include=['float64', 'int64']).columns
            for col in numeric_cols:
                pivot[col] = pivot[col].apply(lambda x: f'{prefix}{x:,.0f}' if x > 0 else '-')
            return pivot
        
        tab_val, tab_qty, tab_trans = st.tabs(["💰 Return Amount", "📦 Return Qty", "📋 Return Transactions"])
        with tab_val:
            if not pivot_data.empty:
                pivot_val = build_pivot_table(pivot_data, 'Return_Amount', '$')
                st.dataframe(pivot_val, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_val.to_csv(index=False)
                st.download_button("📥 Download CSV (Amount)", csv, "returns_item_value.csv", "text/csv")
            else: st.info("No data available")
        with tab_qty:
            if not pivot_data.empty:
                pivot_qty = build_pivot_table(pivot_data, 'Qty_Returned', '')
                st.dataframe(pivot_qty, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_qty.to_csv(index=False)
                st.download_button("📥 Download CSV (Qty)", csv, "returns_item_qty.csv", "text/csv")
            else: st.info("No data available")
        with tab_trans:
            if not pivot_data.empty:
                pivot_trans = build_pivot_table(pivot_data, 'Return_Transactions', '')
                st.dataframe(pivot_trans, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_trans.to_csv(index=False)
                st.download_button("📥 Download CSV (Transactions)", csv, "returns_item_trans.csv", "text/csv")
            else: st.info("No data available")
        
        st.markdown("---")
        
        st.markdown("### 📊 Average Returns Analysis")
        if not item_performance.empty:
            avg_data = item_performance[['Item_Name', 'Total_Returns']].copy()
            avg_data = avg_data.sort_values('Total_Returns', ascending=False)
            top10 = avg_data.head(10)
            if not top10.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=top10['Item_Name'], y=top10['Total_Returns'], name='Total Returns ($)', marker_color='#ef4444'))
                fig.update_layout(title='Top 10 Items by Total Returns', height=400, template='plotly_dark', xaxis={'tickangle': -45}, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                display_avg = avg_data.copy()
                display_avg['Total_Returns'] = display_avg['Total_Returns'].apply(lambda x: f'${x:,.2f}')
                st.dataframe(display_avg, use_container_width=True, height=300, hide_index=True, column_config={"Item_Name": "Item", "Total_Returns": "Total Returns ($)"})
                csv_avg = avg_data.to_csv(index=False)
                st.download_button("📥 Download Average Returns CSV", csv_avg, "avg_returns.csv", "text/csv")

    # ========================================================================
    # PAGE 4: NET SALES ANALYSIS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📊 Net Sales Analysis":
        st.markdown("### 📊 Net Sales Analysis")
        st.caption("Net Sales = Total Sales – Total Returns")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            prefix = "$" if view_type_label == "💰 Value" else ""
            icon = "📊" if view_type_label == "💰 Value" else "📦" if view_type_label == "📦 Quantity" else "📋"
            label = "Net Sales" if view_type_label == "💰 Value" else "Net Qty" if view_type_label == "📦 Quantity" else "Net Trans"
            executive_kpi(label, kpis['net']['current'], kpis['net']['previous'], prefix=prefix, icon=icon, is_value=is_value, filter_context=filter_context, show_context=True)
        with col2:
            executive_kpi("Net Quantity", kpis['net']['qty'], kpis['net']['prev_qty'], icon="📦", is_value=False, filter_context=filter_context, show_context=True)
        with col3:
            executive_kpi("Net Transactions", kpis['net']['trans'], kpis['net']['prev_trans'], icon="📋", is_value=True, filter_context=filter_context, show_context=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📈 Net Sales Trend")
            if view_type_label == "💰 Value":
                y_col = 'Total_Net'; y_label = 'Net Sales ($)'
            elif view_type_label == "📦 Quantity":
                y_col = 'Total_Net_Qty'; y_label = 'Quantity'
            else:
                y_col = 'Total_Net_Transactions'; y_label = 'Transactions'
            fig = create_chart(monthly_data, 'Month_Label', y_col, 'Net Sales Trend', '#22c55e', y_label, st.session_state.chart_type, st.session_state.show_ma, is_value, show_trend=st.session_state.show_trend_line)
            if fig: st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("### 📊 Sales vs Returns")
            if not monthly_data.empty:
                if view_type_label == "💰 Value":
                    sales_col = 'Total_Sales'; returns_col = 'Total_Returns'; net_col = 'Total_Net'; prefix = '$'
                elif view_type_label == "📦 Quantity":
                    sales_col = 'Total_Qty'; returns_col = 'Total_Return_Qty'; net_col = 'Total_Net_Qty'; prefix = ''
                else:
                    sales_col = 'Total_Transactions'; returns_col = 'Total_Return_Transactions'; net_col = 'Total_Net_Transactions'; prefix = ''
                fig = go.Figure()
                fig.add_trace(go.Bar(x=monthly_data['Month_Label'], y=monthly_data[sales_col], name='Sales', marker_color=st.session_state.accent_color, opacity=0.7, text=monthly_data[sales_col].apply(lambda x: f'{prefix}{x:,.0f}'), textposition='outside', textfont=dict(size=9)))
                fig.add_trace(go.Bar(x=monthly_data['Month_Label'], y=monthly_data[returns_col], name='Returns', marker_color='#ef4444', opacity=0.7, text=monthly_data[returns_col].apply(lambda x: f'{prefix}{x:,.0f}'), textposition='outside', textfont=dict(size=9)))
                fig.add_trace(go.Scatter(x=monthly_data['Month_Label'], y=monthly_data[net_col], name='Net', line=dict(color='#22c55e', width=3), mode='lines+markers+text', marker=dict(size=8), text=monthly_data[net_col].apply(lambda x: f'{prefix}{x:,.0f}'), textposition='top center', textfont=dict(size=9)))
                y_title = 'Amount ($)' if view_type_label == "💰 Value" else 'Quantity' if view_type_label == "📦 Quantity" else 'Transactions'
                fig.update_layout(title='Sales vs Returns vs Net', height=400, template='plotly_dark', margin=dict(l=20, r=20, t=50, b=50), xaxis={'title': 'Month', 'tickangle': -45 if len(monthly_data)>10 else 0}, yaxis={'title': y_title}, hovermode='x unified', legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), barmode='group')
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.markdown(f"### 📋 {st.session_state.view_mode} Net Sales by Item")
        use_global = (branch == "All" and location == "All")
        if use_global:
            pivot_data = item_monthly_data[['Item_Code', 'Item_Name', 'Month_Label', 'Net_Amount', 'Net_Qty', 'Net_Transactions']].copy() if not item_monthly_data.empty else pd.DataFrame()
        else:
            conn = get_connection()
            conditions = []; params = []
            if year != "All": conditions.append("Year = ?"); params.append(int(year))
            if month != "All":
                month_map = {"January":1,"February":2,"March":3,"April":4,"May":5,"June":6,"July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
                month_num = month_map.get(month)
                if month_num: conditions.append("Month_Num = ?"); params.append(month_num)
            if period != "All":
                quarter_map = {"Q1 (Jan-Mar)":1,"Q2 (Apr-Jun)":2,"Q3 (Jul-Sep)":3,"Q4 (Oct-Dec)":4}
                q = quarter_map.get(period)
                if q: conditions.append("Quarter = ?"); params.append(q)
            if branch != "All": conditions.append("Branch = ?"); params.append(branch)
            if location != "All": conditions.append("Location = ?"); params.append(location)
            if product_group != "All": conditions.append("Product_Group = ?"); params.append(product_group)
            if division != "All": conditions.append("Division = ?"); params.append(division)
            if item_code != "All": conditions.append("UPPER(Item_Code) = UPPER(?)"); params.append(item_code)
            if item_name != "All": conditions.append("UPPER(Item_Name) = UPPER(?)"); params.append(item_name)
            if supplier != "All": conditions.append("UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))"); params.append(supplier)
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"""
                SELECT Item_Code, Item_Name, Month_Label,
                       SUM(Net_Amount) as Net_Amount,
                       SUM(Net_Qty) as Net_Qty,
                       SUM(Net_Transactions) as Net_Transactions
                FROM branch_item_monthly_analysis
                WHERE {where_clause}
                GROUP BY Item_Code, Item_Name, Month_Label
                ORDER BY Item_Name, Month_Label
            """
            try: pivot_data = conn.execute(query, params).df()
            except: pivot_data = pd.DataFrame()
            
        
        def build_pivot_table(df, value_col, prefix=""):
            if df.empty: return pd.DataFrame()
            pivot = df.pivot_table(index=['Item_Code', 'Item_Name'], columns='Month_Label', values=value_col, aggfunc='sum', fill_value=0)
            pivot = pivot.reindex(sorted(pivot.columns), axis=1)
            pivot['Total'] = pivot.sum(axis=1)
            pivot = pivot.sort_values('Total', ascending=False).reset_index()
            numeric_cols = pivot.select_dtypes(include=['float64', 'int64']).columns
            for col in numeric_cols:
                pivot[col] = pivot[col].apply(lambda x: f'{prefix}{x:,.0f}' if x > 0 else '-')
            return pivot
        
        tab_val, tab_qty, tab_trans = st.tabs(["💰 Net Amount", "📦 Net Qty", "📋 Net Transactions"])
        with tab_val:
            if not pivot_data.empty:
                pivot_val = build_pivot_table(pivot_data, 'Net_Amount', '$')
                st.dataframe(pivot_val, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_val.to_csv(index=False)
                st.download_button("📥 Download CSV (Amount)", csv, "net_item_value.csv", "text/csv")
            else: st.info("No data available")
        with tab_qty:
            if not pivot_data.empty:
                pivot_qty = build_pivot_table(pivot_data, 'Net_Qty', '')
                st.dataframe(pivot_qty, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_qty.to_csv(index=False)
                st.download_button("📥 Download CSV (Qty)", csv, "net_item_qty.csv", "text/csv")
            else: st.info("No data available")
        with tab_trans:
            if not pivot_data.empty:
                pivot_trans = build_pivot_table(pivot_data, 'Net_Transactions', '')
                st.dataframe(pivot_trans, use_container_width=True, height=400, hide_index=True, column_config={"Item_Code": "Item Code", "Item_Name": "Item Name"})
                csv = pivot_trans.to_csv(index=False)
                st.download_button("📥 Download CSV (Transactions)", csv, "net_item_trans.csv", "text/csv")
            else: st.info("No data available")
        
        st.markdown("---")
        
        st.markdown("### 📊 Average Net Sales Analysis")
        if not item_performance.empty:
            avg_data = item_performance[['Item_Name', 'Total_Net']].copy()
            avg_data = avg_data.sort_values('Total_Net', ascending=False)
            top10 = avg_data.head(10)
            if not top10.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=top10['Item_Name'], y=top10['Total_Net'], name='Total Net ($)', marker_color='#22c55e'))
                fig.update_layout(title='Top 10 Items by Total Net Sales', height=400, template='plotly_dark', xaxis={'tickangle': -45}, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                display_avg = avg_data.copy()
                display_avg['Total_Net'] = display_avg['Total_Net'].apply(lambda x: f'${x:,.2f}')
                st.dataframe(display_avg, use_container_width=True, height=300, hide_index=True, column_config={"Item_Name": "Item", "Total_Net": "Total Net ($)"})
                csv_avg = avg_data.to_csv(index=False)
                st.download_button("📥 Download Average Net Sales CSV", csv_avg, "avg_net.csv", "text/csv")

    # ========================================================================
    # PAGE 5: YEAR COMPARISON - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📋 Year Comparison":
        st.markdown("### 📋 Year-over-Year Comparison")
        if not yearly_data.empty:
            st.markdown("#### 📊 Yearly Performance Summary")
            display_df = yearly_data.copy()
            for col in display_df.columns:
                if col != 'Year' and ('Qty' in col or 'Transactions' in col):
                    display_df[col] = display_df[col].apply(lambda x: f'{x:,.0f}')
                elif col != 'Year':
                    display_df[col] = display_df[col].apply(lambda x: f'${x:,.2f}')
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            if len(yearly_data) > 1:
                st.markdown("#### 📈 Year-over-Year Growth")
                yearly_growth = yearly_data.sort_values('Year')
                yearly_growth['Sales_Growth'] = yearly_growth['Total_Sales'].pct_change() * 100
                yearly_growth['Net_Growth'] = yearly_growth['Total_Net'].pct_change() * 100
                yearly_growth['Returns_Growth'] = yearly_growth['Total_Returns'].pct_change() * 100
                yearly_growth = yearly_growth.dropna()
                if not yearly_growth.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=yearly_growth['Year'].astype(str), y=yearly_growth['Sales_Growth'], name='Sales Growth', marker_color=st.session_state.accent_color, text=yearly_growth['Sales_Growth'].apply(lambda x: f'{x:+.1f}%'), textposition='outside', textfont=dict(size=10)))
                    fig.add_trace(go.Bar(x=yearly_growth['Year'].astype(str), y=yearly_growth['Net_Growth'], name='Net Sales Growth', marker_color='#22c55e', text=yearly_growth['Net_Growth'].apply(lambda x: f'{x:+.1f}%'), textposition='outside', textfont=dict(size=10)))
                    fig.add_trace(go.Bar(x=yearly_growth['Year'].astype(str), y=yearly_growth['Returns_Growth'], name='Returns Growth', marker_color='#ef4444', text=yearly_growth['Returns_Growth'].apply(lambda x: f'{x:+.1f}%'), textposition='outside', textfont=dict(size=10)))
                    fig.update_layout(title='Year-over-Year Growth Comparison', height=400, template='plotly_dark', margin=dict(l=20, r=20, t=50, b=20), barmode='group', xaxis_title='Year', yaxis_title='Growth (%)', legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No yearly data available.")
        
        st.markdown("---")
        
        st.markdown("#### 📋 Year-over-Year Comparison by Item")
        tab1, tab2, tab3 = st.tabs(["Sales YoY","Returns YoY","Net Sales YoY"])
        with tab1:
            if view_type_label == "💰 Value": pivot_suffix='value'
            elif view_type_label == "📦 Quantity": pivot_suffix='qty'
            else: pivot_suffix='trans'
            conn = get_connection()
            query = f"SELECT Item_Code, Item_Name, Current_Year, Previous_Year, YoY_Growth_Pct FROM sales_yoy_pivot_{pivot_suffix}"
            if supplier != "All":
                query += f" WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER('{supplier}'))"
            query += " ORDER BY YoY_Growth_Pct DESC NULLS LAST"
            yoy_df = conn.execute(query).df()
            
            if not yoy_df.empty:
                yoy_df['YoY_Growth_Pct'] = yoy_df['YoY_Growth_Pct'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')
                if view_type_label == "💰 Value":
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'${x:,.2f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'${x:,.2f}')
                else:
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'{x:,.0f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'{x:,.0f}')
                st.dataframe(yoy_df, use_container_width=True, hide_index=True)
                csv = yoy_df.to_csv(index=False)
                st.download_button("📥 Download Sales YoY CSV", csv, f"sales_yoy_pivot_{pivot_suffix}.csv", "text/csv")
            else: st.info("No data")
        with tab2:
            if view_type_label == "💰 Value": pivot_suffix='value'
            elif view_type_label == "📦 Quantity": pivot_suffix='qty'
            else: pivot_suffix='trans'
            query = f"SELECT Item_Code, Item_Name, Current_Year, Previous_Year, YoY_Growth_Pct FROM returns_yoy_pivot_{pivot_suffix}"
            if supplier != "All":
                query += f" WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER('{supplier}'))"
            query += " ORDER BY YoY_Growth_Pct DESC NULLS LAST"
            yoy_df = conn.execute(query).df()
            if not yoy_df.empty:
                yoy_df['YoY_Growth_Pct'] = yoy_df['YoY_Growth_Pct'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')
                if view_type_label == "💰 Value":
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'${x:,.2f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'${x:,.2f}')
                else:
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'{x:,.0f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'{x:,.0f}')
                st.dataframe(yoy_df, use_container_width=True, hide_index=True)
                csv = yoy_df.to_csv(index=False)
                st.download_button("📥 Download Returns YoY CSV", csv, f"returns_yoy_pivot_{pivot_suffix}.csv", "text/csv")
            else: st.info("No data")
        with tab3:
            if view_type_label == "💰 Value": pivot_suffix='value'
            elif view_type_label == "📦 Quantity": pivot_suffix='qty'
            else: pivot_suffix='trans'
            query = f"SELECT Item_Code, Item_Name, Current_Year, Previous_Year, YoY_Growth_Pct FROM net_sales_yoy_pivot_{pivot_suffix}"
            if supplier != "All":
                query += f" WHERE UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER('{supplier}'))"
            query += " ORDER BY YoY_Growth_Pct DESC NULLS LAST"
            yoy_df = conn.execute(query).df()
            if not yoy_df.empty:
                yoy_df['YoY_Growth_Pct'] = yoy_df['YoY_Growth_Pct'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')
                if view_type_label == "💰 Value":
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'${x:,.2f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'${x:,.2f}')
                else:
                    yoy_df['Current_Year'] = yoy_df['Current_Year'].apply(lambda x: f'{x:,.0f}')
                    yoy_df['Previous_Year'] = yoy_df['Previous_Year'].apply(lambda x: f'{x:,.0f}')
                st.dataframe(yoy_df, use_container_width=True, hide_index=True)
                csv = yoy_df.to_csv(index=False)
                st.download_button("📥 Download Net Sales YoY CSV", csv, f"net_sales_yoy_pivot_{pivot_suffix}.csv", "text/csv")
            else: st.info("No data")

# ========================================================================
    # PAGE 6: DEMAND FORECAST - ENHANCED WITH STOCK DATE INDICATOR
    # ========================================================================
    elif st.session_state.page == "🔮 Demand Forecast":
        st.markdown("""
        <div style="animation: fadeInDown 0.8s ease-out;">
            <h2 style="font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #0066CC, #7b5ea7, #22c55e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 4px;">🔮 Demand Planning & Forecasting</h2>
            <p style="color: #8899bb; font-size: 0.95rem; margin-top: 0;">Advanced forecast with 9 calculation methods, stock overlay, purchase history, and supplier integration</p>
        </div>
        """, unsafe_allow_html=True)

        # ---- Get stock snapshot date ----
        try:
            conn = get_connection()
            stock_date_result = conn.execute("""
                SELECT MAX(Month_End_Date) as Latest_Stock_Date FROM stock_unpivoted
            """).fetchone()
            latest_stock_date = stock_date_result[0] if stock_date_result and stock_date_result[0] else None
            if latest_stock_date:
                latest_stock_date_str = pd.to_datetime(latest_stock_date).strftime('%Y-%m-%d')
                st.info(f"📅 **Current Stock Data As Of:** {latest_stock_date_str} (Latest available snapshot)")
            else:
                latest_stock_date_str = "Unknown"
                st.warning("⚠️ Stock snapshot date not available")
        except Exception as e:
            latest_stock_date_str = "Unknown"
            st.warning(f"⚠️ Could not retrieve stock date: {e}")

        if not item_monthly_data.empty:
            all_months = sorted(item_monthly_data['Month_Label'].unique())
            default_lookback = min(12, len(all_months))
        else:
            all_months = []
            default_lookback = 12

        st.markdown("""
        <div class="control-panel">
        """, unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5, col6 = st.columns([1.5, 2, 2, 2, 1.5, 1.5])
        with col1:
            view_mode = st.radio("📊 View", ["📦 Qty", "💰 Value"], 
                                index=0, horizontal=True, key="demand_view_mode")
            use_qty = view_mode == "📦 Qty"
        
        with col2:
            if len(all_months) > 0:
                lookback_months = st.slider("📅 Lookback", 3, len(all_months), 
                                           min(default_lookback, len(all_months)), key="lookback_slider")
            else:
                lookback_months = st.slider("📅 Lookback", 3, 24, 12, key="lookback_slider")
                
        with col3:
            forecast_horizon = st.slider("📈 Horizon", 1, 12, st.session_state.forecast_horizon, key="horizon_slider")
            st.session_state.forecast_horizon = forecast_horizon
        
        with col4:
            safety_stock_pct = st.slider("🛡️ Safety %", 0, 100, 20, 5, key="safety_slider") / 100.0
        
        with col5:
            model_options = [
                "Simple Average", 
                "Weighted Average",
                "Median",
                "3-Month MA", 
                "6-Month MA",
                "12-Month MA",
                "Linear Trend", 
                "Exponential Smoothing",
                "Holt-Winters Trend"
            ]
            forecast_model = st.selectbox("🧮 Model", model_options, index=6, key="forecast_model_select")
        
        with col6:
            include_purchase = st.checkbox("📦 Show Purchase", value=True, key="include_purchase_check")
            include_supplier = st.checkbox("🏢 Show Supplier", value=True, key="include_supplier_check")
            st.session_state.show_forecast_confidence = st.checkbox("📊 Confidence Interval", value=st.session_state.show_forecast_confidence, key="show_confidence_check")
        
        st.markdown("</div>", unsafe_allow_html=True)

        if item_monthly_data.empty:
            st.warning("No monthly item data available for selected filters.")
        else:
            available_cols = item_monthly_data.columns.tolist()
            
            if use_qty:
                sales_col_use = 'Qty_Sold'
                net_col_use = 'Net_Qty'
                return_col_use = 'Qty_Returned'
                label_suffix = "Qty"
                prefix_val = ""
            else:
                sales_col_use = 'Sales_Amount'
                net_col_use = 'Net_Amount'
                return_col_use = 'Return_Amount'
                label_suffix = "Value"
                prefix_val = "$"
            
            agg_dict = {}
            if sales_col_use in available_cols:
                agg_dict['Total_Sales'] = (sales_col_use, 'sum')
            if net_col_use in available_cols:
                agg_dict['Total_Net'] = (net_col_use, 'sum')
            if return_col_use in available_cols:
                agg_dict['Total_Returns'] = (return_col_use, 'sum')
            if 'Qty_Sold' in available_cols:
                agg_dict['Total_Qty'] = ('Qty_Sold', 'sum')
            if 'Net_Qty' in available_cols:
                agg_dict['Total_Net_Qty'] = ('Net_Qty', 'sum')
            if 'Qty_Returned' in available_cols:
                agg_dict['Total_Return_Qty'] = ('Qty_Returned', 'sum')
            
            if not agg_dict:
                st.error(f"No numeric columns found for aggregation. Available: {available_cols}")
                st.stop()
            
            monthly_demand = item_monthly_data.groupby(['Year','Month_Num','Month_Label']).agg(**agg_dict).reset_index().sort_values(['Year','Month_Num'])
            
            if monthly_demand.empty:
                st.warning("No monthly sales data available for selected filters.")
            else:
                demand_cols = monthly_demand.columns.tolist()
                
                if 'Total_Net' in demand_cols:
                    forecast_col = 'Total_Net'
                elif 'Total_Sales' in demand_cols:
                    forecast_col = 'Total_Sales'
                else:
                    forecast_col = 'Total_Qty' if 'Total_Qty' in demand_cols else None
                
                qty_col = 'Total_Qty' if 'Total_Qty' in demand_cols else 'Total_Net_Qty'
                return_col = 'Total_Returns' if 'Total_Returns' in demand_cols else None
                sales_col = 'Total_Sales' if 'Total_Sales' in demand_cols else None
                
                if forecast_col is None:
                    st.error(f"Required forecast column not found. Available: {demand_cols}")
                    st.stop()
                
                clean_data = monthly_demand[monthly_demand[forecast_col] > 0].copy()
                
                if clean_data.empty:
                    st.warning("No valid data found after filtering out zero/negative months.")
                    st.stop()
                
                st.info(f"📊 Using {len(clean_data)} valid months (filtered out {len(monthly_demand) - len(clean_data)} months with zero/negative values)")
                
                all_months_available = sorted(clean_data['Month_Label'].unique())
                if len(all_months_available) >= lookback_months:
                    cutoff_month = all_months_available[-lookback_months]
                else:
                    cutoff_month = all_months_available[0] if all_months_available else None
                
                if cutoff_month:
                    historical = clean_data[clean_data['Month_Label'] >= cutoff_month].copy()
                else:
                    historical = clean_data.copy()
                
                if historical.empty:
                    st.warning("No data available for selected filters.")
                else:
                    hist_values = historical[forecast_col].values
                    x = np.arange(len(historical))
                    
                    # Calculate ALL 9 Averages
                    simple_avg_val = clean_data[forecast_col].mean()
                    weights = np.arange(1, len(hist_values) + 1)
                    weighted_avg_val = np.average(hist_values, weights=weights) if len(hist_values) > 0 else 0
                    median_avg_val = np.median(hist_values) if len(hist_values) > 0 else 0
                    avg_3_val = historical[forecast_col].tail(3).mean() if len(historical) >= 3 else simple_avg_val
                    avg_6_val = historical[forecast_col].tail(6).mean() if len(historical) >= 6 else simple_avg_val
                    avg_12_val = historical[forecast_col].tail(12).mean() if len(historical) >= 12 else simple_avg_val
                    
                    if len(historical) >= 3:
                        slope_val, intercept_val = np.polyfit(x, hist_values, 1)
                        trend_val = slope_val * len(historical) + intercept_val
                        y_pred = slope_val * x + intercept_val
                        ss_res = np.sum((hist_values - y_pred) ** 2)
                        ss_tot = np.sum((hist_values - np.mean(hist_values)) ** 2)
                        r_squared_val = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    else:
                        slope_val = 0
                        intercept_val = 0
                        trend_val = simple_avg_val
                        r_squared_val = 0
                    
                    alpha = 0.3
                    smoothed = [hist_values[0]]
                    for val in hist_values[1:]:
                        smoothed.append(alpha * val + (1 - alpha) * smoothed[-1])
                    exp_smooth_val = smoothed[-1]
                    
                    if len(historical) >= 3:
                        level = hist_values[0]
                        trend = (hist_values[1] - hist_values[0]) if len(hist_values) > 1 else 0
                        alpha_l = 0.3
                        alpha_t = 0.1
                        for i in range(1, len(hist_values)):
                            prev_level = level
                            level = alpha_l * hist_values[i] + (1 - alpha_l) * (level + trend)
                            trend = alpha_t * (level - prev_level) + (1 - alpha_t) * trend
                        holt_winters_val = level + trend
                    else:
                        holt_winters_val = simple_avg_val
                    
                    model_map = {
                        "Simple Average": simple_avg_val,
                        "Weighted Average": weighted_avg_val,
                        "Median": median_avg_val,
                        "3-Month MA": avg_3_val,
                        "6-Month MA": avg_6_val,
                        "12-Month MA": avg_12_val,
                        "Linear Trend": trend_val,
                        "Exponential Smoothing": exp_smooth_val,
                        "Holt-Winters Trend": holt_winters_val,
                    }
                    
                    avg_monthly_net = model_map.get(forecast_model, simple_avg_val)
                    
                    if forecast_model == "Linear Trend":
                        forecast_vals = [max(slope_val * (len(historical)+i-1) + intercept_val, 0) for i in range(1, forecast_horizon+1)]
                    else:
                        forecast_vals = [avg_monthly_net] * forecast_horizon
                    
                    total_forecast_agg = sum(forecast_vals)
                    total_net_sales = historical[forecast_col].sum()
                    total_qty_sales = historical[qty_col].sum() if qty_col in historical.columns else 0
                    total_returns = historical[return_col].sum() if return_col and return_col in historical.columns else 0
                    return_rate = (total_returns / total_qty_sales * 100) if total_qty_sales > 0 else 0

                    # ============================================================
                    # FIXED: CURRENT STOCK QUERY WITH PROPER BRANCH/LOCATION FILTERING
                    # ============================================================
                    stock_query = """
                        SELECT 
                            s.Item_Number as Item_Code,
                            SUM(s.Stock_Qty) as Total_Stock
                        FROM stock_unpivoted s
                        WHERE s.Month_End_Date = (SELECT MAX(Month_End_Date) FROM stock_unpivoted)
                    """
                    stock_params = []

                    # Branch filter
                    if branch != "All":
                        stock_query += " AND LOWER(s.Branch_Location) = LOWER(?)"
                        stock_params.append(branch)

                    # Location filter - FIXED for Kinshasa & Goma separate
                    if location != "All":
                        if location.lower() == "kinshasa":
                            stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Kinshasa')
                            )"""
                        elif location.lower() == "goma":
                            stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Goma')
                            )"""
                        elif location.lower() == "lubumbashi":
                            stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            stock_params.append(location)
                        else:
                            stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            stock_params.append(location)

                    # Product Group filter
                    if product_group != "All":
                        stock_query += """ AND s.Item_Number IN (
                            SELECT Item_Code FROM item_master 
                            WHERE LOWER(Product_Group) = LOWER(?)
                        )"""
                        stock_params.append(product_group)

                    # Division filter
                    if division != "All":
                        stock_query += """ AND s.Item_Number IN (
                            SELECT Item_Code FROM item_master 
                            WHERE LOWER(Division) = LOWER(?)
                        )"""
                        stock_params.append(division)

                    # Item Code filter
                    if item_code != "All":
                        stock_query += " AND UPPER(s.Item_Number) = UPPER(?)"
                        stock_params.append(item_code)

                    # Item Name filter
                    if item_name != "All":
                        stock_query += " AND UPPER(s.Item_Name) = UPPER(?)"
                        stock_params.append(item_name)

                    # Supplier filter
                    if supplier != "All":
                        stock_query += """ AND UPPER(s.Item_Number) IN (
                            SELECT UPPER(Item_Code) FROM supplier_product_mapping 
                            WHERE UPPER(Supplier) = UPPER(?)
                        )"""
                        stock_params.append(supplier)

                    stock_query += " GROUP BY s.Item_Number"

                    try:
                        conn = get_connection()
                        stock_df = conn.execute(stock_query, stock_params).df()
                        current_stock_total = stock_df['Total_Stock'].sum() if not stock_df.empty else 0
                        stock_agg = stock_df
                        
                        # Get stock item count
                        stock_item_count = len(stock_df) if not stock_df.empty else 0
                    except Exception as e:
                        st.warning(f"Error loading stock data: {e}")
                        current_stock_total = 0
                        stock_agg = pd.DataFrame()
                        stock_item_count = 0

                    # ============================================================
                    # FIXED: MONTHLY STOCK QUERY WITH PROPER BRANCH/LOCATION FILTERING
                    # ============================================================
                    monthly_stock_query = """
                        SELECT 
                            s.Item_Number as Item_Code,
                            STRFTIME(s.Month_End_Date, '%Y-%m') as Month_Label,
                            SUM(s.Stock_Qty) as Stock_Qty
                        FROM stock_unpivoted s
                        WHERE 1=1
                    """
                    monthly_stock_params = []

                    if branch != "All":
                        monthly_stock_query += " AND LOWER(s.Branch_Location) = LOWER(?)"
                        monthly_stock_params.append(branch)

                    if location != "All":
                        if location.lower() == "kinshasa":
                            monthly_stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Kinshasa')
                            )"""
                        elif location.lower() == "goma":
                            monthly_stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Goma')
                            )"""
                        elif location.lower() == "lubumbashi":
                            monthly_stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            monthly_stock_params.append(location)
                        else:
                            monthly_stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            monthly_stock_params.append(location)

                    if product_group != "All":
                        monthly_stock_query += """ AND s.Item_Number IN (
                            SELECT Item_Code FROM item_master 
                            WHERE LOWER(Product_Group) = LOWER(?)
                        )"""
                        monthly_stock_params.append(product_group)

                    if division != "All":
                        monthly_stock_query += """ AND s.Item_Number IN (
                            SELECT Item_Code FROM item_master 
                            WHERE LOWER(Division) = LOWER(?)
                        )"""
                        monthly_stock_params.append(division)

                    if item_code != "All":
                        monthly_stock_query += " AND UPPER(s.Item_Number) = UPPER(?)"
                        monthly_stock_params.append(item_code)

                    if item_name != "All":
                        monthly_stock_query += " AND UPPER(s.Item_Name) = UPPER(?)"
                        monthly_stock_params.append(item_name)

                    if supplier != "All":
                        monthly_stock_query += """ AND UPPER(s.Item_Number) IN (
                            SELECT UPPER(Item_Code) FROM supplier_product_mapping 
                            WHERE UPPER(Supplier) = UPPER(?)
                        )"""
                        monthly_stock_params.append(supplier)

                    monthly_stock_query += """ 
                        GROUP BY s.Item_Number, STRFTIME(s.Month_End_Date, '%Y-%m') 
                        ORDER BY STRFTIME(s.Month_End_Date, '%Y-%m')
                    """
                    
                    try:
                        conn = get_connection()
                        monthly_stock_full = conn.execute(monthly_stock_query, monthly_stock_params).df()
                        
                        if not monthly_stock_full.empty:
                            stock_chart_data = monthly_stock_full.groupby('Month_Label')['Stock_Qty'].sum().reset_index()
                            stock_chart_data = stock_chart_data[stock_chart_data['Month_Label'].isin(historical['Month_Label'].astype(str).tolist())]
                        else:
                            stock_chart_data = pd.DataFrame()
                    except Exception as e:
                        st.warning(f"Error loading monthly stock data: {e}")
                        stock_chart_data = pd.DataFrame()

                    # ---- Fetch purchase data for overlay ----
                    purchase_overlay_df = pd.DataFrame()
                    if include_purchase:
                        try:
                            purchase_query = """
                                SELECT 
                                    STRFTIME(Purchase_Date, '%Y-%m') as Month_Label,
                                    SUM(Qty) as Purchase_Qty,
                                    SUM(Amount_USD) as Purchase_Amount
                                FROM purchase_all_clean
                                WHERE Purchase_Date IS NOT NULL
                            """
                            purchase_params = []
                            if branch != "All":
                                purchase_query += " AND Branch = ?"
                                purchase_params.append(branch)
                            if location != "All":
                                purchase_query += " AND Branch IN (SELECT Branch FROM location_master WHERE Location = ?)"
                                purchase_params.append(location)
                            if item_code != "All":
                                purchase_query += " AND UPPER(Item_Code) = UPPER(?)"
                                purchase_params.append(item_code)
                            elif item_name != "All":
                                purchase_query += " AND UPPER(Item_Name) = UPPER(?)"
                                purchase_params.append(item_name)
                            if product_group != "All" or division != "All":
                                purchase_query += " AND Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                                if product_group != "All":
                                    purchase_query += " AND LOWER(Product_Group) = LOWER(?)"
                                    purchase_params.append(product_group)
                                if division != "All":
                                    purchase_query += " AND LOWER(Division) = LOWER(?)"
                                    purchase_params.append(division)
                                purchase_query += ")"
                            if supplier != "All":
                                purchase_query += " AND UPPER(Item_Code) IN (SELECT UPPER(Item_Code) FROM supplier_product_mapping WHERE UPPER(Supplier) = UPPER(?))"
                                purchase_params.append(supplier)
                            purchase_query += " GROUP BY STRFTIME(Purchase_Date, '%Y-%m') ORDER BY STRFTIME(Purchase_Date, '%Y-%m')"
                            
                            conn = get_connection()
                            purchase_overlay_df = conn.execute(purchase_query, purchase_params).df()
                        except Exception as e:
                            st.warning(f"Error loading purchase data: {e}")
                            purchase_overlay_df = pd.DataFrame()

                    # ---- Fetch supplier data ----
                    supplier_forecast_df = pd.DataFrame()
                    supplier_product_df = pd.DataFrame()
                    if include_supplier:
                        try:
                            supplier_query = """
                                SELECT 
                                    Supplier,
                                    SUM(Total_Sales) as Supplier_Revenue,
                                    SUM(Total_Qty) as Supplier_Qty,
                                    COUNT(DISTINCT Item_Code) as Product_Count
                                FROM supplier_product_performance
                                WHERE 1=1
                            """
                            supplier_params = []
                            if product_group != "All":
                                supplier_query += " AND LOWER(Product_Group) = LOWER(?)"
                                supplier_params.append(product_group)
                            if division != "All":
                                supplier_query += " AND LOWER(Division) = LOWER(?)"
                                supplier_params.append(division)
                            if item_code != "All":
                                supplier_query += " AND UPPER(Item_Code) = UPPER(?)"
                                supplier_params.append(item_code)
                            if item_name != "All":
                                supplier_query += " AND UPPER(Item_Name) = UPPER(?)"
                                supplier_params.append(item_name)
                            if supplier != "All":
                                supplier_query += " AND UPPER(Supplier) = UPPER(?)"
                                supplier_params.append(supplier)
                            supplier_query += " GROUP BY Supplier ORDER BY Supplier_Revenue DESC"
                            
                            conn = get_connection()
                            supplier_forecast_df = conn.execute(supplier_query, supplier_params).df()
                            
                            supplier_product_query = """
                                SELECT 
                                    Item_Code,
                                    Item_Name,
                                    Product_Group,
                                    Division,
                                    Brand_Name,
                                    Supplier,
                                    Is_Primary_Supplier
                                FROM supplier_product_mapping
                                WHERE 1=1
                            """
                            supplier_product_params = []
                            if product_group != "All":
                                supplier_product_query += " AND LOWER(Product_Group) = LOWER(?)"
                                supplier_product_params.append(product_group)
                            if division != "All":
                                supplier_product_query += " AND LOWER(Division) = LOWER(?)"
                                supplier_product_params.append(division)
                            if item_code != "All":
                                supplier_product_query += " AND UPPER(Item_Code) = UPPER(?)"
                                supplier_product_params.append(item_code)
                            if item_name != "All":
                                supplier_product_query += " AND UPPER(Item_Name) = UPPER(?)"
                                supplier_product_params.append(item_name)
                            if supplier != "All":
                                supplier_product_query += " AND UPPER(Supplier) = UPPER(?)"
                                supplier_product_params.append(supplier)
                            supplier_product_query += " ORDER BY Item_Name, Supplier"
                            
                            conn = get_connection()
                            supplier_product_df = conn.execute(supplier_product_query, supplier_product_params).df()
                        except Exception as e:
                            st.warning(f"Error loading supplier data: {e}")
                            supplier_forecast_df = pd.DataFrame()
                            supplier_product_df = pd.DataFrame()

                    # ---- Calculate KPIs ----
                    safety_stock_total = total_forecast_agg * safety_stock_pct
                    short_excess_total = current_stock_total - total_forecast_agg
                    stock_coverage = (current_stock_total / avg_monthly_net) if avg_monthly_net > 0 else 0
                    status_color = "#22c55e" if short_excess_total >= 0 else "#ef4444"
                    status_text = "✅ Excess Stock" if short_excess_total >= 0 else "⚠️ Short - Reorder"

                    # ---- Stock Date Indicator ----
                    stock_date_display = f"📅 Stock Snapshot: {latest_stock_date_str}" if latest_stock_date_str != "Unknown" else "📅 Stock Snapshot: Not Available"
                    
                    filter_display = f"Branch: {branch if branch != 'All' else 'All'}, Location: {location if location != 'All' else 'All'}, Item: {item_code if item_code != 'All' else 'All'}, Supplier: {supplier if supplier != 'All' else 'All'}"
                    st.caption(f"📌 Filters: {filter_display} | {stock_date_display} | {stock_item_count} items in stock")

                    # ---- SECTION 1: 10 KPI CARDS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📊</i> Executive KPI Dashboard</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # ---- Load PO data for transit and pending KPIs ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_kpi_data(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """Load PO data for KPI calculations. Filters directly on PRF_Location."""
                        conn = get_connection()
                        query = """
                            SELECT 
                                COALESCE(SUM(po.PO_Qty), 0) as Total_PO_Qty,
                                COALESCE(SUM(CASE WHEN po.Shipment_Status = 'Transit' THEN po.PO_Qty ELSE 0 END), 0) as Transit_Qty,
                                COALESCE(SUM(CASE WHEN po.Shipment_Status = 'PO Issued – Awaiting BL' THEN po.PO_Qty ELSE 0 END), 0) as Awaiting_BL_Qty,
                                COALESCE(COUNT(DISTINCT po.PO_No), 0) as PO_Count,
                                COALESCE(COUNT(DISTINCT CASE WHEN po.Shipment_Status = 'PO Issued – Awaiting BL' THEN po.PO_No END), 0) as Awaiting_BL_PO_Count,
                                COALESCE(COUNT(DISTINCT CASE WHEN po.Shipment_Status = 'Transit' THEN po.PO_No END), 0) as Transit_PO_Count
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        # Year filter
                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        
                        # Month filter
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        
                        # Period/Quarter filter
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter - direct PRF_Location match
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match (NO JOIN NEEDED)
                        # PRF_Location already contains: 'Lubumbashi', 'Kinshasa', 'Goma', etc.
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item Code filter
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        
                        # Item Name filter
                        if item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group filter
                        if product_group != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE LOWER(Product_Group) = LOWER(?))"
                            params.append(product_group)
                        
                        # Division filter
                        if division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE LOWER(Division) = LOWER(?))"
                            params.append(division)
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO KPI data: {e}")
                            return pd.DataFrame()

                    # ---- Load PO KPI data ----
                    po_kpi_df = load_po_kpi_data(
                        year, month, period, branch, location,
                        item_code, item_name, product_group, division, supplier
                    )
                    
                    # Extract PO KPI values
                    if not po_kpi_df.empty:
                        transit_qty = po_kpi_df['Transit_Qty'].iloc[0] if 'Transit_Qty' in po_kpi_df.columns else 0
                        awaiting_bl_qty = po_kpi_df['Awaiting_BL_Qty'].iloc[0] if 'Awaiting_BL_Qty' in po_kpi_df.columns else 0
                        awaiting_bl_pos = po_kpi_df['Awaiting_BL_PO_Count'].iloc[0] if 'Awaiting_BL_PO_Count' in po_kpi_df.columns else 0
                        transit_pos = po_kpi_df['Transit_PO_Count'].iloc[0] if 'Transit_PO_Count' in po_kpi_df.columns else 0
                    else:
                        transit_qty = 0
                        awaiting_bl_qty = 0
                        awaiting_bl_pos = 0
                        transit_pos = 0
                    
                    # ---- Display 10 KPI Cards ----
                    kpi_cols = st.columns(10)
                    label_suffix_display = "Value" if not use_qty else "Qty"
                    prefix_display = "$" if not use_qty else ""
                    
                    kpi_data = [
                        (f"Net {label_suffix_display}", f"{prefix_display}{total_net_sales:,.0f}", f"last {lookback_months} months", "📈", "#0066CC"),
                        ("Avg Monthly", f"{prefix_display}{avg_monthly_net:,.0f}", f"per month ({forecast_model})", "📊", "#f59e0b"),
                        (f"Total {label_suffix_display}", f"{prefix_display}{total_qty_sales:,.0f}", f"last {lookback_months} months", "📦", "#22c55e"),
                        ("Returns", f"{prefix_display}{total_returns:,.0f}", f"{return_rate:.1f}% rate", "🔄", "#ef4444"),
                        (f"Current Stock ({latest_stock_date_str})", f"{current_stock_total:,.0f}", f"{stock_item_count} items", "🏷️", "#8b5cf6"),
                        ("Forecast", f"{prefix_display}{total_forecast_agg:,.0f}", f"next {forecast_horizon} months", "🔮", "#22c55e"),
                        ("Safety Stock", f"{prefix_display}{safety_stock_total:,.0f}", f"{safety_stock_pct*100:.0f}% buffer", "🛡️", "#3b82f6"),
                        ("Short/Excess", f"{prefix_display}{short_excess_total:,.0f}", status_text, "⚖️", status_color),
                        (f"🚚 Transit Qty", f"{transit_qty:,.0f}", f"{transit_pos} POs in transit", "🚚", "#3b82f6"),
                        (f"⏳ Awaiting BL", f"{awaiting_bl_qty:,.0f}", f"{awaiting_bl_pos} POs awaiting BL", "⏳", "#f59e0b")
                    ]
                    
                    for i, (label, value, sub, icon, color) in enumerate(kpi_data):
                        with kpi_cols[i]:
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid {color}; animation-delay: {i*0.05}s;">
                                <div class="icon">{icon}</div>
                                <div class="label">
                                    <span>{label}</span>
                                    <span style="font-size:0.5rem; color:#667799;">●</span>
                                </div>
                                <div class="value" style="color: {color};">{value}</div>
                                <div class="sub">
                                    <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:{color};"></span>
                                    {sub}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    # ---- SECTION 2: STOCK COVERAGE ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📊</i> Stock Coverage Analysis</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns([3, 1.2, 1.2, 1.2])
                    with col1:
                        coverage_pct = min((stock_coverage / 6) * 100, 100)
                        color = "#22c55e" if stock_coverage >= 3 else "#f59e0b" if stock_coverage >= 1 else "#ef4444"
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#0d1528,#1a2236); border-radius:12px; padding:14px 20px; border:1px solid #2a3450; animation:fadeInUp 0.6s ease-out; transition: all 0.3s ease;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                                <span style="color:#8899bb; font-size:0.7rem; display:flex; align-items:center; gap:6px;">
                                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{color}; animation:pulse 2s infinite;"></span>
                                    Stock Coverage (Months of Supply)
                                </span>
                                <span style="color:#e8edf5; font-weight:700; font-size:1.1rem; animation:countUp 0.8s ease-out;">{stock_coverage:.1f} months</span>
                            </div>
                            <div style="background:#1a2236; border-radius:20px; height:12px; overflow:hidden; position:relative;">
                                <div style="background:linear-gradient(90deg, {color}, {color}dd); height:100%; width:{coverage_pct}%; border-radius:20px; transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1); position:relative;">
                                    <div style="position:absolute; top:0; left:0; right:0; bottom:0; background:linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent); animation:shimmer 2s infinite;"></div>
                                </div>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-top:4px;">
                                <span style="color:#667799; font-size:0.5rem;">0</span>
                                <span style="color:#667799; font-size:0.5rem;">3 months</span>
                                <span style="color:#667799; font-size:0.5rem;">6+</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:0.65rem; color:#8899bb;">
                                <span>🔴 Critical: &lt;1 month</span>
                                <span>🟡 Warning: 1-3 months</span>
                                <span>🟢 Healthy: 3+ months</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#0d1528,#1a2236); border-radius:12px; padding:14px; border:1px solid #2a3450; text-align:center; animation:fadeInUp 0.6s ease-out 0.1s; transition: all 0.3s ease;">
                            <div style="font-size:0.6rem; color:#8899bb;">Forecast Model</div>
                            <div style="font-size:0.9rem; font-weight:600; color:#e8edf5; margin-top:2px;">{forecast_model}</div>
                            <div style="font-size:0.5rem; color:#667799; margin-top:2px;">● Active</div>
                            <div style="font-size:0.5rem; color:#22c55e; margin-top:4px;">✅ {len(historical)} months data</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        if slope_val != 0:
                            trend_text = "📈 Rising" if slope_val > 0 else "📉 Falling" if slope_val < 0 else "➡️ Flat"
                            trend_color = "#22c55e" if slope_val > 0 else "#ef4444" if slope_val < 0 else "#8899bb"
                            slope_display = f"{slope_val:+.2f}"
                        else:
                            trend_text = "➡️ Flat (Avg)"
                            trend_color = "#8899bb"
                            slope_display = "N/A"
                        
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#0d1528,#1a2236); border-radius:12px; padding:14px; border:1px solid #2a3450; text-align:center; animation:fadeInUp 0.6s ease-out 0.2s; transition: all 0.3s ease;">
                            <div style="font-size:0.6rem; color:#8899bb;">Demand Trend</div>
                            <div style="font-size:0.9rem; font-weight:600; color:{trend_color}; margin-top:2px;">{trend_text}</div>
                            <div style="font-size:0.5rem; color:#667799; margin-top:2px;">● {slope_display} slope</div>
                            <div style="font-size:0.5rem; color:#667799; margin-top:2px;">R²: {r_squared_val:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col4:
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#0d1528,#1a2236); border-radius:12px; padding:14px; border:1px solid #2a3450; text-align:center; animation:fadeInUp 0.6s ease-out 0.3s; transition: all 0.3s ease;">
                            <div style="font-size:0.6rem; color:#8899bb;">Stock Data</div>
                            <div style="font-size:0.9rem; font-weight:600; color:#8b5cf6; margin-top:2px;">{stock_item_count} items</div>
                            <div style="font-size:0.5rem; color:#667799; margin-top:2px;">● Snapshot: {latest_stock_date_str}</div>
                            <div style="font-size:0.5rem; color:#667799; margin-top:2px;">● {location if location != 'All' else 'All Locations'}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # ---- SECTION 3: MAIN CHART ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📈</i> Demand Trend Analysis</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    hist_months = historical['Month_Label'].astype(str).tolist()
                    hist_net = historical[forecast_col].tolist()
                    
                    last_month_dt = pd.to_datetime(hist_months[-1] + '-01') if hist_months else pd.Timestamp.now()
                    future_months = [(last_month_dt + pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(1, forecast_horizon+1)]
                    
                    all_values = hist_net + forecast_vals
                    if not stock_chart_data.empty:
                        all_values = all_values + stock_chart_data['Stock_Qty'].tolist()
                    if not purchase_overlay_df.empty:
                        all_values = all_values + purchase_overlay_df['Purchase_Qty'].tolist()
                    y_max = max(all_values) * 1.35 if all_values else 1000
                    
                    fig = go.Figure()
                    
                    y_axis_title = f"{label_suffix_display} ({prefix_display})" if prefix_display else label_suffix_display
                    
                    fig.add_trace(go.Bar(
                        x=hist_months,
                        y=hist_net,
                        name=f'Net {label_suffix_display}',
                        marker=dict(
                            color=st.session_state.accent_color,
                            opacity=0.9,
                            line=dict(width=1, color='rgba(255,255,255,0.2)')
                        ),
                        text=[f'{prefix_display}{v:,.0f}' for v in hist_net],
                        textposition='inside',
                        textfont=dict(size=14, color='white', weight='bold'),
                        hovertemplate=f'<b>%{{x}}</b><br>Net {label_suffix_display}: %{{y:,.0f}}<extra></extra>',
                        width=0.5
                    ))
                    
                    fig.add_trace(go.Bar(
                        x=future_months,
                        y=forecast_vals,
                        name=f'Forecast {label_suffix_display}',
                        marker=dict(
                            color='#22c55e',
                            opacity=0.85,
                            line=dict(width=1, color='rgba(255,255,255,0.2)')
                        ),
                        text=[f'{prefix_display}{v:,.0f}' for v in forecast_vals],
                        textposition='inside',
                        textfont=dict(size=14, color='white', weight='bold'),
                        hovertemplate=f'<b>%{{x}}</b><br>Forecast: %{{y:,.0f}}<extra></extra>',
                        width=0.5
                    ))
                    
                    if not stock_chart_data.empty and len(stock_chart_data) > 0:
                        fig.add_trace(go.Bar(
                            x=stock_chart_data['Month_Label'].astype(str).tolist(),
                            y=stock_chart_data['Stock_Qty'],
                            name=f'Month-End Stock ({latest_stock_date_str})',
                            marker=dict(
                                color='#00b4d8',
                                opacity=0.7,
                                line=dict(width=1, color='rgba(255,255,255,0.15)')
                            ),
                            text=stock_chart_data['Stock_Qty'].apply(lambda x: f'{x:,.0f}'),
                            textposition='outside',
                            textfont=dict(size=11, color='#00b4d8'),
                            hovertemplate='<b>%{x}</b><br>Stock: %{y:,.0f}<extra></extra>',
                            width=0.5
                        ))
                    
                    if include_purchase and not purchase_overlay_df.empty:
                        purchase_months = purchase_overlay_df['Month_Label'].astype(str).tolist()
                        fig.add_trace(go.Scatter(
                            x=purchase_months,
                            y=purchase_overlay_df['Purchase_Qty'],
                            name='Purchase Qty',
                            line=dict(color='#f59e0b', width=2.5, dash='dot'),
                            mode='lines+markers+text',
                            marker=dict(size=10, color='#f59e0b', symbol='square'),
                            text=purchase_overlay_df['Purchase_Qty'].apply(lambda x: f'{x:,.0f}'),
                            textposition='bottom center',
                            textfont=dict(size=10, color='#f59e0b'),
                            hovertemplate='<b>%{x}</b><br>Purchase: %{y:,.0f}<extra></extra>'
                        ))
                    
                    avg_line_values = [avg_monthly_net] * (len(hist_months) + forecast_horizon)
                    all_months_avg = hist_months + future_months
                    fig.add_trace(go.Scatter(
                        x=all_months_avg,
                        y=avg_line_values,
                        name=f'Avg {label_suffix_display} ({forecast_model})',
                        line=dict(color='#f59e0b', width=3, dash='dash'),
                        mode='lines+markers+text',
                        marker=dict(size=10, color='#f59e0b', symbol='diamond'),
                        text=[f'{prefix_display}{v:,.0f}' for v in avg_line_values],
                        textposition='top center',
                        textfont=dict(size=11, color='#f59e0b'),
                        hovertemplate=f'Average {label_suffix_display}: %{{y:,.0f}}<extra></extra>'
                    ))
                    
                    # Confidence Interval
                    if st.session_state.show_forecast_confidence and len(hist_net) > 3:
                        std_dev = np.std(hist_net)
                        confidence_factor = 1.96 if st.session_state.confidence_interval == 95 else 1.645
                        upper_bound = [avg_monthly_net + confidence_factor * std_dev] * forecast_horizon
                        lower_bound = [max(0, avg_monthly_net - confidence_factor * std_dev)] * forecast_horizon
                        
                        fig.add_trace(go.Scatter(
                            x=future_months + future_months[::-1],
                            y=upper_bound + lower_bound[::-1],
                            fill='toself',
                            fillcolor='rgba(34, 197, 94, 0.15)',
                            line=dict(color='rgba(255,255,255,0)'),
                            name=f'{st.session_state.confidence_interval}% Confidence Interval',
                            showlegend=True,
                            hovertemplate='Confidence Range: %{y:,.0f}<extra></extra>'
                        ))
                    
                    if hist_months:
                        fig.add_vline(x=hist_months[-1], line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=2)
                        fig.add_annotation(
                            x=hist_months[-1],
                            y=y_max * 0.95,
                            text="║ Forecast Start",
                            showarrow=False,
                            font=dict(size=10, color="#8899bb"),
                            textangle=0
                        )
                    
                    fig.update_layout(
                        title=dict(
                            text=f'Monthly {label_suffix_display} Trend with Forecast, Stock & Purchase',
                            font=dict(size=18, color='#e8edf5')
                        ),
                        height=550,
                        template='plotly_dark',
                        margin=dict(l=70, r=70, t=80, b=100),
                        xaxis=dict(
                            title=dict(text='Month', font=dict(size=14, color='#8899bb')),
                            tickangle=-45,
                            tickfont=dict(size=12, color='#e8edf5'),
                            gridcolor='rgba(255,255,255,0.05)',
                            type='category'
                        ),
                        yaxis=dict(
                            title=dict(text=y_axis_title, font=dict(size=14, color='#8899bb')),
                            tickformat=',.0f',
                            gridcolor='rgba(255,255,255,0.05)',
                            range=[0, y_max]
                        ),
                        hovermode='x unified',
                        legend=dict(
                            orientation='h', 
                            yanchor='bottom', 
                            y=1.02, 
                            xanchor='right', 
                            x=1, 
                            font=dict(size=12, color='#e8edf5')
                        ),
                        bargap=0.1,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        transition=dict(duration=800, easing='cubic-in-out')
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                    # ============================================================
                    # LOAD PURCHASE ORDER DATA FOR PIPELINE TRACKING
                    # ============================================================
                    # ---- Load PO Data ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_summary_by_item(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """
                        Aggregate purchase order quantities by item with status breakdown.
                        Filters directly on PRF_Location.
                        """
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.Supplier_Name,
                                po.PRF_Location as Branch,
                                SUM(po.PO_Qty) as Total_PO_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Transit' THEN po.PO_Qty ELSE 0 END) as In_Transit_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Goods Received at Warehouse' THEN po.PO_Qty ELSE 0 END) as Received_Qty,
                                SUM(CASE WHEN po.Shipment_Status NOT IN ('Transit', 'Goods Received at Warehouse', 'Closed') THEN po.PO_Qty ELSE 0 END) as Pending_Qty,
                                COUNT(DISTINCT po.PO_No) as PO_Count,
                                COUNT(DISTINCT po.PRF_No) as PRF_Count
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        # Apply filters
                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " GROUP BY po.Item_Code, po.\"Product_Name_(DRC)\", po.Supplier_Name, po.PRF_Location ORDER BY Total_PO_Qty DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO summary: {e}")
                            return pd.DataFrame()

                    # ---- Load Detailed PO Data for Status Tracking ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_details(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """Load detailed PO data with shipment status. Filters directly on PRF_Location."""
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.PO_No,
                                po.PRF_No,
                                po.PO_Date,
                                po.PO_Qty,
                                po.PO_Total_Amount,
                                po.Supplier_Name,
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.PI_No,
                                po.PI_Date,
                                po.Dispatched_Qty,
                                po.Invoice_Qty,
                                po.Shipment_Status,
                                po.GRN_Qty,
                                po.GRN_Date,
                                po.PO_Status,
                                po.PO_Age_Days,
                                po.PRF_Location as Branch,
                                po.BL_No,
                                po.BL_Date
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " ORDER BY po.PO_Date DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO details: {e}")
                            return pd.DataFrame()

                    # ---- Load the PO data ----
                    with st.spinner("Loading purchase order data..."):
                        po_summary_df = load_po_summary_by_item(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        po_details_df = load_po_details(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        
            

                    # ---- SECTION 4: CRITICAL STOCK ALERTS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>⚠️</i> Critical Stock Alerts</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)                    


                    # ============================================================
                    # LOAD PURCHASE ORDER DATA FOR PIPELINE TRACKING
                    # ============================================================
                    # ---- Load PO Data ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_summary_by_item(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """
                        Aggregate purchase order quantities by item with status breakdown.
                        Filters directly on PRF_Location.
                        """
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.Supplier_Name,
                                po.PRF_Location as Branch,
                                SUM(po.PO_Qty) as Total_PO_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Transit' THEN po.PO_Qty ELSE 0 END) as In_Transit_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Goods Received at Warehouse' THEN po.PO_Qty ELSE 0 END) as Received_Qty,
                                SUM(CASE WHEN po.Shipment_Status NOT IN ('Transit', 'Goods Received at Warehouse', 'Closed') THEN po.PO_Qty ELSE 0 END) as Pending_Qty,
                                COUNT(DISTINCT po.PO_No) as PO_Count,
                                COUNT(DISTINCT po.PRF_No) as PRF_Count
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        # Apply filters
                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " GROUP BY po.Item_Code, po.\"Product_Name_(DRC)\", po.Supplier_Name, po.PRF_Location ORDER BY Total_PO_Qty DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO summary: {e}")
                            return pd.DataFrame()

                    # ---- Load Detailed PO Data for Status Tracking ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_details(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """Load detailed PO data with shipment status. Filters directly on PRF_Location."""
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.PO_No,
                                po.PRF_No,
                                po.PO_Date,
                                po.PO_Qty,
                                po.PO_Total_Amount,
                                po.Supplier_Name,
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.PI_No,
                                po.PI_Date,
                                po.Dispatched_Qty,
                                po.Invoice_Qty,
                                po.Shipment_Status,
                                po.GRN_Qty,
                                po.GRN_Date,
                                po.PO_Status,
                                po.PO_Age_Days,
                                po.PRF_Location as Branch,
                                po.BL_No,
                                po.BL_Date
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " ORDER BY po.PO_Date DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO details: {e}")
                            return pd.DataFrame()

                    # ---- Load the PO data ----
                    with st.spinner("Loading purchase order data..."):
                        po_summary_df = load_po_summary_by_item(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        po_details_df = load_po_details(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        
      

                    # ---- SECTION 4: CRITICAL STOCK ALERTS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>⚠️</i> Critical Stock Alerts</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if not stock_agg.empty and not item_monthly_data.empty:
                        item_agg_dict2 = {}
                        if 'Qty_Sold' in available_cols:
                            item_agg_dict2['Total_Qty'] = ('Qty_Sold', 'sum')
                        if 'Net_Qty' in available_cols:
                            item_agg_dict2['Total_Net_Qty'] = ('Net_Qty', 'sum')
                        if 'Item_Name' in available_cols:
                            item_agg_dict2['Item_Name'] = ('Item_Name', 'first')
                        if 'Product_Group' in available_cols:
                            item_agg_dict2['Product_Group'] = ('Product_Group', 'first')
                        if 'Division' in available_cols:
                            item_agg_dict2['Division'] = ('Division', 'first')
                        
                        item_analysis = item_monthly_data.groupby(['Item_Code']).agg(**item_agg_dict2).reset_index()
                        
                        if not stock_agg.empty:
                            item_analysis['Item_Code'] = item_analysis['Item_Code'].astype(str)
                            stock_agg['Item_Code'] = stock_agg['Item_Code'].astype(str)
                            item_analysis = pd.merge(item_analysis, stock_agg, on='Item_Code', how='left')
                            if 'Item_Name_x' in item_analysis.columns and 'Item_Name_y' in item_analysis.columns:
                                item_analysis['Item_Name'] = item_analysis['Item_Name_x'].fillna(item_analysis['Item_Name_y'])
                                item_analysis = item_analysis.drop(['Item_Name_x', 'Item_Name_y'], axis=1)
                            elif 'Item_Name_y' in item_analysis.columns:
                                item_analysis['Item_Name'] = item_analysis['Item_Name_y']
                                item_analysis = item_analysis.drop('Item_Name_y', axis=1)
                        else:
                            item_analysis['Total_Stock'] = 0
                        
                        item_analysis['Total_Stock'] = item_analysis['Total_Stock'].fillna(0)
                        
                        unique_months = item_monthly_data['Month_Label'].nunique()
                        if unique_months > 0:
                            if 'Total_Net_Qty' in item_analysis.columns:
                                item_analysis['Avg_Monthly_Qty'] = item_analysis['Total_Net_Qty'] / unique_months
                            elif 'Total_Qty' in item_analysis.columns:
                                item_analysis['Avg_Monthly_Qty'] = item_analysis['Total_Qty'] / unique_months
                            else:
                                item_analysis['Avg_Monthly_Qty'] = 0
                        else:
                            item_analysis['Avg_Monthly_Qty'] = 0
                        
                        item_analysis['Stock_Coverage_Months'] = item_analysis.apply(
                            lambda row: row['Total_Stock'] / row['Avg_Monthly_Qty'] if row['Avg_Monthly_Qty'] > 0 else 999, 
                            axis=1
                        )
                        
                        # Count alerts
                        overstock_count = len(item_analysis[
                            (item_analysis['Stock_Coverage_Months'] > 6) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0) &
                            (item_analysis['Total_Stock'] > 0)
                        ])
                        stockout_count = len(item_analysis[
                            (item_analysis['Stock_Coverage_Months'] < 2) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0) &
                            (item_analysis['Total_Stock'] > 0)
                        ]) + len(item_analysis[
                            (item_analysis['Total_Stock'] == 0) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0)
                        ])
                        
                        # Alert summary
                        alert_col1, alert_col2, alert_col3 = st.columns(3)
                        with alert_col1:
                            st.markdown(f"""
                            <div style="background: rgba(59, 130, 246, 0.08); border-radius: 8px; padding: 12px 16px; border: 1px solid #3b82f644; text-align:center;">
                                <span style="font-size:0.7rem; color:#8899bb;">📦 Overstocked Items</span>
                                <div style="font-size:1.4rem; font-weight:700; color:#3b82f6;">{overstock_count}</div>
                                <span style="font-size:0.6rem; color:#667799;">> 6 months coverage</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with alert_col2:
                            st.markdown(f"""
                            <div style="background: rgba(239, 68, 68, 0.08); border-radius: 8px; padding: 12px 16px; border: 1px solid #ef444444; text-align:center;">
                                <span style="font-size:0.7rem; color:#8899bb;">🚨 Stockout Risk</span>
                                <div style="font-size:1.4rem; font-weight:700; color:#ef4444;">{stockout_count}</div>
                                <span style="font-size:0.6rem; color:#667799;">&lt; 2 months coverage</span>
                            </div>
                            """, unsafe_allow_html=True)
                        with alert_col3:
                            healthy_count = len(item_analysis) - overstock_count - stockout_count
                            st.markdown(f"""
                            <div style="background: rgba(34, 197, 94, 0.08); border-radius: 8px; padding: 12px 16px; border: 1px solid #22c55e44; text-align:center;">
                                <span style="font-size:0.7rem; color:#8899bb;">✅ Healthy Stock</span>
                                <div style="font-size:1.4rem; font-weight:700; color:#22c55e;">{healthy_count}</div>
                                <span style="font-size:0.6rem; color:#667799;">2-6 months coverage</span>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # ---- OVERSTOCKED ITEMS (with Transit & Pending Qty) ----
                        st.markdown("""
                        <div class="risk-container" style="animation-delay: 0.1s;">
                            <div style="background: rgba(59, 130, 246, 0.08); border-radius: 12px; padding: 16px 20px; border: 1px solid #3b82f644; margin-bottom: 16px; transition: all 0.3s ease;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <span style="font-size: 1.4rem; animation: pulse 2s infinite;">📦</span>
                                    <div>
                                        <div style="font-weight: 600; color: #e8edf5; font-size: 1rem;">Overstocked Items</div>
                                        <div style="font-size: 0.75rem; color: #8899bb;">Low Average Qty, Huge Stock • Consider reducing order quantities</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        overstocked = item_analysis[
                            (item_analysis['Stock_Coverage_Months'] > 6) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0) &
                            (item_analysis['Total_Stock'] > 0)
                        ].copy()
                        overstocked = overstocked.sort_values('Stock_Coverage_Months', ascending=False)
                        
                        if not overstocked.empty:
                            # Calculate additional KPIs for each item
                            overstocked['Forecast'] = overstocked['Avg_Monthly_Qty'] * forecast_horizon
                            overstocked['Safety_Stock'] = overstocked['Forecast'] * safety_stock_pct
                            overstocked['Short_Excess'] = overstocked['Total_Stock'] - overstocked['Forecast']
                            
                            # ---- FIX: Add PO data (Transit & Pending) ----
                            # Initialize columns with 0
                            overstocked['In_Transit_Qty'] = 0
                            overstocked['Pending_Qty'] = 0
                            
                            if 'po_summary_df' in locals() and not po_summary_df.empty:
                                # Clean and standardize Item_Code for matching
                                overstocked['Item_Code_clean'] = overstocked['Item_Code'].astype(str).str.strip().str.upper()
                                po_summary_df['Item_Code_clean'] = po_summary_df['Item_Code'].astype(str).str.strip().str.upper()
                                
                                # Aggregate PO data by Item_Code
                                po_agg = po_summary_df.groupby('Item_Code_clean').agg({
                                    'In_Transit_Qty': 'sum',
                                    'Pending_Qty': 'sum'
                                }).reset_index()
                                
                                # Merge with overstocked
                                overstocked = overstocked.merge(po_agg, on='Item_Code_clean', how='left', suffixes=('', '_po'))
                                overstocked['In_Transit_Qty'] = overstocked['In_Transit_Qty_po'].fillna(0)
                                overstocked['Pending_Qty'] = overstocked['Pending_Qty_po'].fillna(0)
                                
                                # Drop temporary columns
                                overstocked = overstocked.drop(['Item_Code_clean', 'In_Transit_Qty_po', 'Pending_Qty_po'], axis=1, errors='ignore')
                                
                                # ---- DEBUG: Show match count ----
                                matched_count = len(overstocked[overstocked['In_Transit_Qty'] > 0])
                                st.caption(f"🔍 {matched_count} overstocked items have transit/pending PO data")
                            
                            # Display columns with all KPIs
                            display_cols = [
                                'Item_Code', 'Item_Name', 'Product_Group', 
                                'Total_Stock', 'Avg_Monthly_Qty', 'Stock_Coverage_Months',
                                'Forecast', 'Safety_Stock', 'Short_Excess',
                                'In_Transit_Qty', 'Pending_Qty'
                            ]
                            display_cols = [c for c in display_cols if c in overstocked.columns]
                            display_overstocked = overstocked.head(30)[display_cols].copy()
                            
                            # Format numbers - show actual values
                            for col in ['Total_Stock', 'Avg_Monthly_Qty', 'Forecast', 'Safety_Stock', 'Short_Excess', 'In_Transit_Qty', 'Pending_Qty']:
                                if col in display_overstocked.columns:
                                    display_overstocked[col] = display_overstocked[col].apply(lambda x: f'{x:,.0f}' if pd.notna(x) and x > 0 else '-')
                            if 'Stock_Coverage_Months' in display_overstocked.columns:
                                display_overstocked['Stock_Coverage_Months'] = display_overstocked['Stock_Coverage_Months'].apply(lambda x: f'{x:.1f} months')
                            
                            col_rename = {
                                'Item_Code': 'Item Code',
                                'Item_Name': 'Item Name',
                                'Product_Group': 'Product Group',
                                'Total_Stock': 'Current Stock',
                                'Avg_Monthly_Qty': 'Avg Monthly Qty',
                                'Stock_Coverage_Months': 'Coverage',
                                'Forecast': 'Forecast',
                                'Safety_Stock': 'Safety Stock',
                                'Short_Excess': 'Short/Excess',
                                'In_Transit_Qty': '🚚 Transit Qty',
                                'Pending_Qty': '⏳ Pending Qty'
                            }
                            display_overstocked = display_overstocked.rename(columns={k: v for k, v in col_rename.items() if k in display_overstocked.columns})
                            
                            st.markdown(f"""
                            <div style="background: rgba(59, 130, 246, 0.05); border-radius: 8px; padding: 8px 12px; margin-bottom: 8px; border-left: 3px solid #3b82f6; animation: slideInLeft 0.6s ease-out;">
                                <span style="color: #8899bb; font-size: 0.8rem;">🔍 {len(overstocked)} overstocked items found. Showing top 30.</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.dataframe(display_overstocked, use_container_width=True, height=250, hide_index=True)
                            csv_overstocked = overstocked.to_csv(index=False)
                            st.download_button("📥 Download Overstocked Items", csv_overstocked, "overstocked_items.csv", "text/csv")
                        else:
                            st.success("✅ No overstocked items found!")
                        
                        # ---- STOCKOUT RISK ITEMS (with Transit & Pending Qty) ----
                        st.markdown("""
                        <div class="risk-container" style="animation-delay: 0.3s;">
                            <div style="background: rgba(239, 68, 68, 0.08); border-radius: 12px; padding: 16px 20px; border: 1px solid #ef444444; margin: 20px 0 16px 0; transition: all 0.3s ease;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <span style="font-size: 1.4rem; animation: pulse 2s infinite;">🚨</span>
                                    <div>
                                        <div style="font-weight: 600; color: #e8edf5; font-size: 1rem;">Stockout Risk Items</div>
                                        <div style="font-size: 0.75rem; color: #8899bb;">High Average Qty, Low Stock • Urgent reorder recommended</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        stockout_risk = item_analysis[
                            (item_analysis['Stock_Coverage_Months'] < 2) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0) &
                            (item_analysis['Total_Stock'] > 0)
                        ].copy()
                        zero_stock_items = item_analysis[
                            (item_analysis['Total_Stock'] == 0) & 
                            (item_analysis['Avg_Monthly_Qty'] > 0)
                        ].copy()
                        zero_stock_items['Stock_Coverage_Months'] = 0
                        stockout_risk = pd.concat([stockout_risk, zero_stock_items])
                        stockout_risk = stockout_risk.sort_values('Avg_Monthly_Qty', ascending=False)
                        
                        if not stockout_risk.empty:
                            # Calculate additional KPIs for each item
                            stockout_risk['Forecast'] = stockout_risk['Avg_Monthly_Qty'] * forecast_horizon
                            stockout_risk['Safety_Stock'] = stockout_risk['Forecast'] * safety_stock_pct
                            stockout_risk['Short_Excess'] = stockout_risk['Total_Stock'] - stockout_risk['Forecast']
                            
                            # ---- FIX: Add PO data (Transit & Pending) ----
                            # Initialize columns with 0
                            stockout_risk['In_Transit_Qty'] = 0
                            stockout_risk['Pending_Qty'] = 0
                            
                            if 'po_summary_df' in locals() and not po_summary_df.empty:
                                # Clean and standardize Item_Code for matching
                                stockout_risk['Item_Code_clean'] = stockout_risk['Item_Code'].astype(str).str.strip().str.upper()
                                po_summary_df['Item_Code_clean'] = po_summary_df['Item_Code'].astype(str).str.strip().str.upper()
                                
                                # Aggregate PO data by Item_Code
                                po_agg = po_summary_df.groupby('Item_Code_clean').agg({
                                    'In_Transit_Qty': 'sum',
                                    'Pending_Qty': 'sum'
                                }).reset_index()
                                
                                # Merge with stockout_risk
                                stockout_risk = stockout_risk.merge(po_agg, on='Item_Code_clean', how='left', suffixes=('', '_po'))
                                stockout_risk['In_Transit_Qty'] = stockout_risk['In_Transit_Qty_po'].fillna(0)
                                stockout_risk['Pending_Qty'] = stockout_risk['Pending_Qty_po'].fillna(0)
                                
                                # Drop temporary columns
                                stockout_risk = stockout_risk.drop(['Item_Code_clean', 'In_Transit_Qty_po', 'Pending_Qty_po'], axis=1, errors='ignore')
                            
                            # Display columns with all KPIs
                            display_cols = [
                                'Item_Code', 'Item_Name', 'Product_Group', 
                                'Total_Stock', 'Avg_Monthly_Qty', 'Stock_Coverage_Months',
                                'Forecast', 'Safety_Stock', 'Short_Excess',
                                'In_Transit_Qty', 'Pending_Qty'
                            ]
                            display_cols = [c for c in display_cols if c in stockout_risk.columns]
                            display_risk = stockout_risk.head(30)[display_cols].copy()
                            
                            # Add urgency
                            def get_urgency(row):
                                if row.get('Total_Stock', 0) == 0:
                                    return '🔴 CRITICAL'
                                elif row.get('Stock_Coverage_Months', 999) < 0.5:
                                    return '🔴 URGENT'
                                elif row.get('Stock_Coverage_Months', 999) < 1:
                                    return '🟡 HIGH'
                                else:
                                    return '🟠 MODERATE'
                            display_risk['Urgency'] = display_risk.apply(get_urgency, axis=1)
                            
                            # Format numbers
                            for col in ['Total_Stock', 'Avg_Monthly_Qty', 'Forecast', 'Safety_Stock', 'Short_Excess', 'In_Transit_Qty', 'Pending_Qty']:
                                if col in display_risk.columns:
                                    display_risk[col] = display_risk[col].apply(lambda x: f'{x:,.0f}' if pd.notna(x) and x > 0 else '-')
                            if 'Stock_Coverage_Months' in display_risk.columns:
                                display_risk['Stock_Coverage_Months'] = display_risk['Stock_Coverage_Months'].apply(lambda x: f'{x:.1f} months' if x > 0 else '⚠️ ZERO')
                            
                            col_rename = {
                                'Item_Code': 'Item Code',
                                'Item_Name': 'Item Name',
                                'Product_Group': 'Product Group',
                                'Total_Stock': 'Current Stock',
                                'Avg_Monthly_Qty': 'Avg Monthly Qty',
                                'Stock_Coverage_Months': 'Coverage',
                                'Forecast': 'Forecast',
                                'Safety_Stock': 'Safety Stock',
                                'Short_Excess': 'Short/Excess',
                                'In_Transit_Qty': '🚚 Transit Qty',
                                'Pending_Qty': '⏳ Pending Qty',
                                'Urgency': '⚠️ Urgency'
                            }
                            display_risk = display_risk.rename(columns={k: v for k, v in col_rename.items() if k in display_risk.columns})
                            
                            # Sort by urgency
                            urgency_order = {'🔴 CRITICAL': 0, '🔴 URGENT': 1, '🟡 HIGH': 2, '🟠 MODERATE': 3}
                            if '⚠️ Urgency' in display_risk.columns:
                                display_risk['_urgency_order'] = display_risk['⚠️ Urgency'].map(urgency_order)
                                display_risk = display_risk.sort_values('_urgency_order').drop('_urgency_order', axis=1)
                            
                            st.markdown(f"""
                            <div style="background: rgba(239, 68, 68, 0.05); border-radius: 8px; padding: 8px 12px; margin-bottom: 8px; border-left: 3px solid #ef4444; animation: slideInRight 0.6s ease-out;">
                                <span style="color: #8899bb; font-size: 0.8rem;">🚨 {len(stockout_risk)} items at risk. Showing top 30.</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.dataframe(display_risk, use_container_width=True, height=300, hide_index=True)
                            csv_risk = stockout_risk.to_csv(index=False)
                            st.download_button("📥 Download Stockout Risk Items", csv_risk, "stockout_risk_items.csv", "text/csv")
                        else:
                            st.success("✅ No stockout risk items found!")

                    # ---- SECTION 5: SUPPLIER-WISE DEMAND PLAN ----
                    if include_supplier:
                        st.markdown("""
                        <div class="section-divider">
                            <span class="title"><i>🏢</i> Supplier-Wise Demand Plan</span>
                            <span class="line"></span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if not supplier_forecast_df.empty:
                            st.markdown("#### Supplier Demand Summary")
                            display_supplier = supplier_forecast_df.copy()
                            for col in ['Supplier_Revenue', 'Supplier_Qty']:
                                if col in display_supplier.columns:
                                    display_supplier[col] = display_supplier[col].apply(lambda x: f'{prefix_display}{x:,.0f}')
                            st.dataframe(display_supplier, use_container_width=True, hide_index=True)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                fig_supplier = px.bar(supplier_forecast_df.head(15), 
                                                     x='Supplier_Revenue', y='Supplier',
                                                     orientation='h', title='Top Suppliers by Revenue',
                                                     color='Supplier_Revenue', color_continuous_scale='Greens',
                                                     text_auto='.1s')
                                fig_supplier.update_layout(height=350, template='plotly_dark',
                                                          margin=dict(l=10, r=10, t=40, b=20),
                                                          xaxis_title='Revenue ($)', showlegend=False)
                                fig_supplier.update_traces(textposition='outside', textfont=dict(size=9))
                                st.plotly_chart(fig_supplier, use_container_width=True)
                            with col2:
                                fig_supplier_qty = px.bar(supplier_forecast_df.head(15), 
                                                         x='Supplier_Qty', y='Supplier',
                                                         orientation='h', title='Top Suppliers by Quantity',
                                                         color='Supplier_Qty', color_continuous_scale='Blues',
                                                         text_auto='.1s')
                                fig_supplier_qty.update_layout(height=350, template='plotly_dark',
                                                              margin=dict(l=10, r=10, t=40, b=20),
                                                              xaxis_title='Quantity', showlegend=False)
                                fig_supplier_qty.update_traces(textposition='outside', textfont=dict(size=9))
                                st.plotly_chart(fig_supplier_qty, use_container_width=True)
                            
                            csv_supplier = supplier_forecast_df.to_csv(index=False)
                            st.download_button("📥 Download Supplier Demand Plan", csv_supplier, "supplier_demand_plan.csv", "text/csv")
                        else:
                            st.info("No supplier data available for the selected filters.")
                        
                        if not supplier_product_df.empty:
                            st.markdown("#### Supplier-Product Mapping")
                            display_mapping = supplier_product_df.copy()
                            display_mapping['Is_Primary_Supplier'] = display_mapping['Is_Primary_Supplier'].apply(
                                lambda x: '✅ Primary' if x == 1 else 'Secondary'
                            )
                            st.dataframe(display_mapping, use_container_width=True, height=300, hide_index=True)
                            csv_mapping = supplier_product_df.to_csv(index=False)
                            st.download_button("📥 Download Supplier-Product Mapping", csv_mapping, "supplier_product_mapping.csv", "text/csv")

                    # ---- SECTION 6: PURCHASE HISTORY ----
                    if include_purchase:
                        st.markdown("""
                        <div class="section-divider">
                            <span class="title"><i>📦</i> Purchase History</span>
                            <span class="line"></span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        purchase_df = load_purchase_data(
                            year, month, period, branch, location, 
                            item_code, item_name, product_group, division,
                            supplier, st.session_state.vendor, st.session_state.purchase_type
                        )
                        
                        if not purchase_df.empty:
                            total_purchase_qty = purchase_df['Qty'].sum() if 'Qty' in purchase_df.columns else 0
                            total_purchase_amount = purchase_df['Amount_USD'].sum() if 'Amount_USD' in purchase_df.columns else 0
                            unique_vendors = purchase_df['Vendor'].nunique() if 'Vendor' in purchase_df.columns else 0
                            
                            p_cols = st.columns(4)
                            with p_cols[0]:
                                st.markdown(f"""
                                <div class="purchase-card" style="animation-delay: 0.1s;">
                                    <div class="purchase-label">📦 Total Purchase Qty</div>
                                    <div class="purchase-value">{total_purchase_qty:,.0f}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with p_cols[1]:
                                st.markdown(f"""
                                <div class="purchase-card" style="animation-delay: 0.2s; border-top: 2px solid #22c55e;">
                                    <div class="purchase-label">💰 Total Purchase Value</div>
                                    <div class="purchase-value" style="color: #22c55e;">${total_purchase_amount:,.2f}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with p_cols[2]:
                                st.markdown(f"""
                                <div class="purchase-card" style="animation-delay: 0.3s; border-top: 2px solid #f59e0b;">
                                    <div class="purchase-label">🏢 Unique Vendors</div>
                                    <div class="purchase-value" style="color: #f59e0b;">{unique_vendors}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with p_cols[3]:
                                st.markdown(f"""
                                <div class="purchase-card" style="animation-delay: 0.4s; border-top: 2px solid #8b5cf6;">
                                    <div class="purchase-label">📊 Transactions</div>
                                    <div class="purchase-value" style="color: #8b5cf6;">{len(purchase_df):,}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            display_purchase = purchase_df.sort_values('Purchase_Date', ascending=False).head(100).copy()
                            if 'Purchase_Date' in display_purchase.columns:
                                display_purchase['Purchase_Date'] = pd.to_datetime(display_purchase['Purchase_Date']).dt.strftime('%Y-%m-%d')
                            if 'Qty' in display_purchase.columns:
                                display_purchase['Qty'] = display_purchase['Qty'].apply(lambda x: f'{x:,.0f}')
                            if 'Amount_USD' in display_purchase.columns:
                                display_purchase['Amount_USD'] = display_purchase['Amount_USD'].apply(lambda x: f'${x:,.2f}')
                            col_rename = {
                                'Purchase_Date': 'Date',
                                'Purchase_Type': 'Type',
                                'Branch': 'Branch',
                                'Vendor': 'Vendor',
                                'Item_Code': 'Item Code',
                                'Item_Name': 'Item Name',
                                'Qty': 'Qty',
                                'Amount_USD': 'Amount',
                                'Country': 'Country',
                                'Carrier': 'Carrier'
                            }
                            display_purchase = display_purchase.rename(columns={k: v for k, v in col_rename.items() if k in display_purchase.columns})
                            display_cols = ['Date', 'Type', 'Branch', 'Vendor', 'Item Code', 'Item Name', 'Qty', 'Amount']
                            display_cols = [c for c in display_cols if c in display_purchase.columns]
                            display_purchase = display_purchase[display_cols]
                            st.dataframe(display_purchase, use_container_width=True, height=300, hide_index=True)
                            csv_purchase = purchase_df.to_csv(index=False)
                            st.download_button("📥 Download Purchase History", csv_purchase, "purchase_history.csv", "text/csv")
                        else:
                            st.info("No purchase data available for the selected filters.")

                    # ---- SECTION 7: TWO CHARTS ROW ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📊</i> Growth & Comparison</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        st.markdown("#### 📊 Monthly Growth Rate")
                        if len(historical) > 1:
                            growth_data = historical.copy()
                            growth_data['Growth'] = growth_data[forecast_col].pct_change() * 100
                            growth_data = growth_data.dropna()
                            if not growth_data.empty:
                                colors = ['#22c55e' if x >= 0 else '#ef4444' for x in growth_data['Growth']]
                                fig_growth = go.Figure()
                                fig_growth.add_trace(go.Bar(
                                    x=growth_data['Month_Label'],
                                    y=growth_data['Growth'],
                                    marker=dict(color=colors, opacity=0.8, line=dict(width=0.5, color='rgba(255,255,255,0.1)')),
                                    text=growth_data['Growth'].apply(lambda x: f'{x:+.1f}%'),
                                    textposition='outside',
                                    textfont=dict(size=10, color='#e8edf5')
                                ))
                                fig_growth.add_hline(y=0, line_dash="dash", line_color="#8899bb", line_width=1)
                                fig_growth.update_layout(
                                    height=380, 
                                    template='plotly_dark', 
                                    margin=dict(l=20, r=20, t=30, b=40), 
                                    xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
                                    yaxis=dict(title='Growth %', tickfont=dict(size=10)),
                                    showlegend=False,
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)'
                                )
                                st.plotly_chart(fig_growth, use_container_width=True, config={'displayModeBar': False})
                            else:
                                st.info("Not enough data")
                        else:
                            st.info("Need at least 2 months")
                    
                    with col_chart2:
                        st.markdown("#### 📊 Qty vs Returns")
                        if return_col and return_col in historical.columns and qty_col in historical.columns:
                            fig_vs = go.Figure()
                            fig_vs.add_trace(go.Bar(
                                x=historical['Month_Label'], 
                                y=historical[qty_col], 
                                name='Total Qty', 
                                marker=dict(color='rgba(0,102,204,0.5)', opacity=0.7)
                            ))
                            fig_vs.add_trace(go.Bar(
                                x=historical['Month_Label'], 
                                y=historical[return_col], 
                                name='Returns Qty', 
                                marker=dict(color='rgba(239,68,68,0.6)', opacity=0.7)
                            ))
                            fig_vs.add_trace(go.Scatter(
                                x=historical['Month_Label'], 
                                y=historical[forecast_col], 
                                name=f'Net {label_suffix_display}', 
                                line=dict(color='#22c55e', width=2.5), 
                                mode='lines+markers', 
                                marker=dict(size=7, color='#22c55e')
                            ))
                            fig_vs.update_layout(
                                title=f'Qty vs Returns vs Net {label_suffix_display}', 
                                height=380, 
                                template='plotly_dark', 
                                margin=dict(l=20, r=20, t=40, b=40), 
                                xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
                                yaxis=dict(title='Qty', tickfont=dict(size=10)),
                                legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=10)),
                                barmode='group',
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig_vs, use_container_width=True, config={'displayModeBar': False})
                        else:
                            st.info("Returns data not available")

                    # ---- SECTION 8: MONTHLY SUMMARY TABLE ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📋</i> Monthly Performance Summary</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    monthly_summary_cols = ['Month_Label', qty_col, forecast_col]
                    if return_col and return_col in historical.columns:
                        monthly_summary_cols.append(return_col)
                    if sales_col and sales_col in historical.columns:
                        monthly_summary_cols.append(sales_col)
                    
                    monthly_summary = historical[monthly_summary_cols].copy()
                    col_names = ['Month', 'Total Qty', f'Net {label_suffix_display}']
                    if return_col and return_col in historical.columns:
                        col_names.append('Returns Qty')
                    if sales_col and sales_col in historical.columns:
                        col_names.append(f'Sales {label_suffix_display}')
                    monthly_summary.columns = col_names
                    
                    monthly_summary['Growth %'] = monthly_summary[f'Net {label_suffix_display}'].pct_change() * 100
                    monthly_summary['Growth %'] = monthly_summary['Growth %'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')
                    monthly_summary['Cumulative'] = monthly_summary[f'Net {label_suffix_display}'].cumsum()
                    
                    for col in ['Total Qty', f'Net {label_suffix_display}', 'Returns Qty', f'Sales {label_suffix_display}', 'Cumulative']:
                        if col in monthly_summary.columns:
                            monthly_summary[col] = monthly_summary[col].apply(lambda x: f'{prefix_display}{x:,.0f}' if prefix_display else f'{x:,.0f}')
                    
                    st.markdown("""
                    <div class="table-container">
                        <div class="table-header">
                            <span>📊 Monthly Performance</span>
                            <span class="badge">Data based</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.dataframe(monthly_summary, use_container_width=True, height=250, hide_index=True)
                    csv_monthly = monthly_summary.to_csv(index=False)
                    st.download_button("📥 Download Monthly Summary", csv_monthly, "monthly_summary.csv", "text/csv", use_container_width=True)

                    # ---- SECTION 9: PER-ITEM FORECAST TABLE (Demand Plan with Transit & Pending) ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📊</i> Per-Item Forecast & Stock Status (Demand Plan)</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if 'item_analysis' in locals() and not item_analysis.empty:
                        forecast_df = item_analysis.copy()
                        forecast_df['Avg_Monthly_Net'] = forecast_df['Avg_Monthly_Qty']
                        forecast_df['Forecast'] = forecast_df['Avg_Monthly_Net'] * forecast_horizon
                        forecast_df['Safety_Stock'] = forecast_df['Forecast'] * safety_stock_pct
                        forecast_df['Short_Excess'] = forecast_df['Total_Stock'] - forecast_df['Forecast']
                        
                        # ---- FIX: Add PO data (Transit & Pending) ----
                        # Initialize columns with 0
                        forecast_df['In_Transit_Qty'] = 0
                        forecast_df['Pending_Qty'] = 0
                        
                        if 'po_summary_df' in locals() and not po_summary_df.empty:
                            # Clean and standardize Item_Code for matching
                            forecast_df['Item_Code_clean'] = forecast_df['Item_Code'].astype(str).str.strip().str.upper()
                            po_summary_df['Item_Code_clean'] = po_summary_df['Item_Code'].astype(str).str.strip().str.upper()
                            
                            # Aggregate PO data by Item_Code
                            po_agg = po_summary_df.groupby('Item_Code_clean').agg({
                                'In_Transit_Qty': 'sum',
                                'Pending_Qty': 'sum'
                            }).reset_index()
                            
                            # Merge with forecast_df
                            forecast_df = forecast_df.merge(po_agg, on='Item_Code_clean', how='left', suffixes=('', '_po'))
                            forecast_df['In_Transit_Qty'] = forecast_df['In_Transit_Qty_po'].fillna(0)
                            forecast_df['Pending_Qty'] = forecast_df['Pending_Qty_po'].fillna(0)
                            
                            # Drop temporary columns
                            forecast_df = forecast_df.drop(['Item_Code_clean', 'In_Transit_Qty_po', 'Pending_Qty_po'], axis=1, errors='ignore')
                            
                            # ---- DEBUG: Show match count ----
                            matched_count = len(forecast_df[forecast_df['In_Transit_Qty'] > 0])
                            st.caption(f"🔍 {matched_count} items have transit/pending PO data")
                        
                        def get_status(row):
                            if row['Total_Stock'] < row['Safety_Stock']:
                                return '🔴 Reorder'
                            elif row['Total_Stock'] < row['Forecast']:
                                return '🟡 Low Stock'
                            elif row['Total_Stock'] > row['Forecast'] * 1.5:
                                return '🟢 Overstock'
                            else:
                                return '✅ Healthy'
                        
                        forecast_df['Status'] = forecast_df.apply(get_status, axis=1)
                        
                        # Display columns with all KPIs
                        display_cols = ['Item_Code']
                        if 'Item_Name' in forecast_df.columns:
                            display_cols.append('Item_Name')
                        if 'Product_Group' in forecast_df.columns:
                            display_cols.append('Product_Group')
                        if 'Division' in forecast_df.columns:
                            display_cols.append('Division')
                        if 'Total_Stock' in forecast_df.columns:
                            display_cols.append('Total_Stock')
                        if 'Avg_Monthly_Qty' in forecast_df.columns:
                            display_cols.append('Avg_Monthly_Qty')
                        if 'Forecast' in forecast_df.columns:
                            display_cols.append('Forecast')
                        if 'Safety_Stock' in forecast_df.columns:
                            display_cols.append('Safety_Stock')
                        if 'Short_Excess' in forecast_df.columns:
                            display_cols.append('Short_Excess')
                        if 'In_Transit_Qty' in forecast_df.columns:
                            display_cols.append('In_Transit_Qty')
                        if 'Pending_Qty' in forecast_df.columns:
                            display_cols.append('Pending_Qty')
                        if 'Status' in forecast_df.columns:
                            display_cols.append('Status')
                        
                        display_cols = [c for c in display_cols if c in forecast_df.columns]
                        display_df = forecast_df[display_cols].copy()
                        
                        # Format numbers - show actual values
                        for col in ['Total_Stock', 'Avg_Monthly_Qty', 'Forecast', 'Safety_Stock', 'Short_Excess', 'In_Transit_Qty', 'Pending_Qty']:
                            if col in display_df.columns:
                                display_df[col] = display_df[col].apply(lambda x: f'{prefix_display}{x:,.0f}' if prefix_display and x > 0 else (f'{x:,.0f}' if x > 0 else '-'))
                        
                        col_rename = {
                            'Item_Code': 'Item Code',
                            'Item_Name': 'Item Name',
                            'Product_Group': 'Product Group',
                            'Division': 'Division',
                            'Total_Stock': 'Current Stock',
                            'Avg_Monthly_Qty': f'Avg Monthly {label_suffix_display}',
                            'Forecast': 'Forecast',
                            'Safety_Stock': 'Safety Stock',
                            'Short_Excess': 'Short/Excess',
                            'In_Transit_Qty': '🚚 Transit Qty',
                            'Pending_Qty': '⏳ Pending Qty',
                            'Status': 'Status'
                        }
                        display_df = display_df.rename(columns={k: v for k, v in col_rename.items() if k in display_df.columns})
                        
                        st.markdown("""
                        <div class="table-container">
                            <div class="table-header">
                                <span>📋 Demand Plan - Per Item Forecast & Supply Pipeline</span>
                                <span class="badge">Includes Transit & Pending Quantities</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        search_item = st.text_input("🔍 Search Item", placeholder="Type item code or name...", key="forecast_search")
                        if search_item and 'Item Code' in display_df.columns and 'Item Name' in display_df.columns:
                            display_df = display_df[
                                display_df['Item Code'].str.contains(search_item, case=False, na=False) | 
                                display_df['Item Name'].str.contains(search_item, case=False, na=False)
                            ]
                        
                        st.dataframe(display_df, use_container_width=True, height=400, hide_index=True)
                        csv_forecast = forecast_df.to_csv(index=False)
                        st.download_button("📥 Download Full Forecast Data", csv_forecast, "item_forecast.csv", "text/csv", use_container_width=True)
                    else:
                        st.info("No item-level stock data available for per-item forecast.")

                    # ---- SECTION 10: TOP ITEMS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>🏆</i> Top Items by Forecast</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if 'forecast_df' in locals() and not forecast_df.empty:
                        max_items = min(200, len(forecast_df))
                        top_n = st.slider("Number of Items", 1, max_items, 10, step=1, key="top_items_slider")
                        
                        if 'Forecast' in forecast_df.columns:
                            top_items = forecast_df.nlargest(top_n, 'Forecast')
                        else:
                            top_items = forecast_df.head(top_n)
                        
                        if not top_items.empty and 'Item_Name' in top_items.columns:
                            fig2 = go.Figure()
                            
                            if 'Forecast' in top_items.columns:
                                fig2.add_trace(go.Bar(
                                    x=top_items['Item_Name'],
                                    y=top_items['Forecast'],
                                    name=f'Forecast {label_suffix_display}',
                                    marker=dict(color='#f59e0b', opacity=0.8),
                                    text=top_items['Forecast'].apply(lambda x: f'{prefix_display}{x:,.0f}'),
                                    textposition='outside',
                                    textfont=dict(size=9, color='#f59e0b')
                                ))
                            
                            if 'Total_Stock' in top_items.columns:
                                fig2.add_trace(go.Bar(
                                    x=top_items['Item_Name'],
                                    y=top_items['Total_Stock'],
                                    name='Current Stock (Qty)',
                                    marker=dict(color='#3b82f6', opacity=0.8),
                                    text=top_items['Total_Stock'].apply(lambda x: f'{x:,.0f}'),
                                    textposition='outside',
                                    textfont=dict(size=9, color='#3b82f6')
                                ))
                            
                            if 'Safety_Stock' in top_items.columns:
                                fig2.add_trace(go.Scatter(
                                    x=top_items['Item_Name'],
                                    y=top_items['Safety_Stock'],
                                    name='Reorder Level',
                                    mode='lines+markers',
                                    marker=dict(color='#ef4444', size=10, symbol='x'),
                                    line=dict(color='#ef4444', dash='dash', width=2)
                                ))
                            
                            fig2.update_layout(
                                title=f'Top {top_n} Items: Forecast vs Current Stock',
                                height=400,
                                template='plotly_dark',
                                xaxis=dict(tickangle=-45, tickfont=dict(size=9, color='#e8edf5')),
                                yaxis=dict(title='Qty', tickformat=',.0f', tickfont=dict(size=10)),
                                barmode='group',
                                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=10)),
                                margin=dict(l=30, r=30, t=50, b=80),
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
                            
                            top_display_cols = ['Item_Code', 'Item_Name', 'Product_Group', 'Total_Stock', 'Forecast', 'Short_Excess', 'Status']
                            top_display = top_items[[c for c in top_display_cols if c in top_items.columns]].copy()
                            
                            for col in ['Total_Stock', 'Forecast', 'Short_Excess']:
                                if col in top_display.columns:
                                    top_display[col] = top_display[col].apply(lambda x: f'{prefix_display}{x:,.0f}' if prefix_display else f'{x:,.0f}')
                            
                            col_rename = {
                                'Item_Code': 'Item Code',
                                'Item_Name': 'Item Name',
                                'Product_Group': 'Product Group',
                                'Total_Stock': 'Current Stock (Qty)',
                                'Forecast': f'Forecast {label_suffix_display}',
                                'Short_Excess': 'Short/Excess',
                                'Status': 'Status'
                            }
                            top_display = top_display.rename(columns={k: v for k, v in col_rename.items() if k in top_display.columns})
                            
                            st.markdown("""
                            <div class="table-container">
                                <div class="table-header">
                                    <span>🏆 Top Items</span>
                                    <span class="badge">Data based</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.dataframe(top_display, use_container_width=True, height=250, hide_index=True)
                            
                            csv_top = top_items[['Item_Code', 'Item_Name', 'Total_Stock', 'Forecast', 'Short_Excess', 'Status']].to_csv(index=False)
                            st.download_button("📥 Download Top Items", csv_top, f"top_{top_n}_items.csv", "text/csv", use_container_width=True)
                    else:
                        st.info("No item-level data available for top items analysis.")

                    # ---- SECTION 11: CURRENT STOCK BY BRANCH ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>🏢</i> Current Stock by Branch</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    branch_stock_query = """
                        SELECT 
                            s.Branch_Location AS Branch,
                            s.File_Location AS Location,
                            SUM(s.Stock_Qty) AS Current_Stock
                        FROM stock_unpivoted s
                        WHERE s.Month_End_Date = (SELECT MAX(Month_End_Date) FROM stock_unpivoted)
                    """
                    branch_stock_params = []

                    if item_code != "All":
                        branch_stock_query += " AND UPPER(s.Item_Number) = UPPER(?)"
                        branch_stock_params.append(item_code)
                    elif item_name != "All":
                        branch_stock_query += " AND UPPER(s.Item_Name) = UPPER(?)"
                        branch_stock_params.append(item_name)

                    if branch != "All":
                        branch_stock_query += " AND LOWER(s.Branch_Location) = LOWER(?)"
                        branch_stock_params.append(branch)

                    if location != "All":
                        if location.lower() == "kinshasa":
                            branch_stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Kinshasa')
                            )"""
                        elif location.lower() == "goma":
                            branch_stock_query += """ AND LOWER(s.Branch_Location) IN (
                                SELECT LOWER(Branch) FROM location_master WHERE LOWER(Location) = LOWER('Goma')
                            )"""
                        elif location.lower() == "lubumbashi":
                            branch_stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            branch_stock_params.append(location)
                        else:
                            branch_stock_query += " AND LOWER(s.File_Location) = LOWER(?)"
                            branch_stock_params.append(location)

                    if product_group != "All" or division != "All":
                        branch_stock_query += " AND s.Item_Number IN (SELECT Item_Code FROM item_master WHERE 1=1"
                        if product_group != "All":
                            branch_stock_query += " AND LOWER(Product_Group) = LOWER(?)"
                            branch_stock_params.append(product_group)
                        if division != "All":
                            branch_stock_query += " AND LOWER(Division) = LOWER(?)"
                            branch_stock_params.append(division)
                        branch_stock_query += ")"

                    if supplier != "All":
                        branch_stock_query += """ AND UPPER(s.Item_Number) IN (
                            SELECT UPPER(Item_Code) FROM supplier_product_mapping 
                            WHERE UPPER(Supplier) = UPPER(?)
                        )"""
                        branch_stock_params.append(supplier)

                    branch_stock_query += " GROUP BY s.Branch_Location, s.File_Location ORDER BY Current_Stock DESC"
                    
                    try:
                        conn = get_connection()
                        branch_stock_df = conn.execute(branch_stock_query, branch_stock_params).df()
                    except Exception as e:
                        st.warning(f"Error loading branch stock data: {e}")
                        branch_stock_df = pd.DataFrame()
                    
                    if not branch_stock_df.empty:
                        display_stock = branch_stock_df.copy()
                        display_stock['Current_Stock'] = display_stock['Current_Stock'].apply(lambda x: f'{x:,.0f}')
                        total_stock = branch_stock_df['Current_Stock'].sum()
                        st.markdown(f"""
                        <div style="background: rgba(0, 102, 204, 0.08); border-radius: 8px; padding: 8px 12px; margin-bottom: 10px; border-left: 3px solid #0066CC; animation: slideInLeft 0.6s ease-out;">
                            <span style="color: #8899bb; font-size: 0.85rem;">
                                📊 Total Stock: <strong style="color: #e8edf5;">{total_stock:,.0f}</strong> 
                                across <strong style="color: #e8edf5;">{len(branch_stock_df)}</strong> location(s)
                                <span style="color: #667799; font-size:0.7rem;"> (as of {latest_stock_date_str})</span>
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown("""
                        <div class="table-container">
                            <div class="table-header">
                                <span>🏢 Stock by Location</span>
                                <span class="badge">Qty based</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.dataframe(display_stock, use_container_width=True, hide_index=True)
                        csv_stock = branch_stock_df.to_csv(index=False)
                        st.download_button("📥 Download Stock by Branch", csv_stock, "stock_by_branch.csv", "text/csv")
                    else:
                        st.info("No stock data available for the selected filters.")

                    # ---- SECTION 12: AVERAGE CALCULATION COMPARISON TABLE ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>📊</i> Average Calculation Comparison & Validation</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.caption("Compare all average calculation methods with detailed metrics to validate forecast accuracy")
                    
                    if len(historical) >= 3:
                        all_clean_data = clean_data[forecast_col].values
                        hist_data = historical[forecast_col].values
                        
                        simple_avg_val = clean_data[forecast_col].mean()
                        avg_3_val = historical[forecast_col].tail(3).mean() if len(historical) >= 3 else None
                        avg_6_val = historical[forecast_col].tail(6).mean() if len(historical) >= 6 else None
                        avg_12_val = historical[forecast_col].tail(12).mean() if len(historical) >= 12 else None
                        
                        weights = np.arange(1, len(hist_data) + 1)
                        weighted_avg = np.average(hist_data, weights=weights) if len(hist_data) > 0 else 0
                        median_avg = np.median(hist_data) if len(hist_data) > 0 else 0
                        
                        if len(historical) >= 3:
                            x_vals = np.arange(len(historical))
                            y_vals = historical[forecast_col].values
                            slope_val, intercept_val = np.polyfit(x_vals, y_vals, 1)
                            trend_val = slope_val * len(historical) + intercept_val
                            y_pred = slope_val * x_vals + intercept_val
                            ss_res = np.sum((y_vals - y_pred) ** 2)
                            ss_tot = np.sum((y_vals - np.mean(y_vals)) ** 2)
                            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                        else:
                            slope_val = 0
                            intercept_val = 0
                            trend_val = simple_avg_val
                            r_squared = 0
                        
                        alpha_03 = 0.3
                        smoothed_03 = [hist_data[0]]
                        for val in hist_data[1:]:
                            smoothed_03.append(alpha_03 * val + (1 - alpha_03) * smoothed_03[-1])
                        exp_smooth_03 = smoothed_03[-1]
                        
                        alpha_05 = 0.5
                        smoothed_05 = [hist_data[0]]
                        for val in hist_data[1:]:
                            smoothed_05.append(alpha_05 * val + (1 - alpha_05) * smoothed_05[-1])
                        exp_smooth_05 = smoothed_05[-1]
                        
                        alpha_07 = 0.7
                        smoothed_07 = [hist_data[0]]
                        for val in hist_data[1:]:
                            smoothed_07.append(alpha_07 * val + (1 - alpha_07) * smoothed_07[-1])
                        exp_smooth_07 = smoothed_07[-1]
                        
                        if len(hist_data) >= 3:
                            level = hist_data[0]
                            trend = (hist_data[1] - hist_data[0]) if len(hist_data) > 1 else 0
                            alpha_l = 0.3
                            alpha_t = 0.1
                            for val in hist_data[1:]:
                                prev_level = level
                                level = alpha_l * val + (1 - alpha_l) * (level + trend)
                                trend = alpha_t * (level - prev_level) + (1 - alpha_t) * trend
                            holt_winters = level + trend
                        else:
                            holt_winters = simple_avg_val
                        
                        actual_last = hist_data[-1] if len(hist_data) > 0 else 0
                        
                        comparison_data = []
                        
                        methods = [
                            ("Simple Average (All Time)", simple_avg_val, "All clean data", "Basic average of all valid months"),
                            ("12-Month Moving Average", avg_12_val, "Last 12 months" if avg_12_val is not None else "N/A", "Rolling average of last 12 months" if avg_12_val is not None else "Not enough data"),
                            ("6-Month Moving Average", avg_6_val, "Last 6 months" if avg_6_val is not None else "N/A", "Rolling average of last 6 months" if avg_6_val is not None else "Not enough data"),
                            ("3-Month Moving Average", avg_3_val, "Last 3 months" if avg_3_val is not None else "N/A", "Rolling average of last 3 months" if avg_3_val is not None else "Not enough data"),
                            ("Weighted Average", weighted_avg, "Weighted by recency", "More weight to recent months"),
                            ("Median Average", median_avg, "Robust to outliers", "Middle value of all data points"),
                            ("Linear Trend", trend_val, f"Slope: {slope_val:,.2f}", f"Trend projection, R²: {r_squared:.3f}"),
                            ("Exponential Smoothing (α=0.3)", exp_smooth_03, "α=0.3", "Smooths with 30% weight on recent"),
                            ("Exponential Smoothing (α=0.5)", exp_smooth_05, "α=0.5", "Smooths with 50% weight on recent"),
                            ("Exponential Smoothing (α=0.7)", exp_smooth_07, "α=0.7", "Smooths with 70% weight on recent"),
                            ("Holt-Winters Trend", holt_winters, "With trend component", "Level + trend smoothing"),
                        ]
                        
                        for name, value, param, description in methods:
                            if value is not None and value > 0:
                                if actual_last > 0:
                                    error_pct = abs(value - actual_last) / actual_last * 100
                                    if error_pct < 5:
                                        accuracy = "✅ Excellent"
                                    elif error_pct < 10:
                                        accuracy = "✅ Good"
                                    elif error_pct < 20:
                                        accuracy = "⚠️ Moderate"
                                    elif error_pct < 35:
                                        accuracy = "⚠️ Fair"
                                    else:
                                        accuracy = "❌ Poor"
                                    
                                    bias = "Over" if value > actual_last else "Under" if value < actual_last else "Exact"
                                    
                                    comparison_data.append({
                                        "Method": name,
                                        "Parameter": param,
                                        f"Avg {label_suffix_display}": f"{prefix_display}{value:,.0f}",
                                        "Actual Last": f"{prefix_display}{actual_last:,.0f}",
                                        "Difference": f"{prefix_display}{(value - actual_last):,.0f}",
                                        "Error %": f"{error_pct:.1f}%",
                                        "Bias": bias,
                                        "Accuracy": accuracy,
                                        "Description": description
                                    })
                                else:
                                    comparison_data.append({
                                        "Method": name,
                                        "Parameter": param,
                                        f"Avg {label_suffix_display}": f"{prefix_display}{value:,.0f}",
                                        "Actual Last": "N/A",
                                        "Difference": "N/A",
                                        "Error %": "N/A",
                                        "Bias": "N/A",
                                        "Accuracy": "—",
                                        "Description": description
                                    })
                        
                        comparison_df = pd.DataFrame(comparison_data)
                        
                        st.markdown("#### 📊 Summary Statistics")
                        col1, col2, col3, col4, col5 = st.columns(5)
                        
                        with col1:
                            st.metric("Total Months", f"{len(historical)}")
                        with col2:
                            st.metric("Clean Months", f"{len(clean_data)}", delta=f"Filtered {len(monthly_demand) - len(clean_data)}")
                        with col3:
                            if 'Error %' in comparison_df.columns:
                                errors = comparison_df['Error %'].str.replace('%', '').astype(float)
                                best_idx = errors.idxmin()
                                best_method = comparison_df.iloc[best_idx]['Method']
                                st.metric("Best Method", best_method)
                            else:
                                st.metric("Best Method", "N/A")
                        with col4:
                            if 'Error %' in comparison_df.columns:
                                errors = comparison_df['Error %'].str.replace('%', '').astype(float)
                                st.metric("Avg Error", f"{errors.mean():.1f}%")
                            else:
                                st.metric("Avg Error", "N/A")
                        with col5:
                            if 'Error %' in comparison_df.columns:
                                errors = comparison_df['Error %'].str.replace('%', '').astype(float)
                                st.metric("Error Range", f"{errors.min():.1f}% - {errors.max():.1f}%")
                            else:
                                st.metric("Error Range", "N/A")
                        
                        st.markdown("#### 📋 Complete Average Method Comparison")
                        
                        st.markdown(f"""
                        <div class="table-container">
                            <div class="table-header">
                                <span>📊 All Average Methods</span>
                                <span class="badge">Actual Last Month: {prefix_display}{actual_last:,.0f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        def color_accuracy(val):
                            if "Excellent" in val or "Good" in val:
                                return 'color: #22c55e; font-weight: bold;'
                            elif "Moderate" in val or "Fair" in val:
                                return 'color: #f59e0b; font-weight: bold;'
                            elif "Poor" in val:
                                return 'color: #ef4444; font-weight: bold;'
                            return ''
                        
                        def color_bias(val):
                            if "Over" in str(val):
                                return 'color: #ef4444;'
                            elif "Under" in str(val):
                                return 'color: #3b82f6;'
                            elif "Exact" in str(val):
                                return 'color: #22c55e; font-weight: bold;'
                            return ''
                        
                        styled_df = comparison_df.style.applymap(color_accuracy, subset=['Accuracy'])
                        styled_df = styled_df.applymap(color_bias, subset=['Bias'])
                        st.dataframe(styled_df, use_container_width=True, height=400, hide_index=True)
                        
                        st.markdown("#### 💡 Best Method Recommendation")
                        
                        if 'Error %' in comparison_df.columns:
                            errors_series = comparison_df['Error %'].str.replace('%', '').astype(float)
                            best_idx = errors_series.idxmin()
                            best_row = comparison_df.iloc[best_idx]
                            worst_idx = errors_series.idxmax()
                            worst_row = comparison_df.iloc[worst_idx]
                            
                            current_row = None
                            for idx, row in comparison_df.iterrows():
                                if forecast_model in row['Method']:
                                    current_row = row
                                    break
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 16px 20px; border: 1px solid #22c55e44; text-align: center;">
                                    <div style="font-size: 0.7rem; color: #8899bb;">🏆 BEST METHOD</div>
                                    <div style="font-size: 1.2rem; font-weight: 700; color: #22c55e;">{best_row['Method']}</div>
                                    <div style="font-size: 0.85rem; color: #e8edf5;">Error: {best_row['Error %']}</div>
                                    <div style="font-size: 0.7rem; color: #8899bb;">{best_row['Description']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with col2:
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 16px 20px; border: 1px solid #ef444444; text-align: center;">
                                    <div style="font-size: 0.7rem; color: #8899bb;">⚠️ WORST METHOD</div>
                                    <div style="font-size: 1.2rem; font-weight: 700; color: #ef4444;">{worst_row['Method']}</div>
                                    <div style="font-size: 0.85rem; color: #e8edf5;">Error: {worst_row['Error %']}</div>
                                    <div style="font-size: 0.7rem; color: #8899bb;">{worst_row['Description']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            with col3:
                                if current_row is not None:
                                    st.markdown(f"""
                                    <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 16px 20px; border: 1px solid #f59e0b44; text-align: center;">
                                        <div style="font-size: 0.7rem; color: #8899bb;">🎯 CURRENT METHOD</div>
                                        <div style="font-size: 1.2rem; font-weight: 700; color: #f59e0b;">{current_row['Method']}</div>
                                        <div style="font-size: 0.85rem; color: #e8edf5;">Error: {current_row['Error %']}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        st.markdown("#### ✅ Validation Indicators")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            total_months = len(monthly_demand)
                            clean_months = len(clean_data)
                            quality_score = (clean_months / total_months * 100) if total_months > 0 else 0
                            quality_color = "#22c55e" if quality_score >= 80 else "#f59e0b" if quality_score >= 50 else "#ef4444"
                            st.markdown(f"""
                            <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 14px 16px; border: 1px solid #2a3450; text-align: center;">
                                <div style="font-size: 0.65rem; color: #8899bb;">📊 Data Quality</div>
                                <div style="font-size: 1.4rem; font-weight: 700; color: {quality_color};">{quality_score:.0f}%</div>
                                <div style="font-size: 0.6rem; color: #8899bb;">{clean_months}/{total_months} valid</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            if 'Error %' in comparison_df.columns:
                                errors = comparison_df['Error %'].str.replace('%', '').astype(float)
                                avg_error = errors.mean()
                                confidence = max(0, 100 - avg_error)
                                confidence_color = "#22c55e" if confidence >= 70 else "#f59e0b" if confidence >= 50 else "#ef4444"
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 14px 16px; border: 1px solid #2a3450; text-align: center;">
                                    <div style="font-size: 0.65rem; color: #8899bb;">🎯 Forecast Confidence</div>
                                    <div style="font-size: 1.4rem; font-weight: 700; color: {confidence_color};">{confidence:.0f}%</div>
                                    <div style="font-size: 0.6rem; color: #8899bb;">Avg error: {avg_error:.1f}%</div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        with col3:
                            if len(historical) >= 3 and slope_val != 0:
                                trend_strength = min(abs(slope_val) / (abs(slope_val) + abs(actual_last / len(historical))), 1) * 100
                                trend_color = "#22c55e" if trend_strength >= 30 else "#f59e0b" if trend_strength >= 15 else "#8899bb"
                                trend_direction = "📈 Up" if slope_val > 0 else "📉 Down" if slope_val < 0 else "➡️ Flat"
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 14px 16px; border: 1px solid #2a3450; text-align: center;">
                                    <div style="font-size: 0.65rem; color: #8899bb;">📈 Trend Strength</div>
                                    <div style="font-size: 1.4rem; font-weight: 700; color: {trend_color};">{trend_strength:.0f}%</div>
                                    <div style="font-size: 0.6rem; color: #8899bb;">{trend_direction}</div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        with col4:
                            if r_squared > 0:
                                r2_color = "#22c55e" if r_squared >= 0.7 else "#f59e0b" if r_squared >= 0.4 else "#ef4444"
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 14px 16px; border: 1px solid #2a3450; text-align: center;">
                                    <div style="font-size: 0.65rem; color: #8899bb;">📊 Fit Quality (R²)</div>
                                    <div style="font-size: 1.4rem; font-weight: 700; color: {r2_color};">{r_squared:.3f}</div>
                                    <div style="font-size: 0.6rem; color: #8899bb;">{"Good" if r_squared >= 0.7 else "Moderate" if r_squared >= 0.4 else "Poor"} fit</div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("#### 📈 Visual Comparison")
                        
                        fig_compare = go.Figure()
                        
                        fig_compare.add_trace(go.Bar(
                            x=historical['Month_Label'],
                            y=historical[forecast_col],
                            name=f'Actual {label_suffix_display}',
                            marker=dict(color=st.session_state.accent_color, opacity=0.7),
                            text=historical[forecast_col].apply(lambda x: f'{prefix_display}{x:,.0f}'),
                            textposition='inside',
                            textfont=dict(size=9, color='white')
                        ))
                        
                        avg_methods = [
                            ("Simple Avg", simple_avg_val, "#22c55e", "solid"),
                            ("3-Month MA", avg_3_val, "#f59e0b", "dash") if avg_3_val is not None else None,
                            ("6-Month MA", avg_6_val, "#3b82f6", "dot") if avg_6_val is not None else None,
                            ("Linear Trend", trend_val, "#ef4444", "dashdot") if trend_val is not None else None,
                        ]
                        
                        for name, value, color, dash in avg_methods:
                            if value is not None and value > 0:
                                fig_compare.add_trace(go.Scatter(
                                    x=historical['Month_Label'],
                                    y=[value] * len(historical),
                                    name=f'{name} ({prefix_display}{value:,.0f})',
                                    line=dict(color=color, width=2, dash=dash),
                                    mode='lines'
                                ))
                        
                        future_months_compare = [(pd.to_datetime(historical['Month_Label'].iloc[-1] + '-01') + pd.DateOffset(months=i)).strftime('%Y-%m') 
                                                for i in range(1, forecast_horizon + 1)]
                        fig_compare.add_trace(go.Scatter(
                            x=future_months_compare,
                            y=forecast_vals,
                            name=f'Forecast ({forecast_model})',
                            line=dict(color='#22c55e', width=3, dash='dash'),
                            mode='lines+markers',
                            marker=dict(size=10, color='#22c55e'),
                            text=[f'{prefix_display}{v:,.0f}' for v in forecast_vals],
                            textposition='top center',
                            textfont=dict(size=10, color='#22c55e')
                        ))
                        
                        if len(historical) > 0:
                            fig_compare.add_vline(x=historical['Month_Label'].iloc[-1], line_dash="dash", line_color="rgba(255,255,255,0.3)", line_width=1)
                        
                        fig_compare.update_layout(
                            title=f'Average Method Comparison - {label_suffix_display}',
                            height=450,
                            template='plotly_dark',
                            xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
                            yaxis=dict(title=f'{label_suffix_display} ({prefix_display})', tickformat=',.0f'),
                            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=10)),
                            margin=dict(l=20, r=20, t=50, b=60),
                            hovermode='x unified',
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            bargap=0.1
                        )
                        st.plotly_chart(fig_compare, use_container_width=True, config={'displayModeBar': False})
                        
                        st.markdown("#### 📥 Export Data")
                        col1, col2 = st.columns(2)
                        with col1:
                            csv_compare = comparison_df.to_csv(index=False)
                            st.download_button("📥 Download Comparison Table", csv_compare, "average_comparison_table.csv", "text/csv", use_container_width=True)
                        with col2:
                            monthly_with_avg = historical[['Month_Label', forecast_col]].copy()
                            monthly_with_avg.columns = ['Month', f'Actual_{label_suffix_display}']
                            monthly_with_avg['Simple_Avg'] = simple_avg_val
                            monthly_with_avg['3_Month_MA'] = avg_3_val if avg_3_val is not None else 0
                            monthly_with_avg['6_Month_MA'] = avg_6_val if avg_6_val is not None else 0
                            monthly_with_avg['12_Month_MA'] = avg_12_val if avg_12_val is not None else 0
                            monthly_with_avg['Linear_Trend'] = trend_val if trend_val is not None else 0
                            monthly_with_avg['Forecast'] = forecast_vals[0] if len(forecast_vals) > 0 else 0
                            csv_monthly_avg = monthly_with_avg.to_csv(index=False)
                            st.download_button("📥 Download Monthly Data with Averages", csv_monthly_avg, "monthly_data_with_averages.csv", "text/csv", use_container_width=True)
                        
                    else:
                        st.warning("⚠️ Not enough data points (need at least 3 months) for average comparison.")
                        if len(historical) > 0:
                            st.dataframe(historical[['Month_Label', forecast_col]].tail(12), use_container_width=True, hide_index=True)

                    # ---- SECTION 13: AVERAGE CALCULATION DETAILS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>🔍</i> Average Calculation Details - Drill Down</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.caption("See exactly how each average is calculated with month-by-month breakdown for the selected item")
                    
                    if item_code != "All" or item_name != "All":
                        item_filter_conditions = []
                        item_filter_params = []
                        
                        if item_code != "All":
                            item_filter_conditions.append("Item_Code = ?")
                            item_filter_params.append(item_code)
                        if item_name != "All":
                            item_filter_conditions.append("Item_Name = ?")
                            item_filter_params.append(item_name)
                        
                        item_where = " AND ".join(item_filter_conditions) if item_filter_conditions else "1=1"
                        
                        item_query = f"""
                            SELECT 
                                Month_Label,
                                Year,
                                Month_Num,
                                Sales_Amount,
                                Qty_Sold,
                                Net_Amount,
                                Net_Qty,
                                Qty_Returned,
                                Return_Amount
                            FROM item_monthly_summary
                            WHERE {item_where}
                            ORDER BY Year, Month_Num
                        """
                        
                        try:
                            conn = get_connection()
                            item_detail_data = conn.execute(item_query, item_filter_params).df()
                            
                            if not item_detail_data.empty:
                                if use_qty:
                                    value_col_display = 'Net_Qty'
                                    label_display = "Qty"
                                    prefix_display = ""
                                else:
                                    value_col_display = 'Net_Amount'
                                    label_display = "Value"
                                    prefix_display = "$"
                                
                                values = item_detail_data[value_col_display].values
                                months = item_detail_data['Month_Label'].tolist()
                                
                                clean_indices = [i for i, v in enumerate(values) if v > 0]
                                clean_values = [values[i] for i in clean_indices]
                                clean_months = [months[i] for i in clean_indices]
                                
                                item_display_name = item_code if item_code != 'All' else ''
                                if item_name != 'All':
                                    item_display_name = item_name if not item_display_name else f"{item_display_name} - {item_name}"
                                
                                st.markdown(f"""
                                <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 16px 20px; border: 1px solid #2a3450; margin-bottom: 16px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                                        <div>
                                            <span style="color: #8899bb; font-size: 0.7rem;">📦 SELECTED ITEM</span>
                                            <div style="font-size: 1.2rem; font-weight: 600; color: #e8edf5;">{item_display_name}</div>
                                        </div>
                                        <div style="text-align: right;">
                                            <span style="color: #8899bb; font-size: 0.7rem;">Total Months</span>
                                            <div style="font-size: 1.1rem; font-weight: 600; color: #f59e0b;">{len(item_detail_data)}</div>
                                        </div>
                                        <div style="text-align: right;">
                                            <span style="color: #8899bb; font-size: 0.7rem;">Clean Months</span>
                                            <div style="font-size: 1.1rem; font-weight: 600; color: #22c55e;">{len(clean_values)}</div>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.markdown("#### 📋 Raw Monthly Data")
                                display_data = item_detail_data.copy()
                                for col in ['Sales_Amount', 'Net_Amount', 'Return_Amount']:
                                    if col in display_data.columns:
                                        display_data[col] = display_data[col].apply(lambda x: f'${x:,.2f}' if x != 0 else '-')
                                for col in ['Qty_Sold', 'Net_Qty', 'Qty_Returned']:
                                    if col in display_data.columns:
                                        display_data[col] = display_data[col].apply(lambda x: f'{x:,.0f}' if x != 0 else '-')
                                st.dataframe(display_data, use_container_width=True, height=250, hide_index=True)
                                
                                if len(clean_values) >= 3:
                                    def format_data_points(vals, max_show=5):
                                        if len(vals) <= max_show:
                                            return ', '.join([f'{v:,.0f}' for v in vals])
                                        else:
                                            return f"{', '.join([f'{v:,.0f}' for v in vals[:3]])}, ... , {vals[-1]:,.0f}"
                                    
                                    item_simple = np.mean(clean_values)
                                    item_weights = np.arange(1, len(clean_values) + 1)
                                    item_weighted = np.average(clean_values, weights=item_weights)
                                    item_median = np.median(clean_values)
                                    item_avg3 = np.mean(clean_values[-3:]) if len(clean_values) >= 3 else item_simple
                                    item_avg6 = np.mean(clean_values[-6:]) if len(clean_values) >= 6 else item_simple
                                    item_avg12 = np.mean(clean_values[-12:]) if len(clean_values) >= 12 else item_simple
                                    
                                    if len(clean_values) >= 3:
                                        x_vals_item = np.arange(len(clean_values))
                                        y_vals_item = clean_values
                                        item_slope, item_intercept = np.polyfit(x_vals_item, y_vals_item, 1)
                                        item_trend = item_slope * len(clean_values) + item_intercept
                                    else:
                                        item_slope = 0
                                        item_trend = item_simple
                                    
                                    item_alpha = 0.3
                                    item_smoothed = [clean_values[0]]
                                    for val in clean_values[1:]:
                                        item_smoothed.append(item_alpha * val + (1 - item_alpha) * item_smoothed[-1])
                                    item_exp = item_smoothed[-1]
                                    
                                    if len(clean_values) >= 3:
                                        item_level = clean_values[0]
                                        item_trend_comp = (clean_values[1] - clean_values[0]) if len(clean_values) > 1 else 0
                                        alpha_l = 0.3
                                        alpha_t = 0.1
                                        for i in range(1, len(clean_values)):
                                            prev_level = item_level
                                            item_level = alpha_l * clean_values[i] + (1 - alpha_l) * (item_level + item_trend_comp)
                                            item_trend_comp = alpha_t * (item_level - prev_level) + (1 - alpha_t) * item_trend_comp
                                        item_holt = item_level + item_trend_comp
                                    else:
                                        item_holt = item_simple
                                    
                                    item_calc_data = []
                                    item_calc_data.append({"Method": "1️⃣ Simple Average", f"Result ({label_display})": f"{prefix_display}{item_simple:,.0f}", "Formula": f"Sum / {len(clean_values)}", "Detail": f"All {len(clean_values)} months", "Data Points": format_data_points(clean_values)})
                                    item_calc_data.append({"Method": "2️⃣ Weighted Average", f"Result ({label_display})": f"{prefix_display}{item_weighted:,.0f}", "Formula": "Σ(value×weight)/Σ(weights)", "Detail": "More weight to recent", "Data Points": "Weighted by recency"})
                                    item_calc_data.append({"Method": "3️⃣ Median", f"Result ({label_display})": f"{prefix_display}{item_median:,.0f}", "Formula": "Middle value", "Detail": "Robust to outliers", "Data Points": "Sorted middle value"})
                                    item_calc_data.append({"Method": "4️⃣ 3-Month MA", f"Result ({label_display})": f"{prefix_display}{item_avg3:,.0f}", "Formula": "Last 3 / 3", "Detail": f"Months: {', '.join(clean_months[-3:]) if len(clean_months)>=3 else 'N/A'}", "Data Points": format_data_points(clean_values[-3:]) if len(clean_values)>=3 else "N/A"})
                                    item_calc_data.append({"Method": "5️⃣ 6-Month MA", f"Result ({label_display})": f"{prefix_display}{item_avg6:,.0f}", "Formula": "Last 6 / 6", "Detail": f"Months: {', '.join(clean_months[-6:]) if len(clean_months)>=6 else 'N/A'}", "Data Points": format_data_points(clean_values[-6:]) if len(clean_values)>=6 else "N/A"})
                                    item_calc_data.append({"Method": "6️⃣ 12-Month MA", f"Result ({label_display})": f"{prefix_display}{item_avg12:,.0f}", "Formula": "Last 12 / 12", "Detail": f"Months: {', '.join(clean_months[-12:]) if len(clean_months)>=12 else 'N/A'}", "Data Points": format_data_points(clean_values[-12:]) if len(clean_values)>=12 else "N/A"})
                                    item_calc_data.append({"Method": "7️⃣ Linear Trend", f"Result ({label_display})": f"{prefix_display}{item_trend:,.0f}", "Formula": f"y={item_slope:.2f}x+{item_intercept:.2f}", "Detail": f"Slope: {item_slope:.2f}/month", "Data Points": "Projected from trend"})
                                    item_calc_data.append({"Method": "8️⃣ Exp Smoothing", f"Result ({label_display})": f"{prefix_display}{item_exp:,.0f}", "Formula": "α×current+(1-α)×prev", "Detail": "α=0.3", "Data Points": "Weighted with α=0.3"})
                                    item_calc_data.append({"Method": "9️⃣ Holt-Winters", f"Result ({label_display})": f"{prefix_display}{item_holt:,.0f}", "Formula": "Level + Trend", "Detail": f"Level: {item_level:.0f}, Trend: {item_trend_comp:.2f}" if len(clean_values)>=3 else "N/A", "Data Points": "Double exponential"})
                                    
                                    st.markdown("#### 🧮 How Each Average is Calculated for This Item")
                                    st.dataframe(pd.DataFrame(item_calc_data), use_container_width=True, height=400, hide_index=True)
                                    
                                    csv_item = pd.DataFrame(item_calc_data).to_csv(index=False)
                                    st.download_button("📥 Download Item Drill-Down", csv_item, "item_drilldown.csv", "text/csv", use_container_width=True)
                                    
                                    st.markdown("#### 📊 Visual Comparison for This Item")
                                    fig_item = go.Figure()
                                    fig_item.add_trace(go.Bar(x=clean_months, y=clean_values, name=f'Actual {label_display}', marker=dict(color=st.session_state.accent_color, opacity=0.6), text=[f'{prefix_display}{v:,.0f}' for v in clean_values], textposition='outside', textfont=dict(size=9)))
                                    
                                    item_methods = [
                                        ("Simple Avg", item_simple, "#22c55e", "solid"),
                                        ("Weighted Avg", item_weighted, "#3b82f6", "dash"),
                                        ("Median", item_median, "#8b5cf6", "dot"),
                                        ("3-Month MA", item_avg3, "#f59e0b", "dash"),
                                        ("6-Month MA", item_avg6, "#ec4899", "dot"),
                                        ("12-Month MA", item_avg12, "#14b8a6", "dashdot"),
                                        ("Linear Trend", item_trend, "#ef4444", "dash"),
                                        ("Exp Smooth", item_exp, "#f97316", "solid"),
                                        ("Holt-Winters", item_holt, "#a855f7", "dashdot"),
                                    ]
                                    
                                    for name, value, color, dash in item_methods:
                                        if value > 0:
                                            fig_item.add_trace(go.Scatter(x=clean_months, y=[value] * len(clean_months), name=f'{name}: {prefix_display}{value:,.0f}', line=dict(color=color, width=2, dash=dash), mode='lines'))
                                    
                                    fig_item.update_layout(title=f'All 9 Methods for Selected Item', height=400, template='plotly_dark', xaxis=dict(tickangle=-45), yaxis=dict(title=f'{label_display} ({prefix_display})', tickformat=',.0f'), legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=9)), margin=dict(l=20, r=20, t=50, b=60), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', bargap=0.1)
                                    st.plotly_chart(fig_item, use_container_width=True, config={'displayModeBar': False})
                                    
                                else:
                                    st.warning("Need at least 3 clean months for this item")
                            else:
                                st.info("No data for selected item")
                        except Exception as e:
                            st.warning(f"Error: {e}")
                    else:
                        st.info("🔍 Select a specific **Item Code** or **Item Name** from sidebar to see detailed breakdown")
                        st.markdown("""
                        <div style="background: linear-gradient(145deg, #0d1528, #1a2236); border-radius: 12px; padding: 20px 24px; border: 1px solid #2a3450; margin-top: 12px;">
                            <div style="display: flex; align-items: center; gap: 16px;">
                                <span style="font-size: 2rem;">📋</span>
                                <div>
                                    <div style="font-weight: 600; color: #e8edf5; font-size: 1rem;">How to see calculation details:</div>
                                    <div style="color: #8899bb; font-size: 0.9rem; margin-top: 4px;">
                                        1. Go to the sidebar filters<br>
                                        2. Select a specific <strong style="color: #f59e0b;">Item Code</strong> or <strong style="color: #f59e0b;">Item Name</strong><br>
                                        3. The detailed breakdown will appear here
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)


                     # ---- SECTION 14: PURCHASE ORDER SHIPMENT STATUS & PIPELINE ----


                    # ---- Load PO Data ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_summary_by_item(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """
                        Aggregate purchase order quantities by item with status breakdown.
                        Filters directly on PRF_Location.
                        """
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.Supplier_Name,
                                po.PRF_Location as Branch,
                                SUM(po.PO_Qty) as Total_PO_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Transit' THEN po.PO_Qty ELSE 0 END) as In_Transit_Qty,
                                SUM(CASE WHEN po.Shipment_Status = 'Goods Received at Warehouse' THEN po.PO_Qty ELSE 0 END) as Received_Qty,
                                SUM(CASE WHEN po.Shipment_Status NOT IN ('Transit', 'Goods Received at Warehouse', 'Closed') THEN po.PO_Qty ELSE 0 END) as Pending_Qty,
                                COUNT(DISTINCT po.PO_No) as PO_Count,
                                COUNT(DISTINCT po.PRF_No) as PRF_Count
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        # Apply filters
                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " GROUP BY po.Item_Code, po.\"Product_Name_(DRC)\", po.Supplier_Name, po.PRF_Location ORDER BY Total_PO_Qty DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO summary: {e}")
                            return pd.DataFrame()

                    # ---- Load Detailed PO Data for Status Tracking ----
                    @st.cache_data(ttl=300, show_spinner=False)
                    def load_po_details(year, month, period, branch, location, item_code, item_name, product_group, division, supplier="All"):
                        """Load detailed PO data with shipment status. Filters directly on PRF_Location."""
                        conn = get_connection()
                        query = """
                            SELECT 
                                po.PO_No,
                                po.PRF_No,
                                po.PO_Date,
                                po.PO_Qty,
                                po.PO_Total_Amount,
                                po.Supplier_Name,
                                po.Item_Code,
                                po."Product_Name_(DRC)" as Item_Name,
                                po.PI_No,
                                po.PI_Date,
                                po.Dispatched_Qty,
                                po.Invoice_Qty,
                                po.Shipment_Status,
                                po.GRN_Qty,
                                po.GRN_Date,
                                po.PO_Status,
                                po.PO_Age_Days,
                                po.PRF_Location as Branch,
                                po.BL_No,
                                po.BL_Date
                            FROM purchase_orders po
                            WHERE 1=1
                        """
                        params = []

                        if year != "All":
                            query += " AND EXTRACT(YEAR FROM po.PO_Date) = ?"
                            params.append(int(year))
                        if month != "All":
                            month_map = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                                         "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                            month_num = month_map.get(month)
                            if month_num:
                                query += " AND EXTRACT(MONTH FROM po.PO_Date) = ?"
                                params.append(month_num)
                        if period != "All":
                            quarter_map = {"Q1 (Jan-Mar)":1, "Q2 (Apr-Jun)":2, "Q3 (Jul-Sep)":3, "Q4 (Oct-Dec)":4}
                            q = quarter_map.get(period)
                            if q:
                                query += " AND EXTRACT(QUARTER FROM po.PO_Date) = ?"
                                params.append(q)

                        # Branch filter
                        if branch != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(branch)
                        
                        # LOCATION FILTER - Direct PRF_Location match
                        if location != "All":
                            query += " AND LOWER(po.PRF_Location) = LOWER(?)"
                            params.append(location)
                        
                        # Item filters
                        if item_code != "All":
                            query += " AND UPPER(po.Item_Code) = UPPER(?)"
                            params.append(item_code)
                        elif item_name != "All":
                            query += " AND UPPER(po.\"Product_Name_(DRC)\") = UPPER(?)"
                            params.append(item_name)
                        
                        # Product Group & Division filters
                        if product_group != "All" or division != "All":
                            query += " AND po.Item_Code IN (SELECT Item_Code FROM item_master WHERE 1=1"
                            if product_group != "All":
                                query += " AND LOWER(Product_Group) = LOWER(?)"
                                params.append(product_group)
                            if division != "All":
                                query += " AND LOWER(Division) = LOWER(?)"
                                params.append(division)
                            query += ")"
                        
                        # Supplier filter
                        if supplier != "All":
                            query += " AND UPPER(po.Supplier_Name) = UPPER(?)"
                            params.append(supplier)

                        query += " ORDER BY po.PO_Date DESC"

                        try:
                            df = conn.execute(query, params).df()
                            return df
                        except Exception as e:
                            st.error(f"Error loading PO details: {e}")
                            return pd.DataFrame()

                    # ---- Load the data ----
                    with st.spinner("Loading purchase order data..."):
                        po_summary_df = load_po_summary_by_item(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        po_details_df = load_po_details(
                            year, month, period, branch, location,
                            item_code, item_name, product_group, division, supplier
                        )
                        
                        
                    # ---- SECTION 1.5: SAFETY STOCK & LEAD TIME ANALYSIS ----
                    st.markdown("""
                    <div class="section-divider">
                        <span class="title"><i>🛡️</i> Safety Stock & Lead Time Analysis</span>
                        <span class="line"></span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Load safety stock data
                    with st.spinner("Loading safety stock data..."):
                        safety_stock_df = get_safety_stock_by_item(
                            branch, location, product_group, division, item_code, supplier
                        )
                        safety_stock_summary = get_safety_stock_summary()

                    if not safety_stock_df.empty:
                        # ---- Safety Stock KPIs ----
                        kpi_cols = st.columns(5)
                        
                        total_safety_stock_qty = safety_stock_df['Safety_Stock_Qty'].sum()
                        total_safety_stock_value = safety_stock_df['Safety_Stock_Value'].sum()
                        avg_lead_time = safety_stock_df['Lead_Time'].mean()
                        items_with_supplier = len(safety_stock_df[safety_stock_df['Primary_Supplier'].notna() & (safety_stock_df['Primary_Supplier'] != '')])
                        items_below_safety = len(safety_stock_df[safety_stock_df['Short_Excess'] < 0])
                        total_items = len(safety_stock_df)
                        
                        with kpi_cols[0]:
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid #8b5cf6;">
                                <div class="icon">🛡️</div>
                                <div class="label">Total Safety Stock</div>
                                <div class="value" style="color: #8b5cf6;">{total_safety_stock_qty:,.0f}</div>
                                <div class="sub">Value: ${total_safety_stock_value:,.2f}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with kpi_cols[1]:
                            pct_with_supplier = (items_with_supplier / total_items * 100) if total_items > 0 else 0
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid #22c55e;">
                                <div class="icon">🏢</div>
                                <div class="label">Suppliers Mapped</div>
                                <div class="value" style="color: #22c55e;">{items_with_supplier:,}</div>
                                <div class="sub">{pct_with_supplier:.1f}% of items</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with kpi_cols[2]:
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid #3b82f6;">
                                <div class="icon">⏳</div>
                                <div class="label">Avg Lead Time</div>
                                <div class="value" style="color: #3b82f6;">{avg_lead_time:.0f}</div>
                                <div class="sub">days from order to delivery</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with kpi_cols[3]:
                            pct_below = (items_below_safety / total_items * 100) if total_items > 0 else 0
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid #ef4444;">
                                <div class="icon">⚠️</div>
                                <div class="label">Below Safety Stock</div>
                                <div class="value" style="color: #ef4444;">{items_below_safety:,}</div>
                                <div class="sub">{pct_below:.1f}% of items</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with kpi_cols[4]:
                            avg_safety_per_item = total_safety_stock_qty / total_items if total_items > 0 else 0
                            st.markdown(f"""
                            <div class="forecast-kpi-card" style="border-top: 3px solid #f59e0b;">
                                <div class="icon">📦</div>
                                <div class="label">Avg Safety Stock</div>
                                <div class="value" style="color: #f59e0b;">{avg_safety_per_item:,.0f}</div>
                                <div class="sub">per item</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # ---- Lead Time Distribution Chart ----
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("#### 📊 Lead Time Distribution")
                            lead_dist = safety_stock_df['Lead_Time_Category'].value_counts().reset_index()
                            if len(lead_dist) > 0:
                                lead_dist.columns = ['Category', 'Count']
                                # Handle None values
                                lead_dist['Category'] = lead_dist['Category'].fillna('Unknown')
                                fig = px.pie(lead_dist, values='Count', names='Category', 
                                            title='Items by Lead Time Category',
                                            color_discrete_sequence=px.colors.qualitative.Set3,
                                            hole=0.4)
                                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20))
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No lead time distribution data available")
                        
                        with col2:
                            st.markdown("#### 📊 Demand Stability")
                            demand_dist = safety_stock_df['Demand_Category'].value_counts().reset_index()
                            if len(demand_dist) > 0:
                                demand_dist.columns = ['Category', 'Count']
                                demand_dist['Category'] = demand_dist['Category'].fillna('Unknown')
                                fig = px.pie(demand_dist, values='Count', names='Category',
                                            title='Items by Demand Stability',
                                            color_discrete_sequence=px.colors.qualitative.Pastel,
                                            hole=0.4)
                                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10, r=10, t=40, b=20))
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No demand stability data available")
                        
                        st.markdown("---")
                        
                        # ---- Safety Stock Summary Table ----
                        st.markdown("#### 📋 Safety Stock Summary by Category")
                        
                        if not safety_stock_summary.empty:
                            display_summary = safety_stock_summary.copy()
                            for col in ['Total_Safety_Stock_Qty', 'Total_Safety_Stock_Value', 'Avg_Safety_Stock_Qty', 'Avg_Safety_Stock_Value']:
                                if col in display_summary.columns:
                                    display_summary[col] = display_summary[col].apply(lambda x: f'{x:,.0f}' if pd.notna(x) else '-')
                            if 'Avg_Lead_Time' in display_summary.columns:
                                display_summary['Avg_Lead_Time'] = display_summary['Avg_Lead_Time'].apply(lambda x: f'{x:.0f} days' if pd.notna(x) else '-')
                            
                            st.dataframe(display_summary, use_container_width=True, hide_index=True)
                        else:
                            st.info("No safety stock summary available")
                        
                        st.markdown("---")
                        
                        # ---- Safety Stock by Item Table ----
                        st.markdown("#### 📋 Safety Stock by Item (Lead Time Based)")
                        
                        display_ss = safety_stock_df.copy()
                        
                        # Format columns
                        for col in ['Safety_Stock_Qty', 'Safety_Stock_Value', 'Reorder_Point_Qty', 
                                    'Reorder_Point_Value', 'Current_Stock', 'Short_Excess', 'Avg_Daily_Demand_Qty']:
                            if col in display_ss.columns:
                                display_ss[col] = display_ss[col].apply(lambda x: f'{x:,.0f}' if pd.notna(x) else '-')
                        if 'Avg_Daily_Demand_Value' in display_ss.columns:
                            display_ss['Avg_Daily_Demand_Value'] = display_ss['Avg_Daily_Demand_Value'].apply(lambda x: f'${x:,.2f}' if pd.notna(x) else '-')
                        
                        # Add status column based on Short/Excess
                        def get_stock_status(row):
                            try:
                                short_excess_str = str(row['Short_Excess']).replace(',', '')
                                if short_excess_str.replace('-', '').replace('.', '').isdigit():
                                    short_excess = float(short_excess_str)
                                else:
                                    short_excess = 0
                                if short_excess < 0:
                                    return '🔴 Below Safety Stock'
                                elif short_excess < 100:
                                    return '🟡 At Risk'
                                else:
                                    return '🟢 Healthy'
                            except:
                                return '⚪ Unknown'
                        
                        display_ss['Stock_Status'] = display_ss.apply(get_stock_status, axis=1)
                        
                        # Search
                        search_ss = st.text_input("🔍 Search Item or Supplier", key="safety_stock_search")
                        if search_ss and 'Item_Name' in display_ss.columns and 'Primary_Supplier' in display_ss.columns:
                            display_ss = display_ss[
                                display_ss['Item_Name'].str.contains(search_ss, case=False, na=False) |
                                display_ss['Primary_Supplier'].str.contains(search_ss, case=False, na=False)
                            ]
                        
                        # Select columns for display
                        display_cols = ['Item_Code', 'Item_Name', 'Product_Group', 'Primary_Supplier', 
                                       'Lead_Time', 'Lead_Time_Category', 'Demand_Category',
                                       'Avg_Daily_Demand_Qty', 'Safety_Stock_Qty', 'Current_Stock', 
                                       'Short_Excess', 'Reorder_Point_Qty', 'Stock_Status']
                        display_cols = [c for c in display_cols if c in display_ss.columns]
                        display_ss = display_ss[display_cols]
                        
                        # Rename columns for display
                        col_rename = {
                            'Item_Code': 'Item Code',
                            'Item_Name': 'Item Name',
                            'Product_Group': 'Product Group',
                            'Primary_Supplier': 'Primary Supplier',
                            'Lead_Time': 'Lead Time',
                            'Lead_Time_Category': 'Lead Time Category',
                            'Demand_Category': 'Demand Category',
                            'Avg_Daily_Demand_Qty': 'Daily Demand',
                            'Safety_Stock_Qty': '🛡️ Safety Stock',
                            'Current_Stock': 'Current Stock',
                            'Short_Excess': 'Short/Excess',
                            'Reorder_Point_Qty': '🔄 Reorder Point',
                            'Stock_Status': 'Status'
                        }
                        display_ss = display_ss.rename(columns={k: v for k, v in col_rename.items() if k in display_ss.columns})
                        
                        st.dataframe(
                            display_ss,
                            use_container_width=True,
                            height=400,
                            hide_index=True
                        )
                        
                        # Download button
                        csv_ss = safety_stock_df.to_csv(index=False)
                        st.download_button("📥 Download Safety Stock Data", csv_ss, "safety_stock_data.csv", "text/csv")
                        
                    else:
                        st.info("No safety stock data available. Please run Migration.py to import Supplier Master.")


 




    # ========================================================================
    # PAGE 7: PERFORMANCE RANKING - ENHANCED
    # ========================================================================
    elif st.session_state.page == "🏆 Performance Ranking":
        st.markdown("### 🏆 Performance Ranking")
        if not item_performance.empty:
            if view_type_label == "💰 Value": 
                value_col='Total_Sales'
            elif view_type_label == "📦 Quantity": 
                value_col='Total_Qty'
            else: 
                value_col='Total_Transactions'
            
            st.markdown("#### 📊 Top Products by Performance")
            top_products = item_performance[['Item_Code','Item_Name','Product_Group','Division',value_col]].copy()
            top_products = top_products.sort_values(value_col, ascending=False)
            top_products['Rank'] = range(1, len(top_products)+1)
            top_products['Performance'] = top_products[value_col].rank(pct=True)*100
            display_df = top_products.head(20).copy()
            if view_type_label == "💰 Value": 
                display_df[value_col] = display_df[value_col].apply(lambda x: f'${x:,.2f}')
            else: 
                display_df[value_col] = display_df[value_col].apply(lambda x: f'{x:,.0f}')
            display_df['Performance'] = display_df['Performance'].apply(lambda x: f'{x:.0f}%')
            st.dataframe(display_df[['Rank','Item_Code','Item_Name','Product_Group','Division',value_col,'Performance']], use_container_width=True, hide_index=True, column_config={"Rank":"🏆 Rank","Item_Code":"Item Code","Item_Name":"Item Name","Product_Group":"Product Group","Division":"Division",value_col:"Value","Performance":"Performance %"})
            
            top_20 = top_products.head(20)
            fig = px.bar(top_20, x='Item_Name', y=value_col, title='Top 20 Products by Performance', color=value_col, color_continuous_scale='Viridis', text_auto='.1s')
            fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=60), xaxis={'tickangle':-45 if len(top_20)>10 else 0}, showlegend=False)
            fig.update_traces(textposition='outside', textfont=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 📉 Bottom Products (Needs Improvement)")
            bottom_products = top_products.tail(20).sort_values(value_col, ascending=True)
            if view_type_label == "💰 Value": 
                bottom_products[value_col] = bottom_products[value_col].apply(lambda x: f'${x:,.2f}')
            else: 
                bottom_products[value_col] = bottom_products[value_col].apply(lambda x: f'{x:,.0f}')
            st.dataframe(bottom_products[['Item_Code','Item_Name','Product_Group','Division',value_col]], use_container_width=True, hide_index=True, column_config={"Item_Code":"Item Code","Item_Name":"Item Name","Product_Group":"Product Group","Division":"Division",value_col:"Value"})
            
            # NEW: Performance Heatmap
            if st.session_state.show_advanced_analytics and not item_performance.empty:
                st.markdown("---")
                st.markdown("#### 🔥 Performance Heatmap (Top 50 Products)")
                heatmap_data = top_products.head(50)[['Item_Name', 'Total_Sales', 'Total_Qty', 'Total_Transactions']].copy()
                heatmap_data = heatmap_data.set_index('Item_Name')
                fig = px.imshow(heatmap_data.T, text_auto=True, aspect="auto", title="Product Performance Heatmap", color_continuous_scale="Viridis")
                fig.update_layout(height=500, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data")

    # ========================================================================
    # PAGE 8: PRODUCT PORTFOLIO - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📦 Product Portfolio":
        st.markdown("### 📦 Product Portfolio Analysis")
        if not item_performance.empty:
            if view_type_label == "💰 Value": 
                value_col='Total_Sales'
            elif view_type_label == "📦 Quantity": 
                value_col='Total_Qty'
            else: 
                value_col='Total_Transactions'
            
            st.markdown("#### 📊 Product Group Performance")
            group_summary = item_performance.groupby('Product_Group').agg({value_col:'sum','Item_Code':'nunique','Total_Transactions':'sum'}).reset_index()
            group_summary.columns = ['Product_Group','Total_Value','Product_Count','Transactions']
            group_summary = group_summary.sort_values('Total_Value', ascending=False)
            if view_type_label == "💰 Value": 
                group_summary['Total_Value'] = group_summary['Total_Value'].apply(lambda x: f'${x:,.2f}')
            else: 
                group_summary['Total_Value'] = group_summary['Total_Value'].apply(lambda x: f'{x:,.0f}')
            st.dataframe(group_summary, use_container_width=True, hide_index=True, column_config={"Product_Group":"Product Group","Total_Value":"Value","Product_Count":"Products","Transactions":"Transactions"})
            
            col1, col2 = st.columns(2)
            with col1:
                if view_type_label == "💰 Value":
                    clean_values = group_summary['Total_Value'].str.replace('$','').str.replace(',','').astype(float)
                else: 
                    clean_values = group_summary['Total_Value']
                fig = px.pie(group_summary, values=clean_values, names='Product_Group', title='Revenue by Product Group', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=20))
                fig.update_traces(textposition='inside', textfont=dict(size=11))
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(group_summary, x='Product_Group', y='Product_Count', title='Number of Products by Group', color='Product_Count', color_continuous_scale='Blues', text_auto=True)
                fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=30), showlegend=False, xaxis={'tickangle':-45 if len(group_summary)>8 else 0})
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 🏷️ Brand Performance")
            if 'Brand_Name' in item_performance.columns and not item_performance['Brand_Name'].isna().all():
                brand_summary = item_performance.groupby('Brand_Name').agg({value_col:'sum','Item_Code':'nunique'}).reset_index()
                brand_summary.columns = ['Brand','Total_Value','Product_Count']
                brand_summary = brand_summary.sort_values('Total_Value', ascending=False).head(10)
                fig = px.bar(brand_summary, x='Brand', y='Total_Value', title='Top 10 Brands by Performance', color='Total_Value', color_continuous_scale='Viridis', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=30), xaxis={'tickangle':-45 if len(brand_summary)>6 else 0}, showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            # NEW: Product Portfolio Matrix
            if st.session_state.show_advanced_analytics:
                st.markdown("---")
                st.markdown("#### 📊 Product Portfolio Matrix (BCG Style)")
                portfolio_data = item_performance[['Item_Name', 'Total_Sales', 'Total_Qty', 'Product_Group']].copy()
                portfolio_data['Market_Share'] = portfolio_data['Total_Sales'] / portfolio_data['Total_Sales'].sum() * 100
                portfolio_data['Growth_Rate'] = portfolio_data['Total_Qty'].pct_change().fillna(0) * 100
                portfolio_data['Growth_Rate'] = portfolio_data['Growth_Rate'].clip(-100, 100)
                fig = px.scatter(portfolio_data, x='Market_Share', y='Growth_Rate', 
                                size='Total_Sales', color='Product_Group',
                                hover_name='Item_Name', title='Product Portfolio Matrix',
                                labels={'Market_Share': 'Market Share (%)', 'Growth_Rate': 'Growth Rate (%)'})
                fig.update_layout(height=400, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
        else: 
            st.info("No data")

    # ========================================================================
    # PAGE 9: STOCK ANALYSIS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📦 Stock Analysis":
        st.markdown("### 📦 Stock Level Analysis")
        st.caption(f"Current Stock as of: {latest_date.strftime('%Y-%m-%d') if latest_date else 'No stock data available'}")
        st.caption(f"Supplier Filter: {supplier if supplier != 'All' else 'All Suppliers'}")
        
        if stock_by_location is not None and not stock_by_location.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_stock = stock_by_location['Total_Stock_Qty'].sum() if not stock_by_location.empty else 0
                total_value = stock_by_location['Total_Stock_Value'].sum() if not stock_by_location.empty else 0
                st.markdown(f'<div class="kpi-card"><div class="kpi-icon">📦</div><div class="kpi-label">Current Stock <span style="font-weight:300; font-size:0.6rem; color:#8899bb;">({filter_context})</span></div><div class="kpi-value">{total_stock:,.0f}</div><div class="kpi-previous">Value: ${total_value:,.2f}</div></div>', unsafe_allow_html=True)
            with col2:
                unique_items = stock_by_location['Unique_Items'].sum() if not stock_by_location.empty else 0
                locations = len(stock_by_location) if not stock_by_location.empty else 0
                st.markdown(f'<div class="kpi-card"><div class="kpi-icon">🏷️</div><div class="kpi-label">Active Items <span style="font-weight:300; font-size:0.6rem; color:#8899bb;">({filter_context})</span></div><div class="kpi-value">{unique_items:,.0f}</div><div class="kpi-previous">Across {locations} locations</div></div>', unsafe_allow_html=True)
            with col3:
                stockout_count = len(stock_out_analysis[stock_out_analysis['Stockout_Status'] == 'STOCKOUT']) if not stock_out_analysis.empty else 0
                st.markdown(f'<div class="kpi-card" style="border-color: {"#ef4444" if stockout_count>0 else "#22c55e"};"><div class="kpi-icon">⚠️</div><div class="kpi-label">Stock-out Items <span style="font-weight:300; font-size:0.6rem; color:#8899bb;">({filter_context})</span></div><div class="kpi-value" style="color: {"#ef4444" if stockout_count>0 else "#22c55e"};">{stockout_count}</div><div class="kpi-previous">Items with zero stock</div></div>', unsafe_allow_html=True)
            with col4:
                urgent_orders = len(order_recommendations[order_recommendations['Urgency']=='IMMEDIATE']) if not order_recommendations.empty else 0
                total_recommend = len(order_recommendations) if not order_recommendations.empty else 0
                st.markdown(f'<div class="kpi-card"><div class="kpi-icon">🔄</div><div class="kpi-label">Reorder Items <span style="font-weight:300; font-size:0.6rem; color:#8899bb;">({filter_context})</span></div><div class="kpi-value" style="color: {"#ef4444" if urgent_orders>0 else "#22c55e"};">{total_recommend}</div><div class="kpi-previous">Immediate: {urgent_orders}</div></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            st.markdown("### 📊 Current Stock by Location / Branch")
            col1, col2 = st.columns(2)
            with col1:
                if not stock_by_location.empty:
                    fig = px.bar(stock_by_location.head(15), x='Branch_Location', y='Total_Stock_Qty', title='Top 15 Locations by Current Stock', color='Total_Stock_Value', color_continuous_scale='Blues', text_auto='.1s')
                    fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=60), xaxis={'tickangle':-45}, yaxis_title='Stock Quantity')
                    fig.update_traces(textposition='outside', textfont=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                if not stock_by_location.empty:
                    fig = px.pie(stock_by_location.head(10), values='Total_Stock_Qty', names='Branch_Location', title='Stock Distribution by Location', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                    fig.update_layout(height=400, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=20))
                    fig.update_traces(textposition='inside', textfont=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            st.markdown("### 🔄 Order Recommendations")
            st.caption("Based on BRANCH-WISE current stock and BRANCH-WISE average monthly sales")
            st.caption("Recommended Order = (Branch Avg Sales × 2) - Current Stock")
            if not order_recommendations.empty:
                immediate_orders = order_recommendations[order_recommendations['Urgency']=='IMMEDIATE']
                urgent_orders = order_recommendations[order_recommendations['Urgency']=='URGENT']
                soon_orders = order_recommendations[order_recommendations['Urgency']=='SOON']
                if not immediate_orders.empty:
                    st.markdown("#### 🔴 Critical - Immediate Order Required")
                    st.dataframe(immediate_orders[['Item_Name','Branch_Location','Current_Stock','Branch_Avg_Sales','Recommended_Order_Qty']].head(10), use_container_width=True, hide_index=True, column_config={"Item_Name":"Item","Branch_Location":"Location","Current_Stock":"Current Stock","Branch_Avg_Sales":"Branch Avg Sales","Recommended_Order_Qty":"Recommended Order"})
                if not urgent_orders.empty:
                    st.markdown("#### 🟡 Urgent - Order Soon")
                    st.dataframe(urgent_orders[['Item_Name','Branch_Location','Current_Stock','Branch_Avg_Sales','Recommended_Order_Qty']].head(10), use_container_width=True, hide_index=True, column_config={"Item_Name":"Item","Branch_Location":"Location","Current_Stock":"Current Stock","Branch_Avg_Sales":"Branch Avg Sales","Recommended_Order_Qty":"Recommended Order"})
                if not soon_orders.empty:
                    st.markdown("#### 🟢 Order Soon")
                    st.dataframe(soon_orders[['Item_Name','Branch_Location','Current_Stock','Branch_Avg_Sales','Recommended_Order_Qty']].head(10), use_container_width=True, hide_index=True, column_config={"Item_Name":"Item","Branch_Location":"Location","Current_Stock":"Current Stock","Branch_Avg_Sales":"Branch Avg Sales","Recommended_Order_Qty":"Recommended Order"})
                
                st.markdown("#### 📊 Order Recommendation Summary")
                order_summary = order_recommendations.groupby('Urgency').size().reset_index(name='Count')
                if not order_summary.empty:
                    fig = px.bar(order_summary, x='Urgency', y='Count', title='Items by Order Urgency (Branch-wise)', color='Urgency', color_discrete_map={'IMMEDIATE':'#ef4444','URGENT':'#f59e0b','SOON':'#3b82f6','NOT URGENT':'#22c55e'}, text_auto=True)
                    fig.update_layout(height=300, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=30), showlegend=False)
                    fig.update_traces(textposition='outside', textfont=dict(size=12))
                    st.plotly_chart(fig, use_container_width=True)
            else: 
                st.info("🎉 No items need reordering. All stock levels are healthy!")
            
            st.markdown("---")
            
            st.markdown("### ⚠️ Stock-out Analysis (Items with Zero Stock)")
            st.caption("Based on BRANCH-WISE average sales - items with zero stock at specific branches")
            if not stock_out_analysis.empty:
                stockouts = stock_out_analysis[stock_out_analysis['Stockout_Status'] == 'STOCKOUT']
                if not stockouts.empty:
                    st.dataframe(stockouts[['Item_Number','Branch_Location','Avg_Monthly_Sales']].head(20), use_container_width=True, hide_index=True, column_config={"Item_Number":"Item Code","Branch_Location":"Location","Avg_Monthly_Sales":"Branch Avg Sales"})
                
                st.markdown("#### 📊 Stock-out Summary by Location")
                stockout_summary = stock_out_analysis.groupby('Branch_Location')['Stockout_Status'].value_counts().reset_index(name='Count')
                if not stockout_summary.empty:
                    stockout_pivot = stockout_summary.pivot(index='Branch_Location', columns='Stockout_Status', values='Count').fillna(0)
                    st.dataframe(stockout_pivot, use_container_width=True)
            else: 
                st.info("🎉 No stock-out items found for selected filters!")
            
            st.markdown("---")
            
            st.markdown("### 📊 Stock vs Sales Analysis")
            st.caption("Comparing BRANCH-WISE stock levels with BRANCH-WISE average sales")
            if not stock_status_summary.empty:
                fig = px.pie(stock_status_summary, values='Item_Count', names='Stock_Status', title='Stock Status Distribution (Branch-wise)', hole=0.4, color='Stock_Status', color_discrete_map={'HEALTHY':'#22c55e','LOW_STOCK':'#f59e0b','OVERSTOCK':'#3b82f6','STOCKOUT':'#ef4444'})
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=20))
                fig.update_traces(textposition='inside', textfont=dict(size=12))
                st.plotly_chart(fig, use_container_width=True)
            
            low_stock_items = order_recommendations[(order_recommendations['Urgency']=='URGENT') | (order_recommendations['Urgency']=='SOON')].head(10)
            if not low_stock_items.empty:
                st.markdown("#### 📉 Low Stock Items (Needs Attention)")
                st.dataframe(low_stock_items[['Item_Name','Branch_Location','Current_Stock','Branch_Avg_Sales','Recommended_Order_Qty']], use_container_width=True, hide_index=True, column_config={"Item_Name":"Item","Branch_Location":"Location","Current_Stock":"Current Stock","Branch_Avg_Sales":"Branch Avg Sales","Recommended_Order_Qty":"Recommended Order"})
            
            st.markdown("#### 📋 Stock Status Summary by Location")
            if not stock_status_summary.empty:
                status_pivot = stock_status_summary.pivot(index='Branch_Location', columns='Stock_Status', values='Item_Count').fillna(0)
                status_pivot['Total'] = status_pivot.sum(axis=1)
                status_pivot = status_pivot.sort_values('Total', ascending=False)
                st.dataframe(status_pivot, use_container_width=True)
            
            # NEW: Stock Turnover Analysis
            if st.session_state.show_advanced_analytics and not stock_by_location.empty:
                st.markdown("---")
                st.markdown("#### 🔄 Stock Turnover Analysis")
                turnover_data = stock_by_location.copy()
                turnover_data['Turnover_Ratio'] = turnover_data['Total_Stock_Value'] / turnover_data['Total_Stock_Qty']
                fig = px.bar(turnover_data.head(15), x='Branch_Location', y='Turnover_Ratio', title='Stock Turnover Ratio by Location', color='Turnover_Ratio', color_continuous_scale='Viridis', text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark', margin=dict(l=10,r=10,t=40,b=40), xaxis={'tickangle':-45}, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No stock data available for selected filters.")

    # ========================================================================
    # PAGE 10: PURCHASE ANALYSIS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "📦 Purchase Analysis":
        st.markdown("### 📦 Purchase Analysis")
        st.caption("Comprehensive purchase history, trends, and vendor performance (clean data - excludes returns)")

        col1, col2, col3 = st.columns(3)
        with col1:
            try:
                conn = get_connection()
                vendors = conn.execute("SELECT DISTINCT Vendor FROM purchase_all_clean ORDER BY Vendor").df()
                vendor_options = ["All"] + vendors['Vendor'].tolist() if not vendors.empty else ["All"]
                
            except:
                vendor_options = ["All"]
            idx = vendor_options.index(st.session_state.vendor) if st.session_state.vendor in vendor_options else 0
            new_vendor = st.selectbox("Vendor", vendor_options, index=idx, key="vendor_select")
            if new_vendor != st.session_state.vendor:
                st.session_state.vendor = new_vendor
                st.cache_data.clear()
                st.rerun()
        with col2:
            purchase_types = ["All", "Import", "Local"]
            idx = purchase_types.index(st.session_state.purchase_type) if st.session_state.purchase_type in purchase_types else 0
            new_type = st.selectbox("Purchase Type", purchase_types, index=idx, key="purchase_type_select")
            if new_type != st.session_state.purchase_type:
                st.session_state.purchase_type = new_type
                st.cache_data.clear()
                st.rerun()
        with col3:
            st.markdown(f"**Supplier Filter:** {supplier if supplier != 'All' else 'All Suppliers'}")

        with st.spinner("Loading purchase data..."):
            purchase_df = load_purchase_data(
                year, month, period, branch, location, 
                item_code, item_name, product_group, division,
                supplier, st.session_state.vendor, st.session_state.purchase_type
            )

        if not purchase_df.empty:
            total_qty = purchase_df['Qty'].sum() if 'Qty' in purchase_df.columns else 0
            total_amount = purchase_df['Amount_USD'].sum() if 'Amount_USD' in purchase_df.columns else 0
            unique_vendors = purchase_df['Vendor'].nunique() if 'Vendor' in purchase_df.columns else 0
            total_transactions = len(purchase_df)
            import_count = len(purchase_df[purchase_df['Purchase_Type'] == 'Import']) if 'Purchase_Type' in purchase_df.columns else 0
            local_count = len(purchase_df[purchase_df['Purchase_Type'] == 'Local']) if 'Purchase_Type' in purchase_df.columns else 0

            kpi_cols = st.columns(6)
            with kpi_cols[0]:
                st.markdown(f"""
                <div class="purchase-card">
                    <div class="purchase-label">📦 Total Purchase Qty</div>
                    <div class="purchase-value">{total_qty:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[1]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #22c55e;">
                    <div class="purchase-label">💰 Total Purchase Value</div>
                    <div class="purchase-value" style="color: #22c55e;">${total_amount:,.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[2]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #f59e0b;">
                    <div class="purchase-label">🏢 Unique Vendors</div>
                    <div class="purchase-value" style="color: #f59e0b;">{unique_vendors}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[3]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #8b5cf6;">
                    <div class="purchase-label">📊 Transactions</div>
                    <div class="purchase-value" style="color: #8b5cf6;">{total_transactions:,}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[4]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #0066CC;">
                    <div class="purchase-label">🌍 Import</div>
                    <div class="purchase-value" style="color: #0066CC;">{import_count:,}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[5]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #22c55e;">
                    <div class="purchase-label">🏪 Local</div>
                    <div class="purchase-value" style="color: #22c55e;">{local_count:,}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📈 Purchase Trends")

            purchase_df['Purchase_Date'] = pd.to_datetime(purchase_df['Purchase_Date'], errors='coerce')
            purchase_df = purchase_df.dropna(subset=['Purchase_Date'])

            if not purchase_df.empty:
                purchase_df['Year'] = purchase_df['Purchase_Date'].dt.year
                purchase_df['Month'] = purchase_df['Purchase_Date'].dt.month
                purchase_df['Month_Label'] = purchase_df['Purchase_Date'].dt.strftime('%Y-%m')

                monthly_purchase = purchase_df.groupby(['Year', 'Month', 'Month_Label']).agg({
                    'Qty': 'sum',
                    'Amount_USD': 'sum'
                }).reset_index().sort_values(['Year', 'Month'])

                if not monthly_purchase.empty:
                    monthly_purchase['Display_Month'] = monthly_purchase.apply(
                        lambda row: f"{int(row['Year'])}-{int(row['Month']):02d}", axis=1
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        fig_qty = go.Figure()
                        fig_qty.add_trace(go.Bar(
                            x=monthly_purchase['Display_Month'],
                            y=monthly_purchase['Qty'],
                            name='Purchase Qty',
                            marker=dict(color='#8b5cf6', opacity=0.85),
                            text=monthly_purchase['Qty'].apply(lambda x: f'{x:,.0f}'),
                            textposition='outside',
                            textfont=dict(size=9)
                        ))
                        fig_qty.update_layout(
                            title='Monthly Purchase Quantity',
                            height=350,
                            template='plotly_dark',
                            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
                            yaxis=dict(title='Qty', tickformat=',.0f'),
                            showlegend=False,
                            margin=dict(l=20, r=20, t=40, b=60)
                        )
                        st.plotly_chart(fig_qty, use_container_width=True)

                    with col2:
                        fig_amount = go.Figure()
                        fig_amount.add_trace(go.Bar(
                            x=monthly_purchase['Display_Month'],
                            y=monthly_purchase['Amount_USD'],
                            name='Purchase Value ($)',
                            marker=dict(color='#22c55e', opacity=0.85),
                            text=monthly_purchase['Amount_USD'].apply(lambda x: f'${x:,.0f}'),
                            textposition='outside',
                            textfont=dict(size=9)
                        ))
                        fig_amount.update_layout(
                            title='Monthly Purchase Value',
                            height=350,
                            template='plotly_dark',
                            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
                            yaxis=dict(title='Amount ($)', tickformat='$,.0f'),
                            showlegend=False,
                            margin=dict(l=20, r=20, t=40, b=60)
                        )
                        st.plotly_chart(fig_amount, use_container_width=True)

                st.markdown("---")
                st.markdown("### 🏢 Vendor Analysis")

                vendor_summary = purchase_df.groupby('Vendor').agg({
                    'Qty': 'sum',
                    'Amount_USD': 'sum',
                    'Item_Code': 'nunique'
                }).reset_index().sort_values('Amount_USD', ascending=False)
                vendor_summary.columns = ['Vendor', 'Total_Qty', 'Total_Spend', 'Unique_Items']

                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(vendor_summary.head(15), x='Total_Spend', y='Vendor', 
                                orientation='h', title='Top 15 Vendors by Spend',
                                color='Total_Spend', color_continuous_scale='Greens',
                                text_auto='.1s')
                    fig.update_layout(height=400, template='plotly_dark', 
                                    margin=dict(l=10, r=10, t=40, b=20),
                                    xaxis_title='Total Spend ($)', showlegend=False)
                    fig.update_traces(textposition='outside', textfont=dict(size=9))
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.dataframe(vendor_summary.head(15), use_container_width=True, hide_index=True,
                                column_config={
                                    'Vendor': 'Vendor',
                                    'Total_Qty': 'Total Qty',
                                    'Total_Spend': 'Total Spend ($)',
                                    'Unique_Items': 'Unique Items'
                                })

                st.markdown("---")
                st.markdown("### 📦 Purchase by Item")

                item_purchase = purchase_df.groupby(['Item_Code', 'Item_Name']).agg({
                    'Qty': 'sum',
                    'Amount_USD': 'sum',
                    'Vendor': 'nunique'
                }).reset_index().sort_values('Amount_USD', ascending=False)
                item_purchase.columns = ['Item_Code', 'Item_Name', 'Total_Qty', 'Total_Spend', 'Unique_Vendors']

                try:
                    conn = get_connection()
                    item_info = conn.execute("""
                        SELECT Item_Code, Product_Group, Division 
                        FROM item_master
                    """).df()
                    
                    item_purchase = item_purchase.merge(item_info, on='Item_Code', how='left')
                except:
                    pass

                display_items = item_purchase.head(20).copy()
                display_items['Total_Qty'] = display_items['Total_Qty'].apply(lambda x: f'{x:,.0f}')
                display_items['Total_Spend'] = display_items['Total_Spend'].apply(lambda x: f'${x:,.2f}')
                st.dataframe(display_items, use_container_width=True, height=400, hide_index=True)

                csv_purchase = purchase_df.to_csv(index=False)
                st.download_button("📥 Download Purchase Data", csv_purchase, "purchase_data.csv", "text/csv")
            else:
                st.info("No valid purchase dates found in the data.")
        else:
            st.info("No purchase data available for the selected filters.")


    # ========================================================================
    # PAGE 11: SUPPLIER PERFORMANCE - ENHANCED
    # ========================================================================
    elif st.session_state.page == "🏢 Supplier Performance":
        st.markdown("### 🏢 Supplier Performance Dashboard")
        st.caption("Comprehensive supplier analytics, risk assessment, and performance metrics (PURCHASE data only)")

        with st.spinner("Loading supplier data..."):
            supplier_data = load_supplier_data(year, month, period, branch, location, product_group, division, item_code, item_name, supplier)

        supplier_summary = supplier_data.get('supplier_summary', pd.DataFrame())
        supplier_performance = supplier_data.get('supplier_performance', pd.DataFrame())
        supplier_risk = supplier_data.get('supplier_risk', pd.DataFrame())
        supplier_product_mapping = supplier_data.get('supplier_product_mapping', pd.DataFrame())
        supplier_product_performance = supplier_data.get('supplier_product_performance', pd.DataFrame())

        if not supplier_summary.empty:
            total_suppliers = len(supplier_summary)
            total_supplier_spend = supplier_summary['Total_Sales'].sum() if 'Total_Sales' in supplier_summary.columns else 0
            total_supplier_qty = supplier_summary['Total_Qty'].sum() if 'Total_Qty' in supplier_summary.columns else 0

            kpi_cols = st.columns(4)
            with kpi_cols[0]:
                st.markdown(f"""
                <div class="purchase-card">
                    <div class="purchase-label">🏢 Total Suppliers</div>
                    <div class="purchase-value">{total_suppliers}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[1]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #22c55e;">
                    <div class="purchase-label">💰 Total Supplier Spend</div>
                    <div class="purchase-value" style="color: #22c55e;">${total_supplier_spend:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[2]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #f59e0b;">
                    <div class="purchase-label">📦 Total Supplier Qty</div>
                    <div class="purchase-value" style="color: #f59e0b;">{total_supplier_qty:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi_cols[3]:
                st.markdown(f"""
                <div class="purchase-card" style="border-top: 2px solid #8b5cf6;">
                    <div class="purchase-label">📊 Transactions</div>
                    <div class="purchase-value" style="color: #8b5cf6;">{supplier_summary['Total_Transactions'].sum():,.0f}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # ---- Supplier Purchase Summary ----
            st.markdown("#### 📊 Supplier Purchase Summary")
            st.caption("Purchase spend and quantity by supplier (from purchase data, NOT sales data)")

            display_summary = supplier_summary.copy()
            for col in ['Total_Sales', 'Total_Qty', 'Total_Purchase_Spend', 'Total_Purchase_Qty']:
                if col in display_summary.columns:
                    display_summary[col] = display_summary[col].apply(lambda x: f'{x:,.0f}')
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
            csv_summary = supplier_summary.to_csv(index=False)
            st.download_button("📥 Download Supplier Purchase Summary", csv_summary, "supplier_purchase_summary.csv", "text/csv")

            st.markdown("---")

            # ---- Supplier Performance ----
            if not supplier_performance.empty:
                st.markdown("#### 📈 Supplier Performance Metrics")
                display_perf = supplier_performance.copy()
                for col in ['Total_Ordered_Qty', 'Total_Invoiced_Value', 'Total_Advance_Paid', 'Total_Outstanding_Balance']:
                    if col in display_perf.columns:
                        display_perf[col] = display_perf[col].apply(lambda x: f'{x:,.0f}')
                st.dataframe(display_perf, use_container_width=True, hide_index=True)
                csv_perf = supplier_performance.to_csv(index=False)
                st.download_button("📥 Download Supplier Performance", csv_perf, "supplier_performance.csv", "text/csv")

            st.markdown("---")

            # ---- Supplier Risk Analysis ----
            if not supplier_risk.empty:
                st.markdown("#### ⚠️ Supplier Risk Analysis")

                col1, col2 = st.columns(2)
                with col1:
                    risk_summary = supplier_risk.groupby('Risk_Level').size().reset_index(name='Count')
                    if not risk_summary.empty:
                        fig = px.pie(risk_summary, values='Count', names='Risk_Level', 
                                     title='Supplier Risk Distribution',
                                     color='Risk_Level',
                                     color_discrete_map={'LOW_RISK':'#22c55e', 'MEDIUM_RISK':'#f59e0b', 'HIGH_RISK':'#ef4444'},
                                     hole=0.4)
                        fig.update_layout(height=350, template='plotly_dark')
                        st.plotly_chart(fig, use_container_width=True)

                with col2:
                    status_summary = supplier_risk.groupby('Primary_Supplier_Status').size().reset_index(name='Count')
                    if not status_summary.empty:
                        fig = px.bar(status_summary, x='Primary_Supplier_Status', y='Count',
                                     title='Primary Supplier Status',
                                     color='Count', color_continuous_scale='Blues',
                                     text_auto=True)
                        fig.update_layout(height=350, template='plotly_dark', showlegend=False)
                        fig.update_traces(textposition='outside')
                        st.plotly_chart(fig, use_container_width=True)

                display_risk = supplier_risk.copy()
                for col in ['Total_Revenue', 'Total_Qty', 'Total_Purchase_Spend', 'Total_Purchase_Qty']:
                    if col in display_risk.columns:
                        display_risk[col] = display_risk[col].apply(lambda x: f'{x:,.0f}')
                st.dataframe(display_risk, use_container_width=True, hide_index=True)
                csv_risk = supplier_risk.to_csv(index=False)
                st.download_button("📥 Download Supplier Risk Analysis", csv_risk, "supplier_risk.csv", "text/csv")

            st.markdown("---")

            # ---- Supplier Purchase by Item ----
            if not supplier_product_mapping.empty:
                st.markdown("#### 📦 Supplier Purchase by Item")
                st.caption("What products were purchased from each supplier")

                display_mapping = supplier_product_mapping.copy()
                for col in ['Purchase_Qty', 'Purchase_Spend']:
                    if col in display_mapping.columns:
                        display_mapping[col] = display_mapping[col].apply(lambda x: f'{x:,.0f}')
                if 'Avg_Unit_Cost' in display_mapping.columns:
                    display_mapping['Avg_Unit_Cost'] = display_mapping['Avg_Unit_Cost'].apply(lambda x: f'${x:.2f}')

                search_mapping = st.text_input("🔍 Search Supplier or Item", placeholder="Type supplier name or item code...", key="supplier_search_map")
                if search_mapping:
                    display_mapping = display_mapping[
                        display_mapping['Supplier'].str.contains(search_mapping, case=False, na=False) |
                        display_mapping['Item_Code'].str.contains(search_mapping, case=False, na=False) |
                        display_mapping['Item_Name'].str.contains(search_mapping, case=False, na=False)
                    ]

                st.dataframe(display_mapping, use_container_width=True, height=400, hide_index=True)
                csv_mapping = supplier_product_mapping.to_csv(index=False)
                st.download_button("📥 Download Supplier Purchase by Item", csv_mapping, "supplier_purchase_items.csv", "text/csv")
            else:
                st.info("No supplier purchase data available.")

            # ---- Supplier Product Performance ----
            if not supplier_product_performance.empty:
                st.markdown("---")
                st.markdown("#### 📦 Supplier Product Performance (Combined)")
                st.caption("Sales and purchase performance combined")

                display_spp = supplier_product_performance.copy()
                for col in ['Total_Sales', 'Total_Qty', 'Purchase_Spend', 'Purchase_Qty']:
                    if col in display_spp.columns:
                        display_spp[col] = display_spp[col].apply(lambda x: f'{x:,.0f}')
                if 'Avg_Purchase_Price' in display_spp.columns:
                    display_spp['Avg_Purchase_Price'] = display_spp['Avg_Purchase_Price'].apply(lambda x: f'${x:.2f}')

                search_spp = st.text_input("🔍 Search in Combined Performance", placeholder="Type supplier or item...", key="supplier_search_spp")
                if search_spp:
                    display_spp = display_spp[
                        display_spp['Supplier'].str.contains(search_spp, case=False, na=False) |
                        display_spp['Item_Code'].str.contains(search_spp, case=False, na=False) |
                        display_spp['Item_Name'].str.contains(search_spp, case=False, na=False)
                    ]

                st.dataframe(display_spp, use_container_width=True, height=400, hide_index=True)
                csv_spp = supplier_product_performance.to_csv(index=False)
                st.download_button("📥 Download Supplier Product Performance", csv_spp, "supplier_product_performance.csv", "text/csv")
            
            # NEW: Supplier Performance Scorecard
            if st.session_state.show_advanced_analytics and not supplier_summary.empty:
                st.markdown("---")
                st.markdown("#### 📊 Supplier Performance Scorecard")
                scorecard = supplier_summary.copy()
                scorecard['Spend_Percentage'] = (scorecard['Total_Purchase_Spend'] / scorecard['Total_Purchase_Spend'].sum() * 100).round(1)
                scorecard['Avg_Transaction_Value'] = scorecard['Total_Purchase_Spend'] / scorecard['Total_Transactions']
                scorecard['Items_Per_Transaction'] = scorecard['Unique_Products'] / scorecard['Total_Transactions']
                scorecard = scorecard.rename(columns={
                    'Supplier': 'Supplier',
                    'Total_Purchase_Spend': 'Total Spend ($)',
                    'Total_Purchase_Qty': 'Total Qty',
                    'Total_Transactions': 'Transactions',
                    'Spend_Percentage': 'Spend %',
                    'Avg_Transaction_Value': 'Avg Transaction ($)',
                    'Items_Per_Transaction': 'Items/Trans'
                })
                display_scorecard = scorecard.head(15)[['Supplier', 'Total Spend ($)', 'Total Qty', 'Transactions', 'Spend %', 'Avg Transaction ($)', 'Items/Trans']].copy()
                display_scorecard['Total Spend ($)'] = display_scorecard['Total Spend ($)'].apply(lambda x: f'${x:,.0f}')
                display_scorecard['Total Qty'] = display_scorecard['Total Qty'].apply(lambda x: f'{x:,.0f}')
                display_scorecard['Avg Transaction ($)'] = display_scorecard['Avg Transaction ($)'].apply(lambda x: f'${x:,.2f}')
                display_scorecard['Items/Trans'] = display_scorecard['Items/Trans'].apply(lambda x: f'{x:.2f}')
                display_scorecard['Spend %'] = display_scorecard['Spend %'].apply(lambda x: f'{x:.1f}%')
                st.dataframe(display_scorecard, use_container_width=True, hide_index=True)

        else:
            st.info("No supplier purchase data available for the selected filters.")

    # ========================================================================
    # PAGE 12: FOC ANALYSIS - ENHANCED
    # ========================================================================
    elif st.session_state.page == "🎯 FOC Analysis":
        st.markdown("""
        <div style="animation: fadeInDown 0.8s ease-out;">
            <h2 style="font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #8b5cf6, #7b5ea7, #0066CC); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 4px;">🎯 Free of Charge (FOC) Analysis</h2>
            <p style="color: #8899bb; font-size: 0.95rem; margin-top: 0;">Complete FOC analysis for sales and purchases</p>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Loading FOC data..."):
            foc_data = load_foc_data(year, month, period, branch, location, item_code, item_name, product_group, division, supplier)
        
        foc_sales_summary = foc_data.get('foc_sales_summary', pd.DataFrame())
        foc_monthly = foc_data.get('foc_monthly', pd.DataFrame())
        foc_purchase_summary = foc_data.get('foc_purchase_summary', pd.DataFrame())
        foc_purchase_monthly = foc_data.get('foc_purchase_monthly', pd.DataFrame())
        foc_outliers = foc_data.get('foc_outliers', pd.DataFrame())
        foc_by_branch = foc_data.get('foc_by_branch', pd.DataFrame())
        foc_by_group = foc_data.get('foc_by_group', pd.DataFrame())
        foc_demand_impact = foc_data.get('foc_demand_impact', pd.DataFrame())
        foc_recommendations = foc_data.get('foc_recommendations', pd.DataFrame())

        # ---- FOC Overview KPIs ----
        total_sales_foc = foc_sales_summary['Total_FOC_Qty'].sum() if not foc_sales_summary.empty else 0
        total_sales_qty = foc_sales_summary['Total_Qty_Sold'].sum() if not foc_sales_summary.empty else 0
        total_purchase_foc = foc_purchase_summary['Total_FOC_Qty'].sum() if not foc_purchase_summary.empty else 0
        total_purchase_qty = foc_purchase_summary['Total_Purchase_Qty'].sum() if not foc_purchase_summary.empty else 0
        
        sales_foc_pct = (total_sales_foc / total_sales_qty * 100) if total_sales_qty > 0 else 0
        purchase_foc_pct = (total_purchase_foc / total_purchase_qty * 100) if total_purchase_qty > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="foc-card" style="animation-delay: 0.1s;">
                <div class="foc-label">🎯 Total Sales FOC Qty</div>
                <div class="foc-value">{total_sales_foc:,.0f}</div>
                <div class="foc-sub">{sales_foc_pct:.2f}% of total sales</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="foc-card" style="animation-delay: 0.2s; border-color: #22c55e44;">
                <div class="foc-label">📦 Total Purchase FOC Qty</div>
                <div class="foc-value" style="color: #22c55e;">{total_purchase_foc:,.0f}</div>
                <div class="foc-sub">{purchase_foc_pct:.2f}% of total purchases</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            foc_items = foc_sales_summary['Item_Code'].nunique() if not foc_sales_summary.empty else 0
            st.markdown(f"""
            <div class="foc-card" style="animation-delay: 0.3s; border-color: #f59e0b44;">
                <div class="foc-label">🏷️ Items with FOC</div>
                <div class="foc-value" style="color: #f59e0b;">{foc_items}</div>
                <div class="foc-sub">Products with free quantity</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            foc_branches = foc_sales_summary['Branch'].nunique() if not foc_sales_summary.empty else 0
            st.markdown(f"""
            <div class="foc-card" style="animation-delay: 0.4s; border-color: #3b82f644;">
                <div class="foc-label">🏢 Branches with FOC</div>
                <div class="foc-value" style="color: #3b82f6;">{foc_branches}</div>
                <div class="foc-sub">Locations with FOC transactions</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # ---- FOC Monthly Trend ----
        st.markdown("### 📈 FOC Monthly Trend")
        if not foc_monthly.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=foc_monthly['Month_Label'],
                    y=foc_monthly['Total_FOC_Qty'],
                    name='FOC Qty',
                    marker=dict(color='#8b5cf6', opacity=0.8),
                    text=foc_monthly['Total_FOC_Qty'].apply(lambda x: f'{x:,.0f}'),
                    textposition='outside',
                    textfont=dict(size=9)
                ))
                fig.add_trace(go.Scatter(
                    x=foc_monthly['Month_Label'],
                    y=foc_monthly['FOC_Pct'],
                    name='FOC %',
                    yaxis='y2',
                    mode='lines+markers',
                    line=dict(color='#f59e0b', width=2, dash='dot'),
                    marker=dict(size=6, color='#f59e0b')
                ))
                fig.update_layout(
                    title='Monthly FOC Quantity and Percentage',
                    height=350,
                    template='plotly_dark',
                    xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
                    yaxis=dict(title='FOC Qty', tickformat=',.0f'),
                    yaxis2=dict(title='FOC %', overlaying='y', side='right', tickformat='.1f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    margin=dict(l=20, r=60, t=40, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=foc_monthly['Month_Label'],
                    y=foc_monthly['Total_Qty'],
                    name='Total Qty',
                    mode='lines+markers',
                    line=dict(color='#0066CC', width=2),
                    marker=dict(size=6, color='#0066CC'),
                    text=foc_monthly['Total_Qty'].apply(lambda x: f'{x:,.0f}'),
                    textposition='top center',
                    textfont=dict(size=8)
                ))
                fig.add_trace(go.Scatter(
                    x=foc_monthly['Month_Label'],
                    y=foc_monthly['Paid_Qty'],
                    name='Paid Qty',
                    mode='lines+markers',
                    line=dict(color='#22c55e', width=2),
                    marker=dict(size=6, color='#22c55e'),
                    text=foc_monthly['Paid_Qty'].apply(lambda x: f'{x:,.0f}'),
                    textposition='top center',
                    textfont=dict(size=8)
                ))
                fig.update_layout(
                    title='Total vs Paid vs FOC Quantity',
                    height=350,
                    template='plotly_dark',
                    xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
                    yaxis=dict(title='Qty', tickformat=',.0f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    margin=dict(l=20, r=20, t=40, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No FOC monthly data available.")

        st.markdown("---")

        # ---- FOC by Branch ----
        st.markdown("### 🏢 FOC by Branch")
        if not foc_by_branch.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(foc_by_branch.head(15), x='Branch', y='Total_FOC_Qty',
                             title='Top 15 Branches by FOC Qty',
                             color='Total_FOC_Qty', color_continuous_scale='Purples',
                             text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=40),
                                 xaxis=dict(tickangle=-45 if len(foc_by_branch)>8 else 0),
                                 showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.scatter(foc_by_branch, x='Total_Qty_Sold', y='Total_FOC_Qty',
                                 size='FOC_Transactions', color='Overall_FOC_Pct',
                                 hover_name='Branch', title='FOC vs Total Qty by Branch',
                                 color_continuous_scale='Viridis',
                                 labels={'Total_Qty_Sold': 'Total Qty Sold', 'Total_FOC_Qty': 'FOC Qty'})
                fig.update_layout(height=350, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 📋 Branch FOC Details")
            display_branch = foc_by_branch.copy()
            for col in ['Total_Qty_Sold', 'Total_FOC_Qty', 'Paid_Qty', 'FOC_Transactions']:
                if col in display_branch.columns:
                    display_branch[col] = display_branch[col].apply(lambda x: f'{x:,.0f}')
            if 'Overall_FOC_Pct' in display_branch.columns:
                display_branch['Overall_FOC_Pct'] = display_branch['Overall_FOC_Pct'].apply(lambda x: f'{x:.2f}%')
            if 'Avg_FOC_When_Present' in display_branch.columns:
                display_branch['Avg_FOC_When_Present'] = display_branch['Avg_FOC_When_Present'].apply(lambda x: f'{x:,.2f}')
            col_rename = {
                'Branch': 'Branch',
                'Location': 'Location',
                'Unique_Products_With_FOC': 'Products with FOC',
                'Total_Qty_Sold': 'Total Qty Sold',
                'Total_FOC_Qty': 'FOC Qty',
                'Paid_Qty': 'Paid Qty',
                'FOC_Transactions': 'FOC Transactions',
                'Overall_FOC_Pct': 'FOC %',
                'Avg_FOC_When_Present': 'Avg FOC per Transaction'
            }
            display_branch = display_branch.rename(columns={k: v for k, v in col_rename.items() if k in display_branch.columns})
            st.dataframe(display_branch, use_container_width=True, height=300, hide_index=True)
            csv_branch = foc_by_branch.to_csv(index=False)
            st.download_button("📥 Download FOC by Branch", csv_branch, "foc_by_branch.csv", "text/csv")
        else:
            st.info("No FOC by branch data available.")

        st.markdown("---")

        # ---- FOC by Product Group ----
        st.markdown("### 📦 FOC by Product Group")
        if not foc_by_group.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(foc_by_group, values='Total_FOC_Qty', names='Product_Group',
                             title='FOC Distribution by Product Group',
                             hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=350, template='plotly_dark')
                fig.update_traces(textposition='inside', textfont=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(foc_by_group, x='Product_Group', y='FOC_Percentage',
                             title='FOC Percentage by Product Group',
                             color='FOC_Percentage', color_continuous_scale='Reds',
                             text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=30),
                                 xaxis=dict(tickangle=-45 if len(foc_by_group)>6 else 0),
                                 showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 📋 Product Group FOC Details")
            display_group = foc_by_group.copy()
            for col in ['Total_Qty_Sold', 'Total_FOC_Qty', 'Paid_Qty', 'FOC_Transactions', 'Total_Revenue', 'FOC_Revenue_Value']:
                if col in display_group.columns:
                    display_group[col] = display_group[col].apply(lambda x: f'{x:,.0f}')
            if 'FOC_Percentage' in display_group.columns:
                display_group['FOC_Percentage'] = display_group['FOC_Percentage'].apply(lambda x: f'{x:.2f}%')
            if 'FOC_Value_Pct' in display_group.columns:
                display_group['FOC_Value_Pct'] = display_group['FOC_Value_Pct'].apply(lambda x: f'{x:.2f}%')
            col_rename = {
                'Product_Group': 'Product Group',
                'Total_Qty_Sold': 'Total Qty Sold',
                'Total_FOC_Qty': 'FOC Qty',
                'Paid_Qty': 'Paid Qty',
                'FOC_Transactions': 'FOC Transactions',
                'FOC_Percentage': 'FOC %',
                'Total_Revenue': 'Total Revenue',
                'FOC_Revenue_Value': 'FOC Revenue',
                'FOC_Value_Pct': 'FOC Value %'
            }
            display_group = display_group.rename(columns={k: v for k, v in col_rename.items() if k in display_group.columns})
            st.dataframe(display_group, use_container_width=True, height=250, hide_index=True)
            csv_group = foc_by_group.to_csv(index=False)
            st.download_button("📥 Download FOC by Product Group", csv_group, "foc_by_group.csv", "text/csv")
        else:
            st.info("No FOC by product group data available.")

        st.markdown("---")

        # ---- Top FOC Items ----
        st.markdown("### 🏆 Top Items by FOC")
        if not foc_sales_summary.empty:
            top_n_foc = st.slider("Number of Items to Display", 5, 50, 20, key="foc_top_items")
            
            top_items = foc_sales_summary.nlargest(top_n_foc, 'Total_FOC_Qty')
            
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(top_items, x='Total_FOC_Qty', y='Item_Name',
                             orientation='h', title=f'Top {top_n_foc} Items by FOC Qty',
                             color='FOC_Percentage', color_continuous_scale='Purples',
                             text_auto='.1s')
                fig.update_layout(height=400, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=20),
                                 xaxis_title='FOC Qty', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                high_pct_items = foc_sales_summary[foc_sales_summary['Total_FOC_Qty'] > 0].nlargest(15, 'FOC_Percentage')
                fig = px.bar(high_pct_items, x='FOC_Percentage', y='Item_Name',
                             orientation='h', title='Items by FOC Percentage',
                             color='FOC_Percentage', color_continuous_scale='Reds',
                             text_auto='.1s')
                fig.update_layout(height=400, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=20),
                                 xaxis_title='FOC %', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 📋 Top FOC Items Details")
            display_items = top_items.copy()
            for col in ['Total_Qty_Sold', 'Total_FOC_Qty', 'Paid_Qty', 'Total_Transactions', 'FOC_Transactions']:
                if col in display_items.columns:
                    display_items[col] = display_items[col].apply(lambda x: f'{x:,.0f}')
            if 'FOC_Percentage' in display_items.columns:
                display_items['FOC_Percentage'] = display_items['FOC_Percentage'].apply(lambda x: f'{x:.2f}%')
            if 'Avg_FOC_Per_Transaction' in display_items.columns:
                display_items['Avg_FOC_Per_Transaction'] = display_items['Avg_FOC_Per_Transaction'].apply(lambda x: f'{x:,.2f}')
            col_rename = {
                'Item_Code': 'Item Code',
                'Item_Name': 'Item Name',
                'Product_Group': 'Product Group',
                'Division': 'Division',
                'Branch': 'Branch',
                'Location': 'Location',
                'Total_Qty_Sold': 'Total Qty Sold',
                'Total_FOC_Qty': 'FOC Qty',
                'Paid_Qty': 'Paid Qty',
                'Total_Transactions': 'Total Transactions',
                'FOC_Transactions': 'FOC Transactions',
                'Avg_FOC_Per_Transaction': 'Avg FOC per Transaction',
                'FOC_Percentage': 'FOC %'
            }
            display_items = display_items.rename(columns={k: v for k, v in col_rename.items() if k in display_items.columns})
            st.dataframe(display_items, use_container_width=True, height=400, hide_index=True)
            csv_items = top_items.to_csv(index=False)
            st.download_button("📥 Download Top FOC Items", csv_items, "top_foc_items.csv", "text/csv")
        else:
            st.info("No FOC sales summary data available.")

        st.markdown("---")

        # ---- Purchase FOC ----
        st.markdown("### 🛒 Purchase FOC Analysis")
        if not foc_purchase_summary.empty:
            col1, col2 = st.columns(2)
            with col1:
                top_purchase_foc = foc_purchase_summary.nlargest(15, 'Total_FOC_Qty')
                fig = px.bar(top_purchase_foc, x='Total_FOC_Qty', y='Item_Name',
                             orientation='h', title='Top Purchase FOC by Item',
                             color='FOC_Percentage', color_continuous_scale='Greens',
                             text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=20),
                                 xaxis_title='FOC Qty', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                vendor_foc = foc_purchase_summary.groupby('Vendor')['Total_FOC_Qty'].sum().reset_index().nlargest(15, 'Total_FOC_Qty')
                fig = px.bar(vendor_foc, x='Total_FOC_Qty', y='Vendor',
                             orientation='h', title='Top Vendors by FOC Qty',
                             color='Total_FOC_Qty', color_continuous_scale='Blues',
                             text_auto='.1s')
                fig.update_layout(height=350, template='plotly_dark',
                                 margin=dict(l=10, r=10, t=40, b=20),
                                 xaxis_title='FOC Qty', showlegend=False)
                fig.update_traces(textposition='outside', textfont=dict(size=9))
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("#### 📋 Purchase FOC Details")
            display_purchase_foc = foc_purchase_summary.copy()
            for col in ['Total_Purchase_Qty', 'Total_FOC_Qty', 'Total_Amount', 'FOC_Transactions']:
                if col in display_purchase_foc.columns:
                    display_purchase_foc[col] = display_purchase_foc[col].apply(lambda x: f'{x:,.0f}')
            if 'FOC_Percentage' in display_purchase_foc.columns:
                display_purchase_foc['FOC_Percentage'] = display_purchase_foc['FOC_Percentage'].apply(lambda x: f'{x:.2f}%')
            if 'Avg_FOC_Per_Transaction' in display_purchase_foc.columns:
                display_purchase_foc['Avg_FOC_Per_Transaction'] = display_purchase_foc['Avg_FOC_Per_Transaction'].apply(lambda x: f'{x:,.2f}')
            col_rename = {
                'Purchase_Type': 'Type',
                'Branch': 'Branch',
                'Vendor': 'Vendor',
                'Item_Code': 'Item Code',
                'Item_Name': 'Item Name',
                'Total_Purchase_Qty': 'Total Purchase Qty',
                'Total_FOC_Qty': 'FOC Qty',
                'Total_Amount': 'Total Amount',
                'FOC_Transactions': 'FOC Transactions',
                'Avg_FOC_Per_Transaction': 'Avg FOC per Transaction',
                'FOC_Percentage': 'FOC %'
            }
            display_purchase_foc = display_purchase_foc.rename(columns={k: v for k, v in col_rename.items() if k in display_purchase_foc.columns})
            st.dataframe(display_purchase_foc, use_container_width=True, height=300, hide_index=True)
            csv_purchase_foc = foc_purchase_summary.to_csv(index=False)
            st.download_button("📥 Download Purchase FOC Data", csv_purchase_foc, "purchase_foc.csv", "text/csv")
        else:
            st.info("No purchase FOC data available.")

        st.markdown("---")

        # ---- Purchase FOC Monthly ----
        st.markdown("### 📈 Purchase FOC Monthly Trend")
        if not foc_purchase_monthly.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=foc_purchase_monthly['Month_Label'],
                y=foc_purchase_monthly['Total_FOC_Qty'],
                name='Purchase FOC Qty',
                marker=dict(color='#22c55e', opacity=0.7),
                text=foc_purchase_monthly['Total_FOC_Qty'].apply(lambda x: f'{x:,.0f}'),
                textposition='outside',
                textfont=dict(size=8)
            ))
            fig.add_trace(go.Scatter(
                x=foc_purchase_monthly['Month_Label'],
                y=foc_purchase_monthly['FOC_Percentage'],
                name='FOC %',
                yaxis='y2',
                mode='lines+markers',
                line=dict(color='#f59e0b', width=2, dash='dot'),
                marker=dict(size=6, color='#f59e0b')
            ))
            fig.update_layout(
                title='Monthly Purchase FOC Trend',
                height=350,
                template='plotly_dark',
                xaxis=dict(tickangle=-45, tickfont=dict(size=8)),
                yaxis=dict(title='FOC Qty', tickformat=',.0f'),
                yaxis2=dict(title='FOC %', overlaying='y', side='right', tickformat='.1f'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                margin=dict(l=20, r=60, t=40, b=60)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No purchase FOC monthly data available.")

        st.markdown("---")

        # ---- FOC Outliers ----
        st.markdown("### ⚠️ FOC Outliers")
        if not foc_outliers.empty:
            st.warning(f"Found {len(foc_outliers)} FOC outliers that may require investigation.")
            
            display_outliers = foc_outliers.copy()
            display_outliers['Sale_Date'] = pd.to_datetime(display_outliers['Sale_Date']).dt.strftime('%Y-%m-%d')
            for col in ['Quantity', 'Free_Qty', 'Amount_USD']:
                if col in display_outliers.columns:
                    display_outliers[col] = display_outliers[col].apply(lambda x: f'{x:,.0f}')
            col_rename = {
                'Sale_Date': 'Date',
                'Branch': 'Branch',
                'Item_Code': 'Item Code',
                'Item_Name': 'Item Name',
                'Quantity': 'Quantity',
                'Free_Qty': 'Free Qty',
                'Amount_USD': 'Amount',
                'anomaly_type': 'Anomaly Type'
            }
            display_outliers = display_outliers.rename(columns={k: v for k, v in col_rename.items() if k in display_outliers.columns})
            st.dataframe(display_outliers, use_container_width=True, height=300, hide_index=True)
            csv_outliers = foc_outliers.to_csv(index=False)
            st.download_button("📥 Download FOC Outliers", csv_outliers, "foc_outliers.csv", "text/csv")
        else:
            st.success("✅ No FOC outliers found!")

        st.markdown("---")

        # ---- FOC Recommendations ----
        st.markdown("### 💡 FOC Recommendations")
        if not foc_recommendations.empty:
            critical = foc_recommendations[foc_recommendations['FOC_Severity'] == 'CRITICAL - Review Pricing']
            high = foc_recommendations[foc_recommendations['FOC_Severity'] == 'HIGH - Monitor Closely']
            medium = foc_recommendations[foc_recommendations['FOC_Severity'] == 'MEDIUM - Track Trends']
            
            if not critical.empty:
                st.markdown("#### 🔴 Critical - Review Pricing Strategy")
                st.dataframe(critical[['Item_Code', 'Item_Name', 'Branch', 'Total_FOC_Qty', 'FOC_Pct']].head(10), 
                           use_container_width=True, hide_index=True,
                           column_config={
                               'Item_Code': 'Item Code',
                               'Item_Name': 'Item Name',
                               'Branch': 'Branch',
                               'Total_FOC_Qty': 'FOC Qty',
                               'FOC_Pct': 'FOC %'
                           })
            
            if not high.empty:
                st.markdown("#### 🟡 High FOC - Monitor Closely")
                st.dataframe(high[['Item_Code', 'Item_Name', 'Branch', 'Total_FOC_Qty', 'FOC_Pct']].head(10),
                           use_container_width=True, hide_index=True,
                           column_config={
                               'Item_Code': 'Item Code',
                               'Item_Name': 'Item Name',
                               'Branch': 'Branch',
                               'Total_FOC_Qty': 'FOC Qty',
                               'FOC_Pct': 'FOC %'
                           })
            
            if not medium.empty:
                st.markdown("#### 🟠 Medium FOC - Track Trends")
                st.dataframe(medium[['Item_Code', 'Item_Name', 'Branch', 'Total_FOC_Qty', 'FOC_Pct']].head(10),
                           use_container_width=True, hide_index=True,
                           column_config={
                               'Item_Code': 'Item Code',
                               'Item_Name': 'Item Name',
                               'Branch': 'Branch',
                               'Total_FOC_Qty': 'FOC Qty',
                               'FOC_Pct': 'FOC %'
                           })
            
            csv_recommendations = foc_recommendations.to_csv(index=False)
            st.download_button("📥 Download FOC Recommendations", csv_recommendations, "foc_recommendations.csv", "text/csv")
        else:
            st.info("No FOC recommendations available.")
        
        # ---- NEW: FOC Impact Analysis ----
        if st.session_state.show_advanced_analytics and not foc_demand_impact.empty:
            st.markdown("---")
            st.markdown("### 📊 FOC Impact Analysis")
            
            col1, col2 = st.columns(2)
            with col1:
                # FOC Trend with Moving Average
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=foc_demand_impact['Month_Label'],
                    y=foc_demand_impact['FOC_Pct'],
                    mode='lines+markers',
                    name='FOC %',
                    line=dict(color='#8b5cf6', width=2),
                    marker=dict(size=6, color='#8b5cf6')
                ))
                fig.add_trace(go.Scatter(
                    x=foc_demand_impact['Month_Label'],
                    y=foc_demand_impact['FOC_MA_3'],
                    mode='lines',
                    name='3-Month MA',
                    line=dict(color='#f59e0b', width=2, dash='dash')
                ))
                fig.add_trace(go.Scatter(
                    x=foc_demand_impact['Month_Label'],
                    y=foc_demand_impact['FOC_MA_6'],
                    mode='lines',
                    name='6-Month MA',
                    line=dict(color='#22c55e', width=2, dash='dot')
                ))
                fig.update_layout(
                    title='FOC Percentage Trend with Moving Averages',
                    height=350,
                    template='plotly_dark',
                    xaxis=dict(tickangle=-45),
                    yaxis=dict(title='FOC %', tickformat='.1f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # FOC vs Revenue Impact
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=foc_demand_impact['Month_Label'],
                    y=foc_demand_impact['FOC_Revenue'],
                    name='FOC Revenue',
                    marker=dict(color='#8b5cf6', opacity=0.7)
                ))
                fig.add_trace(go.Scatter(
                    x=foc_demand_impact['Month_Label'],
                    y=foc_demand_impact['FOC_Value_Pct'],
                    name='FOC Value %',
                    yaxis='y2',
                    mode='lines+markers',
                    line=dict(color='#f59e0b', width=2),
                    marker=dict(size=6, color='#f59e0b')
                ))
                fig.update_layout(
                    title='FOC Revenue and Value Percentage',
                    height=350,
                    template='plotly_dark',
                    xaxis=dict(tickangle=-45),
                    yaxis=dict(title='FOC Revenue ($)', tickformat='$,.0f'),
                    yaxis2=dict(title='FOC Value %', overlaying='y', side='right', tickformat='.1f'),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)

# ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown(f"""
    <div class="footer">
        <div style="display: flex; justify-content: space-between; align-items: center; max-width: 1200px; margin: 0 auto; flex-wrap: wrap; gap: 8px;">
            <span>© 2026 Unique Pharma - Kinshasa, Goma & Lubumbashi</span>
            <span>Data refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            <span style="display: flex; align-items: center; gap: 12px;">
                <span class="status-dot"></span>
                <span>v11.0 · Enterprise · FOC Enabled</span>
                <span style="color: #667799;">|</span>
                <span style="color: #667799; font-size: 0.65rem;">👤 {st.session_state.username}</span>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
