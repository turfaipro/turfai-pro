import os, re, json, base64, logging
import os, re, json, base64, logging
import requests
from datetime import datetime

log = logging.getLogger("TurfAI.Generator")

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER  = os.environ.get("GITHUB_OWNER", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "turfai-pro")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")


def lire_template_github():
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


def safe_replace(html, pattern, replacement):
    """Remplacement regex sécurisé — échappe les backslashes dans le remplacement."""
    # re.sub interprète \u, \n etc dans le remplacement — on échappe les backslashes
    safe_repl = replacement.replace("\\", "\\\\")
    try:
        return re.sub(pattern, safe_repl, html, count=1)
    except Exception as e:
        log.warning("safe_replace erreur : %s" % str(e))
        return html


def nettoyer(s):
    """Nettoie une chaîne pour l'utiliser dans re.sub."""
    return str(s).replace("\\", "/").replace("\n", " ").replace("\r", "")


def generer_html(data, historique):
    html = lire_template_github()
    if not html:
        raise FileNotFoundError("Impossible de lire index.html depuis GitHub")

    if not data or not data.get("partants"):
        return html

    partants = data.get("partants", [])
    tries    = data.get("partants_tries", sorted(partants, key=lambda x: x.get("sc", 0), reverse=True))
    today    = datetime.now()

    # ── Bloc JS COURSE ────────────────────────────────
    course_js  = "const COURSE = {\n"
    course_js += "  nom: %s,\n"    % json.dumps(data.get("nom", "QUINTE DU JOUR"), ensure_ascii=True)
    course_js += "  ref: %s,\n"    % json.dumps(data.get("ref", "R1C3"))
    course_js += "  lieu: %s,\n"   % json.dumps(data.get("lieu", "Hippodrome"), ensure_ascii=True)
    course_js += "  date: %s,\n"   % json.dumps(data.get("date", today.strftime("%d/%m/%Y")))
    course_js += "  dist: %s,\n"   % json.dumps(data.get("dist", "2400m Plat Bon"), ensure_ascii=True)
    course_js += "  alloc: %s,\n"  % json.dumps(data.get("alloc", "50 000 E"), ensure_ascii=True)
    course_js += "  partants: %d,\n" % len(partants)
    course_js += "  depart: %s\n"  % json.dumps(data.get("heure", "15h00"))
    course_js += "};"

    # ── Bloc JS PARTANTS ──────────────────────────────
    partants_lines = []
    for p in partants:
        nom = json.dumps(str(p.get("nom", "")), ensure_ascii=True)[1:-1]
        j   = json.dumps(str(p.get("j",  "N/A")), ensure_ascii=True)[1:-1]
        e   = json.dumps(str(p.get("e",  "N/A")), ensure_ascii=True)[1:-1]
        m   = str(p.get("m", "(25) (25) (25)")).replace("'", "")
        line = "  { n:%d, nom:'%s', j:'%s', e:'%s', p:'%s', c:'%s', m:'%s', sc:%s, prob:%s, cote:%s }" % (
            int(p.get("n", 0)),
            nom, j, e,
            str(p.get("p", "58kg")),
            str(p.get("c", "C.1")),
            m,
            str(p.get("sc", 50.0)),
            str(p.get("prob", 6.0)),
            str(p.get("cote", 10.0))
        )
        partants_lines.append(line)
    partants_js = "const PARTANTS = [\n" + ",\n".join(partants_lines) + "\n];"

    # ── Bloc JS HISTORIQUE (5 derniers) ───────────────
    histo_recent = [h for h in historique if h.get("reel")][:5]
    histo_lines  = []
    for h in histo_recent:
        reel_str = json.dumps(h["reel"]) if h.get("reel") else "null"
        prec_str = str(h["prec"]) if h.get("prec") is not None else "null"
        q5_str   = str(h.get("quinte", False)).lower()
        histo_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date", ""), ensure_ascii=True),
                json.dumps(h.get("nom",  ""), ensure_ascii=True),
                json.dumps(h.get("lieu", ""), ensure_ascii=True),
                json.dumps(h.get("predit", [])),
                reel_str, prec_str, q5_str,
                str(h.get("profit", 0))
            )
        )
    histo_js = "const HISTORIQUE = [\n" + ",\n".join(histo_lines) + "\n];"

    # ── Bloc JS HISTORIQUE_FULL (30 derniers) ─────────
    full_lines = []
    for h in historique[:30]:
        reel_str = json.dumps(h["reel"]) if h.get("reel") else "null"
        prec_str = str(h.get("prec", "null"))
        q5_str   = str(h.get("quinte", False)).lower()
        full_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date", ""), ensure_ascii=True),
                json.dumps(h.get("nom",  ""), ensure_ascii=True),
                json.dumps(h.get("lieu", ""), ensure_ascii=True),
                json.dumps(h.get("predit", [])),
                reel_str, prec_str, q5_str,
                str(h.get("profit", 0))
            )
        )
    histo_full_js = "const HISTORIQUE_FULL = [\n" + ",\n".join(full_lines) + "\n];"

    # ── Remplacements sécurisés ───────────────────────
    html = safe_replace(html, r"const COURSE = \{[\s\S]*?\};", course_js)
    html = safe_replace(html, r"const PARTANTS = \[[\s\S]*?\];(?=\s*\n\s*const TOTAL_PROB)", partants_js)
    html = safe_replace(html, r"const HISTORIQUE = \[[\s\S]*?\];(?=\s*\n\s*/\*)", histo_js)
    html = safe_replace(html, r"const HISTORIQUE_FULL = \[[\s\S]*?\];", histo_full_js)

    # ── Sidebar race widget ───────────────────────────
    nom_safe  = nettoyer(data.get("nom", ""))
    lieu_safe = nettoyer(data.get("lieu", ""))
    ref_safe  = data.get("ref", "R1C3")
    heure_safe = data.get("heure", "15h00")

    html = safe_replace(
        html,
        r'class="sidebar-race-name">[^<]*</div>',
        'class="sidebar-race-name">%s</div>' % nom_safe
    )
    html = safe_replace(
        html,
        r'class="sidebar-race-meta">[^<]*</div>',
        'class="sidebar-race-meta">%s - %s - %s</div>' % (lieu_safe, ref_safe, heure_safe)
    )

    log.info("HTML genere : %d caracteres" % len(html))
    return html
