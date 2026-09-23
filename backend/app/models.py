from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text

from .database import Base


class PendingFacture(Base):
    """Une facture uploadee, deja passee dans l'OCR, en attente de
    verification humaine avant d'etre rangee definitivement."""
    __tablename__ = "pending_factures"

    id = Column(Integer, primary_key=True, index=True)
    fichier_original = Column(String, nullable=False)
    chemin_temp = Column(String, nullable=False, unique=True)  # chemin sur disque, dossier temp

    numero_facture = Column(String, nullable=True)
    produit = Column(String, nullable=True)
    delegation = Column(String, nullable=True)
    nom_exploitant = Column(String, nullable=True)
    nom_trouve_bd = Column(Boolean, default=False)
    code_client = Column(String, nullable=True)
    coherent = Column(Boolean, nullable=True)
    score = Column(Integer, default=0)
    confiance = Column(String, default="non_detecte")  # haute / moyenne / non_detecte
    nom_suggere = Column(String, nullable=True)

    statut = Column(String, default="a_verifier")  # a_verifier / validee / rejetee
    date_upload = Column(DateTime, default=datetime.utcnow)
    erreur = Column(Text, nullable=True)


class Facture(Base):
    """Une facture validee, rangee dans le stockage definitif."""
    __tablename__ = "factures"

    id = Column(Integer, primary_key=True, index=True)
    numero_facture = Column(String, nullable=False, index=True)
    produit = Column(String, nullable=True)
    delegation = Column(String, nullable=True)
    nom_exploitant = Column(String, nullable=False, index=True)
    code_client = Column(String, nullable=True)

    chemin_fichier = Column(String, nullable=False, unique=True)  # chemin relatif sous FACTURES_DIR
    score_confiance = Column(Integer, default=0)
    verifie_manuellement = Column(Boolean, default=False)

    date_import = Column(DateTime, default=datetime.utcnow)


class Exploitant(Base):
    """Base des exploitants connus, utilisee pour corriger/valider le nom lu
    par l'OCR (croisement fuzzy dans normalisation.corriger_exploitant)."""
    __tablename__ = "exploitants"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False, unique=True)
