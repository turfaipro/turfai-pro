"""
TurfAI Pro v5 — GitHub Updater
- Push index.html via API GitHub REST
- Gère historique.json (fichier JSON dans le repo GitHub)
- Vercel redéploie automatiquement après chaque push
"""
import os, base64, json, logging
import requests

log = logging.getLogger("TurfAI.GitHub")

TOKEN  = os.environ.get("GITHUB_TOKEN", "")
OWNER  = os.environ.get("GITHUB_OWNER", "")
REPO   = os.environ.get("GITHUB_REPO", "turfai-pro")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
}
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"


def _get_sha(path: str) -> str | None:
    """Récupère le SHA d'un fichier existant dans le repo."""
    try:
        r = requests.get(f"{BASE}/contents/{path}?ref={BRANCH}", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get("sha")
        if r.status_code == 404:
            return None  # Fichier n'existe pas encore
        log.warning(f"get_sha {path} → HTTP {r.status_code}")
        return None
    except Exception as e:
        log.error(f"get_sha exception : {e}")
        return None


def _put_file(path: str, content_bytes: bytes, message: str) -> bool:
    """Crée ou met à jour un fichier dans GitHub."""
    if not TOKEN or not OWNER:
        log.error("GITHUB_TOKEN ou GITHUB_OWNER non configurés")
        return False

    sha = _get_sha(path)
    b64 = base64.b64encode(content_bytes).decode("utf-8")
    payload = {"message": message, "content": b64, "branch": BRANCH}
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(f"{BASE}/contents/{path}", headers=HEADERS, json=payload, timeout=30)
        if r.status_code in (200, 201):
            log.info(f"✅ GitHub : {path} mis à jour")
            return True
        log.error(f"GitHub PUT {path} → HTTP {r.status_code} : {r.text[:200]}")
        return False
    except Exception as e:
        log.error(f"GitHub exception : {e}")
        return False


def push_github(html_content: str, commit_message: str) -> bool:
    """Push index.html vers GitHub."""
    return _put_file(
        path="index.html",
        content_bytes=html_content.encode("utf-8"),
        message=commit_message,
    )


# ── Gestion historique.json ──────────────────────────────────

HISTORIQUE_PATH = "historique.json"

def get_historique_github() -> list:
    """
    Récupère l'historique depuis historique.json dans le repo GitHub.
    Retourne une liste d'entrées (plus récente en premier).
    """
    try:
        r = requests.get(
            f"{BASE}/contents/{HISTORIQUE_PATH}?ref={BRANCH}",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 404:
            log.info("historique.json inexistant — retour liste vide")
            return _historique_defaut()
        if r.status_code != 200:
            log.warning(f"get_historique → HTTP {r.status_code}")
            return _historique_defaut()

        data = r.json()
        content_b64 = data.get("content", "")
        content_str = base64.b64decode(content_b64).decode("utf-8")
        historique = json.loads(content_str)
        log.info(f"✅ Historique chargé : {len(historique)} entrées")
        return historique

    except Exception as e:
        log.error(f"get_historique exception : {e}")
        return _historique_defaut()


def save_historique_github(historique: list) -> bool:
    """Sauvegarde l'historique dans historique.json sur GitHub."""
    content = json.dumps(historique, ensure_ascii=False, indent=2)
    return _put_file(
        path=HISTORIQUE_PATH,
        content_bytes=content.encode("utf-8"),
        message=f"📊 Historique mis à jour — {len(historique)} entrées",
    )


def _historique_defaut() -> list:
    """Historique de démarrage avec les données de démo du HTML."""
    return [
        {"date":"Sam. 14/03/2026","nom":"PRIX GÉNÉRAL DE ROUGEMONT","lieu":"Auteuil",
         "predit":[7,2,4,6,14],"reel":[4,2,7,6,3],"prec":72,"quinte":False,"profit":-3.0},
        {"date":"Jeu. 12/03/2026","nom":"PRIX JOCKER","lieu":"Chantilly",
         "predit":[9,11,6,2,8],"reel":[11,9,6,5,2],"prec":80,"quinte":True,"profit":8.1},
        {"date":"Mer. 11/03/2026","nom":"PRIX KARAMELYOK","lieu":"Vincennes",
         "predit":[7,11,3,5,2],"reel":[7,5,11,2,3],"prec":76,"quinte":True,"profit":5.8},
        {"date":"Mar. 10/03/2026","nom":"PRIX DE GUERVILLE","lieu":"Saint-Cloud",
         "predit":[9,3,6,1,14],"reel":[9,3,6,14,1],"prec":88,"quinte":True,"profit":12.4},
        {"date":"Dim. 01/03/2026","nom":"PRIX SAINT-ALARY","lieu":"Longchamp",
         "predit":[1,6,3,8,15],"reel":[6,1,3,15,8],"prec":80,"quinte":False,"profit":4.5},
        {"date":"Sam. 28/02/2026","nom":"PRIX DES LILAS","lieu":"Chantilly",
         "predit":[8,2,5,11,4],"reel":[8,2,5,4,11],"prec":88,"quinte":True,"profit":15.2},
        {"date":"Ven. 27/02/2026","nom":"PRIX DU GERS","lieu":"Pau",
         "predit":[3,9,7,1,12],"reel":[9,3,7,12,1],"prec":80,"quinte":False,"profit":5.1},
        {"date":"Mer. 25/02/2026","nom":"PRIX CLAIR DE LUNE","lieu":"Saint-Cloud",
         "predit":[2,4,6,9,3],"reel":[2,4,9,6,14],"prec":72,"quinte":False,"profit":-2.0},
        {"date":"Lun. 23/02/2026","nom":"PRIX UNIVERS II","lieu":"Auteuil",
         "predit":[5,1,8,3,7],"reel":[1,5,8,3,7],"prec":84,"quinte":True,"profit":11.0},
    ]


def verifier_connexion() -> bool:
    """Vérifie la connexion GitHub."""
    try:
        r = requests.get("https://api.github.com/user", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            log.info(f"✅ GitHub connecté : {r.json().get('login','?')}")
            return True
        log.error(f"❌ GitHub token invalide : HTTP {r.status_code}")
        return False
    except Exception as e:
        log.error(f"GitHub connexion : {e}")
        return False
