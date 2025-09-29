import json
import streamlit as st
from pathlib import Path
import hashlib
import pandas as pd
from datetime import datetime, timedelta
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

def init_auth():
    # Initialize session states
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
    if 'password_reset_requests' not in st.session_state:
        st.session_state.password_reset_requests = {}
    
    # Set page config with logo
    st.set_page_config(
        page_title="Aideas Timesheet",
        page_icon="aideas_logo.png"
    )

def load_registration_requests():
    requests_file = Path("registration_requests.json")
    if not requests_file.exists():
        requests_file.write_text(json.dumps({}))
    return json.loads(requests_file.read_text())

def save_registration_requests(requests):
    with Path("registration_requests.json").open("w") as f:
        json.dump(requests, f, indent=4)

def validate_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def load_notifications():
    notifications_file = Path("notifications.json")
    if not notifications_file.exists():
        notifications_file.write_text(json.dumps({}))
    return json.loads(notifications_file.read_text())

def save_notifications(notifications):
    with open("notifications.json", "w") as f:
        json.dump(notifications, f, indent=4)

def add_notification(username, message, notification_type="info"):
    notifications = load_notifications()
    if username not in notifications:
        notifications[username] = []
    
    notifications[username].append({
        "message": message,
        "type": notification_type,
        "timestamp": datetime.now().isoformat(),
        "read": False,
        "id": len(notifications[username])
    })
    
    save_notifications(notifications)

def delete_notification(username, notification_id):
    notifications = load_notifications()
    if username in notifications:
        notifications[username] = [n for n in notifications[username] if n["id"] != notification_id]
        save_notifications(notifications)

def mark_notification_as_read(username, notification_id):
    notifications = load_notifications()
    if username in notifications:
        for notification in notifications[username]:
            if notification["id"] == notification_id:
                notification["read"] = True
        save_notifications(notifications)

def show_notifications():
    if not st.session_state.current_user:
        return
    
    notifications = load_notifications()
    user_notifications = notifications.get(st.session_state.current_user, [])
    
    if not user_notifications:
        st.sidebar.info("No notifications")
        return
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Notifications")
    
    user_notifications.sort(key=lambda x: x["timestamp"], reverse=True)
    
    for notification in user_notifications:
        with st.sidebar.expander(
            f"{'🔵 ' if not notification['read'] else '⚪ '}{notification['message'][:30]}...",
            expanded=not notification['read']
        ):
            st.write(notification["message"])
            timestamp = datetime.fromisoformat(notification["timestamp"])
            st.caption(f"Received: {timestamp.strftime('%Y-%m-%d %H:%M')}")
            
            col1, col2 = st.columns(2)
            with col1:
                if not notification["read"]:
                    if st.button("Mark as Read", key=f"read_{notification['id']}"):
                        mark_notification_as_read(st.session_state.current_user, notification["id"])
                        st.rerun()
            with col2:
                if st.button("Delete", key=f"delete_{notification['id']}"):
                    delete_notification(st.session_state.current_user, notification["id"])
                    st.rerun()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    users_file = Path("users.json")
    if not users_file.exists():
        default_admin = {
            "100269": {
                "password": hash_password("Breakin@143"),
                "is_admin": True,
                "name": "Admin",
                "email": "admin@example.com"
            }
        }
        users_file.write_text(json.dumps(default_admin, indent=4))
    return json.loads(users_file.read_text())

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

def register_page():
    st.title("New User Registration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Full Name", key="reg_name")
        employee_id = st.text_input("Employee ID", key="reg_emp_id")
        
    with col2:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
    
    if st.button("Submit Registration Request"):
        if not all([name, employee_id, email, password, confirm_password]):
            st.error("Please fill in all fields")
            return
            
        if not validate_email(email):
            st.error("Please enter a valid email address")
            return
            
        if password != confirm_password:
            st.error("Passwords do not match")
            return
            
        requests = load_registration_requests()
        users = load_users()
        
        # Check if there's a pending request
        if employee_id in requests and requests[employee_id]["status"] == "pending":
            st.error("A registration request for this Employee ID is already pending")
            return
            
        # If request was rejected or the user was deleted, allow new registration
        if employee_id in requests and requests[employee_id]["status"] == "rejected":
            del requests[employee_id]
        
        if employee_id in users:
            st.error("An account with this Employee ID already exists")
            return
            
        requests[employee_id] = {
            "name": name,
            "email": email,
            "password": hash_password(password),
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        save_registration_requests(requests)
        st.success("Registration request submitted successfully! Please wait for admin approval.")

def cleanup_registration_requests():
    requests = load_registration_requests()
    users = load_users()
    
    # Remove registration requests for existing users
    for emp_id in list(requests.keys()):
        if emp_id in users or requests[emp_id]["status"] == "rejected":
            del requests[emp_id]
    
    save_registration_requests(requests)

def registration_requests_tab():
    st.subheader("Registration Requests")
    
    requests = load_registration_requests()
    
    if not requests:
        st.info("No pending registration requests")
        return
        
    for emp_id, request in requests.items():
        if request["status"] == "pending":
            with st.expander(f"Request from {request['name']} ({emp_id})"):
                st.write(f"Name: {request['name']}")
                st.write(f"Email: {request['email']}")
                st.write(f"Requested on: {datetime.fromisoformat(request['timestamp']).strftime('%Y-%m-%d %H:%M')}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Approve", key=f"approve_{emp_id}"):
                        users = load_users()
                        
                        users[emp_id] = {
                            "password": request["password"],
                            "is_admin": False,
                            "name": request["name"],
                            "email": request["email"]
                        }
                        
                        save_users(users)
                        
                        requests[emp_id]["status"] = "approved"
                        save_registration_requests(requests)
                        
                        add_notification(
                            emp_id,
                            "Your registration request has been approved. You can now log in.",
                            "success"
                        )
                        
                        st.success("User approved successfully")
                        st.rerun()
                
                with col2:
                    if st.button("Reject", key=f"reject_{emp_id}"):
                        requests[emp_id]["status"] = "rejected"
                        save_registration_requests(requests)
                        st.error("Request rejected")
                        st.rerun()

def login():
    login_tab, register_tab = st.tabs(["Login", "Register"])
    
    with login_tab:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image("aideas_logo.png", width=200)
        
        if st.session_state.show_forgot_password:
            request_password_reset()
            return
        
        st.title("Login")
        username = st.text_input("Employee ID", key="login_emp_id")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login"):
                users = load_users()
                if username in users and users[username]["password"] == hash_password(password):
                    st.session_state.authenticated = True
                    st.session_state.current_user = username
                    st.session_state.is_admin = users[username].get("is_admin", False)
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with col2:
            if st.button("Forgot Password"):
                st.session_state.show_forgot_password = True
                st.rerun()
    
    with register_tab:
        register_page()

def admin_panel():
    create_tab, view_tab, password_tab, reset_requests_tab, registration_tab = st.tabs([
        "Create User", "View Users", "Password Management", "Reset Requests", "Registration Requests"
    ])
    
    with create_tab:
        st.subheader("Create New User")
        
        new_username = st.text_input("Employee ID", key="create_emp_id")
        new_name = st.text_input("Full Name", key="create_name")
        new_email = st.text_input("Email", key="create_email")
        new_password = st.text_input("Password", type="password", key="create_password")
        is_admin = st.checkbox("Admin Access", key="create_admin_access")
        
        if st.button("Create User"):
            users = load_users()
            if new_username in users:
                st.error("Employee ID already exists")
            elif not all([new_username, new_name, new_email, new_password]):
                st.error("All fields are required")
            elif not validate_email(new_email):
                st.error("Please enter a valid email address")
            else:
                users[new_username] = {
                    "password": hash_password(new_password),
                    "is_admin": is_admin,
                    "name": new_name,
                    "email": new_email
                }
                save_users(users)
                st.success("User created successfully")

    with view_tab:
        st.subheader("User List")
        users = load_users()
        
        user_list = []
        for username, details in users.items():
            user_list.append({
                'Employee ID': username,
                'Name': details.get('name', 'N/A'),
                'Email': details.get('email', 'N/A'),
                'Role': 'Admin' if details.get('is_admin', False) else 'User'
            })
        
        df = pd.DataFrame(user_list)
        st.dataframe(df, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", len(user_list))
        with col2:
            st.metric("Admin Users", len([u for u in user_list if u['Role'] == 'Admin']))
        with col3:
            st.metric("Regular Users", len([u for u in user_list if u['Role'] == 'User']))
        
        st.subheader("Delete User")
        user_to_delete = st.selectbox("Select user to delete", 
                                    [u['Employee ID'] for u in user_list if u['Employee ID'] != st.session_state.current_user],
                                    key="delete_user")
        if st.button("Delete User"):
            if user_to_delete in users:
                # Delete user from users.json
                del users[user_to_delete]
                save_users(users)
                
                # Also clean up any pending registration requests for this user
                requests = load_registration_requests()
                if user_to_delete in requests:
                    del requests[user_to_delete]
                    save_registration_requests(requests)
                
                st.success(f"User {user_to_delete} deleted successfully")
                st.rerun()

    with password_tab:
        st.subheader("Change User Password")
        users = load_users()
        
        user_to_change = st.selectbox("Select user", 
                                    list(users.keys()),
                                    key="change_password_user")
        
        new_password = st.text_input("New Password", type="password", key="new_password")
        confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_password")
        
        if st.button("Change Password"):
            if not new_password or not confirm_password:
                st.error("Please enter and confirm the new password")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                users[user_to_change]["password"] = hash_password(new_password)
                save_users(users)
                st.success(f"Password changed successfully for user {user_to_change}")

    with reset_requests_tab:
        st.subheader("Password Reset Requests")
        
        current_time = datetime.now()
        for username, request_data in list(st.session_state.password_reset_requests.items()):
            request_time = datetime.fromisoformat(request_data["timestamp"])
            if current_time - request_time > timedelta(hours=24):
                del st.session_state.password_reset_requests[username]
        
        if not st.session_state.password_reset_requests:
            st.info("No pending password reset requests")
        else:
            for username, request_data in st.session_state.password_reset_requests.items():
                if request_data["status"] == "pending":
                    st.warning(f"Reset request from user: {username}")
                    request_time = datetime.fromisoformat(request_data["timestamp"])
                    time_ago = current_time - request_time
                    st.text(f"Requested {int(time_ago.total_seconds() / 60)} minutes ago")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_pass = st.text_input(f"New password for {username}", type="password", key=f"reset_{username}")
                        if st.button("Reset Password", key=f"reset_btn_{username}"):
                            if not new_pass:
                                st.error("Please enter a new password")
                            else:
                                users = load_users()
                                users[username]["password"] = hash_password(new_pass)
                                save_users(users)
                                st.session_state.password_reset_requests[username]["status"] = "completed"
                                
                                add_notification(
                                    username,
                                    f"Your password has been reset. Please log in with your new password.",
                                    "password_reset"
                                )
                                
                                st.success(f"Password reset for {username}")
                                st.rerun()
                    with col2:
                        if st.button("Dismiss Request", key=f"dismiss_{username}"):
                            del st.session_state.password_reset_requests[username]
                            add_notification(
                                username,
                                "Your password reset request has been dismissed by the admin. Please submit a new request if needed.",
                                "info"
                            )
                            st.rerun()
                    st.markdown("---")

    with registration_tab:
        registration_requests_tab()

def show_password_reset_form(location="sidebar"):
    """Show password reset form either in sidebar or main area"""
    container = st.sidebar if location == "sidebar" else st
    
    container.markdown("---")
    container.subheader("Reset Password")
    
    old_pass = container.text_input("Current Password", type="password", key=f"old_pass_{location}")
    new_pass = container.text_input("New Password", type="password", key=f"new_pass_{location}")
    confirm_pass = container.text_input("Confirm New Password", type="password", key=f"confirm_pass_{location}")
    
    if container.button("Reset Password", key=f"reset_btn_{location}"):
        users = load_users()
        current_user = st.session_state.current_user
        
        if not old_pass or hash_password(old_pass) != users[current_user]["password"]:
            container.error("Current password is incorrect")
            return False
        
        if not new_pass or not confirm_pass:
            container.error("Please enter and confirm the new password")
            return False
        
        if new_pass != confirm_pass:
            container.error("New passwords do not match")
            return False
            
        if old_pass == new_pass:
            container.error("New password must be different from current password")
            return False
        
        users[current_user]["password"] = hash_password(new_pass)
        save_users(users)
        
        add_notification(
            current_user,
            "Your password has been successfully reset.",
            "password_reset"
        )
        container.success("Password reset successfully")
        return True
    
    return False

def request_password_reset():
    st.title("Password Reset Request")
    username = st.text_input("Enter your Employee ID")
    
    if st.button("Submit Request"):
        users = load_users()
        if username in users:
            st.session_state.password_reset_requests[username] = {
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            st.success("Password reset request submitted. Please wait for admin approval.")
            st.info("You can return to login screen using the button below.")
        else:
            st.error("Employee ID not found")
    
    if st.button("Return to Login"):
        st.session_state.show_forgot_password = False
        st.rerun()

def logout():
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()

def auth_wrapper(main_app):
    init_auth()
    
    if not st.session_state.authenticated:
        login()
    else:
        logout()
        st.sidebar.write(f"Logged in as: {st.session_state.current_user}")
        
        show_notifications()
        
        if not st.session_state.is_admin:
            st.sidebar.markdown("---")
            if st.sidebar.button("🔐 Reset Password", key="show_reset_form"):
                st.session_state.show_password_reset = True
                st.rerun()
            
            if st.session_state.get('show_password_reset', False):
                st.markdown("## Reset Your Password")
                st.write("Please enter your current password and choose a new password.")
                if show_password_reset_form(location="main"):
                    st.session_state.show_password_reset = False
                    st.rerun()
                if st.button("Cancel"):
                    st.session_state.show_password_reset = False
                    st.rerun()
        
        if st.session_state.is_admin:
            tab1, tab2 = st.tabs(["Admin Panel", "Timesheet Generator"])
            with tab1:
                admin_panel()
            with tab2:
                main_app()
        else:
            main_app()
