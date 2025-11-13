from flask import Blueprint


enseignant_bp  = Blueprint('enseignant', __name__, url_prefix='/enseignant', template_folder='templates/enseignant')

from . import routes

