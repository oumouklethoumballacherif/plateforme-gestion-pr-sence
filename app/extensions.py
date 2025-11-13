# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_moment import Moment

# --- Initialisation des extensions ---
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
bcrypt = Bcrypt()
moment = Moment()

login_manager = LoginManager()

# --- Configuration du gestionnaire de connexion ---
login_manager.login_view = "auth.login"          # Vue de connexion par défaut
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "warning"

# --- Fonction de chargement utilisateur pour Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    from app.models import Utilisateur
    return Utilisateur.query.get(int(user_id))



