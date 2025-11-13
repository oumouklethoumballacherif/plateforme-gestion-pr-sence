from app.extensions import db
from app.models import Utilisateur, Enseignant, RoleUtilisateur, JournalAction

def nommer_chef_departement(enseignant_id, admin_id):
    enseignant = Enseignant.query.get(enseignant_id)
    if not enseignant:
        raise ValueError("Enseignant introuvable.")

    departement = enseignant.departement
    ancien_chef = Enseignant.query.filter_by(departement_id=departement.id, est_chef_departement=True).first()

    # rétrograder ancien chef
    if ancien_chef and ancien_chef.id != enseignant.id:
        ancien_chef.est_chef_departement = False
        ancien_chef.utilisateur.role = RoleUtilisateur.ENSEIGNANT
        db.session.add(ancien_chef)

    # nommer nouveau
    enseignant.est_chef_departement = True
    enseignant.utilisateur.role = RoleUtilisateur.CHEF_DEPARTEMENT
    db.session.add(enseignant)

    # journal
    db.session.add(JournalAction(
        utilisateur_id=admin_id,
        action="nommer_chef_departement",
        meta_donnees={"departement_id": departement.id, "nouveau_chef_id": enseignant.id}
    ))
    db.session.commit()


def nommer_chef_filiere(enseignant_id, admin_id):
    enseignant = Enseignant.query.get(enseignant_id)
    if not enseignant:
        raise ValueError("Enseignant introuvable.")
    
    # retrouver la filière liée à cet enseignant
    affectation = enseignant.affectations_filieres[0] if enseignant.affectations_filieres else None
    if not affectation:
        raise ValueError("L’enseignant n’est affecté à aucune filière.")

    filiere = affectation.filiere
    ancien_chef = Enseignant.query.filter_by(est_chef_filiere=True).join("affectations_filieres").filter_by(filiere_id=filiere.id).first()

    if ancien_chef and ancien_chef.id != enseignant.id:
        ancien_chef.est_chef_filiere = False
        ancien_chef.utilisateur.role = RoleUtilisateur.ENSEIGNANT
        db.session.add(ancien_chef)

    enseignant.est_chef_filiere = True
    enseignant.utilisateur.role = RoleUtilisateur.CHEF_FILIERE
    db.session.add(enseignant)

    db.session.add(JournalAction(
        utilisateur_id=admin_id,
        action="nommer_chef_filiere",
        meta_donnees={"filiere_id": filiere.id, "nouveau_chef_id": enseignant.id}
    ))
    db.session.commit()
