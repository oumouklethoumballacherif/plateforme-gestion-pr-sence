# from flask import render_template, redirect, url_for, flash, request
# from flask_login import login_required, current_user
# from . import etudiant_bp
# from .forms import ScanQRForm
# from app.models import Presence, Matiere, SeanceCours
# from app.extensions import db
# from datetime import datetime

# # Dashboard étudiant
# @etudiant_bp.route("/dashboard")
# @login_required
# def dashboard():
#     return render_template("etudiant/dashboard.html")

# # Consultation des matières
# @etudiant_bp.route("/mes_matieres")
# @login_required
# def mes_matieres():
#     filiere_id = current_user.filiere_id
#     matieres = Matiere.query.filter_by(filiere_id=filiere_id).all()
#     return render_template("etudiant/mes_matieres.html", matieres=matieres)

# # Scanner QR Code
# @etudiant_bp.route("/scan_qr", methods=["GET","POST"])
# @login_required
# def scan_qr():
#     form = ScanQRForm()
#     if form.validate_on_submit():
#         qr_code = form.qr_code.data
#         cours = SeanceCours.query.filter_by(qr_code=qr_code).first()
#         if not cours:
#             flash("QR Code invalide ❌", "danger")
#         else:
#             presence = Presence(
#                 etudiant_id=current_user.id,
#                 cours_id=cours.id,
#                 date=datetime.now()
#             )
#             db.session.add(presence)
#             db.session.commit()
#             flash("Présence enregistrée ✅", "success")
#         return redirect(url_for("etudiant_bp.dashboard"))
#     return render_template("etudiant/scan_qr.html", form=form)


from flask import Blueprint, render_template, redirect, request, url_for, flash,jsonify
from flask_login import login_required, current_user
from app.etudiant import etudiant_bp
from app.extensions import db
from app.models import Etudiant, Matiere, Presence, SeanceCours, StatutPresence
from datetime import datetime, timedelta
import pandas as pd



@etudiant_bp.route("/dashboard")
@login_required
def dashboard():
    # Vérifie que c'est un étudiant
    if current_user.role.value != "etudiant":
        flash("Accès interdit", "danger")
        return redirect(url_for("auth.login"))

    # Récupération du profil étudiant
    etudiant = current_user.etudiant_profil

    return render_template(
        "dashboard_etudiant.html",
        etudiant=etudiant
    )

# — Scanner la présence
@etudiant_bp.route("/scan_presence", methods=["POST"])
@login_required
def scan_presence():
    data = request.get_json()
    qr_value = str(data.get("seance_id", "")).strip()

    # Découper ID + clé temporelle
    try:
        seance_id_str, timestamp_key_str = qr_value.split("-")
        seance_id = int(seance_id_str)
    except:
        return jsonify({"error": "QR code invalide"}), 400

    # Vérifier la séance
    seance = SeanceCours.query.get(seance_id)
    if not seance or not seance.active:
        return jsonify({"error": "Séance introuvable ou inactive"}), 400

    # Vérifier la validité temporelle du QR (20 sec)
    current_key = int(datetime.utcnow().timestamp() // 20)
    if abs(current_key - int(timestamp_key_str)) > 1:
        return jsonify({"error": "QR expiré. Rescanner."}), 400

    # Vérification filière et année
    etu = current_user.etudiant_profil
    if seance.matiere.annee_formation.filiere_id != etu.filiere_id or \
       seance.matiere.annee_formation.id != etu.annee_formation_id:
        return jsonify({"error": "Vous ne pouvez pas scanner ce code : séance non autorisée"}), 403

    # Vérification si la présence existe déjà
    presence = Presence.query.filter_by(
        etudiant_id=etu.id,
        seance_id=seance.id
    ).first()

    if presence:
        return jsonify({"message": "Présence déjà enregistrée"}), 200  # <-- ici on renvoie le message

    # Sinon, créer la présence
    presence = Presence(
        etudiant_id=etu.id,
        seance_id=seance.id,
        statut="present"
    )
    db.session.add(presence)
    db.session.commit()

    return jsonify({"message": "Présence enregistrée avec succès"}), 201

@etudiant_bp.route("/matieres", methods=["GET", "POST"])
@login_required
def matieres_etudiant():
    etu = current_user.etudiant_profil

    # Récupérer tous les semestres liés à l'année de formation de l'étudiant
    semestres = etu.annee_formation.semestres  # Assurez-vous que AnneeFormation a relation 'semestres'

    selected_semestre_id = None
    matieres = []

    if request.method == "POST":
        selected_semestre_id = request.form.get("semestre_id")
        if selected_semestre_id:
            matieres = Matiere.query.filter_by(
                annee_formation_id=etu.annee_formation_id,
                semestre_id=selected_semestre_id
            ).all()

    return render_template(
        "matieres.html",
        semestres=semestres,
        matieres=matieres,
        etudiant=etu,
        selected_semestre_id=selected_semestre_id
    )


def calculer_stats_matiere(matiere_id, etudiant_id):
    seances = SeanceCours.query.filter_by(matiere_id=matiere_id) \
        .order_by(SeanceCours.date_prevue).all()

    # Dictionnaires organisés
    stats = {
        "prevue": {"CM": 0, "TD": 0, "TP": 0},
        "active": {"CM": 0, "TD": 0, "TP": 0},
        "present": {"CM": 0, "TD": 0, "TP": 0},
        "absent": {"CM": 0, "TD": 0, "TP": 0},
        "historique": []
    }

    # Récupérer toutes les présences de l’étudiant
    presences = Presence.query.filter_by(etudiant_id=etudiant_id).all()
    presences_ids = {p.seance_id for p in presences}

    for seance in seances:
        type_s = seance.type_seance.value  # CM / TD / TP

        # Séances programmées
        stats["prevue"][type_s] += 1

        # Si séance non démarrée → on n’enregistre ni présence ni absence
        if not seance.active:
            stats["historique"].append({
                "id": seance.id,
                "date": seance.date_prevue.strftime("%d-%m-%Y %H:%M"),
                "type": type_s,
                "active": False,
                "present": False
            })
            continue

        # Séance démarrée
        stats["active"][type_s] += 1

        est_present = seance.id in presences_ids

        if est_present:
            stats["present"][type_s] += 1
        else:
            stats["absent"][type_s] += 1

        # Historique
        stats["historique"].append({
            "id": seance.id,
            "date": seance.date_prevue.strftime("%d-%m-%Y %H:%M"),
            "type": type_s,
            "active": True,
            "present": est_present
        })

    return stats

@etudiant_bp.route("/matiere/<int:matiere_id>")
@login_required
def details_matiere(matiere_id):
    matiere = Matiere.query.get_or_404(matiere_id)
    etu = current_user.etudiant_profil

    # Vérification d'accès
    if matiere.annee_formation_id != etu.annee_formation_id:
        flash("Vous n'avez pas accès à cette matière.", "danger")
        return redirect(url_for("etudiant.matieres_etudiant"))

    # Calcul des statistiques
    stats = calculer_stats_matiere(matiere_id, etu.id)

    return render_template(
        "details_matiere.html",
        matiere=matiere,
        stats=stats,
        historique=stats["historique"],
        etudiant=etu
    )


@etudiant_bp.route("/scan_qr")
@login_required
def scan_qr_page():
    # Vérifie que c'est bien un étudiant
    if current_user.role.value != "etudiant":
        flash("Accès interdit", "danger")
        return redirect(url_for("auth.login"))

    etudiant = current_user.etudiant_profil
    if not etudiant:
        flash("Profil étudiant introuvable.", "warning")
        return redirect(url_for("auth.login"))

    return render_template("scan_qr.html", etudiant=etudiant)
