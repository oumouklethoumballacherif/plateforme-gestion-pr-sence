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
