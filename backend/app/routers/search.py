from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import FACTURES_DIR
from ..database import get_db
from ..models import Facture
from ..schemas import FactureOut, FactureUpdate
from ..ocr.normalisation import (normaliser_numero_facture, extraire_produit,
    extraire_delegation, numero_pour_nom_fichier, nettoyer_nom_exploitant)
from ..storage import chemin_final, deplacer_vers_final

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


@router.put("/{facture_id}", response_model=FactureOut)
def modifier_facture(facture_id: int, modif: FactureUpdate, db: Session = Depends(get_db)):
    """Corrige une facture deja archivee (numero, produit, exploitant) :
    recalcule delegation/produit, renomme et deplace le fichier dans le bon
    dossier, puis met a jour la base."""
    facture = db.query(Facture).get(facture_id)
    if not facture:
        raise HTTPException(404, "Facture introuvable")

    numero = facture.numero_facture
    nom = facture.nom_exploitant
    if modif.numero_facture is not None and modif.numero_facture.strip():
        numero, _, _ = normaliser_numero_facture(modif.numero_facture)
    if modif.nom_exploitant is not None and modif.nom_exploitant.strip():
        nom = modif.nom_exploitant.strip()

    produit = extraire_produit(numero)
    delegation = extraire_delegation(numero)
    if produit is None:
        raise HTTPException(400, "Numero invalide. Format attendu : 26A/REPDIP/D/123")

    ancien = FACTURES_DIR / facture.chemin_fichier
    if not ancien.exists():
        raise HTTPException(404, "Fichier introuvable sur le disque")

    nom_fichier = nettoyer_nom_exploitant(nom) + "__" + numero_pour_nom_fichier(numero)
    annee = None
    parts = Path(facture.chemin_fichier).parts
    if len(parts) >= 2 and parts[1].isdigit():
        annee = int(parts[1])  # on garde l'annee de classement d'origine
    relatif = chemin_final(delegation, produit, nom_fichier, ancien.suffix.lower(), annee)
    if (FACTURES_DIR / relatif) != ancien:
        nouveau = deplacer_vers_final(ancien, relatif)
        facture.chemin_fichier = str(nouveau)

    facture.numero_facture = numero
    facture.produit = produit
    facture.delegation = delegation
    facture.nom_exploitant = nom
    facture.verifie_manuellement = True
    db.commit()
    db.refresh(facture)
    return facture
