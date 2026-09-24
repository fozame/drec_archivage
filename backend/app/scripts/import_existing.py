"""
Script d'import ponctuel : integre des factures DEJA renommees a la main
(format "NOM_EXPLOITANT__PREFIXE-PRODUIT-DELEGATION-NUMERO.ext", comme
produit par renommer_factures_v3.py) dans le stockage et la base de l'appli,
sans repasser par l'OCR puisqu'elles ont deja ete verifiees.

Usage : depuis la machine hote qui fait tourner Docker, avec ton dossier
local de factures deja renommees monte dans le conteneur :

    docker compose run --rm -v /chemin/vers/tes/factures:/import backend \
        python -m app.scripts.import_existing /import

Chaque fichier est deplace (dans le conteneur) vers le stockage definitif
(volume factures_data, organise delegation/annee/produit/...) et une ligne
est creee dans la table `factures`. Les fichiers qui ne suivent pas le
format attendu sont juste signales, pas plantes.
"""
import sys
from pathlib import Path

from ..database import SessionLocal, Base, engine
from ..models import Facture
from ..ocr.normalisation import normaliser_numero_facture, extraire_produit, extraire_delegation
from ..storage import chemin_final, deplacer_vers_final
from ..config import EXTENSIONS_AUTORISEES


def numero_depuis_nom_fichier(numero_avec_tirets: str) -> str:
    """Le nom de fichier remplace '/' par '-' dans le numero canonique
    (PREFIXE/PRODUIT/DELEGATION/NUMERO -> PREFIXE-PRODUIT-DELEGATION-NUMERO).
    On se base sur les 4 segments attendus plutot que de remplacer betement
    tous les tirets (le prefixe ou le numero peuvent eux-memes contenir des
    caracteres ambigus)."""
    parties = numero_avec_tirets.split("-")
    if len(parties) == 4:
        return "/".join(parties)
    # structure inattendue : on tente un remplacement simple (mieux que
    # planter), le resultat sera a verifier dans l'appli si besoin
    return numero_avec_tirets.replace("-", "/")


def importer_dossier(dossier: Path):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    fichiers = [f for f in dossier.rglob("*") if f.is_file() and f.suffix.lower() in EXTENSIONS_AUTORISEES]
    print(f"{len(fichiers)} fichier(s) trouve(s) dans {dossier}")

    importes = 0
    ignores = []

    for f in fichiers:
        if "__" not in f.stem:
            ignores.append((f.name, "pas de '__' dans le nom (format attendu : NOM__NUMERO)"))
            continue

        nom_partie, numero_partie = f.stem.split("__", 1)
        nom_exploitant = nom_partie.replace("_", " ").strip()
        numero_brut = numero_depuis_nom_fichier(numero_partie)

        numero_normalise, _, _ = normaliser_numero_facture(numero_brut)
        produit = extraire_produit(numero_normalise)
        delegation = extraire_delegation(numero_normalise)

        relatif = chemin_final(delegation, produit, f.stem, f.suffix.lower())
        chemin_definitif = deplacer_vers_final(f, relatif)

        facture = Facture(
            numero_facture=numero_normalise,
            produit=produit,
            delegation=delegation,
            nom_exploitant=nom_exploitant,
            code_client=None,
            chemin_fichier=str(chemin_definitif),
            score_confiance=100,
            verifie_manuellement=True,
        )
        db.add(facture)
        importes += 1
        print(f"  OK : {f.name}  ->  {chemin_definitif}")

    db.commit()
    db.close()

    print(f"\n{importes} facture(s) importee(s) dans la base.")
    if ignores:
        print(f"{len(ignores)} fichier(s) ignore(s) :")
        for nom, raison in ignores:
            print(f"  - {nom} : {raison}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python -m app.scripts.import_existing <dossier>")
        sys.exit(1)
    importer_dossier(Path(sys.argv[1]))
