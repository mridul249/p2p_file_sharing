# server.py
from flask import Flask, request, jsonify, send_from_directory
from flask_restful import Resource, Api
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import bcrypt
import os
import logging
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)
api = Api(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

DATABASE = 'database.db'
db_lock = Lock()

# Directories for storing shared files
SHARED_FILES_DIR = os.path.abspath('shared_files')
os.makedirs(SHARED_FILES_DIR, exist_ok=True)

# Initialize Database
def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Users table
        c.execute('''
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Files table
        c.execute('''
            CREATE TABLE files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                file_type TEXT,
                shared_by INTEGER,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(shared_by) REFERENCES users(user_id)
            )
        ''')
        # Ratings table
        c.execute('''
            CREATE TABLE ratings (
                rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                rating_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(file_id) REFERENCES files(file_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                UNIQUE(file_id, user_id)
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Database initialized with users, files, and ratings tables.")

# User Registration Resource
class Register(Resource):
    def post(self):
        data = request.form
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            logging.warning("Registration attempt with missing username or password.")
            return {'message': 'Username and password are required.'}, 400

        # Hash the password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        try:
            with db_lock:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
                user_id = c.lastrowid
                conn.commit()
                conn.close()
            logging.info(f"User '{username}' registered successfully with user_id {user_id}.")
            return {'message': 'User registered successfully.', 'user_id': user_id}, 201
        except sqlite3.IntegrityError:
            logging.warning(f"Registration failed: Username '{username}' already exists.")
            return {'message': 'Username already exists.'}, 400
        except Exception as e:
            logging.error(f"Registration error: {e}")
            return {'message': 'Internal server error.'}, 500

# User Login Resource
class Login(Resource):
    def post(self):
        data = request.form
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            logging.warning("Login attempt with missing username or password.")
            return {'message': 'Username and password are required.'}, 400

        try:
            with db_lock:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute("SELECT user_id, password_hash FROM users WHERE username = ?", (username,))
                user = c.fetchone()
                conn.close()

            if user and bcrypt.checkpw(password.encode('utf-8'), user[1]):
                logging.info(f"User '{username}' logged in successfully with user_id {user[0]}.")
                return {'message': 'Login successful.', 'user_id': user[0]}, 200
            else:
                logging.warning(f"Login failed for username '{username}'. Invalid credentials.")
                return {'message': 'Invalid credentials.'}, 401
        except Exception as e:
            logging.error(f"Login error: {e}")
            return {'message': 'Internal server error.'}, 500

# File Registration Resource
class RegisterFile(Resource):
    def post(self):
        # Use 'multipart/form-data' to handle file upload
        username = request.form.get('username')
        user_id = request.form.get('user_id')
        file = request.files.get('file')

        if not all([username, user_id, file]):
            logging.warning("File registration attempt with missing fields.")
            return {'message': 'Username, user_id, and file are required.'}, 400

        file_name = file.filename
        if file_name == '':
            return {'message': 'No selected file.'}, 400

        # Sanitize the file name
        file_name = os.path.basename(file_name)
        file_path = os.path.join(SHARED_FILES_DIR, file_name)

        try:
            # Save the file
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            file_type = os.path.splitext(file_name)[1].replace('.', '')

            with db_lock:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO files (file_name, file_size, file_type, shared_by)
                    VALUES (?, ?, ?, ?)
                """, (file_name, file_size, file_type, user_id))
                conn.commit()
                conn.close()
            logging.info(f"File '{file_name}' registered by user_id {user_id}.")
            return {'message': 'File registered successfully.'}, 201
        except Exception as e:
            logging.error(f"File registration error: {e}")
            return {'message': 'Internal server error.'}, 500

# File Download Resource
@app.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    try:
        with db_lock:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute("SELECT file_name FROM files WHERE file_id = ?", (file_id,))
            result = c.fetchone()
            conn.close()
        if result:
            file_name = result[0]
            return send_from_directory(SHARED_FILES_DIR, file_name, as_attachment=True)
        else:
            logging.warning(f"Download attempted for non-existent file_id {file_id}.")
            return {'message': 'File not found.'}, 404
    except Exception as e:
        logging.error(f"File download error: {e}")
        return {'message': 'Internal server error.'}, 500

# Search Files Resource
class SearchFiles(Resource):
    def get(self):
        query = request.args.get('query', '')
        file_type = request.args.get('type', '')

        try:
            with db_lock:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                sql = """
                    SELECT f.file_id, f.file_name, f.file_size, f.file_type, u.username,
                           IFNULL(AVG(r.rating), 0) as average_rating, COUNT(r.rating) as rating_count
                    FROM files f
                    JOIN users u ON f.shared_by = u.user_id
                    LEFT JOIN ratings r ON f.file_id = r.file_id
                    WHERE f.file_name LIKE ?
                """
                params = ('%' + query + '%',)

                if file_type:
                    sql += " AND f.file_type = ?"
                    params += (file_type,)

                sql += " GROUP BY f.file_id"

                c.execute(sql, params)
                results = c.fetchall()
                conn.close()

            files = []
            for row in results:
                files.append({
                    'file_id': row[0],
                    'file_name': row[1],
                    'file_size': row[2],
                    'file_type': row[3],
                    'shared_by': row[4],
                    'average_rating': round(row[5], 2),
                    'rating_count': row[6]
                })

            logging.info(f"Search performed with query='{query}' and type='{file_type}'. Found {len(files)} files.")
            return {'files': files}, 200
        except Exception as e:
            logging.error(f"Search error: {e}")
            return {'message': 'Internal server error.'}, 500

# Rate File Resource
class RateFile(Resource):
    def post(self):
        data = request.form
        file_id = data.get('file_id')
        user_id = data.get('user_id')
        rating = data.get('rating')

        if not all([file_id, user_id, rating]):
            logging.warning("Rating attempt with missing fields.")
            return {'message': 'file_id, user_id, and rating are required.'}, 400

        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                logging.warning(f"Invalid rating value: {rating}")
                return {'message': 'Rating must be between 1 and 5.'}, 400
        except ValueError:
            logging.warning(f"Invalid rating type: {rating}")
            return {'message': 'Rating must be an integer between 1 and 5.'}, 400

        try:
            with db_lock:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                # Insert or replace the rating
                c.execute("""
                    INSERT INTO ratings (file_id, user_id, rating)
                    VALUES (?, ?, ?)
                    ON CONFLICT(file_id, user_id) DO UPDATE SET rating=excluded.rating, rating_date=CURRENT_TIMESTAMP
                """, (file_id, user_id, rating))
                conn.commit()
                conn.close()
            logging.info(f"User {user_id} rated file {file_id} with {rating} stars.")
            return {'message': 'Rating submitted successfully.'}, 201
        except Exception as e:
            logging.error(f"Rating error: {e}")
            return {'message': 'Internal server error.'}, 500

# Chat Namespace Handlers
@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    room = 'chat_room'  # Using a single chat room
    join_room(room)
    emit('message', {'user': 'System', 'msg': f'{username} has joined the chat.'}, room=room)
    logging.info(f"User '{username}' joined the chat room.")

@socketio.on('leave')
def handle_leave(data):
    username = data.get('username')
    room = 'chat_room'
    leave_room(room)
    emit('message', {'user': 'System', 'msg': f'{username} has left the chat.'}, room=room)
    logging.info(f"User '{username}' left the chat room.")

@socketio.on('send_message')
def handle_send_message(data):
    username = data.get('username')
    msg = data.get('msg')
    room = 'chat_room'
    emit('message', {'user': username, 'msg': msg}, room=room)
    logging.info(f"Message from '{username}': {msg}")

# Add Resources to API
api.add_resource(Register, '/register')
api.add_resource(Login, '/login')
api.add_resource(RegisterFile, '/register_file')
api.add_resource(SearchFiles, '/search')
api.add_resource(RateFile, '/rate_file')

if __name__ == '__main__':
    init_db()
    logging.info("Starting the server with SocketIO...")
    socketio.run(app, host='0.0.0.0', port=5000)
