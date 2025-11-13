from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Utilisateur, RoleUtilisateur
from app.extensions import db, bcrypt, mail
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime
from app.auth import auth_bp




# ----------------------------------------------------
# 🔐 Génération et vérification de token
# ----------------------------------------------------
def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


# ----------------------------------------------------
# 📨 Envoi des e-mails
# ----------------------------------------------------
def send_email(subject, recipients, template, **kwargs):
    msg = Message(
        subject=subject,
        recipients=recipients,
        html=render_template(template, **kwargs),
        sender=current_app.config.get("MAIL_DEFAULT_SENDER", "balla33cherif@gmail.com"),
    )
    mail.send(msg)


# ----------------------------------------------------
# 🔑 Connexion
# ----------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.redirect_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = Utilisateur.query.filter_by(email=email).first()
        if not user:
            flash("Aucun compte trouvé avec cet e-mail.", "danger")
            return redirect(url_for("auth.login"))

        if not user.email_confirme:
            flash("Veuillez confirmer votre e-mail avant de vous connecter.", "warning")
            return redirect(url_for("auth.login"))

        if not user.mot_de_passe_hash:
            flash("Votre compte n’a pas encore été activé. Veuillez définir votre mot de passe.", "warning")
            return redirect(url_for("auth.login"))

        if bcrypt.check_password_hash(user.mot_de_passe_hash, password):
            if not user.actif:
                flash("Votre compte est désactivé.", "danger")
                return redirect(url_for("auth.login"))

            login_user(user)
            return redirect(url_for("auth.redirect_dashboard"))

        flash("E-mail ou mot de passe incorrect.", "danger")

    return render_template("login.html")


# ----------------------------------------------------
# 🧾 Inscription standard (étudiants)
# ----------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.redirect_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        nom_complet = request.form.get("nom_complet")
        mot_de_passe = request.form.get("mot_de_passe")

        if Utilisateur.query.filter_by(email=email).first():
            flash("Cet e-mail est déjà utilisé.", "warning")
            return redirect(url_for("auth.register"))

        hashed_pw = bcrypt.generate_password_hash(mot_de_passe).decode("utf-8")
        user = Utilisateur(
            email=email,
            nom_complet=nom_complet,
            mot_de_passe_hash=hashed_pw,
            role=RoleUtilisateur.ETUDIANT,
        )
        db.session.add(user)
        db.session.commit()

        token = get_serializer().dumps(email, salt="email-confirm")
        user.token_confirmation = token
        user.token_expiration = datetime.utcnow()
        db.session.commit()

        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        send_email(
            subject="Confirmation de votre adresse e-mail",
            recipients=[user.email],
            template="emails/confirm_email.html",
            confirm_url=confirm_url,
            user=user,
        )

        flash("Un e-mail de confirmation vous a été envoyé.", "info")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ----------------------------------------------------
# ✉️ Confirmation e-mail (enseignant ou étudiant)
# ----------------------------------------------------
@auth_bp.route("/confirm/<token>")
def confirm_email(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
    except SignatureExpired:
        flash("Le lien de confirmation a expiré.", "danger")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("Lien invalide.", "danger")
        return redirect(url_for("auth.login"))

    user = Utilisateur.query.filter_by(email=email).first()
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("auth.register"))

    if user.email_confirme:
        flash("Votre e-mail est déjà confirmé.", "info")
        return redirect(url_for("auth.login"))

    user.email_confirme = True
    db.session.commit()

    # Si c’est un enseignant sans mot de passe → il crée son mot de passe
    if user.role == RoleUtilisateur.ENSEIGNANT and not user.mot_de_passe_hash:
        flash("Veuillez créer votre mot de passe pour activer votre compte.", "info")
        return redirect(url_for("auth.set_password", email=email))

    flash("E-mail confirmé avec succès ! Vous pouvez maintenant vous connecter.", "success")
    return redirect(url_for("auth.login"))


# ----------------------------------------------------
# 🔐 Création du mot de passe (enseignants)
# ----------------------------------------------------
@auth_bp.route("/set_password", methods=["GET", "POST"])
def set_password():
    email = request.args.get("email")
    user = Utilisateur.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        mot_de_passe = request.form.get("mot_de_passe")
        if not mot_de_passe:
            flash("Veuillez saisir un mot de passe.", "warning")
            return redirect(request.url)

        user.mot_de_passe_hash = bcrypt.generate_password_hash(mot_de_passe).decode("utf-8")
        db.session.commit()

        flash("Mot de passe créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("set_password.html", email=email)


# ----------------------------------------------------
# 🔄 Redirection selon le rôle
# ----------------------------------------------------
@auth_bp.route("/redirect_dashboard")
@login_required
def redirect_dashboard():
    role = current_user.role.value  # ou current_user.role selon ton modèle

    if role == "admin_principal":
        return redirect(url_for("admin.dashboard"))

    elif role == "chef_departement":
        return redirect(url_for("chef.dashboard"))

    elif role == "chef_filiere":
        return redirect(url_for("admin.dashboard"))

    elif role == "enseignant":
        return redirect(url_for("enseignant.dashboard"))  # 🔹 remplacé ici

    elif role == "etudiant":
        return redirect(url_for("etudiant.dashboard"))  # 🔹 cohérence en français

    else:
        logout_user()
        flash("Rôle inconnu. Contactez l’administrateur.", "danger")
        return redirect(url_for("auth.login"))


# ----------------------------------------------------
# 🚪 Déconnexion
# ----------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for("auth.login"))


# ----------------------------------------------------
# 🔑 Mot de passe oublié
# ----------------------------------------------------
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = Utilisateur.query.filter_by(email=email).first()

        if not user:
            flash("Aucun compte trouvé avec cet e-mail.", "danger")
            return redirect(url_for("auth.forgot_password"))

        token = get_serializer().dumps(email, salt="password-reset")
        reset_url = url_for("auth.reset_password", token=token, _external=True)
        send_email(
            subject="Réinitialisation de votre mot de passe",
            recipients=[email],
            template="emails/reset_password.html",
            reset_url=reset_url,
            user=user,
        )

        flash("Un e-mail de réinitialisation a été envoyé.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


# ----------------------------------------------------
# 🔁 Réinitialiser le mot de passe
# ----------------------------------------------------
@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt="password-reset", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("Lien invalide ou expiré.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = Utilisateur.query.filter_by(email=email).first()
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        new_password = request.form.get("mot_de_passe")
        user.mot_de_passe_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        db.session.commit()
        flash("Mot de passe mis à jour avec succès.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)
