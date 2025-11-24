from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app,jsonify
from flask_login import login_required, current_user,logout_user
from app.models import Departement, Matiere, Filiere, SeanceCours, AnneeFormation, Enseignant, Utilisateur, RoleUtilisateur, EnseignantFiliere, AffectationMatiere, TypeSeance, db
from app.extensions import bcrypt, mail
from flask_mail import Message
from werkzeug.utils import secure_filename
import pandas as pd
import os
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from functools import wraps
import secrets
from sqlalchemy.orm import joinedload
from app.admin import admin_bp 
from sqlalchemy.exc import IntegrityError




# ----------------------------------------------------
# Fonction utilitaire : génération de token + envoi mail
# ----------------------------------------------------
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


# ----------------------------------------------------
# Tableau de bord dynamique selon rôle
# ----------------------------------------------------
@admin_bp.route("/dashboard")
@login_required
def dashboard():
    role = getattr(current_user.role, "value", None) or getattr(current_user.role, "name", None)
    
    if role != "admin_principal":
        flash("Accès réservé à l’administrateur principal.", "warning")
        return redirect(url_for("auth.login"))  # ✅ pas redirect_dashboard
    
    return render_template("dashboard_admin_principal.html")



# ----------------------------------------------------


# GESTION DES DÉPARTEMENTS
# ----------------------------------------------------
@admin_bp.route("/departements", methods=["GET", "POST"])
@login_required
def manage_departments():
    departements = Departement.query.all()

    if request.method == "POST":
        nom = request.form.get("nom")
        code = request.form.get("code")

        if not nom:
            flash("Le nom du département est obligatoire.", "warning")
            return redirect(url_for("admin.manage_departments"))

        departement = Departement(nom=nom, code=code)
        db.session.add(departement)
        db.session.commit()
        flash(f"Département {nom} créé avec succès.", "success")
        return redirect(url_for("admin.manage_departments"))

    return render_template("departements.html", departements=departements)


@admin_bp.route("/departements/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_department(id):
    departement = Departement.query.get_or_404(id)
    if request.method == "POST":
        departement.nom = request.form.get("nom")
        departement.code = request.form.get("code")
        db.session.commit()
        flash(f"Département {departement.nom} modifié avec succès.", "success")
        return redirect(url_for("admin.manage_departments"))
    return render_template("edit_department.html", departement=departement)

@admin_bp.route("/departements/<int:id>/delete", methods=["POST"])
@login_required
def delete_department(id):
    departement = Departement.query.get_or_404(id)

    from app.models import Filiere, AnneeFormation, Matiere, SeanceCours, Presence, Etudiant, Enseignant

    # 🔥 0️⃣ SUPPRIMER LES ENSEIGNANTS LIES DIRECTEMENT AU DEPARTEMENT
    enseignants_dep = Enseignant.query.filter_by(departement_id=departement.id).all()
    for ens in enseignants_dep:
        # Supprimer toutes ses séances
        seances_ens = SeanceCours.query.filter_by(enseignant_id=ens.id).all()
        for s in seances_ens:
            Presence.query.filter_by(seance_id=s.id).delete()
            db.session.delete(s)

        # Supprimer l'utilisateur lié
        user = ens.utilisateur
        db.session.delete(ens)
        db.session.delete(user)

    # 1️⃣ Récupérer les filières du département
    filieres = Filiere.query.filter_by(departement_id=departement.id).all()

    for filiere in filieres:

        # 2️⃣ Supprimer les étudiants + présences
        etudiants = Etudiant.query.filter_by(filiere_id=filiere.id).all()
        for etu in etudiants:
            Presence.query.filter_by(etudiant_id=etu.id).delete()
            db.session.delete(etu)

        # 3️⃣ Supprimer les années + matières + séances
        annees = AnneeFormation.query.filter_by(filiere_id=filiere.id).all()
        for an in annees:

            matieres = Matiere.query.filter_by(annee_formation_id=an.id).all()
            for mat in matieres:

                seances = SeanceCours.query.filter_by(matiere_id=mat.id).all()
                for s in seances:
                    Presence.query.filter_by(seance_id=s.id).delete()
                    db.session.delete(s)

                db.session.delete(mat)

            db.session.delete(an)

        # 4️⃣ Supprimer les enseignants liés à cette filière
        enseignants_filiere = Enseignant.query.filter_by(filiere_id=filiere.id).all()
        for ens in enseignants_filiere:
            user = ens.utilisateur
            db.session.delete(ens)
            db.session.delete(user)

        # 5️⃣ Supprimer la filière
        db.session.delete(filiere)

    # 6️⃣ Supprimer le département
    db.session.delete(departement)

    db.session.commit()

    flash(f"Département {departement.nom} supprimé avec succès.", "success")
    return redirect(url_for("admin.manage_departments"))



# ----------------------------------------------------
# AJOUT / IMPORTATION DES ENSEIGNANTS
# ----------------------------------------------------
@admin_bp.route("/enseignants", methods=["GET", "POST"])
@login_required
def manage_teachers():
    enseignants = Enseignant.query.all()
    departements = Departement.query.all()

    # Ajout manuel
    if request.method == "POST" and not request.files.get("excel_file"):
        email = request.form.get("email")
        nom_complet = request.form.get("nom_complet")
        departement_id = request.form.get("departement_id")

        if not all([email, nom_complet, departement_id]):
            flash("Tous les champs sont obligatoires.", "warning")
            return redirect(url_for("admin.manage_teachers"))

        if Utilisateur.query.filter_by(email=email).first():
            flash("Cet e-mail est déjà utilisé.", "danger")
            return redirect(url_for("admin.manage_teachers"))

        # Création utilisateur sans mot de passe → enverra un mail de création
        user = Utilisateur(
            email=email,
            nom_complet=nom_complet,
            mot_de_passe_hash=None,
            role=RoleUtilisateur.ENSEIGNANT,
            email_confirme=False,
        )
        db.session.add(user)
        db.session.commit()

        enseignant = Enseignant(utilisateur_id=user.id, departement_id=departement_id)
        db.session.add(enseignant)
        db.session.commit()

        # Envoi du lien d’activation
        token = get_serializer().dumps(email, salt="email-confirm")
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        send_email(
            subject="Activation de votre compte enseignant",
            recipients=[email],
            template="emails/confirm_email.html",
            confirm_url=confirm_url,
            user=user,
        )

        flash(f"Enseignant {nom_complet} ajouté et mail d’activation envoyé.", "success")
        return redirect(url_for("admin.manage_teachers"))

    # Importation via Excel
    excel_file = request.files.get("excel_file")
    if excel_file:
        filename = secure_filename(excel_file.filename)
        filepath = os.path.join("uploads", filename)
        os.makedirs("uploads", exist_ok=True)
        excel_file.save(filepath)
        df = pd.read_excel(filepath)

        for _, row in df.iterrows():
            email = str(row["email"]).strip()
            nom = str(row["nom_complet"]).strip()
            departement_id = int(row["departement_id"])

            if Utilisateur.query.filter_by(email=email).first():
                continue

            user = Utilisateur(
                email=email,
                nom_complet=nom,
                mot_de_passe_hash=None,
                role=RoleUtilisateur.ENSEIGNANT,
                email_confirme=False,
            )
            db.session.add(user)
            db.session.commit()

            enseignant = Enseignant(utilisateur_id=user.id, departement_id=departement_id)
            db.session.add(enseignant)
            db.session.commit()

            # Envoi d’email à chaque enseignant
            token = get_serializer().dumps(email, salt="email-confirm")
            confirm_url = url_for("auth.confirm_email", token=token, _external=True)
            send_email(
                subject="Activation de votre compte enseignant",
                recipients=[email],
                template="emails/confirm_email.html",
                confirm_url=confirm_url,
                user=user,
            )

        flash("Enseignants importés avec succès et e-mails d’activation envoyés.", "success")
        return redirect(url_for("admin.manage_teachers"))

    return render_template("enseignants.html", enseignants=enseignants, departements=departements)


@admin_bp.route("/enseignants/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_teacher(id):
    enseignant = Enseignant.query.get_or_404(id)
    user = enseignant.utilisateur
    departements = Departement.query.all()

    if request.method == "POST":
        email = request.form.get("email")
        nom_complet = request.form.get("nom_complet")
        departement_id = request.form.get("departement_id")

        if Utilisateur.query.filter(Utilisateur.email == email, Utilisateur.id != user.id).first():
            flash("Cet email est déjà utilisé par un autre compte.", "danger")
            return redirect(url_for("admin.edit_teacher", id=id))

        user.email = email
        user.nom_complet = nom_complet
        enseignant.departement_id = departement_id

        db.session.commit()

        flash("Enseignant modifié avec succès.", "success")
        return redirect(url_for("admin.manage_teachers"))

    return render_template("edit_enseignant.html",
        enseignant=enseignant,
        user=user,
        departements=departements)

        #supprimer un enseignant 

@admin_bp.route("/enseignants/<int:id>/delete", methods=["POST"])
@login_required
def delete_teacher(id):
    enseignant = Enseignant.query.get_or_404(id)
    user = enseignant.utilisateur

    from app.models import SeanceCours, Presence, AffectationMatiere, EnseignantFiliere

    # 1️⃣ Supprimer les séances + présences associées
    seances = SeanceCours.query.filter_by(enseignant_id=enseignant.id).all()
    for seance in seances:
        Presence.query.filter_by(seance_id=seance.id).delete()
        db.session.delete(seance)

    # 2️⃣ Supprimer les affectations de matières
    AffectationMatiere.query.filter_by(enseignant_id=enseignant.id).delete()

    # 3️⃣ Supprimer les liens enseignant ↔ filières
    EnseignantFiliere.query.filter_by(enseignant_id=enseignant.id).delete()

    # 4️⃣ Supprimer l'enseignant
    db.session.delete(enseignant)

    # 5️⃣ Supprimer le compte utilisateur
    db.session.delete(user)

    # 6️⃣ Commit
    db.session.commit()

    flash("Enseignant supprimé avec toutes ses affectations, séances, présences et filières.", "success")
    return redirect(url_for("admin.manage_teachers"))




# ----------------------------------------------------
# AFFECTATION / RETRAIT DES CHEFS DE filiere
# ----------------------------------------------------

@admin_bp.route("/get_enseignants/<int:departement_id>")
@login_required
def get_enseignants(departement_id):
    enseignants = Enseignant.query.filter_by(departement_id=departement_id).all()
    return jsonify([{'id': e.id, 'nom_complet': e.utilisateur.nom_complet} for e in enseignants])

@admin_bp.route("/assign_heads", methods=["GET", "POST"])
@login_required
def assign_heads():
    departements = Departement.query.all()
    enseignants = Enseignant.query.all()

    if request.method == "POST":
        departement_id = request.form.get("departement_id")
        enseignant_id = request.form.get("enseignant_id")

        departement = Departement.query.get(departement_id)
        nouveau_chef = Enseignant.query.get(enseignant_id)

        if not departement or not nouveau_chef:
            flash("Sélection invalide.", "danger")
            return redirect(url_for("admin.assign_heads"))

        # Vérification d’appartenance
        if nouveau_chef.departement_id != departement.id:
            flash("Cet enseignant n'appartient pas à ce département.", "warning")
            return redirect(url_for("admin.assign_heads"))

        # Retirer ancien chef
        ancien_chef = Enseignant.query.filter_by(departement_id=departement.id, est_chef_departement=True).first()
        if ancien_chef and ancien_chef.id != nouveau_chef.id:
            ancien_chef.est_chef_departement = False
            ancien_chef.utilisateur.role = RoleUtilisateur.ENSEIGNANT
            db.session.add(ancien_chef)
            flash(f"{ancien_chef.utilisateur.nom_complet} redevient enseignant titulaire.", "info")

        # Nommer nouveau chef
        nouveau_chef.est_chef_departement = True
        nouveau_chef.utilisateur.role = RoleUtilisateur.CHEF_DEPARTEMENT
        db.session.add(nouveau_chef)
        db.session.commit()

        flash(f"{nouveau_chef.utilisateur.nom_complet} est maintenant Chef du département {departement.nom}.", "success")
        return redirect(url_for("admin.assign_heads"))

    return render_template("assign_heads.html", departements=departements, enseignants=enseignants)

@admin_bp.route("/liste_chefs_departements", methods=["GET", "POST"])
@login_required
def liste_chefs_departements():
    role = getattr(current_user.role, "value", None)
    if role != "admin_principal":
        flash("Accès réservé à l’administrateur principal.", "danger")
        return redirect(url_for("auth.redirect_dashboard"))

    departements = Departement.query.all()
    enseignants = Enseignant.query.all()

    # Si l'admin veut changer le chef
    if request.method == "POST":
        departement_id = request.form.get("departement_id")
        enseignant_id = request.form.get("enseignant_id")

        if not departement_id or not enseignant_id:
            flash("Veuillez sélectionner un département et un enseignant.", "warning")
            return redirect(url_for("admin.liste_chefs_departements"))

        departement = Departement.query.get_or_404(departement_id)

        # Retirer l’ancien chef
        ancien_chef = Enseignant.query.filter_by(departement_id=departement.id, est_chef_departement=True).first()
        if ancien_chef:
          ancien_chef.est_chef_departement = False

        # Nommer le nouveau chef
        nouveau_chef = Enseignant.query.get_or_404(enseignant_id)
        nouveau_chef.est_chef_departement = True

        db.session.commit()

        flash(f"{nouveau_chef.utilisateur.nom_complet} est désormais chef du département {departement.nom}.", "success")
        return redirect(url_for("admin.liste_chefs_departements"))

    return render_template(
        "assign_head.html",
        departements=departements,
        enseignants=enseignants
    )
@admin_bp.route("/nommer_chef/<int:departement_id>/<int:enseignant_id>")
@login_required
def nommer_chef_departement(departement_id, enseignant_id):
    from flask_login import logout_user, current_user

    # 🔹 Récupérer le département
    departement = Departement.query.get_or_404(departement_id)

    # 🔹 Trouver tous les enseignants du département
    enseignants_du_departement = Enseignant.query.filter_by(departement_id=departement.id).all()

    # 🔹 Rétrograder TOUS les chefs existants dans ce département
    for ens in enseignants_du_departement:
        if ens.est_chef_departement:
            ens.est_chef_departement = False
            if ens.utilisateur:
                ens.utilisateur.role = "enseignant"

    # 🔹 Nommer le nouveau chef
    nouveau_chef = Enseignant.query.get_or_404(enseignant_id)
    nouveau_chef.est_chef_departement = True
    if nouveau_chef.utilisateur:
        nouveau_chef.utilisateur.role = "chef_departement"

    # 🔹 Sauvegarde sûre
    db.session.flush()
    db.session.commit()

    # 🔹 Déconnexion de l'ancien chef si connecté
    if ancien_chef := next((e for e in enseignants_du_departement if e.utilisateur_id == current_user.id and e.utilisateur.role == "enseignant"), None):
        logout_user()
        flash("Votre rôle a été mis à jour. Veuillez vous reconnecter.", "info")
        return redirect(url_for("auth.login"))

    # 🔹 Confirmation
    flash(f"{nouveau_chef.utilisateur.nom_complet} est maintenant chef du département {departement.nom}.", "success")
    return redirect(url_for("admin.liste_chefs_departements"))
