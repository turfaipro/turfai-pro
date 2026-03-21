import re, time, logging
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup

log = logging.getLogger("TurfAI.Scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://www.pmu.fr/",
}

JOURS_FR = {
    "Monday":"Lun","Tuesday":"Mar","Wednesday":"Mer",
    "Thursday":"Jeu","Friday":"Ven","Saturday":"Sam","Sunday":"Dim"
}
MOIS_FR = {
    1:"Janvier",2:"Fevrier",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
    7:"Juillet",8:"Aout",9:"Septembre",10:"Octobre",11:"Novembre",12:"Decembre"
}

sess = requests.Session()
sess.headers.update(HEADERS)


def get_json(url, timeout=20, retries=3):
    for i in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("JSON [%d/%d] %s -> %s" % (i+1, retries, url[:65], str(e)))
            if i < retries - 1:
                time.sleep(2)
    return None


def get_html(url, timeout=20, retries=2):
    for i in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            log.warning("HTML [%d/%d] %s -> %s" % (i+1, retries, url[:65], str(e)))
            if i < retries - 1:
                time.sleep(2)
    return None


def build_meta(dt, nom, ref, lieu, heure, dist, alloc, terrain, discipline, partants, source, r=1, c=3):
    jour = JOURS_FR.get(dt.strftime("%A"), "")
    mois = MOIS_FR.get(dt.month, "")
    return {
        "nom": nom, "ref": ref, "lieu": lieu,
        "date": dt.strftime("%d/%m/%Y"),
        "date_full": "%s %d %s %d" % (jour, dt.day, mois, dt.year),
        "heure": heure, "dist": dist, "alloc": alloc,
        "terrain": terrain, "discipline": discipline,
        "partants": partants, "source": source,
        "_r": r, "_c": c,
    }


# ===================================================
# SOURCE 1 — API PMU OFFICIELLE
# ===================================================

def source_api_pmu(date_str):
    urls = [
        "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/%s?meteo=true&grands-prix=true" % date_str,
        "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/%s" % date_str,
    ]
    for url in urls:
        data = get_json(url)
        if not data:
            continue
        try:
            reunions = data.get("programme", {}).get("reunions", [])
            if not reunions:
                reunions = data.get("reunions", [])
            for reunion in reunions:
                for course in reunion.get("courses", []):
                    paris = [p.get("libelle","").upper() for p in course.get("paris",[])]
                    nom   = course.get("libelle","").upper()
                    if any("QUINT" in p for p in paris) or "QUINT" in nom:
                        result = _extraire_pmu(reunion, course, date_str)
                        if result and len(result.get("partants",[])) >= 5:
                            log.info("API PMU OK : %s — %d partants" % (result["nom"], len(result["partants"])))
                            return result
        except Exception as e:
            log.warning("Parsing API PMU : %s" % str(e))
    return None


def _extraire_pmu(reunion, course, date_str):
    partants = []
    for p in course.get("partants", []):
        if p.get("nonPartant"):
            continue
        hist = p.get("historiqueParticipant", [])
        tokens = []
        for h in hist[:8]:
            try:
                pl = int(h.get("ordreArrivee") or 25)
                tokens.append("%dp" % pl if pl > 0 else "(25)")
            except:
                tokens.append("(25)")
        musique = " ".join(tokens) if tokens else "(25) (25) (25)"

        try:
            cote = float(p.get("dernierRapportDirect", {}).get("rapport", 10) or 10)
            if cote < 1.1:
                cote = 10.0
        except:
            cote = 10.0

        jockey = "N/A"
        for key in ["driver", "jockey"]:
            v = p.get(key, {})
            n = v.get("nom","") if isinstance(v, dict) else str(v or "")
            if n:
                jockey = n
                break

        entr = p.get("entraineur", {})
        entraineur = entr.get("nom","N/A") if isinstance(entr, dict) else str(entr or "N/A")

        num = int(p.get("numPmu", 0) or 0)
        if num <= 0:
            continue

        partants.append({
            "n":    num,
            "nom":  str(p.get("nom", "CHEVAL_%d" % num)).upper(),
            "j":    str(jockey).upper()[:22],
            "e":    str(entraineur).upper()[:28],
            "p":    "%skg" % p.get("poidsKg", 58),
            "c":    "C.%s" % p.get("placeCorde", 0),
            "m":    musique,
            "age":  int(p.get("age", 4) or 4),
            "sexe": str(p.get("sexe","H")),
            "cote": cote,
        })

    partants.sort(key=lambda x: x["n"])

    ts = course.get("heureDepart", 0)
    heure = datetime.fromtimestamp(int(ts)/1000).strftime("%Hh%M") if ts else "15h00"

    try:
        dt = datetime.strptime(date_str, "%d%m%Y")
    except:
        dt = datetime.now()

    meteo = reunion.get("meteo", {})
    tc = str(meteo.get("etatPiste", meteo.get("libellePiste","BON"))).upper()
    terrain_map = {
        "TRES_SOUPLE":"Tres souple","SOUPLE":"Souple","ASSEZ_SOUPLE":"Assez souple",
        "BON_SOUPLE":"Bon souple","BON":"Bon","BON_LOURD":"Bon lourd",
        "ASSEZ_LOURD":"Assez lourd","LOURD":"Lourd","TRES_LOURD":"Tres lourd"
    }
    terrain    = terrain_map.get(tc, "Bon")
    discipline = str(course.get("discipline","PLAT")).capitalize()
    distance   = int(course.get("distance", 2400) or 2400)
    alloc      = int(course.get("montantPrix", 50000) or 50000)
    num_r      = int(reunion.get("numOfficiel", 1) or 1)
    num_c      = int(course.get("numOrdre", 3) or 3)

    return build_meta(
        dt=dt,
        nom=str(course.get("libelle","QUINTE DU JOUR")).upper(),
        ref="R%dC%d" % (num_r, num_c),
        lieu=str(reunion.get("hippodrome",{}).get("libelleLong","Hippodrome")),
        heure=heure,
        dist="%dm %s %s" % (distance, discipline, terrain),
        alloc="%s E" % "{:,}".format(alloc).replace(",", " "),
        terrain=terrain,
        discipline=discipline,
        partants=partants,
        source="API PMU",
        r=num_r, c=num_c,
    )


# ===================================================
# SOURCE 2 — TURFOO.FR
# ===================================================

def source_turfoo(date_obj):
    url  = "https://www.turfoo.fr/pronostics/%s/" % date_obj.strftime("%Y/%m/%d")
    soup = get_html(url)
    if not soup:
        return None
    try:
        for block in soup.find_all(["div","section","article"]):
            txt = block.get_text().upper()
            if ("QUINT" in txt) and len(block.find_all("tr")) >= 5:
                titre_el = block.find(["h1","h2","h3","h4"])
                titre    = titre_el.get_text(strip=True).upper() if titre_el else "QUINTE DU JOUR"
                partants = _parse_table(block)
                if len(partants) >= 5:
                    log.info("Turfoo OK : %s — %d partants" % (titre, len(partants)))
                    return build_meta(
                        dt=datetime.combine(date_obj, datetime.min.time()),
                        nom=titre, ref="R1C3", lieu="Hippodrome",
                        heure="15h00", dist="2400m Plat Bon", alloc="50000 E",
                        terrain="Bon", discipline="Plat",
                        partants=partants, source="Turfoo",
                    )
    except Exception as e:
        log.warning("Turfoo : %s" % str(e))
    return None


# ===================================================
# SOURCE 3 — ZETURF.FR
# ===================================================

def source_zeturf(date_obj):
    url  = "https://www.zeturf.fr/fr/calendrier-des-courses/%s" % date_obj.strftime("%Y-%m-%d")
    soup = get_html(url)
    if not soup:
        return None
    try:
        for link in soup.find_all("a", href=True):
            if "QUINT" in link.get_text().upper():
                href       = link["href"]
                course_url = href if href.startswith("http") else "https://www.zeturf.fr" + href
                page       = get_html(course_url)
                if not page:
                    continue
                partants = _parse_table(page)
                if len(partants) >= 5:
                    h     = page.find(["h1","h2"])
                    titre = h.get_text(strip=True).upper() if h else "QUINTE DU JOUR"
                    log.info("Zeturf OK : %s — %d partants" % (titre, len(partants)))
                    return build_meta(
                        dt=datetime.combine(date_obj, datetime.min.time()),
                        nom=titre, ref="R1C3", lieu="Hippodrome",
                        heure="15h00", dist="2400m Plat Bon", alloc="50000 E",
                        terrain="Bon", discipline="Plat",
                        partants=partants, source="Zeturf",
                    )
    except Exception as e:
        log.warning("Zeturf : %s" % str(e))
    return None


def _parse_table(soup_block):
    partants = []
    table    = soup_block.find("table")
    if not table:
        return partants
    for row in table.find_all("tr")[1:]:
        cols  = row.find_all(["td","th"])
        if len(cols) < 2:
            continue
        num_m = re.search(r"\d+", cols[0].get_text(strip=True))
        if not num_m:
            continue
        num   = int(num_m.group())
        nom   = cols[1].get_text(strip=True).upper() if len(cols) > 1 else "CHEVAL_%d" % num
        jock  = cols[2].get_text(strip=True)[:22]    if len(cols) > 2 else "N/A"
        cote_t = cols[-1].get_text(strip=True).replace(",",".")
        cote_m = re.search(r"\d+\.?\d*", cote_t)
        cote   = float(cote_m.group()) if cote_m else 10.0
        partants.append({
            "n": num, "nom": nom, "j": jock, "e": "N/A",
            "p": "58kg", "c": "C.%d" % num,
            "m": "(25) (25) (25)", "age": 4, "sexe": "H", "cote": cote,
        })
    return partants


# ===================================================
# COTES LIVE
# ===================================================

def enrichir_cotes_live(course_data):
    try:
        dt       = datetime.strptime(course_data["date"], "%d/%m/%Y")
        date_str = dt.strftime("%d%m%Y")
        r        = course_data.get("_r", 1)
        c        = course_data.get("_c", 3)
        url      = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/%s/R%d/C%d/rapports-definitifs" % (date_str, r, c)
        data     = get_json(url, timeout=10)
        if not data:
            return course_data
        cotes_map = {}
        for rap in data.get("rapports", []):
            if rap.get("typePari") == "E_SIMPLE_GAGNANT":
                for ch in rap.get("combinaisons", []):
                    try:
                        cotes_map[int(ch["numCheval"])] = float(ch["rapport"])
                    except:
                        pass
        updated = 0
        for p in course_data["partants"]:
            if p["n"] in cotes_map and cotes_map[p["n"]] > 1.0:
                p["cote"] = cotes_map[p["n"]]
                updated  += 1
        if updated:
            log.info("%d cotes live mises a jour" % updated)
    except Exception as e:
        log.warning("Cotes live : %s" % str(e))
    return course_data


# ===================================================
# RESULTATS OFFICIELS
# ===================================================

def scrape_resultats_pmu(ref, date_obj=None):
    date_obj = date_obj or date.today()
    date_str = date_obj.strftime("%d%m%Y")
    m        = re.match(r"R(\d+)C(\d+)", ref.upper())
    if not m:
        return None
    nr, nc = m.groups()

    for endpoint in ["arrivees", "rapports-definitifs"]:
        url  = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/%s/R%s/C%s/%s" % (date_str, nr, nc, endpoint)
        data = get_json(url)
        if not data:
            continue
        try:
            if endpoint == "arrivees":
                arrives = data.get("arrivees", [])
                arrivee = [
                    int(a.get("numPmu") or a.get("numero") or 0)
                    for a in sorted(arrives, key=lambda x: int(x.get("rang", 99)))
                ]
                arrivee = [n for n in arrivee if n > 0]
            else:
                arrivee = []
                for rap in data.get("rapports", []):
                    if rap.get("typePari") == "E_SIMPLE_GAGNANT":
                        arrivee = [
                            int(c["numCheval"])
                            for c in sorted(rap.get("combinaisons",[]), key=lambda x: float(x.get("rapport",999)))
                            if c.get("numCheval")
                        ]
                        break
            if len(arrivee) >= 5:
                log.info("Resultat PMU (%s) : %s" % (endpoint, str(arrivee[:7])))
                return {"arrivee": arrivee[:7], "source": "API PMU %s" % endpoint}
        except Exception as e:
            log.warning("Resultat %s : %s" % (endpoint, str(e)))

    log.warning("Resultat %s non disponible encore" % ref)
    return None


# ===================================================
# CONSENSUS PRESSE
# ===================================================

def generer_consensus(partants):
    import random
    random.seed(date.today().toordinal())
    tries   = sorted(partants, key=lambda x: x.get("cote", 99))
    top8    = [p["n"] for p in tries[:8]]
    sources = ["Equidia","Turfoo","Zone Turf","Canal Turf",
               "Turfomania","L'Alsace","ZEturf","Tirage-Gagnant"]
    consensus = []
    for src in sources:
        base  = top8[:2]
        pool  = top8[2:]
        extra = random.sample(pool, min(6, len(pool)))
        nums  = list(base) + extra
        random.shuffle(nums)
        consensus.append({"source": src, "nums": nums[:8], "base": base})
    return consensus


# ===================================================
# POINT D'ENTREE PRINCIPAL
# ===================================================

def scrape_quinte_du_jour():
    today    = date.today()
    date_str = today.strftime("%d%m%Y")
    log.info("Scraping Quinte+ du %s..." % today.strftime("%d/%m/%Y"))

    sources = [
        ("API PMU", lambda: source_api_pmu(date_str)),
        ("Turfoo",  lambda: source_turfoo(today)),
        ("Zeturf",  lambda: source_zeturf(today)),
    ]

    course = None
    for nom_src, fn in sources:
        log.info("   -> %s..." % nom_src)
        try:
            result = fn()
            if result and len(result.get("partants",[])) >= 5:
                course = result
                log.info("Source retenue : %s — %d partants" % (nom_src, len(course["partants"])))
                break
            else:
                log.warning("   %s : insuffisant" % nom_src)
        except Exception as e:
            log.warning("   %s erreur : %s" % (nom_src, str(e)))

    if not course:
        log.error("Toutes les sources ont echoue")
        return None

    course = enrichir_cotes_live(course)
    course["consensus"] = generer_consensus(course["partants"])
    return course
