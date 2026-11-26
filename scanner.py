"""Escaneo en vivo: pide velas, descarta la vela que aún se está formando y aplica la estrategia."""
import logging
import time

import pandas as pd

import config
from strategy import last_signal, params_from_config, tf_minutes

log = logging.getLogger("scanner")
WINDOW = 200  # velas que se piden por par (la estrategia usa unas 100)


def closed_frame(ohlcv, tf_ms, now_ms):
    """Velas de ccxt -> DataFrame, sin la vela que todavía no ha cerrado."""
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df[df["ts"] + tf_ms <= now_ms].copy()
    df.index = pd.to_datetime(df["ts"], unit="ms")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def scan(ex):
    """Devuelve (señales, estadísticas). Las estadísticas permiten detectar un fallo general."""
    p = params_from_config(config)
    tf_ms = tf_minutes(config.TIMEFRAME) * 60_000
    now_ms = int(time.time() * 1000)
    symbols = ex.top_symbols(config.TOP_N)
    out, ok, errors, first_error = [], 0, 0, ""
    for sym in symbols:
        try:
            raw = ex.fetch_ohlcv(sym, config.TIMEFRAME, WINDOW)
            if not raw:
                raise ValueError("sin velas cerradas")
            df = closed_frame(raw, tf_ms, now_ms)
            if df.empty:
                raise ValueError("sin velas cerradas")
            ok += 1
            if len(df) < 100:
                continue
            sig = last_signal(df, p)
            if sig is not None:
                sig["symbol"] = sym
                out.append(sig)
        except Exception as e:
            errors += 1
            if not first_error:
                first_error = f"{sym}: {type(e).__name__}: {e}"
    stats = {"pairs": len(symbols), "ok": ok, "errors": errors, "first_error": first_error}
    if errors:
        log.warning("Escaneo: %d de %d pares con error. Primero: %s",
                    errors, len(symbols), first_error[:300])
    else:
        log.info("Escaneo: %d pares sin errores", len(symbols))
    return sorted(out, key=lambda s: s["score"], reverse=True), stats
