 import schedule, time, logging, os, json
from datetime import datetime, date

from scraper        import scrape_quinte_du_jour, scrape_resultats_pmu, enrichir_cotes_live
from analyzer       import analyser_partants
from generator      import generer_html
from github_updater import push_github, get_historique_github, save_historique_github
from notifier       import notifier_whatsapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("turfai.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger("TurfAI")

JOURS = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]
STATE = {"course": None, "html_ok": False, "resultat_ok": False, "today": None}


def tache_matin():
    today = date.today().isoformat()
    log.info("=" * 60)
    log.info("MATIN — %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    log.info("=" * 60)
    try:
        log.info("Scraping PMU...")
        course = scrape_quinte_du_jour()
        if not course or len(course.get("partants", [])) < 5:
            log.error("Aucune course Quinte+ valide")
            notifier_whatsapp("TurfAI : Aucun Quinte+ trouve aujourd'hui.")
            return

        log.info("%s — %s %s" % (course["nom"], course["lieu"], course["heure"]))

        log.info("Analyse IA...")
        course_ia = analyser_partants(course)
        fav = course_ia["favori"]
        q5  = course_ia["grilles"]["quinte"]
        log.info("Favori N°%d %s sc=%s" % (fav["n"], fav["nom"], fav["sc"]))
        log.info("Quinte+ : %s" % str(q5))

        STATE["course"]    = course_ia
        STATE["today"]     = today
        STATE["html_ok"]   = False
        STATE["resultat_ok"] = False

        log.info("Generation HTML...")
        historique = get_historique_github()
        html = generer_html(course_ia, historique)
        log.info("%d caracteres" % len(html))

        log.info("Push GitHub...")
        commit = "Quinte+ %s — %s" % (date.today().strftime("%d/%m/%Y"), course["nom"])
        if push_github(html, commit):
            log.info("Vercel redéploie dans ~30s")
            STATE["html_ok"] = True
        else:
            log.error("Echec push GitHub")
            return

        vb  = course_ia.get("best_vb", fav)
        msg = (
            "TurfAI Pro — Quinte+ du %s\n\n"
            "%s — %s %s %s\n\n"
            "Favori IA : N°%d %s (score %s)\n"
            "Best VB : N°%d %s\n\n"
            "Quinte+ base : %s\n\n"
            "https://turfai-pro-liard.vercel.app"
        ) % (
            date.today().strftime("%d/%m/%Y"),
            course["nom"], course["lieu"], course.get("ref","R1C3"), course["heure"],
            fav["n"], fav["nom"], str(fav["sc"]),
            vb["n"], vb["nom"],
            " - ".join(map(str, q5))
        )
        notifier_whatsapp(msg)
        log.info("Tache matin OK !")

    except Exception as e:
        log.error("Erreur matin : %s" % str(e))
        notifier_whatsapp("TurfAI ERREUR : %s" % str(e)[:100])


def tache_cotes():
    if not STATE.get("course"):
        return
    log.info("Mise a jour cotes 11h00...")
    try:
        course_maj = enrichir_cotes_live(STATE["course"])
        if course_maj:
            STATE["course"] = course_maj
            historique = get_historique_github()
            html = generer_html(course_maj, historique)
            push_github(html, "Cotes %s — %s" % (datetime.now().strftime("%H:%M"), course_maj["nom"]))
            log.info("Cotes mises a jour")
    except Exception as e:
        log.warning("Erreur cotes : %s" % str(e))


def tache_resultats():
    if STATE.get("resultat_ok"):
        return
    log.info("=" * 60)
    log.info("RESULTATS — %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    log.info("=" * 60)
    try:
        course = STATE.get("course", {})
        ref    = course.get("ref", "R1C3")
        nom    = course.get("nom", "Quinte du jour")
        lieu   = course.get("lieu", "")

        log.info("Scraping resultat %s..." % ref)
        resultat = scrape_resultats_pmu(ref)
        if not resultat or not resultat.get("arrivee"):
            log.warning("Resultat pas encore disponible — retry plus tard")
            return

        arrivee = resultat["arrivee"][:7]
        log.info("Arrivee : %s" % str(arrivee))

        predit = course.get("grilles", {}).get("quinte", [])
        if not predit:
            tries  = sorted(course.get("partants",[]), key=lambda x: x.get("prob",0), reverse=True)
            predit = [p["n"] for p in tries[:5]]

        prec, q5_ok, profit = calculer_precision(predit, arrivee)
        log.info("Precision %d%% | Q5=%s | Profit=%s" % (prec, str(q5_ok), str(profit)))

        today     = date.today()
        today_str = today.strftime("%d/%m/%Y")
        entree = {
            "date":   "%s. %s" % (JOURS[today.weekday()], today_str),
            "nom":    nom,
            "lieu":   lieu,
            "predit": predit[:5],
            "reel":   arrivee[:5],
            "prec":   prec,
            "quinte": q5_ok,
            "profit": profit,
        }

        historique = get_historique_github()
        historique = [h for h in historique if not h.get("date","").endswith(today_str)]
        historique.insert(0, entree)
        historique = historique[:30]

        save_historique_github(historique)
        html = generer_html(STATE.get("course") or {}, historique)
        commit = "Resultat %s — %s — %d%%" % (today_str, nom, prec)
        if push_github(html, commit):
            log.info("HTML resultat pushe !")
            STATE["resultat_ok"] = True

        communs = len(set(predit[:5]) & set(arrivee[:5]))
        msg = (
            "TurfAI Pro — Resultat Quinte+ %s\n\n"
            "%s — %s\n\n"
            "Predit IA : %s\n"
            "Arrivee : %s\n\n"
            "Precision : %d%% | %d/5 communs\n"
            "Profit : %s\n\n"
            "https://turfai-pro-liard.vercel.app"
        ) % (
            today_str, nom, lieu,
            " - ".join(map(str, predit[:5])),
            " - ".join(map(str, arrivee[:5])),
            prec, communs,
            "%+.2f euros" % profit
        )
        notifier_whatsapp(msg)
        log.info("Tache resultats OK !")

    except Exception as e:
        log.error("Erreur resultats : %s" % str(e))


def calculer_precision(predit, arrivee):
    if not predit or not arrivee:
        return 0, False, 0.0
    a5 = arrivee[:5]
    p5 = predit[:5]
    communs = set(p5) & set(a5)
    n = len(communs)
    score = sum(max(0.4, 1.0 - abs(p5.index(x) - a5.index(x)) * 0.12) for x in communs)
    prec  = min(100, int(score / 5 * 100))
    q5_ok = n >= 5
    if q5_ok:
        profit = 45.0
    elif n >= 4:
        profit = 8.0
    elif n >= 3:
        profit = 3.0
    elif n >= 2:
        profit = -1.5
    else:
        profit = -3.0
    return prec, q5_ok, round(profit, 2)


def demarrer():
    log.info("TurfAI Pro v5 — Backend demarre")
    schedule.every().day.at("08:00").do(tache_matin)
    schedule.every().day.at("11:00").do(tache_cotes)
    schedule.every().day.at("16:00").do(tache_resultats)
    schedule.every().day.at("16:30").do(tache_resultats)
    schedule.every().day.at("17:00").do(tache_resultats)
    log.info("Scheduler : 08h00 - 11h00 - 16h00 - 16h30 - 17h00")
    log.info("Execution immediate au demarrage...")
    tache_matin()
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    demarrer()
