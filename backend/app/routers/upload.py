import shutil
from pathlib import Path

import cv2
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from ..config import TEMP_DIR, EXTENSIONS_AUTORISEES, Y_FRAC, H_FRAC, RIGHT_COL_RATIO
from ..database import get_db
from ..models import PendingFacture, Exploitant
from ..ocr.facture_ocr_final import extract_facture_info
from ..ocr.normalisation import analyser_facture
from ..storage import nom_temp_unique, extraire_zip_vers_temp
from ..schemas import UploadResume

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _base_exploitants(db: Session) -> list[str]:
    return [e.nom for e in db.query(Exploitant).all()]


def _traiter_image(chemin_image: Path, nom_original: str, db: Session, base_exploitants: list[str]) -> PendingFacture:
    pending = PendingFacture(fichier_original=nom_original, chemin_temp=str(chemin_image))

    img = cv2.imread(str(chemin_image))
    if img is None:
        pending.erreur = "Image illisible (fichier corrompu ou format non supporte)"
        db.add(pending)
        db.commit()
        db.refresh(pending)
        return pending

    H, W = img.shape[:2]
    y, h = int(H * Y_FRAC), int(H * H_FRAC)
    crop = img[y:y + h, 0:W]

    try:
        info = extract_facture_info(crop, right_col_ratio=RIGHT_COL_RATIO)
        resultat = analyser_facture(info, base_exploitants=base_exploitants)
        for cle, valeur in resultat.items():
            setattr(pending, cle, valeur)
    except Exception as exc:
        pending.erreur = f"Erreur OCR : {exc}"

    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


@router.post("", response_model=UploadResume)
async def uploader_factures(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Accepte un ou plusieurs fichiers en une fois : images individuelles,
    tous les fichiers d'un dossier (selection multiple cote navigateur), ou
    une archive .zip contenant des images (eventuellement dans des
    sous-dossiers). Chaque image trouvee est passee dans le pipeline OCR et
    place en attente de verification (statut "a_verifier").
    """
    base_exploitants = _base_exploitants(db)

    images_a_traiter: list[tuple[Path, str]] = []  # (chemin_temp, nom_original)
    erreurs = 0

    for upload in files:
        nom = upload.filename or "sans_nom"
        suffixe = Path(nom).suffix.lower()

        if suffixe == ".zip":
            chemin_zip = nom_temp_unique(nom)
            with open(chemin_zip, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            try:
                for chemin_img in extraire_zip_vers_temp(chemin_zip):
                    images_a_traiter.append((chemin_img, chemin_img.name))
            except Exception:
                erreurs += 1
            finally:
                chemin_zip.unlink(missing_ok=True)

        elif suffixe in EXTENSIONS_AUTORISEES:
            chemin_dest = nom_temp_unique(nom)
            with open(chemin_dest, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            images_a_traiter.append((chemin_dest, nom))

        else:
            erreurs += 1

    pending_ids = []
    for chemin_img, nom_original in images_a_traiter:
        pending = _traiter_image(chemin_img, nom_original, db, base_exploitants)
        pending_ids.append(pending.id)
        if pending.erreur:
            erreurs += 1

    return UploadResume(
        total_fichiers=len(files),
        traites=len(images_a_traiter),
        erreurs=erreurs,
        pending_ids=pending_ids,
    )
