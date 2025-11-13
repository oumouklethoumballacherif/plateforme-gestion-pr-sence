from flask import Flask
from app.extensions import db, migrate, mail, bcrypt, login_manager, moment
from app.config import Config
from flask import Blueprint, render_template
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialiser les extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    moment.init_app(app)

    # Importer et enregistrer les blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.admin.chef_departement import chef_bp
    from app.enseignant import enseignant_bp
    from app.etudiant import etudiant_bp
    from app.admin.chef_filere import chef_filiere_bp
    

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(enseignant_bp)
    app.register_blueprint(etudiant_bp)
    app.register_blueprint(chef_bp)
    app.register_blueprint(chef_filiere_bp)



    # Page d'accueil
    @app.route("/")
    def index():
        return render_template("index.html", current_year=datetime.now().year)

    return app


