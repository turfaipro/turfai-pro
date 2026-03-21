 import math, logging
from itertools import combinations as itertools_combinations

log = logging.getLogger("TurfAI.Analyzer")

POIDS = {
    "forme":      0.30,
    "regularite": 0.20,
    "jockey":     0.15,
    "entraineur": 0.15,
    "cote":       0.12,
    "poids":      0.08,
}

JOCKEYS_TOP = {
    "GUYON M":95,"SOUMILLON C":93,"DEMURO C":90,"POUCHIN A":88,
    "PASQUIER S":87,"BARZALONA M":86,"LEMAITRE A":85,"MADAMET A":84,
    "HARDOUIN E":83,"LECOEUVRE C":82,"BACHELOT T":80,"MOSSE G":79,
    "LEFEBVRE C":78,"HAMELIN A":77,"PICCONE T":76,"GRANDIN MAR":80,
    "CRASTUS A":74,"LERNER Y":72,"DONWORTH TIM":76,
    "REVELEY J":82,"GOOP B":88,"RAFFIN E":87,"DUVALDESTIN T":86,
    "BAZIRE N":90,"ABRIVARD A":85,"VELON M":83,"NIVARD F":87,
}

ENTRAINEURS_TOP = {
    "FABRE":95,"ROHAUT":88,"BOTTI":86,"GRAFFARD":87,
    "BRANDT":85,"HEAD":84,"MELE":82,"WATTEL":81,
    "CAULLERY":78,"DUBOIS":80,"CHAPPLE-HYAM":79,"DELAUNAY":78,
    "MONFORT":80,"PAYSAN":75,"BONILLA":76,"SOGORB":77,"FORESI":74,
}


def score_jockey(nom):
    nom_up = str(nom).upper().strip()
    for k, v in JOCKEYS_TOP.items():
        if k in nom_up or nom_up in k:
            return float(v)
    return 65.0


def score_entraineur(nom):
    nom_up = str(nom).upper().strip()
    for k, v in ENTRAINEURS_TOP.items():
        if k in nom_up:
            return float(v)
    return 60.0


def parser_musique(musique):
    import re
    tokens = str(musique).upper().split()
    places = []
    for t in tokens[:8]:
        clean = re.sub(r"[^0-9]", "", t)
        if t in ("(25)", "DA", "DM", "TH", "AH", "TA", "NP", "0", "DSQ"):
            places.append(25)
        elif clean:
            try:
                places.append(min(int(clean), 25))
            except:
                places.append(15)
        else:
            places.append(15)
    return places if places else [15, 15, 15]


def score_forme(musique):
    places = parser_musique(musique)
    if not places:
        return 40.0
    score, poids_tot = 0.0, 0.0
    for i, p in enumerate(places[:6]):
        w = 1.0 / (i + 1)
        if p == 1:
            pts = 100
        elif p == 2:
            pts = 85
        elif p == 3:
            pts = 72
        elif p <= 5:
            pts = 60
        elif p <= 8:
            pts = 45
        elif p == 25:
            pts = 25
        else:
            pts = 30
        score    += pts * w
        poids_tot += w
    return round(score / poids_tot, 1) if poids_tot else 40.0


def score_regularite(musique):
    places  = parser_musique(musique)
    valides = [p for p in places if p < 20]
    if len(valides) < 2:
        return 50.0
    moy   = sum(valides) / len(valides)
    var   = sum((p - moy)**2 for p in valides) / len(valides)
    ecart = math.sqrt(var)
    score = max(0, 100 - ecart * 8)
    if moy <= 3:
        score = min(100, score * 1.2)
    elif moy <= 5:
        score = min(100, score * 1.05)
    return round(score, 1)


def score_poids(poids_str):
    try:
        kg = float(str(poids_str).replace("kg","").strip())
        return round(max(20.0, min(100.0, 100 - (kg - 53) * 4)), 1)
    except:
        return 60.0


def score_cote(cote):
    try:
        c = float(cote)
        if c <= 0:
            return 50.0
        prob = (1.0 / c) * 100.0
        return round(min(80.0, prob * 3.5), 1)
    except:
        return 50.0


def calculer_score(partant, nb=16):
    s_forme = score_forme(partant.get("m", "(25)"))
    s_reg   = score_regularite(partant.get("m", "(25)"))
    s_jock  = score_jockey(partant.get("j", ""))
    s_entr  = score_entraineur(partant.get("e", ""))
    s_cote  = score_cote(partant.get("cote", 10.0))
    s_pds   = score_poids(partant.get("p", "58kg"))

    sc = (
        s_forme * POIDS["forme"]      +
        s_reg   * POIDS["regularite"] +
        s_jock  * POIDS["jockey"]     +
        s_entr  * POIDS["entraineur"] +
        s_cote  * POIDS["cote"]       +
        s_pds   * POIDS["poids"]
    )
    sc = round(min(99.9, max(5.0, sc)), 1)
    return dict(list(partant.items()) + [("sc", sc)])


def generer_grilles(tries):
    top5 = [p["n"] for p in tries[:5]]
    top4 = top5[:4]
    top3 = top5[:3]
    top2 = top5[:2]
    top8 = [p["n"] for p in tries[:8]]
    alt1 = top4 + [tries[5]["n"]] if len(tries) > 5 else top5
    alt2 = top3 + [tries[4]["n"], tries[5]["n"]] if len(tries) > 5 else top5
    vbs  = [p["n"] for p in tries if p.get("is_vb", False)]
    return {
        "couple":      top2,
        "tierce":      top3,
        "quarte":      top4,
        "quinte":      top5,
        "alt1":        alt1,
        "alt2":        alt2,
        "elargi8":     top8,
        "bases":       top2,
        "complements": [tries[i]["n"] for i in range(2, min(5, len(tries)))],
        "jokers":      [tries[i]["n"] for i in range(5, min(8, len(tries)))],
        "value_bets":  vbs[:5],
    }


def generer_kelly(tries, capital=100.0, kelly_pct=0.25):
    total = sum(p["prob"] for p in tries)
    mises = {}
    for p in tries:
        mise_raw     = capital * kelly_pct * (p["prob"] / total)
        mises[p["n"]] = max(1.5, round(mise_raw * 2) / 2)
    return mises


def analyser_partants(course):
    partants = course["partants"]
    nb       = len(partants)

    partants = [calculer_score(p, nb) for p in partants]

    total_sc = sum(p["sc"] for p in partants)
    for p in partants:
        p["prob"]  = round((p["sc"] / total_sc) * 100, 1)
        p_cote     = (1.0 / p["cote"]) * 100.0 if p.get("cote", 0) > 0 else 10.0
        p["edge"]  = round(p["prob"] - p_cote, 1)
        p["is_vb"] = p["edge"] > 0

    tries = sorted(partants, key=lambda x: x["sc"], reverse=True)
    for i, p in enumerate(tries):
        p["rang_ia"] = i + 1

    by_num = sorted(partants, key=lambda x: x["n"])

    favori  = tries[0]
    vbs     = [p for p in tries if p["is_vb"]]
    best_vb = max(vbs, key=lambda x: x["edge"]) if vbs else favori
    grilles = generer_grilles(tries)
    mises   = generer_kelly(tries, capital=100.0)

    log.info("Analyse : %d partants | Favori N°%d %s sc=%s" % (nb, favori["n"], favori["nom"], str(favori["sc"])))
    log.info("Quinte+ base : %s | VB : %d detectes" % (str(grilles["quinte"]), len(vbs)))

    result = dict(course)
    result["partants"]       = by_num
    result["partants_tries"] = tries
    result["favori"]         = favori
    result["best_vb"]        = best_vb
    result["nb_vb"]          = len(vbs)
    result["grilles"]        = grilles
    result["mises_kelly"]    = mises
    result["total_prob"]     = sum(p["prob"] for p in partants)
    return result
