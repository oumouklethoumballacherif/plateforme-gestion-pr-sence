from flask import Blueprint


# Création du Blueprint d'authentification
auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="templates/auth")

from . import routes  # importer les routes à la fin pour éviter les import circul