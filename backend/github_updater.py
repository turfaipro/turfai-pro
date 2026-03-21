import os, base64, json, logging
import os, base64, json, logging
import requests

log = logging.getLogger("TurfAI.GitHub")

TOKEN  = os.environ.get("GITHUB_TOKEN", "")
OWNER  = os.environ.get("GITHUB_OWNER", "")
REPO   = os.environ.get("GITHUB_REPO", "turfai-pro")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")

HISTORIQUE_PATH = "historique.json"


def get_headers():
    return {
        "Authorization": "Bearer %s" % TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def get_base_url():
    return "https://api.github.com/repos/%s/%s" % (OWNER, REPO)


def _get_sha(path):
    try:
        url = "%s/contents/%s?ref=%s" % (get_base_url(), path, BRANCH)
        r   = requests.get(url, headers=get_headers(), timeout=15)
        if r.status_code == 200:
            return r.json().get("sha")
        if r.status_code == 404:
            return None
        log.warning("get_sha %s -> HTTP %d" % (path, r.status_code))
        return None
    except Exception as e:
        log.error("get_sha exception : %s" % str(e))
        return None


def _put_file(path, content_bytes, message):
    if not TOKEN or not OWNER:
        log.error("GITHUB_TOKEN ou GITHUB_OWNER non configures")
        return False

    sha     = _get_sha(path)
    b64     = base64.b64encode(content_bytes).decode("utf-8")
    payload = {"message": message, "content": b64, "branch": BRANCH}
    if sha:
        payload["sha"] = sha

    try:
        url = "%s/contents/%s" % (get_base_url(), path)
        r   = requests.put(url, headers=get_headers(), json=payload, timeout=30)
        if r.status_code in (200, 201):
            log.info("GitHub OK : %s mis a jour" % path)
            return True
        log.error("GitHub PUT %s -> HTTP %d : %s" % (path, r.status_code, r.text[:200]))
        return False
    except Exception as e:
        log.error("GitHub exception : %s" % str(e))
        return False


def push_github(html_content, commit_message):
    return _put_file(
        path="index.html",
        content_bytes=html_content.encode("utf-8"),
        message=commit_message,
    )


def get_historique_github():
    try:
        url = "%s/contents/%s?ref=%s" % (get_base_url(), HISTORIQUE_PATH, BRANCH)
        r   = requests.get(url, headers=get_headers(), timeout=15)
        if r.status_code == 404:
            log.info("historique.json inexistant — retour liste vide")
            return _historique_defaut()
        if r.status_code != 200:
            log.warning("get_historique -> HTTP %d" % r.status_code)
            return _historique_defaut()
        content_b64 = r.json().get("content", "")
        content_str = base64.b64decode(content_b64).decode("utf-8")
        historique  = json.loads(content_str)
        log.info("Historique charge : %d entrees" % len(historique))
        return historique
    except Exception as e:
        log.error("get_historique exception : %s" % str(e))
        return _historique_defaut()


def save_historique_github(historique):
    content = json.dumps(historique, ensure_ascii=False, indent=2)
    return _put_file(
        path=HISTORIQUE_PATH,
        content_bytes=content.encode("utf-8"),
        message="Historique mis a jour — %d entrees" % len(historique),
    )


def _historique_defaut():
    return [
        {"date":"Sam. 14/03/2026","nom":"PRIX GENERAL DE ROUGEMONT","lieu":"Auteuil",
         "predit":[7,2,4,6,14],"reel":[4,2,7,6,3],"prec":72,"quinte":False,"profit":-3.0},
        {"date":"Jeu. 12/03/2026","nom":"PRIX JOCKER","lieu":"Chantilly",
         "predit":[9,11,6,2,8],"reel":[11,9,6,5,2],"prec":80,"quinte":True,"profit":8.1},
        {"date":"Mer. 11/03/2026","nom":"PRIX KARAMELYOK","lieu":"Vincennes",
         "predit":[7,11,3,5,2],"reel":[7,5,11,2,3],"prec":76,"quinte":True,"profit":5.8},
        {"date":"Mar. 10/03/2026","nom":"PRIX DE GUERVILLE","lieu":"Saint-Cloud",
         "predit":[9,3,6,1,14],"reel":[9,3,6,14,1],"prec":88,"quinte":True,"profit":12.4},
        {"date":"Sam. 28/02/2026","nom":"PRIX DES LILAS","lieu":"Chantilly",
         "predit":[8,2,5,11,4],"reel":[8,2,5,4,11],"prec":88,"quinte":True,"profit":15.2},
    ]


def verifier_connexion():
    try:
        r = requests.get("https://api.github.com/user", headers=get_headers(), timeout=10)
        if r.status_code == 200:
            login = r.json().get("login","?")
            log.info("GitHub connecte : %s" % login)
            return True
        log.error("GitHub token invalide : HTTP %d" % r.status_code)
        return False
    except Exception as e:
        log.error("GitHub connexion : %s" % str(e))
        return False
