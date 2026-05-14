import streamlit as st
import pandas as pd
import sqlite3
import os
import base64
from datetime import datetime

# --- 1. SMART DATABASE SETUP ---
def setup_database():
    conn = sqlite3.connect('clients.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, amount REAL, date TEXT, month_year TEXT)''')
    
    required_columns = [
        ('phone', 'TEXT'),
        ('password', 'TEXT DEFAULT "1234"'), # New: Password for login
        ('monthly_fee', 'REAL DEFAULT 0.0'),
        ('total_paid', 'REAL DEFAULT 0.0'),
        ('remarks', 'TEXT'),
        ('file_name', 'TEXT'),
        ('join_date', 'TEXT'),
        ('status', 'TEXT DEFAULT "Active"')
    ]
    
    for col_name, col_type in required_columns:
        try:
            c.execute(f"ALTER TABLE clients ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    return conn

conn = setup_database()
c = conn.cursor()

if not os.path.exists("scanned_docs"):
    os.makedirs("scanned_docs")

# --- 2. STYLING ---
st.set_page_config(page_title="Secure Client Portal", layout="wide", page_icon="🔒")

# Helper for download links
def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}" style="text-decoration: none; color: white; background-color: #007bff; padding: 10px 20px; border-radius: 5px;">📥 Download {file_label}</a>'
    return href

# --- 3. LOGIN LOGIC ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None
    st.session_state['username'] = None

def login_user(user, pwd):
    # Check Admin
    if user == "admin" and pwd == "admin123":
        st.session_state['logged_in'] = True
        st.session_state['user_role'] = "admin"
        st.session_state['username'] = "Admin"
        return True
    
    # Check Client Database
    df_users = pd.read_sql_query("SELECT name, phone FROM clients", conn)
    if user in df_users['name'].values:
        actual_pwd = df_users[df_users['name'] == user]['phone'].values[0]
        if pwd == str(actual_pwd):
            st.session_state['logged_in'] = True
            st.session_state['user_role'] = "client"
            st.session_state['username'] = user
            return True
    return False

# --- 4. LOGIN UI ---
if not st.session_state['logged_in']:
    st.title("🔒 Secure Login Portal")
    with st.form("login_form"):
        user = st.text_input("Username (Your Name)")
        pwd = st.text_input("Password (Phone Number)", type="password")
        if st.form_submit_button("Login"):
            if login_user(user, pwd):
                st.rerun()
            else:
                st.error("Invalid Username or Password")
    st.stop() # Stop the script here if not logged in

# --- 5. LOGGED IN AREA ---
with st.sidebar:
    st.success(f"Welcome, {st.session_state['username']}!")
    if st.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.divider()

# --- ADMIN VIEW ---
if st.session_state['user_role'] == "admin":
    choice = st.sidebar.radio("Admin Menu", ["🏠 Dashboard", "👥 All Clients", "➕ Add Client"])

    if choice == "🏠 Dashboard":
        st.title("🚀 Admin Analytics")
        df = pd.read_sql_query("SELECT * FROM clients", conn)
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Monthly Target", f"${df['monthly_fee'].sum():,.2f}")
            c2.metric("Total Collected", f"${df['total_paid'].sum():,.2f}")
            c3.metric("Total Clients", len(df))
            st.dataframe(df, use_container_width=True)

    elif choice == "👥 All Clients":
        st.title("👤 Manage Portals")
        names = pd.read_sql_query("SELECT name FROM clients", conn)['name'].tolist()
        selected = st.selectbox("Select Client to Edit", names)
        # (Insert update logic from previous version here)
        st.info("Update logic available in individual portals.")

    elif choice == "➕ Add Client":
        st.title("📝 Register New User")
        with st.form("new_u"):
            n = st.text_input("Full Name")
            p = st.text_input("Phone (will be their password)")
            f = st.number_input("Monthly Fee", min_value=0.0)
            if st.form_submit_button("Create Account"):
                c.execute("INSERT INTO clients (name, phone, monthly_fee, total_paid, join_date, status) VALUES (?,?,?,?,?,?)", 
                          (n, p, f, 0.0, datetime.now().strftime("%Y-%m-%d"), "Active"))
                conn.commit()
                st.success("Account created!")

# --- CLIENT VIEW ---
else:
    st.title(f"👋 Hello, {st.session_state['username']}")
    client_name = st.session_state['username']
    
    # Fetch ONLY this client's data
    client = pd.read_sql_query("SELECT * FROM clients WHERE name=?", conn, params=(client_name,)).iloc[0]
    history = pd.read_sql_query("SELECT amount, date, month_year FROM payments WHERE client_name=? ORDER BY date DESC", conn, params=(client_name,))

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Your Payment History")
        st.table(history) if not history.empty else st.write("No payments yet.")
        
        st.divider()
        st.subheader("Your Documents")
        if client['file_name'] and client['file_name'] != "No File":
            path = os.path.join("scanned_docs", client['file_name'])
            st.markdown(get_binary_file_downloader_html(path, "My Document"), unsafe_allow_html=True)
        else:
            st.write("No documents uploaded by admin yet.")

    with col2:
        st.metric("Your Monthly Fee", f"${client['monthly_fee']:,.2f}")
        st.metric("Total You've Paid", f"${client['total_paid']:,.2f}")
        st.info("Contact Admin to update your details or report a payment.")