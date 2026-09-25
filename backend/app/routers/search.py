from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import FACTURES_DIR
from ..database import get_db
from ..models import Facture
from ..schemas import FactureOut

router = APIRouter(prefix="/api/factures", tags=["recherche"])


@router.get("", response_model=list[FactureOut])
def rechercher_factures(
    q: str = Query("", description="Recherche libre : numero de facture ou nom de l'exploitant"),
    delegation: str | None = None,
    produit: str | None = None,
    limite: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Facture)
    if q:
        motif = f"%{q}%"
        query = query.filter(or_(
            Facture.numero_facture.ilike(motif),
            Facture.nom_exploitant.ilike(motif),
            Facture.code_client.ilike(motif),
        ))
    if delegation:
        query = query.filter(Facture.delegation == delegation)
    if produit:
        query = query.filter(Facture.produit == produit)

    return query.order_by(Facture.date_import.desc()).limit(limite).all()


@router.get("/{facture_id}", response_model=FactureOut)
def detail_facture(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(Facture).get(facture_id)
    if not facture:
        raise HTTPException(404, "Facture introuvable")
    return facture


@router.get("/{facture_id}/fichier")
def fichier_facture(facture_id: int, db: Session = Depends(get_db)):
    """Sert l'image originale de la facture -> consultation et impression
    directement depuis le navigateur (Ctrl+P sur l'image affichee)."""
    facture = db.query(Facture).get(facture_id)
    if not facture:
        raise HTTPException(404, "Facture introuvable")
    chemin = FACTURES_DIR / facture.chemin_fichier
    if not chemin.exists():
        raise HTTPException(404, "Fichier introuvable sur le disque")
    return FileResponse(chemin)


@router.delete("/{facture_id}")
def supprimer_facture(facture_id: int, db: Session = Depends(get_db)):
    """Supprime definitivement une facture : le fichier sur le disque ET
    son entree en base. Utilise depuis la page de recherche (ex: doublon,
    scan de mauvaise qualite, erreur de classement)."""
    facture = db.query(Facture).get(facture_id)
    if not facture:
        raise HTTPException(404, "Facture introuvable")

    chemin = FACTURES_DIR / facture.chemin_fichier
    Path(chemin).unlink(missing_ok=True)

    db.delete(facture)
    db.commit()
    return {"ok": True, "message": "Facture supprimee."}
