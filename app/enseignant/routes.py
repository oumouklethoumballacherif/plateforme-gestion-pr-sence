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

@enseignant_bp.route("/cours", methods=["GET", "POST"])
@login_required
def manage_cours():
    departement_id = current_user.enseignant_profil.departement_id
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()

    # Charger les matières avec la relation complète pour éviter les erreurs
    matieres = Matiere.query.options(
        joinedload(Matiere.annee_formation).joinedload(AnneeFormation.filiere)
    ).join(AnneeFormation).filter(AnneeFormation.filiere.has(departement_id=departement_id)).all()

    if request.method == "POST":
        matiere_id = request.form.get("matiere_id")
        type_seance = request.form.get("type_seance")
        date_prevue = request.form.get("date_prevue")
        duree = request.form.get("duree_minutes")

        qr_token = secrets.token_urlsafe(16)
        matiere = Matiere.query.get(matiere_id)
        if not matiere:
            flash("Matière introuvable.", "danger")
            return redirect(url_for("chef.manage_cours"))

        seance = SeanceCours(
            matiere_id=matiere_id,
            enseignant_id=current_user.enseignant_profil.id,
            filiere_id=matiere.annee_formation.filiere.id if matiere.annee_formation and matiere.annee_formation.filiere else None,
            type_seance=TypeSeance[type_seance],
            date_prevue=datetime.strptime(date_prevue, "%Y-%m-%d %H:%M"),
            duree_minutes=duree,
            qr_token=qr_token
        )
        db.session.add(seance)
        db.session.commit()
        flash("Cours créé avec succès.", "success")
        return redirect(url_for("chef.manage_cours"))

    return render_template("cours.html", matieres=matieres, filieres=filieres)

# -----------------------------
# Démarrer un cours (QR Code)
# -----------------------------
@enseignant_bp.route("/start_cours/<int:matiere_id>")
@login_required
def start_cours(matiere_id):
    seance = SeanceCours.query.filter_by(
        matiere_id=matiere_id,
        enseignant_id=current_user.enseignant_profil.id
    ).first()

    if not seance:
        flash("Cours introuvable.", "danger")
        return redirect(url_for("chef.manage_cours"))

    seance.active = True
    db.session.commit()
    return render_template("qr_code.html", seance=seance)

# -----------------------------
# Modifier un cours
# -----------------------------
@enseignant_bp.route("/edit_cours/<int:matiere_id>", methods=["GET", "POST"])
@login_required
def edit_cours(matiere_id):
    seance = SeanceCours.query.filter_by(
        matiere_id=matiere_id,
        enseignant_id=current_user.enseignant_profil.id
    ).first()

    if request.method == "POST":
        seance.date_prevue = datetime.strptime(request.form.get("date_prevue"), "%Y-%m-%d %H:%M")
        seance.duree_minutes = request.form.get("duree_minutes")
        db.session.commit()
        flash("Cours modifié avec succès.", "success")
        return redirect(url_for("chef.manage_cours"))

    return render_template("edit_cours.html", seance=seance)

# -----------------------------
# Supprimer un cours
# -----------------------------
@enseignant_bp.route("/delete_cours/<int:matiere_id>")
@login_required
def delete_cours(matiere_id):
    seance = SeanceCours.query.filter_by(
        matiere_id=matiere_id,
        enseignant_id=current_user.enseignant_profil.id
    ).first()

    if seance:
        db.session.delete(seance)
        db.session.commit()
        flash("Cours supprimé avec succès.", "success")

    return redirect(url_for("chef.manage_cours"))

@enseignant_bp.route("/presences", methods=["GET", "POST"])
@login_required
def view_presences():
    """
    Permet au Chef de département de consulter les présences des étudiants
    avec filtres (filière, matière, type de cours, date).
    """
    departement_id = current_user.enseignant_profil.departement_id

    # Charger les données de base pour les filtres
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()
    matieres = Matiere.query.options(
        joinedload(Matiere.annee_formation).joinedload(AnneeFormation.filiere)
    ).join(AnneeFormation).filter(AnneeFormation.filiere.has(departement_id=departement_id)).all()

    # Récupération des paramètres de filtre
    filiere_id = request.form.get("filiere_id")
    matiere_id = request.form.get("matiere_id")
    date_filtre = request.form.get("date_filtre")

    # Requête de base
    query = SeanceCours.query.join(Matiere).join(Filiere).filter(
        Filiere.departement_id == departement_id
    )

    # Appliquer les filtres
    if filiere_id and filiere_id != "all":
        query = query.filter(SeanceCours.filiere_id == filiere_id)

    if matiere_id and matiere_id != "all":
        query = query.filter(SeanceCours.matiere_id == matiere_id)

    if date_filtre:
        try:
            date_parsed = datetime.strptime(date_filtre, "%Y-%m-%d").date()
            query = query.filter(db.func.date(SeanceCours.date_prevue) == date_parsed)
        except ValueError:
            flash("Format de date invalide.", "warning")

    # Récupération des séances filtrées
    seances = query.order_by(SeanceCours.date_prevue.desc()).all()

    return render_template(
        "view_presences.html",
        filieres=filieres,
        matieres=matieres,
        seances=seances,
        selected_filiere=filiere_id,
        selected_matiere=matiere_id,
        selected_date=date_filtre
    )


@enseignant_bp.route("/statistics")
@login_required
def view_statistics():
    enseignant = getattr(current_user, "enseignant_profil", None)
    if not enseignant:
        flash("Profil enseignant incomplet.", "warning")
        return redirect(url_for("auth.login"))

    # Exemple : récupérer les matières de l'enseignant
    matieres = [aff.matiere for aff in enseignant.affectations_matieres]
    return render_template("enseignant/statistics.html", matieres=matieres)

