# final-compre/config/config.py
import os
from config.paths import SECRET_KEY, SERVING_HOST, PORT

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:postgres@localhost:6432/frs"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = SECRET_KEY
    HOST = 'http://localhost'
    SERV_HOST = f'http://{SERVING_HOST}'
    PORT = PORT