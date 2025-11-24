from flask import Blueprint


etudiant_bp  = Blueprint('etudiant', __name__, url_prefix='/etudiant', template_folder='templates/etudiant')

from . import routes

