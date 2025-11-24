from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import login_required, current_user
from app.enseignant import enseignant_bp
from app.models import Departement, Matiere, Filiere, SeanceCours, AnneeFormation, Enseignant, Utilisateur, RoleUtilisateur, EnseignantFiliere, AffectationMatiere, TypeSeance, db
from datetime import datetime
import secrets
from sqlalchemy.orm import joinedload


@enseignant_bp.route("/dashboard")
@login_required
def dashboard():
    # Vérifie que c'est bien un enseignant
    if current_user.role.value != "enseignant":
        flash("Accès interdit", "danger")
        return redirect(url_for("auth.login"))
    
    # Ici tu peux ajouter des données dynamiques à afficher
    return render_template("dashboard_enseignant.html", enseignant=current_user)

# -----------------------------
# GESTION DES COURS
# -----------------------------

