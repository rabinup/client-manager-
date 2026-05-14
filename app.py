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
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, amount REAL, date TEXT, month_year TEXT)''')
    
    # Required columns for the Online Version
    required_columns = [
        ('phone', 'TEXT'),
        ('email', 'TEXT'),
        ('company_name', 'TEXT'),
        ('password', 'TEXT DEFAULT "1234"'),
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

# --- 2. STYLING & UTILS ---
st.set_page_config(page_title="Business Portal Online", layout="wide", page_icon="🌐")

def get_download_link(file_path, label):
    with open(file_path, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    return f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(file_path)}" style="text-decoration:none; background-color:#007bff; color:white; padding:8px 16px; border-radius:5px;">📥 Download {label}</a>'

# --- 3. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user_role': None, 'user_email': None, 'user_name': None})

# --- 4. LOGIN & REGISTRATION PORTAL ---
if not st.session_state['logged_in']:
    st.title("🛡️ Secure Business Gateway")
    tab_login, tab_reg, tab_forgot = st.tabs(["Login", "Create Account", "Forgot Password"])

    with tab_login:
        with st.form("login"):
            email_in = st.text_input("Email Address")
            pass_in = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                if email_in == "admin@company.com" and pass_in == "admin123":
                    st.session_state.update({'logged_in': True, 'user_role': 'admin', 'user_name': 'Administrator'})
                    st.rerun()
                else:
                    user_data = pd.read_sql_query("SELECT * FROM clients WHERE email=?", conn, params=(email_in,))
                    if not user_data.empty and str(user_data.iloc[0]['password']) == pass_in:
                        st.session_state.update({
                            'logged_in': True, 
                            'user_role': 'client', 
                            'user_email': email_in, 
                            'user_name': user_data.iloc[0]['name']
                        })
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

    with tab_reg:
        with st.form("register"):
            st.subheader("New Client Registration")
            r_name = st.text_input("Full Name")
            r_comp = st.text_input("Company Name")
            r_email = st.text_input("Email")
            r_phone = st.text_input("Phone")
            r_pass = st.text_input("Set Password", type="password")
            if st.form_submit_button("Register Account"):
                c.execute("INSERT INTO clients (name, email, phone, company_name, password, join_date, status) VALUES (?,?,?,?,?,?,?)",
                          (r_name, r_email, r_phone, r_comp, r_pass, datetime.now().strftime("%Y-%m-%d"), "Active"))
                conn.commit()
                st.success("Account created! You can now login.")

    with tab_forgot:
        st.write("Enter your email to request a password reset from the administrator.")
        f_email = st.text_input("Registered Email")
        if st.button("Request Reset"):
            st.info(f"Reset request logged for {f_email}. Contact admin@company.com")
    st.stop()

# --- 5. SHARED SIDEBAR ---
with st.sidebar:
    st.title("Settings")
    st.write(f"Logged in as: **{st.session_state['user_name']}**")
    if st.button("Logout"):
        st.session_state.update({'logged_in': False, 'user_role': None})
        st.rerun()
    st.divider()

# --- 6. ADMIN DASHBOARD ---
if st.session_state['user_role'] == 'admin':
    menu = st.sidebar.radio("Admin Panel", ["Home Dashboard", "Manage Clients", "Payments History"])
    
    if menu == "Home Dashboard":
        st.title("📈 Global Business Analytics")
        df = pd.read_sql_query("SELECT * FROM clients", conn)
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Projected Monthly", f"${df['monthly_fee'].sum():,.2f}")
            c2.metric("Total Revenue", f"${df['total_paid'].sum():,.2f}")
            c3.metric("Total Users", len(df))
            st.dataframe(df[['name', 'company_name', 'email', 'monthly_fee', 'status']], use_container_width=True)

    elif menu == "Manage Clients":
        names = pd.read_sql_query("SELECT name FROM clients", conn)['name'].tolist()
        sel = st.selectbox("Select Client Profile", names)
        client = pd.read_sql_query("SELECT * FROM clients WHERE name=?", conn, params=(sel,)).iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            new_fee = st.number_input("Update Monthly Fee", value=client['monthly_fee'])
            new_stat = st.selectbox("Status", ["Active", "Suspended"], index=0 if client['status']=="Active" else 1)
        with col2:
            new_file = st.file_uploader("Upload New Document for Client")
        
        if st.button("Save Profile Changes"):
            fname = new_file.name if new_file else client['file_name']
            if new_file:
                with open(os.path.join("scanned_docs", new_file.name), "wb") as f:
                    f.write(new_file.getbuffer())
            c.execute("UPDATE clients SET monthly_fee=?, status=?, file_name=? WHERE name=?", (new_fee, new_stat, fname, sel))
            conn.commit()
            st.success("Client Updated.")

# --- 7. CLIENT PORTAL ---
else:
    client = pd.read_sql_query("SELECT * FROM clients WHERE email=?", conn, params=(st.session_state['user_email'],)).iloc[0]
    st.title(f"🏢 {client['company_name']}")
    st.subheader(f"Welcome, {client['name']}")
    
    tab1, tab2 = st.tabs(["My Payments", "Security & Docs"])
    
    with tab1:
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Your Monthly Bill", f"${client['monthly_fee']:,.2f}")
        col_m2.metric("Total Paid to Date", f"${client['total_paid']:,.2f}")
        
        history = pd.read_sql_query("SELECT amount, date, month_year FROM payments WHERE client_name=?", conn, params=(client['name'],))
        st.write("### Payment History")
        st.table(history) if not history.empty else st.info("No records found.")

    with tab2:
        st.write("### 🔐 Password Manager")
        with st.expander("Change My Password"):
            new_p = st.text_input("New Password", type="password")
            if st.button("Update Password"):
                c.execute("UPDATE clients SET password=? WHERE email=?", (new_p, client['email']))
                conn.commit()
                st.success("Password changed!")

        st.divider()
        st.write("### 📂 My Shared Documents")
        if client['file_name'] and client['file_name'] != "No File":
            path = os.path.join("scanned_docs", client['file_name'])
            if os.path.exists(path):
                st.markdown(get_download_link(path, client['file_name']), unsafe_allow_html=True)
            else: st.error("File missing on server.")
        else: st.info("No documents uploaded yet.")