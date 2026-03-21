"""
TurfAI Pro v5 — Orchestrateur Principal
Planification :
  08:00 → Scrape Quinté+ → Analyse IA → Génère HTML → Push GitHub → WhatsApp
  11:00 → Mise à jour cotes live
  16:00 / 16:30 / 17:00 → Récupère résultats réels → Historique → Push → WhatsApp
"""
import schedule, time, logging, os, json
from datetime import datetime, date

from scraper   import scrape_quinte_du_jour, scrape_resultats_pmu, enrichir_cotes_live
from analyzer  import analyser_partants
from generator import generer_html
from github_updater import push_github, get_historique_github, save_historique_github
from notifier  import notifier_whatsapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("turfai.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger("TurfAI")

# État journalier
STATE = {"course": None, "html_ok": False, "resultat_ok": False, "today": None}

JOURS = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]

# ═══════════════════════════════════════════
# TÂCHE MATIN — 08h00
# ═══════════════════════════════════════════
def tache_matin():
    today = date.today().isoformat()
    log.info("="*60)
    log.info(f"🌅  MATIN — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info("="*60)
    try:
        # 1. Scraping
        log.info("📡 Scraping PMU...")
        course = scrape_quinte_du_jour()
        if not course or len(course.get("partants",[])) < 5:
            log.error("❌ Aucune course Quinté+ valide")
            notifier_whatsapp("⚠️ TurfAI : Aucun Quinté+ trouvé aujourd'hui.")
            return

        log.info(f"✅ {course['nom']} — {course['lieu']} {course['heure']}")

        # 2. Analyse IA
        log.info("🤖 Analyse IA...")
        course_ia = analyser_partants(course)
        fav = course_ia["favori"]
        q5  = course_ia["grilles"]["quinte"]
        log.info(f"✅ Favori N°{fav['n']} {fav['nom']} sc={fav['sc']}")
        log.info(f"✅ Quinté+ : {q5}")

        STATE.update({"course": course_ia, "today": today, "html_ok": False, "resultat_ok": False})

        # 3. Génération HTML
        log.info("🔨 Génération HTML...")
        historique = get_historique_github()
        html = generer_html(course_ia, historique)
        log.info(f"✅ {len(html):,} caractères")

        # 4. Push GitHub
        log.info("📤 Push GitHub...")
        commit = f"🏇 Quinté+ {date.today().strftime('%d/%m/%Y')} — {course['nom']}"
        if push_github(html, commit):
            log.info("✅ Vercel redéploie dans ~30s")
            STATE["html_ok"] = True
        else:
            log.error("❌ Échec push GitHub")
            return

        # 5. WhatsApp
        vb = course_ia.get("best_vb", fav)
        msg = (
            f"🏇 *TurfAI Pro — Quinté+ du {date.today().strftime('%d/%m/%Y')}*\n\n"
            f"📍 *{course['nom']}*\n"
            f"   {course['lieu']} · {course.get('ref','R1C3')} · {course['heure']}\n"
            f"   {course['dist']} · Terrain {course.get('terrain','Bon')}\n\n"
            f"🥇 Favori IA : N°{fav['n']} *{fav['nom']}* (score {fav['sc']})\n"
            f"💰 Best VB : N°{vb['n']} {vb['nom']} (+{vb.get('edge',0):.1f}%)\n\n"
            f"🎯 Quinté+ base : *{' – '.join(map(str,q5))}*\n\n"
            f"👉 https://turfai-pro.vercel.app"
        )
        notifier_whatsapp(msg)
        log.info("🎉 Tâche matin OK !")

    except Exception as e:
        log.error(f"💥 Erreur matin : {e}", exc_info=True)
        notifier_whatsapp(f"💥 TurfAI ERREUR : {str(e)[:100]}")


# ═══════════════════════════════════════════
# TÂCHE COTES — 11h00
# ═══════════════════════════════════════════
def tache_cotes():
    if not STATE.get("course"):
        return
    log.info("📈 Mise à jour cotes 11h00...")
    try:
        course_maj = enrichir_cotes_live(STATE["course"])
        if course_maj:
            STATE["course"] = course_maj
            historique = get_historique_github()
            html = generer_html(course_maj, historique)
            push_github(html, f"📈 Cotes {datetime.now().strftime('%H:%M')} — {course_maj['nom']}")
            log.info("✅ Cotes mises à jour")
    except Exception as e:
        log.warning(f"Erreur cotes : {e}")


# ═══════════════════════════════════════════
# TÂCHE RÉSULTATS — 16h00 / 16h30 / 17h00
# ═══════════════════════════════════════════
def tache_resultats():
    if STATE.get("resultat_ok"):
        return
    log.info("="*60)
    log.info(f"🏁  RÉSULTATS — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info("="*60)
    try:
        course = STATE.get("course", {})
        ref    = course.get("ref", "R1C3")
        nom    = course.get("nom", "Quinté du jour")
        lieu   = course.get("lieu", "")

        # 1. Scrape résultat PMU
        log.info(f"📡 Scraping résultat {ref}...")
        resultat = scrape_resultats_pmu(ref)
        if not resultat or not resultat.get("arrivee"):
            log.warning("⏳ Résultat pas encore disponible — retry plus tard")
            return

        arrivee = resultat["arrivee"][:7]
        log.info(f"✅ Arrivée : {arrivee}")

        # 2. Calcul précision
        predit = course.get("grilles", {}).get("quinte", [])
        if not predit:
            tries = sorted(course.get("partants",[]), key=lambda x: x.get("prob",0), reverse=True)
            predit = [p["n"] for p in tries[:5]]

        prec, q5_ok, profit = calculer_precision(predit, arrivee)
        log.info(f"✅ Précision {prec}% | Q5={q5_ok} | Profit={profit:+.2f}€")

        # 3. Mise à jour historique
        today = date.today()
        today_str = today.strftime("%d/%m/%Y")
        entree = {
            "date": f"{JOURS[today.weekday()]}. {today_str}",
            "nom": nom,
            "lieu": lieu,
            "predit": predit[:5],
            "reel": arrivee[:5],
            "prec": prec,
            "quinte": q5_ok,
            "profit": profit,
        }
        historique = get_historique_github()
        historique = [h for h in historique if not h.get("date","").endswith(today_str)]
        historique.insert(0, entree)
        historique = historique[:30]  # Garder 30 derniers jours

        # 4. Sauvegarder historique + régénérer HTML
        save_historique_github(historique)
        html = generer_html(STATE.get("course") or {}, historique)
        commit = f"🏁 Résultat {today_str} — {nom} — {prec}%"
        if push_github(html, commit):
            log.info("✅ HTML résultat pushé !")
            STATE["resultat_ok"] = True

        # 5. WhatsApp résultat
        communs = len(set(predit[:5]) & set(arrivee[:5]))
        msg = (
            f"🏁 *TurfAI Pro — Résultat Quinté+ {today_str}*\n\n"
            f"📍 *{nom}* — {lieu}\n\n"
            f"🤖 Prédit IA : {' – '.join(map(str,predit[:5]))}\n"
            f"✅ Arrivée réelle : {' – '.join(map(str,arrivee[:5]))}\n\n"
            f"📊 Précision : *{prec}%* | {communs}/5 communs\n"
            f"💰 Profit estimé : *{profit:+.2f}€*\n"
            f"{'🎉 QUINTÉ+ TROUVÉ !' if q5_ok else '📈 Bonne perf.' if prec>=75 else '📉 Résultat difficile'}\n\n"
            f"👉 Historique mis à jour :\nhttps://turfai-pro.vercel.app"
        )
        notifier_whatsapp(msg)
        log.info("🎉 Tâche résultats OK !")

    except Exception as e:
        log.error(f"💥 Erreur résultats : {e}", exc_info=True)


def calculer_precision(predit: list, arrivee: list) -> tuple:
    if not predit or not arrivee:
        return 0, False, 0.0
    a5 = arrivee[:5]; p5 = predit[:5]
    communs = set(p5) & set(a5)
    n = len(communs)
    score = sum(max(0.4, 1.0 - abs(p5.index(x) - a5.index(x)) * 0.12) for x in communs)
    prec = min(100, int(score / 5 * 100))
    q5_ok = n >= 5
    profit = 45.0 if q5_ok else 8.0 if n >= 4 else 3.0 if n >= 3 else -1.5 if n >= 2 else -3.0
    return prec, q5_ok, round(profit, 2)


# ═══════════════════════════════════════════
# DÉMARRAGE
# ═══════════════════════════════════════════
def demarrer():
    log.info("╔══════════════════════════════════════╗")
    log.info("║  TurfAI Pro v5 — Backend démarré      ║")
    log.info("╚══════════════════════════════════════╝")

    schedule.every().day.at("08:00").do(tache_matin)
    schedule.every().day.at("11:00").do(tache_cotes)
    schedule.every().day.at("16:00").do(tache_resultats)
    schedule.every().day.at("16:30").do(tache_resultats)
    schedule.every().day.at("17:00").do(tache_resultats)

    log.info("⏰ Scheduler : 08h00 · 11h00 · 16h00 · 16h30 · 17h00")
    log.info("🚀 Exécution immédiate au démarrage...")
    tache_matin()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    demarrer()
