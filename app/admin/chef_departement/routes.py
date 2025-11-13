from flask import Blueprint, render_template, flash, redirect,  request, url_for, abort
from flask_login import login_required, current_user
from app.models import Departement, Matiere, Filiere, SeanceCours, AnneeFormation, Enseignant, Utilisateur, RoleUtilisateur, EnseignantFiliere, AffectationMatiere, TypeSeance, db
from app.extensions import bcrypt, mail
from sqlalchemy.orm import joinedload
from app.admin.chef_departement import chef_bp
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from functools import wraps
import secrets
from sqlalchemy.orm import joinedload



@chef_bp.route("/dashboard")
@login_required
def dashboard():
    role = getattr(current_user.role, "value", None) or getattr(current_user.role, "name", None)
    if role != "chef_departement":
        flash("Accès réservé au chef de département.", "warning")
        return redirect(url_for("auth.login"))  # ✅ pas redirect_dashboard

    departement_id = getattr(current_user.enseignant_profil, "departement_id", None)
    if not departement_id:
        flash("Profil enseignant incomplet. Contactez l'administrateur.", "danger")
        return redirect(url_for("auth.login"))  # ✅ pas redirect_dashboard

    filieres = Filiere.query.filter_by(departement_id=departement_id).all()

    matieres = (
        Matiere.query.options(
            joinedload(Matiere.annee_formation).joinedload(AnneeFormation.filiere)
        )
        .join(AnneeFormation)
        .filter(AnneeFormation.filiere.has(departement_id=departement_id))
        .all()
    )

    return render_template("dashboard_chef_departement.html", filieres=filieres, matieres=matieres)

# -----------------------------
# FILIÈRES
# -----------------------------
@chef_bp.route("/filieres", methods=["GET", "POST"])
@login_required
def manage_filieres():
    departement_id = current_user.enseignant_profil.departement_id
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()

    if request.method == "POST":
        nom = request.form.get("nom")
        code = request.form.get("code")
        if nom:
            filiere = Filiere(nom=nom, code=code, departement_id=departement_id)
            db.session.add(filiere)
            db.session.commit()
            flash(f"Filière {nom} ajoutée avec succès.", "success")
            return redirect(url_for("chef.manage_filieres"))

    return render_template("filieres.html", filieres=filieres)

# Modifier une filière
@chef_bp.route("/filieres/<int:filiere_id>/edit", methods=["GET", "POST"])
@login_required
def edit_filiere(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)
    if request.method == "POST":
        filiere.nom = request.form.get("nom")
        filiere.code = request.form.get("code")
        db.session.commit()
        flash("Filière mise à jour avec succès ✅", "success")
        return redirect(url_for("chef.manage_filieres"))
    return render_template("edit_filiere.html", filiere=filiere)

# Supprimer une filière
@chef_bp.route("/filieres/<int:filiere_id>/delete")
@login_required
def delete_filiere(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)
    db.session.delete(filiere)
    db.session.commit()
    flash("Filière supprimée avec succès 🗑️", "success")
    return redirect(url_for("chef.manage_filieres"))

# -----------------------------
# Affecter Enseignants aux filières
# -----------------------------
@chef_bp.route("/assign_teacher_filiere", methods=["GET", "POST"])
@login_required
def assign_teacher_filiere():
    chef = current_user.enseignant_profil
    if not chef or not chef.est_chef_departement:
        flash("Accès réservé au chef de département.", "danger")
        return redirect(url_for("auth.redirect_dashboard"))

    departement_id = chef.departement_id
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()
    enseignants = Enseignant.query.filter_by(departement_id=departement_id).all()

    # ✅ POST : affecter un enseignant à une filière
    if request.method == "POST":
        filiere_id = request.form.get("filiere_id")
        enseignant_id = request.form.get("enseignant_id")

        exist = EnseignantFiliere.query.filter_by(
            filiere_id=filiere_id, enseignant_id=enseignant_id
        ).first()

        if exist:
            flash("Cet enseignant est déjà affecté à cette filière.", "warning")
        else:
            affectation = EnseignantFiliere(filiere_id=filiere_id, enseignant_id=enseignant_id)
            db.session.add(affectation)
            db.session.commit()
            flash("Enseignant affecté avec succès ✅", "success")

        return redirect(url_for("chef.assign_teacher_filiere"))

    # 🔍 GET : afficher toutes les affectations existantes
    affectations = (
        db.session.query(EnseignantFiliere, Enseignant, Filiere)
        .join(Enseignant, Enseignant.id == EnseignantFiliere.enseignant_id)
        .join(Filiere, Filiere.id == EnseignantFiliere.filiere_id)
        .filter(Filiere.departement_id == departement_id)
        .all()
    )

    return render_template(
        "assign_teacher_filiere.html",
        filieres=filieres,
        enseignants=enseignants,
        affectations=affectations,
    )
@chef_bp.route("/delete_affectation/<int:affectation_id>", methods=["POST"])
@login_required
def delete_affectation(affectation_id):
    chef = current_user.enseignant_profil
    if not chef or not chef.est_chef_departement:
        flash("Accès réservé au chef de département.", "danger")
        return redirect(url_for("auth.redirect_dashboard"))

    affectation = EnseignantFiliere.query.get_or_404(affectation_id)

    # 🔒 Vérifie que la filière appartient au même département
    if affectation.filiere.departement_id != chef.departement_id:
       abort(403)

    db.session.delete(affectation)
    db.session.commit()
    flash("Affectation supprimée avec succès 🗑️", "success")

    return redirect(url_for("chef.assign_teacher_filiere"))


@chef_bp.route("/departement/enseignants")
@login_required
def enseignants_du_departement():
    chef = current_user.enseignant_profil
    if not chef or not chef.est_chef_departement:
        flash("Accès non autorisé.", "danger")
        return redirect(url_for("auth.login"))

    enseignants = Enseignant.query.filter_by(departement_id=chef.departement_id).all()
    return render_template("enseignants_departement.html", enseignants=enseignants)


# -----------------------------
# GESTION DES COURS
# -----------------------------
@chef_bp.route("/cours", methods=["GET", "POST"])
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
@chef_bp.route("/start_cours/<int:matiere_id>")
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
@chef_bp.route("/edit_cours/<int:matiere_id>", methods=["GET", "POST"])
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
@chef_bp.route("/delete_cours/<int:matiere_id>")
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

@chef_bp.route("/presences", methods=["GET", "POST"])
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

@chef_bp.route("/assign_chef_filiere", methods=["GET", "POST"])
@login_required
def assign_chef_filiere():
    chef = current_user.enseignant_profil
    if not chef or not chef.est_chef_departement:
        flash("Accès réservé au chef de département.", "danger")
        return redirect(url_for("auth.redirect_dashboard"))

    departement_id = chef.departement_id
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()
    enseignants = Enseignant.query.filter_by(departement_id=departement_id).all()

    if request.method == "POST":
        filiere_id = request.form.get("filiere_id")
        enseignant_id = request.form.get("enseignant_id")

        if not filiere_id or not enseignant_id:
            flash("Veuillez sélectionner une filière et un enseignant.", "warning")
            return redirect(url_for("chef.assign_chef_filiere"))

        filiere = Filiere.query.get_or_404(filiere_id)
        nouvel_ens = Enseignant.query.get_or_404(enseignant_id)

        # Vérification d’appartenance
        if nouvel_ens.departement_id != departement_id or filiere.departement_id != departement_id:
            flash("Enseignant ou filière non valide.", "danger")
            return redirect(url_for("chef.assign_chef_filiere"))

        # 🎯 --- 1) Récupérer TOUS les liens enseignants-filières ---
        liens = EnseignantFiliere.query.filter_by(filiere_id=filiere.id).all()

        # 🎯 --- 2) Rétrograder tout ancien chef ---
        for lien in liens:
            if lien.est_chef_filiere:
                lien.est_chef_filiere = False
                if lien.enseignant.utilisateur:
                    lien.enseignant.utilisateur.role = "ENSEIGNANT"
                db.session.add(lien)
        
        
        # 🎯 --- 3) Trouver ou créer le lien du nouvel enseignant ---
        nouveau_lien = EnseignantFiliere.query.filter_by(
            filiere_id=filiere.id,
            enseignant_id=nouvel_ens.id
        ).first()

        if not nouveau_lien:
            nouveau_lien = EnseignantFiliere(
                filiere_id=filiere.id,
                enseignant_id=nouvel_ens.id,
                est_chef_filiere=True
            )
            db.session.add(nouveau_lien)
        else:
            nouveau_lien.est_chef_filiere = True

        # 🎯 --- 4) Mettre rôle utilisateur ---
        if nouvel_ens.utilisateur:
            nouvel_ens.utilisateur.role = "CHEF_FILIERE"

        # 🎯 --- 5) Commit final ---
        db.session.flush()
        db.session.commit()

        flash(
            f"{nouvel_ens.utilisateur.nom_complet} est maintenant Chef de la filière {filiere.nom}.",
            "success"
        )
        return redirect(url_for("chef.assign_chef_filiere"))
    # Avant return render_template(...)
        # Créer le mapping filiere_id → chef actuel
    filiere_chef_map = {}
    for filiere in filieres:
        lien_chef = EnseignantFiliere.query.filter_by(
            filiere_id=filiere.id,
            est_chef_filiere=True
        ).first()
        filiere_chef_map[filiere.id] = lien_chef.enseignant if lien_chef else None


    return render_template("assign_chef_filiere.html", filieres=filieres, enseignants=enseignants, filiere_chef_map=filiere_chef_map)


@chef_bp.route("/liste_chefs_filieres")
@login_required
def liste_chefs_filieres():
    chef = current_user.enseignant_profil
    if not chef or not chef.est_chef_departement:
        flash("Accès réservé au chef de département.", "danger")
        return redirect(url_for("auth.redirect_dashboard"))

    departement_id = chef.departement_id
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()

    return render_template("assign_chef_filiere.html", filieres=filieres)
