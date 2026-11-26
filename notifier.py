import logging
import requests

import config

log = logging.getLogger("notifier")


def send(text):
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.info("[TG sin configurar] %s", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        log.error("Telegram falló: %s", e)
