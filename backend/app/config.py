import os
from pathlib import Path

# URL de connexion a la base. En local (sans Docker) on retombe sur SQLite
# pour pouvoir tester sans Postgres. En production (docker-compose), la
# variable d'environnement DATABASE_URL pointe vers le conteneur Postgres.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./factures_dev.db",
)

# Dossier ou atterrissent les fichiers juste apres upload, en attente de
# verification/validation (avant d'avoir un nom et un emplacement definitifs).
TEMP_DIR = Path(os.environ.get("TEMP_DIR", "/data/uploads_temp"))

# Dossier de stockage final des factures validees, organise par
# delegation/annee/produit/NOM__NUMERO.ext
FACTURES_DIR = Path(os.environ.get("FACTURES_DIR", "/data/factures"))

TEMP_DIR.mkdir(parents=True, exist_ok=True)
FACTURES_DIR.mkdir(parents=True, exist_ok=True)

EXTENSIONS_AUTORISEES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# Position/hauteur (en proportion de la hauteur totale de l'image) de la zone
# d'entete a analyser. A ajuster si un nouveau modele de facture n'est pas
# bien detecte.
Y_FRAC = float(os.environ.get("Y_FRAC", "0.171"))
H_FRAC = float(os.environ.get("H_FRAC", "0.257"))
RIGHT_COL_RATIO = float(os.environ.get("RIGHT_COL_RATIO", "0.48"))
