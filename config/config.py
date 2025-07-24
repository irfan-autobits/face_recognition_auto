# config/config.py
import os
from config.paths import SECRET_KEY, HOST, PORT

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:postgres@localhost:6432/frs"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = SECRET_KEY
    HOST = HOST
    PORT = PORT