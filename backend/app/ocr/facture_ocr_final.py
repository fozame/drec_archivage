import re
import cv2
from rapidocr_onnxruntime import RapidOCR

_engine = RapidOCR()  # a instancier une seule fois


def _run_ocr(img):
    result, _ = _engine(img)
    if not result:
        return ""
    boxes = sorted(result, key=lambda r: (min(p[1] for p in r[0]), min(p[0] for p in r[0])))
    return "\n".join(text for box, text, score in boxes)


def _extract_numero_facture(text):
    # 1) motif specifique au format observe : 26A-ADMP/D/553, 26A-ADMP/D/553bis,
    #    26A-ADMP/Y/490 ... chiffre(s)+lettre - lettres / code / chiffres(+suffixe)
    #    C'est independant de l'ordre des lignes rendu par l'OCR, donc plus fiable
    #    qu'une recherche "pres du libelle".
    match = re.search(
        r"\b(\d{1,3}[A-Za-z]-[A-Za-z]{2,8}/[A-Za-z0-9]{1,3}/\d{2,5}[A-Za-z]{0,4})\b",
        text
    )
    if match:
        return match.group(1)

    # 2) repli : valeur pres du libelle "N Facture", sur la meme ligne,
    #    puis en remontant AVANT de regarder apres (l'OCR place souvent
    #    la valeur au-dessus du libelle plutot qu'en dessous)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if re.search(r"N[°o0]?\s*Facture", line, re.IGNORECASE):
            after = re.split(r"Facture\s*[:;\-]?", line, maxsplit=1, flags=re.IGNORECASE)
            if len(after) > 1 and after[1].strip():
                candidate = re.sub(r"[^A-Za-z0-9\-/]+$", "", after[1].strip())
                if len(candidate) >= 3:
                    return candidate
            for j in (i - 1, i + 1):
                if 0 <= j < len(lines) and j != i:
                    cand = lines[j].strip()
                    looks_like_date = re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", cand)
                    if (re.search(r"[A-Za-z0-9]{3,}", cand)
                            and not looks_like_date
                            and not re.search(r"Facture|Date|Client|Budg[ée]taire|P[ée]riode", cand, re.IGNORECASE)):
                        return cand
    return None


def _extract_nom_exploitant(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bp_idx = None
    for i, line in enumerate(lines):
        # "BP :", "BP:990" et "B.P.365" (point au lieu d'espace) doivent tous matcher
        if re.match(r"^B[\.\s]*P[\.\s]*[:.]?", line, re.IGNORECASE):
            bp_idx = i
            break
    if bp_idx is None:
        return None

    name_lines = []
    for line in reversed(lines[:bp_idx]):
        if re.search(r"Facture|Cl+[ie]+nt|Budg[ée]taire|P[ée]riode|^Date|RECEPTION|JOURS", line, re.IGNORECASE):
            break
        # un nom d'exploitant (organisme/entreprise) ne contient jamais de
        # chiffre dans nos exemples ; une ligne avec un chiffre est presque
        # toujours un "code client" mal lu par l'OCR (ex: DLT465B1S au lieu
        # de DLT-465BIS, ou le tiret et le 'I' disparaissent/se deforment)
        if re.search(r"\d", line):
            break
        name_lines.append(line)
    return " ".join(reversed(name_lines)).strip() or None


def _extract_code_client(text):
    # motif "DLT-465", "DLT-465bis", "YCE-490" ... juste sous "Code client :"
    # sert de verification croisee avec le numero de facture (meme suffixe)
    match = re.search(r"\b([A-Za-z]{2,5}[\s\-]\d{2,6}[A-Za-z]{0,4})\b", text)
    return match.group(1).strip() if match else None


def _digits_suffix(s):
    if not s:
        return None
    last_part = s.replace(" ", "-").split("/")[-1]
    m = re.search(r"(\d{2,6})", last_part)
    return m.group(1) if m else None


def extract_facture_info(images, right_col_ratio=0.48, debug=False):
    """
    OCR (RapidOCR) + extraction du numero de facture et du nom de l'exploitant.

    images          : np.ndarray ou list[np.ndarray] (crops issus de crop_images)
    right_col_ratio : proportion (0-1) ou commence la colonne exploitant
    debug           : si True, affiche le texte OCR brut de chaque colonne

    return : dict ou liste de dict {"numero_facture":..., "nom_exploitant":..., "texte_gauche":..., "texte_droite":...}
    """
    def _process(img, idx=None):
        h, w = img.shape[:2]
        left = img[:, 0:int(w * (right_col_ratio + 0.04))]
        right = img[:, int(w * right_col_ratio):w]

        text_left = _run_ocr(left)
        text_right = _run_ocr(right)

        numero_facture = _extract_numero_facture(text_left)
        code_client = _extract_code_client(text_right)

        num_suffix = _digits_suffix(numero_facture)
        code_suffix = _digits_suffix(code_client)
        coherent = (num_suffix is None or code_suffix is None or num_suffix == code_suffix)

        info = {
            "numero_facture": numero_facture,
            "nom_exploitant": _extract_nom_exploitant(text_right),
            "code_client": code_client,
            "coherent": coherent,  # False = le numero de facture et le code client
                                    # ne se correspondent pas -> a verifier manuellement
            "texte_gauche": text_left,
            "texte_droite": text_right,
        }

        if debug:
            label = f"[image {idx}]" if idx is not None else ""
            print(f"--- {label} TEXTE GAUCHE ---")
            print(text_left)
            print(f"--- {label} TEXTE DROITE ---")
            print(text_right)
            print(f"--- {label} RESULTAT --- numero={info['numero_facture']!r}  code_client={info['code_client']!r}  "
                  f"coherent={info['coherent']}  nom={info['nom_exploitant']!r}\n")

        return info

    if isinstance(images, list):
        return [_process(img, idx=i) for i, img in enumerate(images)]
    else:
        return _process(images)
