from flask import Blueprint

etudiant_bp = Blueprint(
    "etudiant_bp",
    __name__,
    template_folder="templates"
)

from . import routes
