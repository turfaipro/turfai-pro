"""
TurfAI Pro v5 — Notifier WhatsApp via CallMeBot
"""
import os, logging
import requests
from urllib.parse import quote

log = logging.getLogger("TurfAI.Notifier")

PHONE  = os.environ.get("WHATSAPP_PHONE", "")
APIKEY = os.environ.get("CALLMEBOT_KEY", "")


def notifier_whatsapp(message: str) -> bool:
    if not PHONE or not APIKEY:
        log.debug("WhatsApp non configuré (PHONE ou APIKEY manquant) — message ignoré")
        return False
    url = f"https://api.callmebot.com/whatsapp.php?phone={PHONE}&text={quote(message)}&apikey={APIKEY}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and ("Message queued" in r.text or "OK" in r.text):
            log.info(f"✅ WhatsApp envoyé ({len(message)} chars)")
            return True
        log.warning(f"WhatsApp HTTP {r.status_code}: {r.text[:80]}")
        return False
    except Exception as e:
        log.warning(f"WhatsApp exception : {e}")
        return False
