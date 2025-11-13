from flask import Blueprint


chef_filiere_bp = Blueprint('chef_filiere', __name__, url_prefix='/chef_filiere', template_folder='templates/chef_filiere')

from . import routes