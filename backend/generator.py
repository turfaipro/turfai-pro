"""
TurfAI Pro v5 — Générateur HTML
Lit le template base.html et remplace les données de la course + historique.
Produit exactement la structure JS attendue par le frontend.
"""
import os, re, json, logging
from datetime import datetime, date

log = logging.getLogger("TurfAI.Generator")

TEMPLATE_PATH = os.environ.get("TEMPLATE_PATH", "/app/template.html")
JOURS_FR = {
    "Monday":"Lundi","Tuesday":"Mardi","Wednesday":"Mercredi",
    "Thursday":"Jeudi","Friday":"Vendredi","Saturday":"Samedi","Sunday":"Dimanche"
}
MOIS_FR = {
    1:"Janvier",2:"Février",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
    7:"Juillet",8:"Août",9:"Septembre",10:"Octobre",11:"Novembre",12:"Décembre"
}


def date_fr(dt: datetime = None) -> str:
    dt = dt or datetime.now()
    j = JOURS_FR.get(dt.strftime("%A"), dt.strftime("%A"))
    m = MOIS_FR.get(dt.month, dt.strftime("%B"))
    return f"{j} {dt.day} {m} {dt.year}"


def generer_html(data: dict, historique: list) -> str:
    """
    Génère le fichier index.html complet.
    Remplace dans le template :
      - Les données JS (COURSE, PARTANTS, HISTORIQUE, HISTORIQUE_FULL)
      - Les blocs HTML statiques (race header, consensus, KPIs dashboard)
    """
    # Lire le template
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        log.error(f"Template introuvable : {TEMPLATE_PATH}")
        raise

    if not data or not data.get("partants"):
        log.warning("Pas de données course — template retourné sans modification")
        return html

    # ── Préparer les données ──────────────────────────────────
    course    = data
    partants  = data["partants"]       # Triés par numéro
    tries     = data["partants_tries"] # Triés par score IA
    favori    = data["favori"]
    best_vb   = data["best_vb"]
    grilles   = data["grilles"]
    mises     = data["mises_kelly"]
    consensus = data.get("consensus", [])
    nb        = len(partants)
    today     = datetime.now()

    # ── Bloc JS COURSE ────────────────────────────────────────
    course_js = f"""const COURSE = {{
  nom: {json.dumps(course['nom'])},
  ref: {json.dumps(course.get('ref','R1C3'))},
  lieu: {json.dumps(course['lieu'])},
  date: {json.dumps(course['date'])},
  dist: {json.dumps(course['dist'])},
  alloc: {json.dumps(course['alloc'])},
  partants: {nb},
  depart: {json.dumps(course['heure'])}
}};"""

    # ── Bloc JS PARTANTS ──────────────────────────────────────
    def partant_js(p):
        nom = p["nom"].replace("'", "\\'").replace('"', '\\"')
        j   = p["j"].replace("'", "\\'")
        e   = p["e"].replace("'", "\\'")
        return (
            f"  {{ n:{p['n']}, nom:'{nom}', j:'{j}', e:'{e}', "
            f"p:'{p['p']}', c:'{p['c']}', m:'{p['m']}', "
            f"sc:{p['sc']}, prob:{p['prob']}, cote:{p['cote']} }}"
        )

    partants_js = "const PARTANTS = [\n"
    partants_js += ",\n".join(partant_js(p) for p in partants)
    partants_js += "\n];"

    # ── Bloc JS HISTORIQUE (5 dernières) ─────────────────────
    histo_recent = [h for h in historique if h.get("reel") is not None][:5]
    histo_js = "const HISTORIQUE = [\n"
    histo_rows = []
    for h in histo_recent:
        reel_str = json.dumps(h["reel"]) if h["reel"] else "null"
        prec_str = str(h["prec"]) if h["prec"] is not None else "null"
        q5_str   = str(h["quinte"]).lower() if h["quinte"] is not None else "null"
        histo_rows.append(
            f"  {{ date:{json.dumps(h['date'])}, nom:{json.dumps(h['nom'])}, "
            f"lieu:{json.dumps(h['lieu'])}, predit:{json.dumps(h['predit'])}, "
            f"reel:{reel_str}, prec:{prec_str}, quinte:{q5_str}, profit:{h.get('profit',0)} }}"
        )
    histo_js += ",\n".join(histo_rows) + "\n];"

    # ── Bloc JS HISTORIQUE_FULL (30 dernières) ────────────────
    histo_full_js = "const HISTORIQUE_FULL = [\n"
    full_rows = []
    for h in historique[:30]:
        reel_str = json.dumps(h["reel"]) if h.get("reel") else "null"
        prec_str = str(h["prec"]) if h.get("prec") is not None else "null"
        q5_str   = str(h.get("quinte","false")).lower()
        full_rows.append(
            f"  {{ date:{json.dumps(h['date'])}, nom:{json.dumps(h['nom'])}, "
            f"lieu:{json.dumps(h['lieu'])}, predit:{json.dumps(h.get('predit',[]))}, "
            f"reel:{reel_str}, prec:{prec_str}, quinte:{q5_str}, profit:{h.get('profit',0)} }}"
        )
    histo_full_js += ",\n".join(full_rows) + "\n];"

    # ── Remplacements dans le HTML ────────────────────────────
    # Pattern : remplacer le bloc const COURSE ... jusqu'à const TOTAL_PROB
    html = re.sub(
        r"const COURSE = \{[\s\S]*?\};",
        course_js,
        html, count=1
    )

    html = re.sub(
        r"const PARTANTS = \[[\s\S]*?\];(?=\s*\n\s*const TOTAL_PROB)",
        partants_js,
        html, count=1
    )

    html = re.sub(
        r"const HISTORIQUE = \[[\s\S]*?\];(?=\s*\n\s*/\*)",
        histo_js,
        html, count=1
    )

    html = re.sub(
        r"const HISTORIQUE_FULL = \[[\s\S]*?\];",
        histo_full_js,
        html, count=1
    )

    # ── Remplacements HTML statiques ─────────────────────────
    q5  = grilles["quinte"]
    q5_str = " – ".join(map(str, q5))

    # Race widget sidebar
    html = re.sub(
        r'<div class="sidebar-race-name">[^<]*</div>',
        f'<div class="sidebar-race-name">{course["nom"]}</div>',
        html, count=1
    )
    html = re.sub(
        r'<div class="sidebar-race-meta">[^<]*</div>',
        f'<div class="sidebar-race-meta">{course["lieu"]} · {course.get("ref","R1C3")} · {course["heure"]}</div>',
        html, count=1
    )

    # KPI Dashboard — Favori IA
    html = re.sub(
        r'(<div class="kpi-val" style="color:var\(--green\)">)[^<]*(</div>\s*<div class="kpi-label">Favori IA)',
        rf'\g<1>N°{favori["n"]}\g<2>',
        html, count=1
    )
    html = re.sub(
        r'(Favori IA — )[A-Z\s]+(<)',
        rf'\g<1>{favori["nom"]}\g<2>',
        html, count=1
    )

    # Score favori
    html = re.sub(
        r'(▲ Score )\d+\.?\d*',
        rf'\g<1>{favori["sc"]}',
        html, count=1
    )

    # Prob victoire max
    html = re.sub(
        r'(<div class="kpi-val" style="color:var\(--blue\)">)\d+\.?\d*(%</div>\s*<div class="kpi-label">Prob\.)',
        rf'\g<1>{favori["prob"]}%\g<2>',
        html, count=1
    )

    # Date topbar
    date_display = f'{JOURS_FR.get(today.strftime("%A"),"Lundi")} {today.day} {MOIS_FR[today.month]} {today.year}'
    html = re.sub(
        r'(id="page-title">Dashboard <span>)[^<]*(</span>)',
        rf'\g<1>{date_display}\g<2>',
        html, count=1
    )

    # Race header
    html = re.sub(
        r'(PRIX DE LA GLORIETTE — R1C3)',
        f'{course["nom"]} — {course.get("ref","R1C3")}',
        html
    )
    html = re.sub(r'(<strong>)Saint-Cloud(</strong>)', rf'\g<1>{course["lieu"]}\g<2>', html)
    html = re.sub(r'(<strong>)2 400m Herbe Lourd(</strong>)', rf'\g<1>{course["dist"]}\g<2>', html)
    html = re.sub(r'(<strong>)50 900 €(</strong>)', rf'\g<1>{course["alloc"]}\g<2>', html)
    html = re.sub(r'(<strong>)15h15(</strong>)', rf'\g<1>{course["heure"]}\g<2>', html)

    # Consensus presse (si disponible)
    if consensus:
        html = _injecter_consensus(html, consensus)

    # Timestamp génération
    ts = datetime.now().strftime("%d/%m/%Y à %H:%M")
    html = re.sub(
        r'TurfAI Pro v[45]\.0 · [^·]+ R[12]C[0-9] · [^·]+ · \d{2}/\d{2}/\d{4}',
        f'TurfAI Pro v5 · {course["nom"]} {course.get("ref","R1C3")} · {course["lieu"]} · {course["date"]} · Généré {ts}',
        html
    )

    log.info(f"✅ HTML généré — {len(html):,} caractères")
    return html


def _injecter_consensus(html: str, consensus: list) -> str:
    """Remplace le bloc consensus presse dans le HTML."""
    base_set = set()
    if consensus:
        base_set = set(consensus[0].get("base", []))

    src_html = ""
    for src in consensus:
        nums_html = "".join(
            f'<div class="cn {'cn-base' if n in base_set else 'cn-comp'}">{n}</div>'
            for n in src.get("nums", [])[:8]
        )
        src_html += (
            f'<div class="consensus-row">'
            f'<span class="source-name">{src["source"]}</span>'
            f'<div class="consensus-nums">{nums_html}</div>'
            f'</div>\n        '
        )

    # Remplacer le contenu du bloc consensus
    html = re.sub(
        r'(<div style="padding:14px 18px">)\s*(<div class="consensus-row">[\s\S]*?</div>)\s*(</div>)',
        rf'\g<1>\n        {src_html}\g<3>',
        html, count=1
    )
    return html
