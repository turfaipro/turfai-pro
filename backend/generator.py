import os, re, json, base64, logging
import requests
from datetime import datetime, date

log = logging.getLogger("TurfAI.Generator")

JOURS_FR = {
    "Monday":"Lundi","Tuesday":"Mardi","Wednesday":"Mercredi",
    "Thursday":"Jeudi","Friday":"Vendredi","Saturday":"Samedi","Sunday":"Dimanche"
}
MOIS_FR = {
    1:"Janvier",2:"Fevrier",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
    7:"Juillet",8:"Aout",9:"Septembre",10:"Octobre",11:"Novembre",12:"Decembre"
}

# Variables GitHub pour lire index.html
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER  = os.environ.get("GITHUB_OWNER", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "turfai-pro")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")


def lire_template_github():
    """Lit index.html directement depuis GitHub via l'API."""
    url = "https://api.github.com/repos/%s/%s/contents/index.html?ref=%s" % (
        GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH
    )
    headers = {
        "Authorization": "Bearer %s" % GITHUB_TOKEN,
        "Accept": "application/vnd.github+json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        content_b64 = r.json().get("content", "")
        content = base64.b64decode(content_b64).decode("utf-8")
        log.info("Template lu depuis GitHub (%d caracteres)" % len(content))
        return content
    except Exception as e:
        log.error("Impossible de lire index.html depuis GitHub : %s" % str(e))
        return None


def generer_html(data, historique):
    """Génère le fichier index.html complet avec les nouvelles données."""

    # Lire le template depuis GitHub
    html = lire_template_github()
    if not html:
        log.error("Template introuvable")
        raise FileNotFoundError("Impossible de lire index.html depuis GitHub")

    if not data or not data.get("partants"):
        log.warning("Pas de donnees course — template retourne sans modification")
        return html

    partants = data.get("partants", [])
    tries    = data.get("partants_tries", sorted(partants, key=lambda x: x.get("sc",0), reverse=True))
    favori   = data.get("favori", tries[0] if tries else {})
    grilles  = data.get("grilles", {})
    today    = datetime.now()

    # ── Bloc JS COURSE ────────────────────────────────
    course_js = "const COURSE = {\n"
    course_js += "  nom: %s,\n"   % json.dumps(data.get("nom","QUINTE DU JOUR"))
    course_js += "  ref: %s,\n"   % json.dumps(data.get("ref","R1C3"))
    course_js += "  lieu: %s,\n"  % json.dumps(data.get("lieu","Hippodrome"))
    course_js += "  date: %s,\n"  % json.dumps(data.get("date",today.strftime("%d/%m/%Y")))
    course_js += "  dist: %s,\n"  % json.dumps(data.get("dist","2400m Plat Bon"))
    course_js += "  alloc: %s,\n" % json.dumps(data.get("alloc","50 000 E"))
    course_js += "  partants: %d,\n" % len(partants)
    course_js += "  depart: %s\n" % json.dumps(data.get("heure","15h00"))
    course_js += "};"

    # ── Bloc JS PARTANTS ──────────────────────────────
    partants_lines = []
    for p in partants:
        nom = str(p.get("nom","")).replace("'","\\'").replace('"','\\"')
        j   = str(p.get("j","N/A")).replace("'","\\'")
        e   = str(p.get("e","N/A")).replace("'","\\'")
        line = "  { n:%d, nom:'%s', j:'%s', e:'%s', p:'%s', c:'%s', m:'%s', sc:%s, prob:%s, cote:%s }" % (
            p.get("n",0), nom, j, e,
            p.get("p","58kg"), p.get("c","C.1"),
            p.get("m","(25) (25) (25)"),
            str(p.get("sc",50.0)),
            str(p.get("prob",6.0)),
            str(p.get("cote",10.0))
        )
        partants_lines.append(line)
    partants_js = "const PARTANTS = [\n" + ",\n".join(partants_lines) + "\n];"

    # ── Bloc JS HISTORIQUE (5 derniers) ───────────────
    histo_recent = [h for h in historique if h.get("reel")][:5]
    histo_lines  = []
    for h in histo_recent:
        reel_str = json.dumps(h["reel"]) if h.get("reel") else "null"
        prec_str = str(h["prec"]) if h.get("prec") is not None else "null"
        q5_str   = str(h.get("quinte",False)).lower()
        histo_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date","")),
                json.dumps(h.get("nom","")),
                json.dumps(h.get("lieu","")),
                json.dumps(h.get("predit",[])),
                reel_str, prec_str, q5_str,
                str(h.get("profit",0))
            )
        )
    histo_js = "const HISTORIQUE = [\n" + ",\n".join(histo_lines) + "\n];"

    # ── Bloc JS HISTORIQUE_FULL (30 derniers) ─────────
    full_lines = []
    for h in historique[:30]:
        reel_str = json.dumps(h["reel"]) if h.get("reel") else "null"
        prec_str = str(h.get("prec","null"))
        q5_str   = str(h.get("quinte",False)).lower()
        full_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date","")),
                json.dumps(h.get("nom","")),
                json.dumps(h.get("lieu","")),
                json.dumps(h.get("predit",[])),
                reel_str, prec_str, q5_str,
                str(h.get("profit",0))
            )
        )
    histo_full_js = "const HISTORIQUE_FULL = [\n" + ",\n".join(full_lines) + "\n];"

    # ── Remplacements dans le HTML ────────────────────
    html = re.sub(r"const COURSE = \{[\s\S]*?\};", course_js, html, count=1)
    html = re.sub(r"const PARTANTS = \[[\s\S]*?\];(?=\s*\n\s*const TOTAL_PROB)", partants_js, html, count=1)
    html = re.sub(r"const HISTORIQUE = \[[\s\S]*?\];(?=\s*\n\s*/\*)", histo_js, html, count=1)
    html = re.sub(r"const HISTORIQUE_FULL = \[[\s\S]*?\];", histo_full_js, html, count=1)

    # ── Sidebar race widget ───────────────────────────
    html = re.sub(
        r'class="sidebar-race-name">[^<]*</div>',
        'class="sidebar-race-name">%s</div>' % data.get("nom",""),
        html, count=1
    )
    html = re.sub(
        r'class="sidebar-race-meta">[^<]*</div>',
        'class="sidebar-race-meta">%s &middot; %s &middot; %s</div>' % (
            data.get("lieu",""), data.get("ref","R1C3"), data.get("heure","15h00")
        ),
        html, count=1
    )

    # ── Timestamp ─────────────────────────────────────
    ts = today.strftime("%d/%m/%Y a %H:%M")
    html = re.sub(
        r"TurfAI Pro v[45]\.0 [^<'\"]*",
        "TurfAI Pro v5 · %s %s · %s · Genere %s" % (
            data.get("nom",""), data.get("ref",""), data.get("lieu",""), ts
        ),
        html
    )

    log.info("HTML genere : %d caracteres" % len(html))
    return html
 
