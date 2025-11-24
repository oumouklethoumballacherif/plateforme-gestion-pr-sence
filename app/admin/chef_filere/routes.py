from flask import Blueprint, render_template, flash, redirect,  request, url_for, abort
from flask_login import login_required, current_user
from app.models import Departement, Matiere, Filiere, SeanceCours, AnneeFormation, Enseignant,Etudiant, Utilisateur, RoleUtilisateur, EnseignantFiliere, AffectationMatiere, TypeSeance,Presence, StatutPresence, db
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
from flask import current_app
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from app.extensions import bcrypt, mail
import pdfkit
from flask import render_template, request, send_file
from flask import make_response

import io



from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import Filiere, AnneeFormation, Semestre, Matiere, EnseignantFiliere, Etudiant

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app.models import Filiere, AnneeFormation, Semestre, Matiere, Enseignant, Etudiant, EnseignantFiliere, AffectationMatiere, SeanceCours
from app.extensions import db
from sqlalchemy.orm import joinedload
from flask import Response


@chef_filiere_bp.route("/dashboard")
@login_required
def dashboard():

    # Vérifier le rôle
    role = getattr(current_user.role, "value", None) or getattr(current_user.role, "name", None)
    if role != "chef_filiere":
        flash("Accès réservé au chef de filière.", "warning")
        return redirect(url_for("auth.login"))

    # Profil enseignant
    enseignant = current_user.enseignant_profil
    if not enseignant:
        flash("Profil enseignant introuvable.", "danger")
        return redirect(url_for("auth.login"))

    # 🔍 Trouver la filière dont il est chef via la table EnseignantFiliere
    lien_chef = EnseignantFiliere.query.filter_by(
        enseignant_id=enseignant.id,
        est_chef_filiere=True
    ).first()

    if not lien_chef:
        flash("Aucune filière associée à votre rôle de chef de filière.", "danger")
        return redirect(url_for("auth.login"))

    # La seule filière dont il est chef
    filiere = Filiere.query.get(lien_chef.filiere_id)

    # Récupérer toutes les matières de cette filière
    matieres = (
        Matiere.query
        .options(
            joinedload(Matiere.annee_formation).joinedload(AnneeFormation.filiere)
        )
        .join(AnneeFormation)
        .filter(AnneeFormation.filiere_id == filiere.id)
        .all()
    )

    # Renvoyer le template avec UNE SEULE filière
    return render_template(
        "dashboard_chef_filiere.html",
        filieres=[filiere],   # ⚠️ sous forme de liste pour la boucle Jinja
        matieres=matieres
    )





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

def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def send_email(subject, recipients, template, **kwargs):
    msg = Message(
        subject=subject,
        recipients=recipients,
        html=render_template(template, **kwargs),
        sender=current_app.config.get("MAIL_DEFAULT_SENDER", "oumaimajabrane2001@gmail.com"),
    )
    mail.send(msg)

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

    if not all([nom_complet, email, matricule, annee_id]):
        flash("Tous les champs sont obligatoires.", "danger")
        return redirect(url_for('chef_filiere.students'))

    if Utilisateur.query.filter_by(email=email).first():
        flash(f"L'email {email} existe déjà.", "warning")
        return redirect(url_for('chef_filiere.students'))

    if Etudiant.query.filter_by(matricule=matricule).first():
        flash(f"Le matricule {matricule} existe déjà.", "warning")
        return redirect(url_for('chef_filiere.students'))

    try:
        # Création de l'utilisateur sans mot de passe
        user = Utilisateur(
            email=email,
            nom_complet=nom_complet,
            mot_de_passe_hash=None,
            role=RoleUtilisateur.ETUDIANT,
            email_confirme=False
        )
        db.session.add(user)
        db.session.flush()  # Pour récupérer user.id

        # Création de l'étudiant
        etu = Etudiant(
            utilisateur_id=user.id,
            matricule=matricule,
            annee_formation_id=annee_id,
            filiere_id=filiere.id
        )
        db.session.add(etu)
        db.session.commit()

        # Envoi du mail d’activation
        token = get_serializer().dumps(email, salt="email-confirm")
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        send_email(
            subject="Activation de votre compte étudiant",
            recipients=[email],
            template="emails/confirm_email.html",
            confirm_url=confirm_url,
            user=user
        )

        flash(f"L'étudiant {nom_complet} a été ajouté et un mail d’activation a été envoyé.", "success")
        logger.info(f"Étudiant ajouté : {nom_complet} ({email})")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur add_student : {e}")
        flash("Erreur lors de l'ajout de l'étudiant ou de l'envoi de l'email.", "danger")

    return redirect(url_for('chef_filiere.students'))


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
        skipped_rows = []

        for idx, row in df.iterrows():
            nom = row.get('nom_complet')
            email = row.get('email')
            matricule = row.get('matricule')
            annee_libelle = row.get('annee_libelle')

            # Vérification des valeurs manquantes
            if pd.isna(nom) or pd.isna(email) or pd.isna(matricule) or pd.isna(annee_libelle):
                skipped_rows.append((idx+2, "Données manquantes"))  # +2 car Excel commence à 1 et header
                continue

            # Vérification doublons
            if Utilisateur.query.filter_by(email=email).first():
                skipped_rows.append((idx+2, "Email déjà existant"))
                continue

            if Etudiant.query.filter_by(matricule=matricule).first():
                skipped_rows.append((idx+2, "Matricule déjà existant"))
                continue

            # Trouver l'année
            annee = AnneeFormation.query.filter_by(libelle=annee_libelle).first()
            if not annee:
                skipped_rows.append((idx+2, f"Année introuvable : {annee_libelle}"))
                continue

            try:
                # Création utilisateur sans mot de passe
                user = Utilisateur(
                    nom_complet=nom,
                    email=email,
                    mot_de_passe_hash=None,
                    role=RoleUtilisateur.ETUDIANT,
                    email_confirme=False
                )
                db.session.add(user)
                db.session.flush()  # récupérer user.id

                # Création de l'étudiant
                etu = Etudiant(
                    utilisateur_id=user.id,
                    matricule=matricule,
                    annee_formation_id=annee.id,
                    filiere_id=filiere.id
                )
                db.session.add(etu)

                # Envoi du mail d’activation
                token = get_serializer().dumps(email, salt="email-confirm")
                confirm_url = url_for("auth.confirm_email", token=token, _external=True)
                send_email(
                    subject="Activation de votre compte étudiant",
                    recipients=[email],
                    template="emails/confirm_email.html",
                    confirm_url=confirm_url,
                    user=user
                )

                import_count += 1

            except Exception as e:
                db.session.rollback()
                skipped_rows.append((idx+2, f"Erreur DB : {e}"))
                continue

        db.session.commit()

        flash(f"{import_count} étudiants importés avec succès.", "success")
        if skipped_rows:
            messages = [f"Ligne {row[0]} : {row[1]}" for row in skipped_rows]
            flash("Certains étudiants n'ont pas été importés :<br>" + "<br>".join(messages), "warning")

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
def cours_matieres():
    selected_filiere = request.args.get('filiere', type=int)
    selected_annee = request.args.get('annee', type=int)
    selected_semestre = request.args.get('semestre', type=int)

    enseignant = Enseignant.query.filter_by(utilisateur_id=current_user.id).first()

    if enseignant:
        matieres_query = Matiere.query.join(AffectationMatiere).filter(
            AffectationMatiere.enseignant_id == enseignant.id
        )
    else:
        matieres_query = Matiere.query.filter(False)

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

    # 🔹 Filtrage dynamique
    annees = AnneeFormation.query.filter_by(filiere_id=selected_filiere).all() if selected_filiere else []
    semestres = Semestre.query.filter_by(annee_id=selected_annee).all() if selected_annee else []

    return render_template(
        'cours_matieres.html',
        matieres=matieres,
        filieres=filieres,
        annees=annees,
        semestres=semestres,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        selected_semestre=selected_semestre
    )






@chef_filiere_bp.route("/cours/<int:matiere_id>", methods=["GET", "POST"])
@login_required
def matiere_seances(matiere_id):
    # Récupérer la matière
    matiere = Matiere.query.get_or_404(matiere_id)

    # Vérifier que l'utilisateur connecté est bien un enseignant
    enseignant = Enseignant.query.filter_by(utilisateur_id=current_user.id).first()
    if not enseignant:
        flash("Vous n'êtes pas enregistré comme enseignant.", "error")
        return redirect(url_for("chef_filiere.cours_matieres"))

    # POST : création d'une nouvelle séance
    if request.method == "POST":
        type_seance = request.form.get("type_seance")
        date_prevue = request.form.get("date_prevue")
        duree_minutes = request.form.get("duree_minutes", type=int)

        if not type_seance or not date_prevue or not duree_minutes:
            flash("Veuillez remplir tous les champs.", "warning")
            return redirect(url_for("chef_filiere.matiere_seances", matiere_id=matiere.id))

        # Récupérer filière et année depuis la matière (si applicable)
        filiere_id = matiere.annee_formation.filiere.id if matiere.annee_formation and matiere.annee_formation.filiere else None
        annee_id = matiere.annee_formation.id if matiere.annee_formation else None

        # Créer la séance
        seance = SeanceCours(
            matiere_id=matiere.id,
            enseignant_id=enseignant.id,  # ID correct dans la table enseignants
            filiere_id=filiere_id,
            annee_formation_id=annee_id,
            type_seance=type_seance,
            date_prevue=datetime.fromisoformat(date_prevue),
            duree_minutes=duree_minutes,
            active=False,  # par défaut inactive
            date_creation=datetime.utcnow()
        )
        db.session.add(seance)
        db.session.commit()
        flash("Séance créée avec succès !", "success")
        return redirect(url_for("chef_filiere.matiere_seances", matiere_id=matiere.id))

    # GET : afficher toutes les séances de cet enseignant pour cette matière
    seances = SeanceCours.query.filter_by(matiere_id=matiere.id, enseignant_id=enseignant.id).all()
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

@chef_filiere_bp.route("/seance/<int:seance_id>/qr-img")
@login_required
def seance_qr_img(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)

    # QR qui change toutes les 20 secondes
    timestamp_key = int(datetime.utcnow().timestamp() // 20)
    qr_data = f"{seance.id}-{timestamp_key}"

    # Génération image
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Réponse + NO CACHE (IMPORTANT)
    response = Response(buf.getvalue(), mimetype="image/png")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


@chef_filiere_bp.route("/seance/<int:seance_id>/qr")
@login_required
def seance_qr(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)

    if not seance.active:
        flash("La séance n'est pas démarrée.", "warning")
        return redirect(url_for("chef_filiere.matiere_seances", matiere_id=seance.matiere_id))

    return render_template("seance_qr.html", seance=seance)


@chef_filiere_bp.route("/seance/<int:seance_id>/start")
@login_required
def start_seance(seance_id):
    seance = SeanceCours.query.get_or_404(seance_id)
    seance.active = True
    db.session.commit()

    return redirect(url_for("chef_filiere.seance_qr", seance_id=seance.id))

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

# historique seance 
@chef_filiere_bp.route("/historique_seance/<int:seance_id>")
@login_required
def historique_seance(seance_id):
    # Récupérer la séance
    seance = SeanceCours.query.get_or_404(seance_id)

    # Récupérer tous les étudiants de la filière et année
    etudiants = Etudiant.query.filter_by(
        filiere_id=seance.matiere.annee_formation.filiere_id,
        annee_formation_id=seance.matiere.annee_formation.id
    ).all()

    # Construire l'historique
    historique = []
    for etu in etudiants:
        presence = Presence.query.filter_by(
            etudiant_id=etu.id,
            seance_id=seance.id
        ).first()
        statut = presence.statut.value if presence else "absent"
        historique.append({
            "etudiant": etu,
            "statut": statut,
            "date_scan": presence.date_scan if presence else None
        })

    return render_template(
        "historique_seance.html",
        seance=seance,        # 🔹 Important : passer seance
        historique=historique
    )




# -----------------------------
# PRESENCES & STATS
# -----------------------------
@chef_filiere_bp.route("/get_presences/<int:seance_id>")
@login_required
def get_presences(seance_id):
    # Récupérer toutes les présences de la séance
    presences = Presence.query.filter_by(seance_id=seance_id).order_by(Presence.date_scan.asc()).all()

    # Retourner JSON avec le nom complet depuis Utilisateur et l'heure du scan
    result = [
        {
            "nom": p.etudiant.utilisateur.nom_complet,  # <-- ici on passe par utilisateur
            "heure": p.date_scan.strftime("%H:%M:%S")
        }
        for p in presences
    ]
    return jsonify(result)



#route présence:-------------
@chef_filiere_bp.route("/presences", methods=["GET"])
@login_required
def presences():
    # Filtrage des paramètres
    selected_filiere = request.args.get("filiere", type=int)
    selected_annee = request.args.get("annee", type=int)
    selected_semestre = request.args.get("semestre", type=int)
    selected_matiere = request.args.get("matiere", type=int)

    # Matières disponibles pour le chef de filière
    matieres_query = Matiere.query
    if selected_filiere:
        matieres_query = matieres_query.join(AnneeFormation).filter(AnneeFormation.filiere_id == selected_filiere)
    if selected_annee:
        matieres_query = matieres_query.filter(Matiere.annee_formation_id == selected_annee)
    if selected_semestre:
        matieres_query = matieres_query.filter(Matiere.semestre_id == selected_semestre)
    if selected_matiere:
        matieres_query = matieres_query.filter(Matiere.id == selected_matiere)

    matieres = matieres_query.all()
    matieres_ids = [m.id for m in matieres]

    # Liste des présences
    presences = Presence.query.join(SeanceCours).filter(
        SeanceCours.matiere_id.in_(matieres_ids)
    ).order_by(Presence.date_scan.desc()).all()

    # Statistiques
    total_presences = len(presences)
    total_etudiants = len({p.etudiant_id for p in presences})
    stats_par_matiere = {}
    for mat in matieres:
        pres_mat = [p for p in presences if p.seance.matiere_id == mat.id]
        stats_par_matiere[mat.titre] = {
            "total_presences": len(pres_mat),
            "etudiants_diff": len({p.etudiant_id for p in pres_mat})
        }

    # Données pour les filtres
    filieres = Filiere.query.all()
    annees = AnneeFormation.query.all()
    semestres = Semestre.query.all()

    return render_template(
        "chef_filiere_presences.html",
        presences=presences,
        filieres=filieres,
        annees=annees,
        semestres=semestres,
        matieres=matieres,
        stats_par_matiere=stats_par_matiere,
        total_presences=total_presences,
        total_etudiants=total_etudiants,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        selected_semestre=selected_semestre,
        selected_matiere=selected_matiere
    )

# ----------------- Fonction pour calculer les stats d'une matière -----------------

def calculer_stats_matiere(matiere_id, annee_id):
    etudiants_stats = []

    matiere = Matiere.query.get(matiere_id)
    if not matiere:
        return []

    filiere_id = matiere.semestre.annee.filiere.id

    # ⚡ Filtrer les étudiants par filière et année de formation
    etudiants = Etudiant.query.filter_by(filiere_id=filiere_id, annee_formation_id=annee_id).all()

    seances = SeanceCours.query.filter_by(matiere_id=matiere_id).all()
    total_CM_TD = len([s for s in seances if s.type_seance.name in ["CM", "TD"]])
    total_TP = len([s for s in seances if s.type_seance.name == "TP"])

    for etu in etudiants:
        presences = Presence.query.join(SeanceCours).filter(
            Presence.etudiant_id == etu.id,
            SeanceCours.matiere_id == matiere_id
        ).all()

        pres_CM_TD = len([p for p in presences if p.seance.type_seance.name in ["CM", "TD"] and p.statut == StatutPresence.PRESENT])
        abs_TP = len([p for p in presences if p.seance.type_seance.name == "TP" and p.statut != StatutPresence.PRESENT])

        # ⚡ Calcul de l'assiduité et du statut
        assiduite = (pres_CM_TD / total_CM_TD * 100) if total_CM_TD > 0 else 0
        note = round((assiduite / 100) * 20, 2)
        statut_etudiant = "RATTRAPAGE" if (assiduite < 25 or abs_TP >= 2) else "NORMAL"

        etudiants_stats.append({
            "etudiant": etu.utilisateur,
            "assiduite": round(assiduite, 2),
            "note": note,
            "statut": statut_etudiant
        })

    return etudiants_stats



# ----------------- Route Statistiques -----------------
# @chef_filiere_bp.route('/statistiques', methods=['GET'])
# @login_required
# def statistiques():
#     # Récupération des filtres GET
#     selected_filiere = request.args.get("filiere")
#     selected_annee = request.args.get("annee")
#     selected_semestre = request.args.get("semestre")
#     selected_matiere = request.args.get("matiere")

#     # Chargement des filières
#     filieres = Filiere.query.order_by(Filiere.nom).all()
#     if not selected_filiere and filieres:
#         selected_filiere = str(filieres[0].id)

#     # Chargement des années
#     annees = AnneeFormation.query.filter_by(filiere_id=selected_filiere).order_by(AnneeFormation.ordre).all() if selected_filiere else []
#     if not selected_annee and annees:
#         selected_annee = str(annees[0].id)

#     # Chargement des semestres
#     semestres = Semestre.query.filter_by(annee_id=selected_annee).all() if selected_annee else []
#     if not selected_semestre and semestres:
#         selected_semestre = str(semestres[0].id)

#     # Chargement des matières
#     matieres = Matiere.query.filter_by(semestre_id=selected_semestre).all() if selected_semestre else []

#     # Calcul des stats si matière sélectionnée
#     etudiants_stats = calculer_stats_matiere(selected_matiere) if selected_matiere else []

#     # Debug
#     print("---- DEBUG STATISTIQUES ----")
#     print("Filieres :", [f.id for f in filieres])
#     print("Selected Filiere:", selected_filiere)
#     print("Selected Annee :", selected_annee)
#     print("Selected Semestre:", selected_semestre)
#     print("Selected Matiere:", selected_matiere)

#     return render_template(
#         "chef_filiere_statistiques.html",
#         filieres=filieres,
#         annees=annees,
#         semestres=semestres,
#         matieres=matieres,
#         selected_filiere=selected_filiere,
#         selected_annee=selected_annee,
#         selected_semestre=selected_semestre,
#         selected_matiere=selected_matiere,
#         etudiants_stats=etudiants_stats
#     )


# ----------------- Routes JSON pour les filtres dynamiques -----------------
@chef_filiere_bp.route('/get_annees/<int:filiere_id>')
@login_required
def get_annees(filiere_id):
    annees = AnneeFormation.query.filter_by(filiere_id=filiere_id).order_by(AnneeFormation.ordre).all()
    return jsonify([{"id": a.id, "libelle": a.libelle} for a in annees])

@chef_filiere_bp.route('/get_semestres/<int:annee_id>')
@login_required
def get_semestres(annee_id):
    semestres = Semestre.query.filter_by(annee_id=annee_id).all()
    return jsonify([{"id": s.id, "libelle": s.libelle} for s in semestres])  # libelle et non nom




@chef_filiere_bp.route('/get_matieres/<int:semestre_id>')
@login_required
def get_matieres(semestre_id):
    user = current_user
    enseignant = user.enseignant_profil
    semestre = Semestre.query.get(semestre_id)
    matieres = []

    if not semestre or not enseignant:
        return jsonify([])

    # Vérifier si c'est chef de filière
    est_chef = EnseignantFiliere.query.filter_by(
        enseignant_id=enseignant.id,
        filiere_id=semestre.annee.filiere.id,
        est_chef_filiere=True
    ).first() is not None

    if est_chef:
        matieres = Matiere.query.filter_by(semestre_id=semestre_id).all()
    else:
        # Sinon seulement matières qu'il enseigne
        matieres = Matiere.query.join(AffectationMatiere).filter(
            AffectationMatiere.enseignant_id == enseignant.id,
            Matiere.semestre_id == semestre_id
        ).all()

    return jsonify([{"id": m.id, "titre": m.titre} for m in matieres])












def get_filieres_chef(user_id):
    return (
        Filiere.query
            .join(EnseignantFiliere)
            .filter(
                EnseignantFiliere.enseignant_id == user_id,
                EnseignantFiliere.est_chef_filiere == True
            ).all()
    )


def get_filieres_enseignant(user_id):
    return (
        Filiere.query
            .join(AnneeFormation)
            .join(Semestre)
            .join(Matiere)
            .join(AffectationMatiere)
            .filter(AffectationMatiere.enseignant_id == user_id)
            .distinct()
            .all()
    )

def get_filieres_accessibles(user):
    """
    Renvoie toutes les filières accessibles à l'utilisateur :
    - celles dont il est chef (est_chef_filiere=True)
    - celles où il enseigne au moins une matière
    """
    enseignant = user.enseignant_profil
    if not enseignant:
        return []

    # 1️⃣ Filières dont il est chef
    filieres_chef = Filiere.query.join(EnseignantFiliere).filter(
        EnseignantFiliere.enseignant_id == enseignant.id,
        EnseignantFiliere.est_chef_filiere == True
    )

    # 2️⃣ Filières où il enseigne
    filieres_enseignant = Filiere.query.join(AnneeFormation).join(Semestre).join(Matiere).join(AffectationMatiere).filter(
        AffectationMatiere.enseignant_id == enseignant.id
    )

    # Union + distinct
    return filieres_chef.union(filieres_enseignant).distinct().all()



def get_matieres_accessibles(user_id, semestre_id):
    semestre = Semestre.query.get(semestre_id)
    filiere = semestre.annee.filiere

    # Vérifier s'il est chef de cette filière
    est_chef = (
        EnseignantFiliere.query
            .filter_by(
                enseignant_id=user_id,
                filiere_id=filiere.id,
                est_chef_filiere=True
            ).first() is not None
    )

    if est_chef:
        # Chef → accès à TOUTES les matières de ce semestre
        return Matiere.query.filter_by(semestre_id=semestre_id).all()

    # Sinon → afficher SEULEMENT les matières qu’il enseigne
    return (
        Matiere.query
            .join(AffectationMatiere)
            .filter(
                AffectationMatiere.enseignant_id == user_id,
                Matiere.semestre_id == semestre_id
            ).all()
    )


@chef_filiere_bp.route('/statistiques', methods=['GET'])
@login_required
def statistiques():
    # ---------------- FILTRES GET ----------------
    selected_filiere = request.args.get("filiere")
    selected_annee = request.args.get("annee")
    selected_semestre = request.args.get("semestre")
    selected_matiere = request.args.get("matiere")

    # ---------------- FILIERES ACCESSIBLES ----------------
    # Le chef de filière ne voit que les filières où il est chef ou enseignant
    enseignant = current_user.enseignant_profil
    filieres = [ef.filiere for ef in enseignant.affectations_filieres]

    if not selected_filiere and filieres:
        selected_filiere = str(filieres[0].id)

    # ---------------- ANNEES ----------------
    annees = AnneeFormation.query.filter_by(filiere_id=selected_filiere).order_by(AnneeFormation.ordre).all() if selected_filiere else []
    if not selected_annee and annees:
        selected_annee = str(annees[0].id)

    # ---------------- SEMESTRES ----------------
    semestres = Semestre.query.filter_by(annee_id=selected_annee).all() if selected_annee else []
    if not selected_semestre and semestres:
        selected_semestre = str(semestres[0].id)

    # ---------------- MATIERES ----------------
    matieres = Matiere.query.filter_by(semestre_id=selected_semestre).all() if selected_semestre else []

    # ---------------- CALCUL DES STATISTIQUES ----------------
    etudiants_stats = []
    if selected_matiere and selected_annee:
        etudiants_stats = calculer_stats_matiere(int(selected_matiere), int(selected_annee))

    # ---------------- DEBUG ----------------
    print("---- DEBUG STATISTIQUES ----")
    print("Filieres:", [f.id for f in filieres])
    print("Selected Filiere:", selected_filiere)
    print("Selected Annee:", selected_annee)
    print("Selected Semestre:", selected_semestre)
    print("Selected Matiere:", selected_matiere)
    print("Nombre d'étudiants stats:", len(etudiants_stats))

    # ---------------- RENDER ----------------
    return render_template(
        "chef_filiere_statistiques.html",
        filieres=filieres,
        annees=annees,
        semestres=semestres,
        matieres=matieres,
        selected_filiere=selected_filiere,
        selected_annee=selected_annee,
        selected_semestre=selected_semestre,
        selected_matiere=selected_matiere,
        etudiants_stats=etudiants_stats
    )


