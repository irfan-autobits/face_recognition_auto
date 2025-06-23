# final-compre/config/config.py
import os
from config.paths import SECRET_KEY

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:postgres@localhost:6432/frs"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = SECRET_KEY
    HOST = 'http://localhost'
    SERV_HOST = 'http://irfan-Latitude-5490.local'
    PORT = '5757'