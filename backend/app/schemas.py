from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PendingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fichier_original: str
    numero_facture: Optional[str] = None
    produit: Optional[str] = None
    delegation: Optional[str] = None
    nom_exploitant: Optional[str] = None
    nom_trouve_bd: bool = False
    code_client: Optional[str] = None
    coherent: Optional[bool] = None
    score: int = 0
    confiance: str = "non_detecte"
    nom_suggere: Optional[str] = None
    statut: str
    date_upload: datetime
    erreur: Optional[str] = None


class PendingUpdate(BaseModel):
    """Champs modifiables par l'utilisateur pendant la verification."""
    numero_facture: Optional[str] = None
    nom_exploitant: Optional[str] = None


class ValidationResult(BaseModel):
    id: int
    statut: str
    chemin_final: Optional[str] = None
    message: str


class FactureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_facture: str
    produit: Optional[str] = None
    delegation: Optional[str] = None
    nom_exploitant: str
    code_client: Optional[str] = None
    chemin_fichier: str
    score_confiance: int
    verifie_manuellement: bool
    date_import: datetime


class UploadResume(BaseModel):
    total_fichiers: int
    traites: int
    erreurs: int
    pending_ids: list[int]
