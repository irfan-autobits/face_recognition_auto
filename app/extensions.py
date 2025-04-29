# app/extensions.py
from flask_socketio import SocketIO

# Create it once, no app bound yet
socketio = SocketIO(cors_allowed_origins="*")
