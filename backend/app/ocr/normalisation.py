"""
Normalisation du numero de facture, croisement avec la base des exploitants,
et calcul du score de confiance.

Ce module est le meme moteur que renommer_factures_v3.py, mais expose des
fonctions unitaires (par facture) plutot que le traitement d'un dossier
entier : l'appli web traite les factures une par une au moment de l'upload.
"""
import re
import difflib

PRODUITS = ["ADMP", "AGR", "DE", "DR", "FE", "FH", "FST", "HOM", "LOYER", "LS",
            "PEN", "RADIF", "RAM", "RARN", "REPDIP", "RFOR", "ROP", "RPIP", "VIGN", "VSAT"]

DELEGATIONS = {"Y": "Yaounde", "B": "Bamenda", "D": "Douala", "G": "Garoua"}

_CONFUSIONS_DELEGATION = {
    "Y": {"Y", "N", "V", "T"},
    "B": {"B", "8", "R"},
    "D": {"D", "0", "O"},
    "G": {"G", "6", "C", "Q"},
}

_FORMAT_CANONIQUE = re.compile(r"^\d{2}[A-Z]/[A-Z]+/[YBDG]/\d+[A-Z]*$")


# ---------------------------------------------------------------------------
# Normalisation du numero de facture : PREFIXE/PRODUIT/DELEGATION/NUMERO
# ---------------------------------------------------------------------------

def _corriger_produit_segment(segment):
    match = difflib.get_close_matches(segment.upper(), PRODUITS, n=1, cutoff=0.5)
    if not match:
        return segment.upper(), False
    produit_corrige = match[0]
    return produit_corrige, (produit_corrige != segment.upper())


def _corriger_delegation(lettre):
    lettre = lettre.upper()
    if lettre in DELEGATIONS:
        return lettre, False
    for code, confusions in _CONFUSIONS_DELEGATION.items():
        if lettre in confusions:
            return code, True
    return None, False


def _tenter_split_produit_delegation(segment):
    if len(segment) < 3:
        return None, None, False
    candidat_produit, candidat_deleg = segment[:-1], segment[-1]
    deleg, deleg_corrigee = _corriger_delegation(candidat_deleg)
    if deleg is None:
        return None, None, False
    produit_corrige, produit_corrige_flag = _corriger_produit_segment(candidat_produit)
    ratio = difflib.SequenceMatcher(None, candidat_produit.upper(), produit_corrige).ratio()
    if ratio < 0.6:
        return None, None, False
    return produit_corrige, deleg, (produit_corrige_flag or deleg_corrigee)


def normaliser_numero_facture(numero_facture):
    """
    Normalise au format canonique PREFIXE/PRODUIT/DELEGATION/NUMERO+SUFFIXE.
    return : (numero_normalise, quelque_chose_corrige, format_complet)
    """
    if not numero_facture:
        return numero_facture, False, False
    numero_facture = numero_facture.strip()

    m = re.match(
        r"^(\d{2}[A-Za-z])[\s\-/]+([A-Za-z0-9]+)/([A-Za-z0-9]+)/(\d+)([A-Za-z]*)$",
        numero_facture
    )
    if m:
        prefixe, produit, deleg_brut, numero, suffixe = m.groups()
        produit_corrige, produit_corrige_flag = _corriger_produit_segment(produit)
        deleg, deleg_corrigee = _corriger_delegation(deleg_brut)
        if deleg:
            canon = f"{prefixe.upper()}/{produit_corrige}/{deleg}/{numero}{suffixe.upper()}"
            return canon, (produit_corrige_flag or deleg_corrigee), True
        canon = f"{prefixe.upper()}/{produit_corrige}/{deleg_brut.upper()}/{numero}{suffixe.upper()}"
        return canon, True, False

    m = re.match(
        r"^(\d{2}[A-Za-z])[\s\-/]+([A-Za-z0-9]+)/(\d+)([A-Za-z]*)$",
        numero_facture
    )
    if m:
        prefixe, segment, numero, suffixe = m.groups()
        produit, deleg, corrige = _tenter_split_produit_delegation(segment)
        if produit and deleg:
            canon = f"{prefixe.upper()}/{produit}/{deleg}/{numero}{suffixe.upper()}"
            return canon, True, True
        produit_corrige, produit_corrige_flag = _corriger_produit_segment(segment)
        canon = f"{prefixe.upper()}/{produit_corrige}/{numero}{suffixe.upper()}"
        return canon, produit_corrige_flag, False

    return numero_facture, False, False


def extraire_produit(numero_normalise):
    if not numero_normalise or not _FORMAT_CANONIQUE.match(numero_normalise):
        return None
    return numero_normalise.split("/")[1]


def extraire_delegation(numero_normalise):
    if not numero_normalise or not _FORMAT_CANONIQUE.match(numero_normalise):
        return None
    return DELEGATIONS.get(numero_normalise.split("/")[2])


def numero_pour_nom_fichier(numero_normalise):
    """'/' est interdit dans un nom de fichier -> remplace par '-'."""
    if not numero_normalise:
        return None
    return numero_normalise.replace("/", "-")


# ---------------------------------------------------------------------------
# Croisement avec la base des exploitants
# ---------------------------------------------------------------------------

def normaliser_nom(texte):
    if not texte:
        return ""
    return re.sub(r"[^A-Z0-9]", "", texte.upper())


def corriger_exploitant(nom_ocr, base_exploitants, cutoff=0.6):
    """
    base_exploitants : liste de noms canoniques connus (peut venir de la
                        table `exploitants` en base), ou liste vide pour
                        desactiver le croisement.
    return : (nom_corrige, trouve_dans_bd)
    """
    if not nom_ocr or not base_exploitants:
        return nom_ocr, False

    nom_norm = normaliser_nom(nom_ocr)
    index_norm = {normaliser_nom(n): n for n in base_exploitants}

    if nom_norm in index_norm:
        return index_norm[nom_norm], True

    candidats = difflib.get_close_matches(nom_norm, index_norm.keys(), n=1, cutoff=cutoff)
    if candidats:
        return index_norm[candidats[0]], True

    return nom_ocr, False


def nettoyer_nom_exploitant(nom_exploitant):
    """Nettoie le nom pour un usage dans un nom de fichier."""
    if not nom_exploitant:
        return None
    nom = re.sub(r"[\\/:*?\"<>|]", " ", nom_exploitant)
    nom = re.sub(r"\s+", "_", nom.strip())
    return nom.upper()


# ---------------------------------------------------------------------------
# Score de confiance (0-100)
# ---------------------------------------------------------------------------

def calculer_score(numero_brut, format_complet, numero_corrige_flag,
                    nom_exploitant, nom_trouve_bd, code_client, coherent):
    if not numero_brut:
        return 0

    score = 0
    score += 40 if format_complet else 15
    if nom_exploitant:
        score += 15
        if nom_trouve_bd:
            score += 15
    if code_client:
        score += 20 if coherent else -30
    else:
        score += 10
    if format_complet and not numero_corrige_flag:
        score += 10

    return max(0, min(100, score))


def niveau_confiance(score):
    if score == 0:
        return "non_detecte"
    if score >= 80:
        return "haute"
    return "moyenne"


def analyser_facture(info, base_exploitants=None):
    """
    Prend le dict retourne par extract_facture_info(...) pour UNE facture et
    calcule tout ce qu'il faut pour la proposition de renommage :
    numero normalise, produit, delegation, nom corrige, score, confiance,
    nom de fichier suggere (sans extension).

    return : dict pret a etre enregistre en base (table pending).
    """
    numero_brut = info.get("numero_facture")
    numero_normalise, numero_corrige_flag, format_complet = normaliser_numero_facture(numero_brut)
    produit = extraire_produit(numero_normalise)
    delegation = extraire_delegation(numero_normalise)

    nom_ocr = info.get("nom_exploitant")
    nom_corrige, nom_trouve_bd = corriger_exploitant(nom_ocr, base_exploitants)

    score = calculer_score(numero_brut, format_complet, numero_corrige_flag,
                            nom_ocr, nom_trouve_bd, info.get("code_client"), info.get("coherent"))
    confiance = niveau_confiance(score)

    nom_nettoye = nettoyer_nom_exploitant(nom_corrige)
    numero_fichier = numero_pour_nom_fichier(numero_normalise)
    nom_suggere = f"{nom_nettoye}__{numero_fichier}" if (nom_nettoye and numero_fichier) else None

    return {
        "numero_facture": numero_normalise,
        "produit": produit,
        "delegation": delegation,
        "nom_exploitant": nom_corrige,
        "nom_trouve_bd": nom_trouve_bd,
        "code_client": info.get("code_client"),
        "coherent": info.get("coherent"),
        "score": score,
        "confiance": confiance,
        "nom_suggere": nom_suggere,
    }
