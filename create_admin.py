from flask import Flask
from app.models import Utilisateur, RoleUtilisateur
from app.extensions import db, bcrypt


def create_default_admin():
    """Créer automatiquement l'admin principal s'il n'existe pas."""

    # Vérifier s'il existe déjà un admin principal
    admin = Utilisateur.query.filter_by(role=RoleUtilisateur.ADMIN_PRINCIPAL).first()

    if not admin:
        hash_pw = bcrypt.generate_password_hash("123").decode("utf-8")

        admin = Utilisateur(
            email="oumouklethoumballacherif@gmail.com",
            nom_complet="Admin Principal",
            mot_de_passe_hash=hash_pw,
            role=RoleUtilisateur.ADMIN_PRINCIPAL,
            actif=True,
            email_confirme=True
        )

        db.session.add(admin)
        db.session.commit()

        print("✔ Admin principal créé automatiquement.")
    else:
        print("ℹ Admin principal existe déjà.")


def create_app():
    app = Flask(__name__)
    
    # --- initialisation extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    
    # --- création des tables + admin ---
    with app.app_context():
        db.create_all()
        create_default_admin()

    return app
