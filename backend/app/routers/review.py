from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PendingFacture, Facture
from ..ocr.normalisation import normaliser_numero_facture, extraire_produit, extraire_delegation, \
    nettoyer_nom_exploitant, numero_pour_nom_fichier
from ..schemas import PendingOut, PendingUpdate, ValidationResult
from ..storage import chemin_final, deplacer_vers_final

router = APIRouter(prefix="/api/pending", tags=["revue"])


@router.get("", response_model=list[PendingOut])
def lister_pending(statut: str = "a_verifier", ordre: str = "desc", db: Session = Depends(get_db)):
    """
    Liste les factures en attente de verification.
    ordre="desc" (par defaut) : haute confiance d'abord (validation rapide en lot).
    ordre="asc" : les moins fiables d'abord (pour traiter en priorite les cas difficiles).
    """
    q = db.query(PendingFacture).filter(PendingFacture.statut == statut)
    q = q.order_by(PendingFacture.score.desc() if ordre == "desc" else PendingFacture.score.asc())
    return q.all()


@router.get("/{pending_id}", response_model=PendingOut)
def detail_pending(pending_id: int, db: Session = Depends(get_db)):
    pending = db.query(PendingFacture).get(pending_id)
    if not pending:
        raise HTTPException(404, "Facture en attente introuvable")
    return pending


@router.get("/{pending_id}/image")
def image_pending(pending_id: int, db: Session = Depends(get_db)):
    pending = db.query(PendingFacture).get(pending_id)
    if not pending or not Path(pending.chemin_temp).exists():
        raise HTTPException(404, "Image introuvable")
    return FileResponse(pending.chemin_temp)


@router.put("/{pending_id}", response_model=PendingOut)
def modifier_pending(pending_id: int, modif: PendingUpdate, db: Session = Depends(get_db)):
    """
    Permet de corriger a la main le numero de facture et/ou le nom de
    l'exploitant proposes par l'OCR, avant validation. Le nom de fichier
    suggere est recalcule immediatement a partir des valeurs corrigees.
    """
    pending = db.query(PendingFacture).get(pending_id)
    if not pending:
        raise HTTPException(404, "Facture en attente introuvable")

    if modif.numero_facture is not None:
        numero_normalise, _, _ = normaliser_numero_facture(modif.numero_facture)
        pending.numero_facture = numero_normalise
        pending.produit = extraire_produit(numero_normalise)
        pending.delegation = extraire_delegation(numero_normalise)

    if modif.nom_exploitant is not None:
        pending.nom_exploitant = modif.nom_exploitant.strip()

    nom_nettoye = nettoyer_nom_exploitant(pending.nom_exploitant)
    numero_fichier = numero_pour_nom_fichier(pending.numero_facture)
    pending.nom_suggere = f"{nom_nettoye}__{numero_fichier}" if (nom_nettoye and numero_fichier) else None

    db.commit()
    db.refresh(pending)
    return pending


@router.post("/{pending_id}/valider", response_model=ValidationResult)
def valider_pending(pending_id: int, db: Session = Depends(get_db)):
    """
    Confirme la facture (avec les eventuelles corrections manuelles deja
    enregistrees via PUT) : deplace le fichier vers son emplacement
    definitif et cree l'entree correspondante dans la table `factures`.
    """
    pending = db.query(PendingFacture).get(pending_id)
    if not pending:
        raise HTTPException(404, "Facture en attente introuvable")
    if not pending.nom_exploitant or not pending.numero_facture:
        raise HTTPException(400, "Nom de l'exploitant et numero de facture requis avant validation")

    nom_fichier = nettoyer_nom_exploitant(pending.nom_exploitant) + "__" + \
        numero_pour_nom_fichier(pending.numero_facture)
    extension = Path(pending.chemin_temp).suffix.lower()

    relatif = chemin_final(pending.delegation, pending.produit, nom_fichier, extension)
    chemin_definitif = deplacer_vers_final(Path(pending.chemin_temp), relatif)

    facture = Facture(
        numero_facture=pending.numero_facture,
        produit=pending.produit,
        delegation=pending.delegation,
        nom_exploitant=pending.nom_exploitant,
        code_client=pending.code_client,
        chemin_fichier=str(chemin_definitif),
        score_confiance=pending.score,
        verifie_manuellement=True,
    )
    db.add(facture)
    pending.statut = "validee"
    db.commit()

    return ValidationResult(
        id=pending_id, statut="validee", chemin_final=str(chemin_definitif),
        message="Facture validee et rangee.",
    )


@router.post("/{pending_id}/rejeter", response_model=ValidationResult)
def rejeter_pending(pending_id: int, db: Session = Depends(get_db)):
    """Marque la facture comme rejetee (ex: doublon, scan illisible). Le
    fichier original reste dans le dossier temporaire pour verification
    manuelle ulterieure plutot que d'etre supprime silencieusement."""
    pending = db.query(PendingFacture).get(pending_id)
    if not pending:
        raise HTTPException(404, "Facture en attente introuvable")
    pending.statut = "rejetee"
    db.commit()
    return ValidationResult(id=pending_id, statut="rejetee", message="Facture rejetee.")
