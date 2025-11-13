from functools import wraps
from flask import abort
from flask_login import current_user
from app.models import RoleUtilisateur

def role_required(*roles_autorises):
    """Décorateur générique pour restreindre l'accès selon le rôle."""
    def wrapper(view_func):
        @wraps(view_func)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles_autorises:
                abort(403)
            return view_func(*args, **kwargs)
        return decorated
    return wrapper


def admin_principal_required(view_func):
    return role_required(RoleUtilisateur.ADMIN_PRINCIPAL)(view_func)


def enseignant_required(view_func):
    return role_required(RoleUtilisateur.ENSEIGNANT,
        RoleUtilisateur.CHEF_DEPARTEMENT,
        RoleUtilisateur.CHEF_FILIERE)(view_func)


def etudiant_required(view_func):
    return role_required(RoleUtilisateur.ETUDIANT)(view_func)
