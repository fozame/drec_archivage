from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Facture, PendingFacture

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def obtenir_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Facture.id)).scalar() or 0
    score_moyen = db.query(func.avg(Facture.score_confiance)).scalar() or 0

    total_en_attente = (
        db.query(func.count(PendingFacture.id))
        .filter(PendingFacture.statut == "a_verifier")
        .scalar() or 0
    )

    par_delegation = (
        db.query(Facture.delegation, func.count(Facture.id))
        .group_by(Facture.delegation)
        .order_by(func.count(Facture.id).desc())
        .all()
    )
    par_produit = (
        db.query(Facture.produit, func.count(Facture.id))
        .group_by(Facture.produit)
        .order_by(func.count(Facture.id).desc())
        .all()
    )

    # Evolution sur les 12 derniers mois (regroupe par mois cote Python :
    # reste correct quelle que soit la BD, SQLite comme Postgres).
    debut = datetime.utcnow() - timedelta(days=365)
    dates = db.query(Facture.date_import).filter(Facture.date_import >= debut).all()
    compte_par_mois: dict[str, int] = {}
    for (date_import,) in dates:
        cle = date_import.strftime("%Y-%m")
        compte_par_mois[cle] = compte_par_mois.get(cle, 0) + 1
    par_mois = [{"mois": m, "total": c} for m, c in sorted(compte_par_mois.items())]

    return {
        "total_factures": total,
        "total_en_attente": total_en_attente,
        "score_moyen": round(score_moyen, 1),
        "par_delegation": [{"cle": cle or "Non classee", "total": total} for cle, total in par_delegation],
        "par_produit": [{"cle": cle or "Non classe", "total": total} for cle, total in par_produit],
        "par_mois": par_mois,
    }
