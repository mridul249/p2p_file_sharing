# client_streamlit.py

import streamlit as st
import requests
import socketio
import threading
import os
import logging
from datetime import datetime
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Server Configuration
DEFAULT_SERVER_URL = 'http://10.35.13.164:5000'  # Update as needed

# Directories
DOWNLOAD_DIR = os.path.abspath('downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Initialize SocketIO client
sio = socketio.Client()
chat_queue = queue.Queue()

# Session state initialization
for key in ['logged_in', 'user_id', 'username', 'chat_messages', 'connected', 'current_page', 'update_chat_started', 'server_url']:
    if key not in st.session_state:
        if key == 'server_url':
            st.session_state[key] = DEFAULT_SERVER_URL
        elif key == 'chat_messages':
            st.session_state[key] = []
        elif key == 'update_chat_started':
            st.session_state[key] = False
        elif key == 'logged_in':
            st.session_state[key] = False
        elif key == 'connected':
            st.session_state[key] = False
        else:
            st.session_state[key] = None

# SocketIO event handlers
@sio.event
def message(data):
    user = data.get('user')
    msg = data.get('msg')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] **{user}**: {msg}"
    chat_queue.put(formatted_message)
    logging.info(f"Received message: {formatted_message}")

@sio.event
def connect():
    logging.info("SocketIO connected.")
    st.session_state.connected = True
    if st.session_state.username:
        sio.emit('join', {'username': st.session_state.username})

@sio.event
def disconnect():
    logging.info("SocketIO disconnected.")
    st.session_state.connected = False

def connect_socketio(server_url, username):
    try:
        sio.connect(server_url)
        logging.info("Connected to SocketIO server.")
    except Exception as e:
        logging.error(f"Failed to connect to chat server: {e}")
        st.error("Failed to connect to chat server.")

def disconnect_socketio(username):
    try:
        sio.emit('leave', {'username': username})
        sio.disconnect()
        logging.info("Disconnected from SocketIO server.")
    except Exception as e:
        logging.error(f"Failed to disconnect from chat server: {e}")

def update_chat():
    while True:
        while not chat_queue.empty():
            msg = chat_queue.get()
            st.session_state.chat_messages.append(msg)
        sio.sleep(1)

# Apply custom CSS styling
def custom_css():
    st.markdown("""
    <style>
    /* Set background color */
    .stApp {
        background-color: #1e1e2f;
        color: #ffffff;
    }
    /* Navbar styling */
    .navbar {
        background-color: #27293d;
        padding: 1em;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .navbar button {
        color: #ffffff;
        background-color: #27293d;
        border: none;
        padding: 0.5em 1em;
        margin-right: 0.5em;
        font-weight: bold;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    .navbar button:hover {
        background-color: #3c3f58;
        border-radius: 5px;
    }
    /* Button styling */
    .stButton>button {
        color: #ffffff;
        background-color: #4a7ebc;
        border: none;
        border-radius: 5px;
        padding: 0.5em 1em;
        font-weight: bold;
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #3a6aa8;
    }
    /* Input fields */
    .stTextInput>div>div>input {
        background-color: #2e2e3e;
        color: #ffffff;
        border: 1px solid #4a4a5e;
        border-radius: 5px;
        padding: 0.5em;
    }
    /* Tabs styling */
    .stTabs [role="tablist"] button {
        color: #ffffff;
        font-weight: bold;
        background-color: #27293d;
        border: none;
        border-radius: 5px;
        padding: 0.5em 1em;
        margin-right: 0.5em;
        transition: background-color 0.3s ease;
    }
    .stTabs [role="tablist"] .stTabs-tabButton-selected {
        background-color: #4a7ebc;
    }
    /* Chat messages */
    .chat-message {
        background-color: #2e2e3e;
        padding: 0.5em;
        border-radius: 5px;
        margin-bottom: 0.5em;
    }
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #1e1e2f;
    }
    ::-webkit-scrollbar-thumb {
        background: #4a7ebc;
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #3a6aa8;
    }
    </style>
    """, unsafe_allow_html=True)

# Streamlit App
def main():
    # Set page config as the first Streamlit command
    st.set_page_config(
        page_title="P2P LAN File Sharing System",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Apply custom CSS after set_page_config
    custom_css()

    # Hide Streamlit default hamburger menu and footer
    hide_streamlit_style = """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    # Navbar Implementation
    navbar_placeholder = st.empty()
    with navbar_placeholder.container():
        cols = st.columns([1, 1, 1, 1])  # Adjust column widths as needed

        # Home Button with Emoji
        if cols[0].button("🏠 Home"):
            st.session_state.current_page = "Home"
        
        # Chat Button with Emoji
        if cols[1].button("💬 Chat"):
            st.session_state.current_page = "Chat"
        
        # Conditional Login/Register or Logout Buttons with Emojis
        if st.session_state.logged_in:
            if cols[2].button("🔒 Logout"):
                st.session_state.current_page = "Logout"
        else:
            if cols[2].button("🔑 Login"):
                st.session_state.current_page = "Login"
            if cols[3].button("📝 Register"):
                st.session_state.current_page = "Register"

    # Render the selected page
    page = st.session_state.get('current_page', 'Home')

    if page == "Home":
        if st.session_state.logged_in:
            home_page(st.session_state.server_url)
        else:
            st.error("Please log in to access this page.")
    elif page == "Chat":
        if st.session_state.logged_in:
            chat_page()
        else:
            st.error("Please log in to access this page.")
    elif page == "Login":
        login_page()
    elif page == "Register":
        register_page()
    elif page == "Logout":
        logout_page()
    else:
        st.error("Page not found.")

def register_page():
    st.header("Create a New Account")
    st.write("Fill in the details below to create a new account.")
    with st.form("register_form", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        server_url = st.text_input("Server URL", value=st.session_state.server_url)
        submit = st.form_submit_button("Register")
    if submit:
        if not username or not password:
            st.error("Please provide both username and password.")
        elif not server_url:
            st.error("Please provide the server URL.")
        else:
            # Update server_url in session_state
            st.session_state.server_url = server_url
            try:
                response = requests.post(
                    f"{st.session_state.server_url}/register",
                    data={'username': username, 'password': password}
                )
                if response.status_code == 201:
                    st.success("Registration successful. Please log in.")
                    logging.info(f"User '{username}' registered successfully.")
                    st.session_state.current_page = "Login"
                else:
                    st.error(response.json().get('message', 'Registration failed.'))
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")

def login_page():
    st.header("Welcome Back!")
    st.write("Enter your credentials to log in.")
    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        server_url = st.text_input("Server URL", value=st.session_state.server_url)
        submit = st.form_submit_button("Login")
    if submit:
        if not username or not password:
            st.error("Please provide both username and password.")
        elif not server_url:
            st.error("Please provide the server URL.")
        else:
            # Update server_url in session_state
            st.session_state.server_url = server_url
            try:
                response = requests.post(
                    f"{st.session_state.server_url}/login",
                    data={'username': username, 'password': password}
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.user_id = data['user_id']
                    st.session_state.username = username
                    st.success("Logged in successfully.")
                    logging.info(f"User '{username}' logged in.")
                    st.session_state.current_page = "Home"
                    if not st.session_state.update_chat_started:
                        threading.Thread(
                            target=connect_socketio,
                            args=(st.session_state.server_url, username),
                            daemon=True
                        ).start()
                        threading.Thread(
                            target=update_chat,
                            daemon=True
                        ).start()
                        st.session_state.update_chat_started = True
                else:
                    st.error(response.json().get('message', 'Login failed.'))
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")

def logout_page():
    disconnect_socketio(st.session_state.username)
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.chat_messages = []
    st.success("Logged out successfully.")
    logging.info("User logged out.")
    st.session_state.current_page = "Login"

def home_page(server_url):
    st.header(f"Hello, {st.session_state.username}!")
    tabs = st.tabs(["📤 Share File", "🔍 Search Files", "📁 My Shared Files"])
    with tabs[0]:
        share_file_page(server_url)
    with tabs[1]:
        search_files_page(server_url)
    with tabs[2]:
        my_shared_files_page(server_url)

def share_file_page(server_url):
    st.subheader("Share a File")
    st.write("Upload a file to share with others.")
    uploaded_file = st.file_uploader("Choose a file", type=None)
    if uploaded_file and st.button("Share File"):
        try:
            files = {
                'file': (uploaded_file.name, uploaded_file.getvalue())
            }
            data = {
                'username': st.session_state.username,
                'user_id': st.session_state.user_id
            }
            response = requests.post(
                f"{server_url}/register_file",
                data=data,
                files=files
            )
            if response.status_code == 201:
                st.success("File shared successfully.")
                logging.info(f"File '{uploaded_file.name}' shared.")
            else:
                st.error(response.json().get('message', 'Failed to share file.'))
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")

def search_files_page(server_url):
    st.subheader("Search Files")
    st.write("Find files shared by others.")
    with st.form("search_form"):
        query = st.text_input("File Name")
        file_type = st.text_input("File Type")
        submit = st.form_submit_button("Search")
    if submit:
        try:
            params = {'query': query, 'type': file_type}
            response = requests.get(f"{server_url}/search", params=params)
            if response.status_code == 200:
                files = response.json().get('files', [])
                if files:
                    for file in files:
                        display_file_info(file, server_url)
                else:
                    st.info("No files found.")
            else:
                st.error("Search failed.")
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")

def my_shared_files_page(server_url):
    st.subheader("My Shared Files")
    st.write("Manage the files you've shared.")
    try:
        params = {'query': '', 'type': ''}
        response = requests.get(f"{server_url}/search", params=params)
        if response.status_code == 200:
            files = response.json().get('files', [])
            my_files = [
                file for file in files
                if file['shared_by'] == st.session_state.username
            ]
            if my_files:
                for index, file in enumerate(my_files):
                    display_file_info(file, server_url, show_rating=False, index=index)
            else:
                st.info("You haven't shared any files yet.")
        else:
            st.error("Failed to retrieve your files.")
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")

def display_file_info(file, server_url, show_rating=False, index=None):
    with st.container():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**Name:** {file['file_name']}")
            st.markdown(f"**Size:** {file['file_size']} bytes")
            st.markdown(f"**Type:** {file['file_type']}")
            st.markdown(f"**Shared by:** {file['shared_by']}")
        with col2:
            download_url = f"{server_url}/download/{file['file_id']}"
            try:
                file_response = requests.get(download_url)
                if file_response.status_code == 200:
                    # Use index to ensure unique key
                    if index is not None:
                        key = f"download_{file['file_id']}_{index}"
                    else:
                        key = f"download_{file['file_id']}_{file['file_name']}"
                    st.download_button(
                        label="Download",
                        data=file_response.content,
                        file_name=file['file_name'],
                        key=key  # Unique key
                    )
                else:
                    st.error("Failed to download file.")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
        st.markdown("---")

def chat_page():
    st.header("💬 Chat Room")
    st.write("Connect with others in the network.")
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_messages[-50:]:
            st.markdown(f"<div class='chat-message'>{msg}</div>", unsafe_allow_html=True)
    new_message = st.text_input("Your message", key="chat_input")
    if st.button("Send"):
        if st.session_state.connected:
            if new_message.strip():
                try:
                    sio.emit('send_message', {
                        'username': st.session_state.username,
                        'msg': new_message
                    })
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    formatted_message = f"[{timestamp}] **{st.session_state.username}**: {new_message}"
                    st.session_state.chat_messages.append(formatted_message)
                    logging.info(f"Message sent: {new_message}")
                except Exception as e:
                    st.error(f"Failed to send message: {e}")
            else:
                st.warning("Cannot send empty message.")
        else:
            st.error("Not connected to the chat server.")
    if not st.session_state.update_chat_started:
        threading.Thread(target=update_chat, daemon=True).start()
        st.session_state.update_chat_started = True

if __name__ == "__main__":
    main()
