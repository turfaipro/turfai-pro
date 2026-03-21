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


def safe_sub(pattern, replacement, html):
    """Remplacement regex sécurisé."""
    safe = replacement.replace("\\", "\\\\")
    try:
        result = re.sub(pattern, safe, html, count=1)
        return result
    except Exception as e:
        log.warning("safe_sub erreur [%s] : %s" % (pattern[:30], str(e)))
        return html


def generer_html(data, historique):
    html = lire_template_github()
    if not html:
        raise FileNotFoundError("Impossible de lire index.html depuis GitHub")

    if not data or not data.get("partants"):
        return html

    partants = data.get("partants", [])
    today    = datetime.now()

    nouveau_nom   = str(data.get("nom",   "QUINTE DU JOUR"))
    nouveau_ref   = str(data.get("ref",   "R1C3"))
    nouveau_lieu  = str(data.get("lieu",  "Hippodrome"))
    nouveau_date  = str(data.get("date",  today.strftime("%d/%m/%Y")))
    nouveau_heure = str(data.get("heure", "15h00"))
    nouveau_dist  = str(data.get("dist",  "2400m Plat Bon"))
    nouveau_alloc = str(data.get("alloc", "50 000 E"))

    # ── Extraire l'ancien nom depuis le JS pour le remplacer partout ──
    m_ancien = re.search(r"const COURSE = \{[\s\S]*?nom:\s*['\"]([^'\"]+)['\"]", html)
    ancien_nom = m_ancien.group(1) if m_ancien else None

    m_ancien_ref = re.search(r"const COURSE = \{[\s\S]*?ref:\s*['\"]([^'\"]+)['\"]", html)
    ancien_ref = m_ancien_ref.group(1) if m_ancien_ref else None

    m_ancien_date = re.search(r"const COURSE = \{[\s\S]*?date:\s*['\"]([^'\"]+)['\"]", html)
    ancien_date = m_ancien_date.group(1) if m_ancien_date else None

    # ── Bloc JS COURSE ────────────────────────────────────────────────
    course_js  = "const COURSE = {\n"
    course_js += "  nom: %s,\n"    % json.dumps(nouveau_nom,   ensure_ascii=True)
    course_js += "  ref: %s,\n"    % json.dumps(nouveau_ref)
    course_js += "  lieu: %s,\n"   % json.dumps(nouveau_lieu,  ensure_ascii=True)
    course_js += "  date: %s,\n"   % json.dumps(nouveau_date)
    course_js += "  dist: %s,\n"   % json.dumps(nouveau_dist,  ensure_ascii=True)
    course_js += "  alloc: %s,\n"  % json.dumps(nouveau_alloc, ensure_ascii=True)
    course_js += "  partants: %d,\n" % len(partants)
    course_js += "  depart: %s\n"  % json.dumps(nouveau_heure)
    course_js += "};"

    # ── Bloc JS PARTANTS ──────────────────────────────────────────────
    lines = []
    for p in partants:
        nom = json.dumps(str(p.get("nom", "")), ensure_ascii=True)[1:-1]
        j   = json.dumps(str(p.get("j",  "N/A")), ensure_ascii=True)[1:-1]
        e   = json.dumps(str(p.get("e",  "N/A")), ensure_ascii=True)[1:-1]
        m   = str(p.get("m", "(25) (25) (25)")).replace("'", "")
        lines.append(
            "  { n:%d, nom:'%s', j:'%s', e:'%s', p:'%s', c:'%s', m:'%s', sc:%s, prob:%s, cote:%s }" % (
                int(p.get("n", 0)), nom, j, e,
                str(p.get("p","58kg")), str(p.get("c","C.1")), m,
                str(p.get("sc",50.0)), str(p.get("prob",6.0)), str(p.get("cote",10.0))
            )
        )
    partants_js = "const PARTANTS = [\n" + ",\n".join(lines) + "\n];"

    # ── Bloc JS HISTORIQUE ────────────────────────────────────────────
    histo_recent = [h for h in historique if h.get("reel")][:5]
    h_lines = []
    for h in histo_recent:
        h_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date",""),  ensure_ascii=True),
                json.dumps(h.get("nom",""),   ensure_ascii=True),
                json.dumps(h.get("lieu",""),  ensure_ascii=True),
                json.dumps(h.get("predit",[])),
                json.dumps(h["reel"]) if h.get("reel") else "null",
                str(h["prec"]) if h.get("prec") is not None else "null",
                str(h.get("quinte",False)).lower(),
                str(h.get("profit",0))
            )
        )
    histo_js = "const HISTORIQUE = [\n" + ",\n".join(h_lines) + "\n];"

    # ── Bloc JS HISTORIQUE_FULL ───────────────────────────────────────
    full_lines = []
    for h in historique[:30]:
        full_lines.append(
            "  { date:%s, nom:%s, lieu:%s, predit:%s, reel:%s, prec:%s, quinte:%s, profit:%s }" % (
                json.dumps(h.get("date",""),  ensure_ascii=True),
                json.dumps(h.get("nom",""),   ensure_ascii=True),
                json.dumps(h.get("lieu",""),  ensure_ascii=True),
                json.dumps(h.get("predit",[])),
                json.dumps(h["reel"]) if h.get("reel") else "null",
                str(h.get("prec","null")),
                str(h.get("quinte",False)).lower(),
                str(h.get("profit",0))
            )
        )
    histo_full_js = "const HISTORIQUE_FULL = [\n" + ",\n".join(full_lines) + "\n];"

    # ── Remplacements JS ──────────────────────────────────────────────
    html = safe_sub(r"const COURSE = \{[\s\S]*?\};", course_js, html)
    html = safe_sub(r"const PARTANTS = \[[\s\S]*?\];(?=\s*\n\s*const TOTAL_PROB)", partants_js, html)
    html = safe_sub(r"const HISTORIQUE = \[[\s\S]*?\];(?=\s*\n\s*/\*)", histo_js, html)
    html = safe_sub(r"const HISTORIQUE_FULL = \[[\s\S]*?\];", histo_full_js, html)

    # ── Remplacements HTML statiques — nom de course partout ─────────
    if ancien_nom and ancien_nom != nouveau_nom:
        html = html.replace(ancien_nom, nouveau_nom)
        log.info("Remplacement nom : %s -> %s" % (ancien_nom[:30], nouveau_nom[:30]))

    if ancien_ref and ancien_ref != nouveau_ref:
        html = html.replace(ancien_ref, nouveau_ref)

    if ancien_date and ancien_date != nouveau_date:
        html = html.replace(ancien_date, nouveau_date)

    # ── Sidebar meta ──────────────────────────────────────────────────
    html = safe_sub(
        r'(class="sidebar-race-meta">)[^<]*(</div>)',
        'class="sidebar-race-meta">%s - %s - %s</div>' % (nouveau_lieu, nouveau_ref, nouveau_heure),
        html
    )

    log.info("HTML genere : %d caracteres" % len(html))
    return html
