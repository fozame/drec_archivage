# Gestion des factures numerisees

Application interne : import des scans de factures (OCR automatique),
verification/renommage assiste, recherche et impression.

## Demarrage (sur le serveur interne)

```bash
cp .env.example .env
nano .env                 # change le mot de passe de la base
docker compose up -d --build
```

L'appli est ensuite disponible sur `http://<ip-du-serveur>:8000`.

- **Importer** : depose des fichiers, un dossier entier ou une archive .zip.
- **Verifier / renommer** : les factures sont classees par score de
  confiance (haute / moyenne / non detectee), on corrige si besoin le
  numero ou le nom, on valide -> le fichier est deplace et range
  automatiquement.
- **Rechercher** : par numero de facture, nom de l'exploitant ou code
  client. Cliquer sur un resultat ouvre l'image dans un nouvel onglet
  (Ctrl+P pour imprimer).

## Mettre a jour l'appli

```bash
git pull                        # ou copie les nouveaux fichiers
docker compose up -d --build
```

Les donnees (base Postgres, factures rangees, fichiers en attente) sont
dans des volumes Docker nommes (`db_data`, `factures_data`,
`uploads_temp`) : elles survivent a une mise a jour ou un redemarrage,
tant que tu ne fais pas `docker compose down -v`.

## Sauvegardes

Deux choses a sauvegarder regulierement :

```bash
# 1) la base (metadonnees, recherche)
docker compose exec db pg_dump -U factures factures > backup_$(date +%F).sql

# 2) les fichiers eux-memes (le volume factures_data)
docker run --rm -v facture_app_factures_data:/data -v $(pwd):/backup \
    alpine tar czf /backup/factures_$(date +%F).tar.gz -C /data .
```

## Charger la base des exploitants connus

Pour que le croisement/correction automatique du nom fonctionne, ajoute tes
exploitants connus via l'API (une seule fois, ou a chaque nouvel
exploitant) :

```bash
curl -X POST http://localhost:8000/api/exploitants/import \
  -H "Content-Type: application/json" \
  -d '["ORANGE CAMEROUN SA", "VIETTEL CAMEROUN", "HOPITAL GENERAL DE DOUALA"]'
```

(un petit script pour importer directement depuis ton fichier Excel peut
etre ajoute si besoin — dis-le moi.)

## Ajuster la detection si un nouveau modele de facture n'est pas bien lu

Trois variables d'environnement dans `docker-compose.yml`, section
`backend > environment` :

- `Y_FRAC` / `H_FRAC` : position et hauteur (en % de la hauteur totale de
  l'image) de la zone d'entete a analyser.
- `RIGHT_COL_RATIO` : ou commence la colonne "nom de l'exploitant" dans
  cette zone.

Modifie, puis `docker compose up -d` (pas besoin de rebuild pour un simple
changement de variable d'environnement).

## Organisation du stockage

```
factures_data/
  Douala/
    2026/
      VSAT/
        SOCIETE_NATIONALE_DE_RAFFINERIE_(SONARA)__26A-VSAT-D-179BIS.jpg
      FH/
        ORANGE_CAMEROUN_SA__26A-FH-D-464.jpg
  Yaounde/
    ...
```

La base Postgres (table `factures`) reste la source de verite pour la
recherche ; le dossier n'est que le stockage physique, organise pour
rester exploitable meme sans passer par l'appli.

## Architecture

- **backend/** : API FastAPI (Python) + pipeline OCR (RapidOCR) +
  moteur de normalisation/scoring deja valide sur les scans reels.
- **db** (conteneur Postgres) : metadonnees + recherche.
- Deux volumes Docker separent le stockage des fichiers (`factures_data`,
  `uploads_temp`) de la base (`db_data`), pour pouvoir les sauvegarder
  independamment.
- Le frontend (pages Importer / Verifier / Rechercher) est servi
  directement par le backend (`/static`) : un seul conteneur applicatif,
  pas de build front separe -> deploiement et mise a jour simplifies.
