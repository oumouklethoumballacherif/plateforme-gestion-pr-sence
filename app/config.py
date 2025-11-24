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
    MAIL_USERNAME = "oumaimajabrane2001@gmail.com"
    MAIL_PASSWORD = "iqda rrci viks ptpe"
    MAIL_DEFAULT_SENDER = ("Université", "oumaimajabrane2001@gmail.com")