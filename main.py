import datetime as dt
import logging
import time

import config
from exchange import BingX
from notifier import send
from scanner import scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")

ERROR_REPEAT_SEC = 1800     # un mismo error se avisa por Telegram como mucho cada 30 min
NODATA_REPEAT_SEC = 3600    # el aviso "ningún par devuelve velas" se repite como mucho cada hora


def fmt(sig):
    head = "🟢 LONG" if sig["side"] == "LONG" else "🔴 SHORT"
    qm = " · QM" if sig["qm"] else ""
    return (
        f"{head} {sig['symbol']} ({config.TIMEFRAME}){qm}\n"
        f"Score: {sig['score']:.0f}/100\n"
        f"Entrada: {sig['entry']:.6g}\n"
        f"SL: {sig['sl']:.6g}\n"
        f"TP: {sig['tp']:.6g}\n"
        f"Coste estimado: {sig['cost_r']:.2f}R del riesgo\n"
        f"Volumen x{sig['vol_ratio']:.1f} · Compresión {sig['compression']:.2f}"
    )


def can_trade(ex, sig, day_start_bal):
    if day_start_bal is None:
        return False                          # sin saldo de referencia no se opera
    if day_start_bal - ex.balance_usdt() >= config.DAILY_LOSS_LIMIT:
        send("⛔ Límite de pérdida diaria alcanzado. No se abren más operaciones hoy.")
        return False
    positions = ex.open_positions()
    if len(positions) >= config.MAX_OPEN:
        return False
    return not any(p.get("symbol") == sig["symbol"] for p in positions)


def load_markets_with_retry(ex):
    """Carga los mercados públicos. Si BingX no responde, reintenta con espera creciente."""
    delay = 20
    while True:
        try:
            ex.load()
            return
        except Exception as e:
            log.exception("No se pudieron cargar los mercados")
            send(f"⚠️ No se pudieron cargar los mercados de BingX ({type(e).__name__}). "
                 f"Reintento en {delay}s.")
            time.sleep(delay)
            delay = min(delay * 2, 600)


def main():
    ex = BingX()
    report = config.credentials_report()
    log.info("Claves: %s", report)
    head = f"🤖 Bot iniciado · modo={config.TRADE_MODE} · TF={config.TIMEFRAME}"
    if config.TRADE_MODE != "live":
        head += "\n(en este modo las claves no se usan)"
    send(f"{head}\n{report}")
    for note in config.CONFIG_NOTES:
        send(f"⚠️ {note}")

    load_markets_with_retry(ex)

    trade_ok = False
    if config.TRADE_MODE == "live":
        trade_ok, detail = ex.check_private()
        if trade_ok:
            send("🔐 Claves de BingX válidas. Modo live activo.")
        else:
            send(f"⛔ Modo live desactivado. Motivo: {detail}\n"
                 "El bot sigue enviando señales, sin operar.")

    cooldown = {}
    day = None
    day_start_bal = None
    last_err = ("", 0.0)
    last_nodata = 0.0

    while True:
        try:
            now = time.time()
            today = dt.date.today()
            if trade_ok and day != today:
                day_start_bal = ex.balance_usdt()
                day = today

            signals, stats = scan(ex)
            if stats["pairs"] and stats["ok"] == 0 and now - last_nodata > NODATA_REPEAT_SEC:
                send(f"⚠️ Ningún par devolvió velas de BingX. TF usado: {config.TIMEFRAME}, "
                     f"intervalo enviado: {ex.sent_interval()}. Error: {stats['first_error'][:300]}")
                last_nodata = now

            for sig in signals:
                sym = sig["symbol"]
                if now - cooldown.get(sym, 0) < config.COOLDOWN_MIN * 60:
                    continue
                cooldown[sym] = now
                send(fmt(sig))

                if config.TRADE_MODE == "dry":
                    send(f"🧪 DRY: se habría abierto {sym} {sig['side']}")
                elif trade_ok and can_trade(ex, sig, day_start_bal):
                    if ex.place_trade(sig) is not None:
                        send(f"✅ Orden ejecutada: {sym} {sig['side']}")
        except Exception as e:
            log.exception("Error en ciclo: %s", e)
            kind = type(e).__name__
            if kind != last_err[0] or time.time() - last_err[1] > ERROR_REPEAT_SEC:
                send(f"⚠️ Error en el bot: {kind}: {e}")
                last_err = (kind, time.time())

        time.sleep(config.SCAN_INTERVAL)


if __name__ == "__main__":
    main()
