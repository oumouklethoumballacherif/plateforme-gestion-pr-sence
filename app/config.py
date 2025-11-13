# app/config.py
import os

class Config:
    SECRET_KEY = "une_clef_secrete"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/university_presence"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Config Mail (si tu utilises Flask-Mail)
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = "balla33cherif@gmail.com"
    MAIL_PASSWORD = "jlwz amtt hveq sosk"
    MAIL_DEFAULT_SENDER = ("Université", "balla33cherif@gmail.com")