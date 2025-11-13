from flask import Blueprint


chef_bp = Blueprint('chef', __name__, url_prefix='/chef', template_folder='templates/chef')

from . import routes