"""
Gestion des fichiers sur disque :
- reception des uploads (fichiers individuels, dossier, zip) -> TEMP_DIR
- deplacement d'une facture validee vers son emplacement definitif dans
  FACTURES_DIR, organise en delegation / annee / produit / NOM__NUMERO.ext
"""
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from .config import TEMP_DIR, FACTURES_DIR, EXTENSIONS_AUTORISEES


def nom_temp_unique(nom_original: str) -> Path:
    ext = Path(nom_original).suffix.lower()
    return TEMP_DIR / f"{uuid.uuid4().hex}{ext}"


def extraire_zip_vers_temp(chemin_zip: Path) -> list[Path]:
    """Extrait un zip dans un sous-dossier unique de TEMP_DIR et retourne la
    liste des images trouvees a l'interieur (sous-dossiers inclus)."""
    dossier_extraction = TEMP_DIR / f"zip_{uuid.uuid4().hex}"
    dossier_extraction.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(chemin_zip, "r") as z:
        z.extractall(dossier_extraction)

    images = [
        p for p in dossier_extraction.rglob("*")
        if p.is_file() and p.suffix.lower() in EXTENSIONS_AUTORISEES
        and not p.name.startswith("__MACOSX") and "__MACOSX" not in p.parts
    ]
    return images


def chemin_final(delegation: str | None, produit: str | None, nom_fichier: str, extension: str,
                  annee: int | None = None) -> Path:
    """Construit le chemin relatif : delegation/annee/produit/nom_fichier.ext
    Les segments inconnus sont remplaces par des dossiers "divers"/"AUTRE"
    pour ne jamais bloquer un classement, meme incomplet."""
    annee = annee or datetime.now().year
    seg_deleg = delegation or "AUTRE"
    seg_produit = produit or "AUTRE"
    return Path(seg_deleg) / str(annee) / seg_produit / f"{nom_fichier}{extension}"


def deplacer_vers_final(chemin_source: Path, chemin_relatif: Path) -> Path:
    """Deplace le fichier source vers FACTURES_DIR/chemin_relatif, en gerant
    les collisions de nom (ajout d'un suffixe _2, _3...)."""
    destination = FACTURES_DIR / chemin_relatif
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        stem, ext = destination.stem, destination.suffix
        compteur = 2
        while destination.exists():
            destination = destination.parent / f"{stem}_{compteur}{ext}"
            compteur += 1

    shutil.move(str(chemin_source), str(destination))
    return destination.relative_to(FACTURES_DIR)


def supprimer_temp(chemin: Path):
    try:
        Path(chemin).unlink(missing_ok=True)
    except Exception:
        pass
