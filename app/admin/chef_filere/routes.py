from flask import Blueprint, render_template, flash, redirect,  request, url_for, abort
from flask_login import login_required, current_user
from app.models import Departement, Matiere, Filiere, SeanceCours, AnneeFormation, Enseignant,Etudiant, Utilisateur, RoleUtilisateur, EnseignantFiliere, AffectationMatiere, TypeSeance, db
from app.extensions import bcrypt, mail
from sqlalchemy.orm import joinedload
from app.admin.chef_filere import chef_filiere_bp
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from functools import wraps
import secrets
from sqlalchemy.orm import joinedload
import pandas as pd
import logging


from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import Filiere, AnneeFormation, Semestre, Matiere, EnseignantFiliere, Etudiant

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app.models import Filiere, AnneeFormation, Semestre, Matiere, Enseignant, Etudiant, EnseignantFiliere, AffectationMatiere, SeanceCours
from app.extensions import db
from sqlalchemy.orm import joinedload



@chef_filiere_bp.route("/dashboard")
@login_required
def dashboard():
    # Vérifier le rôle
    role = getattr(current_user.role, "value", None) or getattr(current_user.role, "name", None)
    if role != "chef_filiere":
        flash("Accès réservé au chef de filière.", "warning")
        return redirect(url_for("auth.login"))  # ✅ pas redirect_dashboard

    # Récupérer le département du chef de filière
    departement_id = getattr(current_user.enseignant_profil, "departement_id", None)
    if not departement_id:
        flash("Profil enseignant incomplet. Contactez l'administrateur.", "danger")
        return redirect(url_for("auth.login"))  # ✅ pas redirect_dashboard

    # Récupérer toutes les filières du département
    filieres = Filiere.query.filter_by(departement_id=departement_id).all()

    # Récupérer toutes les matières du département
    matieres = (
        Matiere.query.options(
            joinedload(Matiere.annee_formation).joinedload(AnneeFormation.filiere)
        )
        .join(AnneeFormation)
        .filter(AnneeFormation.filiere.has(departement_id=departement_id))
        .all()
    )

    # Renvoyer le template spécifique au chef de filière
    return render_template("dashboard_chef_filiere.html", filieres=filieres, matieres=matieres)



# -----------------------------
# FORMATION (single page with tabs: années / semestres / matieres / séances)
@chef_filiere_bp.route("/<int:filiere_id>/formation")
@login_required
def formation(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)

    # Vérifier que l'utilisateur est chef de filière
    ef = EnseignantFiliere.query.filter_by(
        enseignant_id=current_user.enseignant_profil.id,
        filiere_id=filiere.id,
        est_chef_filiere=True
    ).first()
    if not ef:
        flash("Accès réservé au chef de filière pour cette filière.", "warning")
        return redirect(url_for("chef_filiere.dashboard"))

    # Charger les années avec semestres et matières
    annees = AnneeFormation.query.options(
        joinedload(AnneeFormation.semestres)
        .joinedload(Semestre.matieres)
    ).filter_by(filiere_id=filiere.id).all()

    # Charger les enseignants du département
    enseignants = Enseignant.query.filter_by(departement_id=filiere.departement_id).all()

    return render_template(
        "formation.html",
        filiere=filiere,
        annees=annees,
        enseignants=enseignants
    )

# Ajouter une année
@chef_filiere_bp.route('/<int:filiere_id>/annees/add', methods=['POST'])
@login_required
def add_annee(filiere_id):
    libelle = request.form.get('libelle')
    ordre = request.form.get('ordre', 1)
    annee = AnneeFormation(libelle=libelle, ordre=ordre, filiere_id=filiere_id)
    db.session.add(annee)
    db.session.commit()
    flash("Année ajoutée avec succès.", "success")
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))

# --- Supprimer Année ---
@chef_filiere_bp.route('/annees/<int:annee_id>/delete', methods=['POST'])
@login_required
def delete_annee(annee_id):
    annee = AnneeFormation.query.get_or_404(annee_id)
    filiere_id = annee.filiere_id
    db.session.delete(annee)
    db.session.commit()
    flash("Année supprimée.", "success")
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))

# Ajouter un semestre
@chef_filiere_bp.route('/semestres/<int:annee_id>/add', methods=['POST'])
@login_required
def add_semestre(annee_id):
    libelle = request.form.get('libelle')
    semestre = Semestre(libelle=libelle, annee_id=annee_id)
    db.session.add(semestre)
    db.session.commit()
    flash("Semestre ajouté avec succès.", "success")
    # On récupère la filière pour le redirect
    filiere_id = Semestre.query.get(semestre.id).annee.filiere_id
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))


# --- Supprimer Semestre ---
@chef_filiere_bp.route('/semestres/<int:semestre_id>/delete', methods=['POST'])
@login_required
def delete_semestre(semestre_id):
    semestre = Semestre.query.get_or_404(semestre_id)
    filiere_id = semestre.annee.filiere_id
    db.session.delete(semestre)
    db.session.commit()
    flash("Semestre supprimé.", "success")
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))

# Ajouter une matière

@chef_filiere_bp.route('/matieres/<int:semestre_id>/add', methods=['POST'])
@login_required
def add_matiere(semestre_id):
    titre = request.form.get('titre')
    total_seances = int(request.form.get('total_seances') or 0)
    cm_seances = int(request.form.get('cm_seances') or 0)
    td_seances = int(request.form.get('td_seances') or 0)
    tp_seances = int(request.form.get('tp_seances') or 0)

    semestre = Semestre.query.get_or_404(semestre_id)

    # Créer la matière
    matiere = Matiere(
        titre=titre,
        total_seances=total_seances,
        cm_seances=cm_seances,
        td_seances=td_seances,
        tp_seances=tp_seances,
        semestre_id=semestre.id,
        annee_formation_id=semestre.annee_id  # correspond à l'année de formation du semestre
    )
    db.session.add(matiere)
    db.session.commit()

    flash("Matière ajoutée avec succès.", "success")
    # Redirection vers la page formation de la filière
    filiere_id = semestre.annee.filiere_id
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))

# --- Supprimer Matière ---
@chef_filiere_bp.route('/matieres/<int:matiere_id>/delete', methods=['POST'])
@login_required
def delete_matiere(matiere_id):
    matiere = Matiere.query.get_or_404(matiere_id)
    filiere_id = matiere.semestre.annee.filiere_id
    db.session.delete(matiere)
    db.session.commit()
    flash("Matière supprimée.", "success")
    return redirect(url_for('chef_filiere.formation', filiere_id=filiere_id))




# -----------------------------
# ASSIGNATIONS (affecter matières à enseignants)
# -----------------------------
@chef_filiere_bp.route('/filiere/<int:filiere_id>/assignations', methods=['GET', 'POST'])
@login_required
def assignations_filter(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)
    
    # Récupérer toutes les années de la filière
    annees = AnneeFormation.query.filter_by(filiere_id=filiere.id).order_by(AnneeFormation.ordre).all()
    semestres = []
    matieres = []

    selected_annee_id = request.form.get('annee_id', type=int)
    selected_semestre_id = request.form.get('semestre_id', type=int)

    if selected_annee_id:
        semestres = Semestre.query.filter_by(annee_id=selected_annee_id).order_by(Semestre.ordre).all()
    
    if selected_semestre_id:
        matieres = Matiere.query.filter_by(semestre_id=selected_semestre_id).all()
    
    enseignants = Enseignant.query.all()

    return render_template(
        "assignations.html",
        filiere=filiere,
        annees=annees,
        semestres=semestres,
        matieres=matieres,
        enseignants=enseignants,
        selected_annee_id=selected_annee_id,
        selected_semestre_id=selected_semestre_id
    )


@chef_filiere_bp.route('/filiere/<int:filiere_id>/assignations/add', methods=['POST'])
@login_required
def assignations_add(filiere_id):
    matiere_id = request.form.get('matiere_id', type=int)
    enseignant_id = request.form.get('enseignant_id', type=int)

    if not matiere_id or not enseignant_id:
        flash("Veuillez choisir une matière et un enseignant.", "warning")
        return redirect(url_for('chef_filiere.assignations_filter', filiere_id=filiere_id))

    # Vérifier si l'affectation existe déjà
    exist = AffectationMatiere.query.filter_by(matiere_id=matiere_id, enseignant_id=enseignant_id).first()
    if exist:
        flash("Cet enseignant est déjà affecté à cette matière.", "warning")
        return redirect(url_for('chef_filiere.assignations_filter', filiere_id=filiere_id))

    # Créer l'affectation
    affect = AffectationMatiere(matiere_id=matiere_id, enseignant_id=enseignant_id)
    db.session.add(affect)
    db.session.commit()

    flash("Enseignant affecté avec succès !", "success")
    return redirect(url_for('chef_filiere.assignations_filter', filiere_id=filiere_id))

# Modifier une affectation
@chef_filiere_bp.route('/assignation/<int:affectation_id>/edit', methods=['GET', 'POST'])
@login_required
def assignation_edit(affectation_id):
    affect = AffectationMatiere.query.get_or_404(affectation_id)
    enseignants = Enseignant.query.all()

    if request.method == 'POST':
        enseignant_id = request.form.get('enseignant_id', type=int)
        if enseignant_id:
            affect.enseignant_id = enseignant_id
            db.session.commit()
            flash("Affectation mise à jour !", "success")
            return redirect(url_for('chef_filiere.assignations_filter', filiere_id=affect.matiere.semestre.annee.filiere.id))
        else:
            flash("Veuillez choisir un enseignant.", "warning")

    return render_template("assignation_edit.html", affect=affect, enseignants=enseignants)


# Supprimer une affectation
@chef_filiere_bp.route('/assignation/<int:affectation_id>/delete', methods=['POST'])
@login_required
def assignation_delete(affectation_id):
    affect = AffectationMatiere.query.get_or_404(affectation_id)
    filiere_id = affect.matiere.semestre.annee.filiere.id
    db.session.delete(affect)
    db.session.commit()
    flash("Affectation supprimée !", "success")
    return redirect(url_for('chef_filiere.assignations_filter', filiere_id=filiere_id))




# -----------------------------
# ETUDIANTS
# -----------------------------
# -------------------------------
logger = logging.getLogger(__name__)
# -------------------------------
# Helper: récupérer la filière du chef
# -------------------------------
def get_filiere_of_chef():
    enseignant = current_user.enseignant_profil
    if not enseignant:
        return None
    ef = EnseignantFiliere.query.filter_by(
        enseignant_id=enseignant.id,
        est_chef_filiere=True
    ).first()
    if ef:
        return ef.filiere
    return None

# -------------------------------
# Liste des étudiants
# -------------------------------

@chef_filiere_bp.route('/students', methods=['GET'])
@login_required
def students():
    filiere = get_filiere_of_chef()
    if not filiere:
        flash("Aucune filière assignée pour ce chef.", "warning")
        return redirect(url_for("auth.login"))

    annees = AnneeFormation.query.filter_by(filiere_id=filiere.id).all()
    etudiants = Etudiant.query.options(
        joinedload(Etudiant.utilisateur),
        joinedload(Etudiant.annee_formation)
    ).filter_by(filiere_id=filiere.id).all()

    return render_template('students.html', filiere=filiere, annees=annees, etudiants=etudiants)

# -------------------------------
# Ajouter un étudiant
# -------------------------------
@chef_filiere_bp.route('/students/add', methods=['POST'])
@login_required
def add_student():
    filiere = get_filiere_of_chef()
    if not filiere:
        flash("Aucune filière assignée pour ce chef.", "warning")
        return redirect(url_for("auth.login"))

    nom_complet = request.form.get('nom_complet')
    email = request.form.get('email')
    matricule = request.form.get('matricule')
    annee_id = request.form.get('annee_id')

    if not (nom_complet and email and matricule and annee_id):
        flash("Tous les champs sont obligatoires.", "danger")
        return redirect(url_for('chef_filiere.students'))

    if Utilisateur.query.filter_by(email=email).first():
        flash(f"L'email {email} existe déjà.", "warning")
        return redirect(url_for('chef_filiere.students'))

    if Etudiant.query.filter_by(matricule=matricule).first():
        flash(f"Le matricule {matricule} existe déjà.", "warning")
        return redirect(url_for('chef_filiere.students'))

    try:
        user = Utilisateur(nom_complet=nom_complet, email=email, role='etudiant')
        db.session.add(user)
        db.session.flush()

        etu = Etudiant(
            utilisateur_id=user.id,
            matricule=matricule,
            annee_formation_id=annee_id,
            filiere_id=filiere.id
        )
        db.session.add(etu)
        db.session.commit()

        flash(f"L'étudiant {nom_complet} a été ajouté avec succès !", "success")
        logger.info(f"Étudiant ajouté : {nom_complet} ({email})")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur add_student : {e}")
        flash("Erreur lors de l'ajout de l'étudiant.", "danger")

    return redirect(url_for('chef_filiere.students'))

# -------------------------------
# Importation des étudiants depuis Excel
# -------------------------------
@chef_filiere_bp.route('/students/import', methods=['POST'])
@login_required
def import_students():
    filiere = get_filiere_of_chef()
    if not filiere:
        flash("Aucune filière assignée pour ce chef.", "warning")
        return redirect(url_for("auth.login"))

    file = request.files.get('excel_file')
    if not file:
        flash("Veuillez sélectionner un fichier Excel.", "danger")
        return redirect(url_for('chef_filiere.students'))

    try:
        df = pd.read_excel(file)
        required_columns = ['nom_complet', 'email', 'matricule', 'annee_libelle']
        for col in required_columns:
            if col not in df.columns:
                flash(f"Colonne manquante : {col}", "danger")
                return redirect(url_for('chef_filiere.students'))

        import_count = 0

        for _, row in df.iterrows():

            # Ignorer les lignes vides
            if pd.isna(row['nom_complet']) or pd.isna(row['email']):
                continue
            
            # Vérifier email déjà existant
            if Utilisateur.query.filter_by(email=row['email']).first():
                continue
            
            # Vérifier duplicat matricule
            if Etudiant.query.filter_by(matricule=row['matricule']).first():
                continue

            # 🔥 Trouver l'année par son libellé
            annee = AnneeFormation.query.filter_by(libelle=row['annee_libelle']).first()

            if not annee:
                flash(f"Année introuvable : {row['annee_libelle']}", "danger")
                continue

            # Création de l'utilisateur
            user = Utilisateur(
                nom_complet=row['nom_complet'],
                email=row['email'],
                role='etudiant'
            )

            db.session.add(user)
            db.session.flush()

            # Création de l'étudiant
            etu = Etudiant(
                utilisateur_id=user.id,
                matricule=row['matricule'],
                annee_formation_id=annee.id,   # 🎯 On utilise l'ID trouvé automatiquement
                filiere_id=filiere.id
            )

            db.session.add(etu)
            import_count += 1

        db.session.commit()
        flash(f"{import_count} étudiants importés avec succès.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'import : {e}", "danger")

    return redirect(url_for('chef_filiere.students'))

# -------------------------------
# Modifier un étudiant
# -------------------------------
@chef_filiere_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    filiere = get_filiere_of_chef()
    if not filiere:
        flash("Aucune filière assignée pour ce chef.", "warning")
        return redirect(url_for("auth.login"))

    etu = Etudiant.query.get_or_404(student_id)
    user = Utilisateur.query.get_or_404(etu.utilisateur_id)

    # 🔥 Récupérer les années de la filière (OBLIGATOIRE pour remplir le <select>)
    annees = AnneeFormation.query.filter_by(filiere_id=filiere.id).all()

    if request.method == 'POST':
        nom_complet = request.form.get('nom_complet')
        email = request.form.get('email')
        matricule = request.form.get('matricule')
        annee_id = request.form.get('annee_id')

        if not (nom_complet and email and matricule and annee_id):
            flash("Tous les champs sont obligatoires.", "danger")
            return redirect(url_for('chef_filiere.edit_student', student_id=student_id))

        # Vérifier email existant
        email_exist = Utilisateur.query.filter(
            Utilisateur.email == email,
            Utilisateur.id != user.id
        ).first()

        if email_exist:
            flash(f"L'utilisateur avec l'email {email} existe déjà.", "warning")
            return redirect(url_for('chef_filiere.edit_student', student_id=student_id))

        try:
            user.nom_complet = nom_complet
            user.email = email
            etu.matricule = matricule
            etu.annee_formation_id = annee_id

            db.session.commit()
            flash(f"L'étudiant {nom_complet} a été mis à jour avec succès !", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la modification : {e}", "danger")

        return redirect(url_for('chef_filiere.students'))

    return render_template(
        'edit_student.html',
        filiere=filiere,
        etu=etu,
        user=user,
        annees=annees   # 🔥 AJOUT ESSENTIEL
    )




@chef_filiere_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    filiere = get_filiere_of_chef()
    if not filiere:
        flash("Aucune filière assignée pour ce chef.", "warning")
        return redirect(url_for("auth.login"))

    etu = Etudiant.query.get_or_404(student_id)
    user = Utilisateur.query.get_or_404(etu.utilisateur_id)

    try:
        db.session.delete(etu)
        db.session.delete(user)
        db.session.commit()
        flash(f"L'étudiant {user.nom_complet} a été supprimé.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {e}", "danger")

    return redirect(url_for('chef_filiere.students'))



# ------------------------------------------------------


# -----------------------------
# COURS (chef's filiere) + teacher space (for his own other matieres)

from flask import Blueprint, render_template, request, redirect, url_for, flash,jsonify
from flask_login import login_required, current_user
from app.models import Filiere, AnneeFormation, Matiere, SeanceCours, TypeSeance
from app.extensions import db
from datetime import datetime
import uuid
import qrcode
import io
import base64

from flask import jsonify
from app.models import Semestre


# --------------------------------------------------

# --- Page filtrage matières ---
# Route pour afficher les matières avec filtres
# route chef_cours
@chef_filiere_bp.route('/matieres', methods=['GET'])
@login_required
def matieres():
    selected_filiere = request.args.get('filiere', type=int)
    selected_annee = request.args.get('annee', type=int)
    selected_semestre = request.args.get('semestre', type=int)

    # Récupérer l'enseignant lié à l'utilisateur connecté
    enseignant = Enseignant.query.filter_by(utilisateur_id=current_user.id).first()

    if enseignant:
        # Requête pour récupérer uniquement les matières affectées à cet enseignant
        matieres_query = Matiere.query.join(AffectationMatiere).filter(
            AffectationMatiere.enseignant_id == enseignant.id
        )
    else:
        # Si l'utilisateur n'est pas enseignant, ne rien retourner
        matieres_query = Matiere.query.filter(False)  # renvoie vide

    # Appliquer les filtres facultatifs
    if selected_filiere:
        matieres_query = matieres_query.join(AnneeFormation).filter(
            AnneeFormation.filiere_id == selected_filiere
        )
    if selected_annee:
        matieres_query = matieres_query.filter(Matiere.annee_formation_id == selected_annee)
    if selected_semestre:
        matieres_query = matieres_query.filter(Matiere.semestre_id == selected_semestre)

    matieres = matieres_query.all()

    filieres = Filiere.query.all()
    annees = AnneeFormation.query.all()
    semestres = Semestre.query.all()

    return render_template(
        'matieres.html',
        matieres=matieres,
        filieres=filieres,
        annees=annees,
        semestres=semestres,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        selected_semestre=selected_semestre
    )

# Route pour récupérer dynamiquement les semestres d'une année (pour ton JS)
@chef_filiere_bp.route('/get_semestres/<int:annee_id>')
@login_required
def get_semestres(annee_id):
    semestres = Semestre.query.filter_by(annee_id=annee_id).all()
    return jsonify([{'id': s.id, 'libelle': s.libelle} for s in semestres])


# --- Page séances pour une matière ---
@chef_filiere_bp.route("/cours/<int:matiere_id>", methods=["GET", "POST"])
@login_required
def matiere_seances(matiere_id):
    matiere = Matiere.query.get_or_404(matiere_id)

    if request.method == "POST":
        type_seance = request.form.get("type_seance")
        date_prevue = request.form.get("date_prevue")
        duree_minutes = request.form.get("duree_minutes", type=int)

        seance = SeanceCours(
            matiere_id=matiere.id,
            enseignant_id=current_user.id,
            type_seance=type_seance,
            date_prevue=datetime.fromisoformat(date_prevue),
            duree_minutes=duree_minutes
        )
        db.session.add(seance)
        db.session.commit()
        flash("Séance créée !", "success")
        return redirect(url_for("chef_filiere.matiere_seances", matiere_id=matiere.id))

    seances = SeanceCours.query.filter_by(matiere_id=matiere.id, enseignant_id=current_user.id).all()
    total_seances = len(seances)
    started_seances = sum(1 for s in seances if s.active)
    remaining_seances = total_seances - started_seances

    return render_template(
        "seances.html",
        matiere=matiere,
        seances=seances,
        total_seances=total_seances,
        started_seances=started_seances,
        remaining_seances=remaining_seances
    )

# --- Démarrer une séance ---
@chef_filiere_bp.route("/seance/<int:seance_id>/start")
@login_required
def start_seance(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)
    seance.active = True
    db.session.commit()
    flash("Séance démarrée.", "success")
    return redirect(url_for("chef_filiere.matiere_seances", matiere_id=seance.matiere_id))

# --- Modifier une séance ---
@chef_filiere_bp.route("/seance/<int:seance_id>/edit", methods=["GET", "POST"])
@login_required
def edit_seance(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)
    if request.method == "POST":
        seance.type_seance = request.form.get("type_seance")
        seance.date_prevue = datetime.fromisoformat(request.form.get("date_prevue"))
        seance.duree_minutes = int(request.form.get("duree_minutes"))
        db.session.commit()
        flash("Séance modifiée !", "success")
        return redirect(url_for("chef_filiere.matiere_seances", matiere_id=seance.matiere_id))
    return render_template("edit_seance.html", seance=seance)

# --- Supprimer une séance ---
@chef_filiere_bp.route("/seance/<int:seance_id>/delete", methods=["POST"])
@login_required
def delete_seance(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)
    matiere_id = seance.matiere_id
    db.session.delete(seance)
    db.session.commit()
    flash("Séance supprimée !", "success")
    return redirect(url_for("chef_filiere.matiere_seances", matiere_id=matiere_id))



# -----------------------------
# PRESENCES & STATS
# -----------------------------
@chef_filiere_bp.route("/<int:filiere_id>/presences")
@login_required
def presences(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)
    if not EnseignantFiliere.query.filter_by(enseignant_id=current_user.enseignant_profil.id, filiere_id=filiere.id, est_chef_filiere=True).first():
        abort(403)
    # for simplicity, we'll load seances with presences — tailor as needed
    seances = SeanceCours.query.filter_by(filiere_id=filiere.id).order_by(SeanceCours.date_prevue.desc()).all()
    return render_template("chef_filiere/presences.html", filiere=filiere, seances=seances)


@chef_filiere_bp.route("/<int:filiere_id>/stats")
@login_required
def stats(filiere_id):
    filiere = Filiere.query.get_or_404(filiere_id)
    if not EnseignantFiliere.query.filter_by(enseignant_id=current_user.enseignant_profil.id, filiere_id=filiere.id, est_chef_filiere=True).first():
        abort(403)
    # calculate aggregated stats — placeholder values; implement real logic
    matieres = Matiere.query.join(AnneeFormation).filter(AnneeFormation.filiere_id==filiere.id).all()
    # attach placeholders for template
    for m in matieres:
        m.total_present = 0
        m.total_absent = 0
        m.rattrapage_count = 0
    return render_template("stats.html", filiere=filiere, matieres=matieres)


# -----------------------------
# Teacher space (enseignant features, for current_user)
# -----------------------------
@chef_filiere_bp.route("/teacher_space")
@login_required
def teacher_space():
    # shows exactly what an enseignant can do for his own matieres (in any filiere)
    ens = current_user.enseignant_profil
    if not ens:
        abort(403)
    # matieres affectées to this enseignant
    affectations = ens.affectations_matieres
    return render_template("teacher_space.html", affectations=affectations)