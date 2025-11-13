from datetime import datetime
from enum import Enum
from app.extensions import db
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin



# -----------------------------
# ENUMS
# -----------------------------
class RoleUtilisateur(Enum):
    ADMIN_PRINCIPAL = "admin_principal"  # Admin principal (non enseignant)
    CHEF_DEPARTEMENT = "chef_departement"  # Chef de département (enseignant)
    CHEF_FILIERE = "chef_filiere"  # Chef de filière (enseignant)
    ENSEIGNANT = "enseignant"  # Enseignant titulaire
    ETUDIANT = "etudiant"


class TypeSeance(Enum):
    CM = "CM"
    TD = "TD"
    TP = "TP"


# -----------------------------
# TABLES PRINCIPALES
# -----------------------------
class Departement(db.Model):
    __tablename__ = "departements"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=True, unique=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    filieres = db.relationship("Filiere", back_populates="departement", cascade="all, delete-orphan")
    


class Filiere(db.Model):
    __tablename__ = "filieres"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), nullable=True)
    departement_id = db.Column(db.Integer, db.ForeignKey("departements.id"), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    departement = db.relationship("Departement", back_populates="filieres")
    annees = db.relationship("AnneeFormation", back_populates="filiere", cascade="all, delete-orphan")
    etudiants = db.relationship("Etudiant", back_populates="filiere")


class AnneeFormation(db.Model):
    __tablename__ = "annees_formation"
    id = db.Column(db.Integer, primary_key=True)
    filiere_id = db.Column(db.Integer, db.ForeignKey("filieres.id"), nullable=False)
    libelle = db.Column(db.String(50), nullable=False)  # ex: L1, L2, M1
    ordre = db.Column(db.Integer, nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    filiere = db.relationship("Filiere", back_populates="annees")
    matieres = db.relationship("Matiere", back_populates="annee_formation", cascade="all, delete-orphan")


# -----------------------------
# UTILISATEURS
# -----------------------------
class Utilisateur(db.Model, UserMixin):
    __tablename__ = "utilisateurs"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    nom_complet = db.Column(db.String(200), nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.Enum(RoleUtilisateur), nullable=False)
    actif = db.Column(db.Boolean, default=True)
    
    # --- Gestion mail de confirmation ---
    email_confirme = db.Column(db.Boolean, default=False)
    token_confirmation = db.Column(db.String(255), nullable=True, unique=True)
    token_expiration = db.Column(db.DateTime, nullable=True)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    enseignant_profil = db.relationship("Enseignant", uselist=False, back_populates="utilisateur", cascade="all, delete-orphan")
    etudiant_profil = db.relationship("Etudiant", uselist=False, back_populates="utilisateur", cascade="all, delete-orphan")

class Enseignant(db.Model):
    __tablename__ = "enseignants"
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False, unique=True)
    matricule_enseignant = db.Column(db.String(50), nullable=True, unique=True)
    departement_id = db.Column(db.Integer, db.ForeignKey("departements.id"), nullable=False)
    est_chef_departement = db.Column(db.Boolean, default=False)
    est_chef_filiere = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    utilisateur = db.relationship("Utilisateur", back_populates="enseignant_profil")
    departement = db.relationship("Departement")

    affectations_matieres = db.relationship("AffectationMatiere", back_populates="enseignant", cascade="all, delete-orphan")
    affectations_filieres = db.relationship("EnseignantFiliere", back_populates="enseignant", cascade="all, delete-orphan")


class Etudiant(db.Model):
    __tablename__ = "etudiants"
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False, unique=True)
    matricule = db.Column(db.String(50), nullable=False, unique=True)
    filiere_id = db.Column(db.Integer, db.ForeignKey("filieres.id"), nullable=False)
    annee_formation_id = db.Column(db.Integer, db.ForeignKey("annees_formation.id"), nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    utilisateur = db.relationship("Utilisateur", back_populates="etudiant_profil")
    filiere = db.relationship("Filiere", back_populates="etudiants")
    annee_formation = db.relationship("AnneeFormation")
    presences = db.relationship("Presence", back_populates="etudiant", cascade="all, delete-orphan")


# -----------------------------
# MATIERES ET COURS
# -----------------------------
class Matiere(db.Model):
    __tablename__ = "matieres"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=True)
    titre = db.Column(db.String(300), nullable=False)
    annee_formation_id = db.Column(db.Integer, db.ForeignKey("annees_formation.id"), nullable=False)

    total_seances = db.Column(db.Integer, nullable=False, default=0)
    cm_seances = db.Column(db.Integer, nullable=False, default=0)
    td_seances = db.Column(db.Integer, nullable=False, default=0)
    tp_seances = db.Column(db.Integer, nullable=False, default=0)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    annee_formation = db.relationship("AnneeFormation", back_populates="matieres")
    affectations = db.relationship("AffectationMatiere", back_populates="matiere", cascade="all, delete-orphan")
    seances = db.relationship("SeanceCours", back_populates="matiere", cascade="all, delete-orphan")


class AffectationMatiere(db.Model):
    __tablename__ = "affectations_matieres"
    id = db.Column(db.Integer, primary_key=True)
    matiere_id = db.Column(db.Integer, db.ForeignKey("matieres.id"), nullable=False)
    enseignant_id = db.Column(db.Integer, db.ForeignKey("enseignants.id"), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    matiere = db.relationship("Matiere", back_populates="affectations")
    enseignant = db.relationship("Enseignant", back_populates="affectations_matieres")


class EnseignantFiliere(db.Model):
    __tablename__ = "enseignant_filieres"
    id = db.Column(db.Integer, primary_key=True)
    enseignant_id = db.Column(db.Integer, db.ForeignKey("enseignants.id"), nullable=False)
    filiere_id = db.Column(db.Integer, db.ForeignKey("filieres.id"), nullable=False)
    est_chef_filiere = db.Column(db.Boolean, default=False)  # ✅ ajout ici
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    enseignant = db.relationship("Enseignant", back_populates="affectations_filieres")
    filiere = db.relationship("Filiere")


# -----------------------------
# SEANCES ET PRESENCES
# -----------------------------
class SeanceCours(db.Model):
    __tablename__ = "seances_cours"
    id = db.Column(db.Integer, primary_key=True)
    matiere_id = db.Column(db.Integer, db.ForeignKey("matieres.id"), nullable=False)
    enseignant_id = db.Column(db.Integer, db.ForeignKey("enseignants.id"), nullable=False)
    filiere_id = db.Column(db.Integer, db.ForeignKey("filieres.id"), nullable=True)
    annee_formation_id = db.Column(db.Integer, db.ForeignKey("annees_formation.id"), nullable=True)

    type_seance = db.Column(db.Enum(TypeSeance), nullable=False)
    date_prevue = db.Column(db.DateTime, nullable=False)
    duree_minutes = db.Column(db.Integer, nullable=True)

    qr_token = db.Column(db.String(255), nullable=True, unique=True)
    active = db.Column(db.Boolean, default=False)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    matiere = db.relationship("Matiere", back_populates="seances")
    enseignant = db.relationship("Enseignant")
    presences = db.relationship("Presence", back_populates="seance", cascade="all, delete-orphan")


class StatutPresence(Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSE = "excuse"


class Presence(db.Model):
    __tablename__ = "presences"
    id = db.Column(db.Integer, primary_key=True)
    seance_id = db.Column(db.Integer, db.ForeignKey("seances_cours.id"), nullable=False)
    etudiant_id = db.Column(db.Integer, db.ForeignKey("etudiants.id"), nullable=False)
    statut = db.Column(db.Enum(StatutPresence), nullable=False, default=StatutPresence.PRESENT)
    date_scan = db.Column(db.DateTime, default=datetime.utcnow)

    seance = db.relationship("SeanceCours", back_populates="presences")
    etudiant = db.relationship("Etudiant", back_populates="presences")

    __table_args__ = (
        db.UniqueConstraint('seance_id', 'etudiant_id', name='uix_seance_etudiant'),
    )


# -----------------------------
# STATUT DES ETUDIANTS
# -----------------------------
class StatutEtudiant(db.Model):
    __tablename__ = "statuts_etudiants"
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey("etudiants.id"), nullable=False)
    matiere_id = db.Column(db.Integer, db.ForeignKey("matieres.id"), nullable=False)
    en_rattrapage = db.Column(db.Boolean, default=False)
    derniere_evaluation = db.Column(db.DateTime, default=datetime.utcnow)

    etudiant = db.relationship("Etudiant")
    matiere = db.relationship("Matiere")

    __table_args__ = (
        db.UniqueConstraint('etudiant_id', 'matiere_id', name='uix_etudiant_matiere_statut'),
    )


# -----------------------------
# IMPORTS ET JOURNALISATION
# -----------------------------
class Importation(db.Model):
    __tablename__ = "importations"
    id = db.Column(db.Integer, primary_key=True)
    lance_par_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=False)
    nom_fichier = db.Column(db.String(255), nullable=False)
    statut = db.Column(db.String(50), nullable=False, default="en_attente")
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_fin = db.Column(db.DateTime, nullable=True)

    lance_par = db.relationship("Utilisateur")


class JournalAction(db.Model):
    __tablename__ = "journaux_actions"
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey("utilisateurs.id"), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    meta_donnees = db.Column(db.JSON, nullable=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    utilisateur = db.relationship("Utilisateur")


# -----------------------------
# NOTES
# -----------------------------
# - Le calcul du pourcentage d'absences et le passage en rattrapage seront gérés
#   dans la logique métier (services ou signaux SQLAlchemy).
# - Règle de rattrapage : 25% d'absences en CM+TD ou 2 absences en TP.
# - Vérifications : un chef de département ou de filière doit appartenir à son département.
# - Les importations Excel créent une trace (Importation + JournalAction).
# - Indexer les colonnes filtrées fréquemment : seances_cours.date_prevue, matieres.annee_formation_id,
#   presences.etudiant_id, presences.seance_id.

# Fin du fichier models.py
