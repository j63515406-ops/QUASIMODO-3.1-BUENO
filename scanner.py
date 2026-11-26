import logging
import numpy as np
import pandas as pd

import config
from qm_detector import detect_qm

log = logging.getLogger("scanner")


def _indicators(df):
    df["ema9"] = df.close.ewm(span=9, adjust=False).mean()
    df["ema21"] = df.close.ewm(span=21, adjust=False).mean()
    tr = pd.concat([
        df.high - df.low,
        (df.high - df.close.shift()).abs(),
        (df.low - df.close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    return df


def analyze(symbol, ohlcv):
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.iloc[:-1]                       # solo velas cerradas
    if len(df) < 60:
        return None
    df = _indicators(df)

    last = df.iloc[-1]
    atr = float(last.atr)
    if np.isnan(atr) or atr <= 0:
        return None

    atr_base = float(df.atr.iloc[-50:].mean())
    compression = atr / atr_base if atr_base > 0 else 1.0
    vol_ratio = float(df.volume.iloc[-3:].mean() / max(df.volume.iloc[-23:-3].mean(), 1e-9))
    prev_high = float(df.high.iloc[-21:-1].max())
    prev_low = float(df.low.iloc[-21:-1].min())
    breakout = 1 if last.close > prev_high else -1 if last.close < prev_low else 0
    trend = 1 if last.ema9 > last.ema21 else -1

    qm = detect_qm(df.high.values, df.low.values, df.close.values, atr)

    if qm:
        direction = qm["dir"]
    elif breakout:
        direction = "LONG" if breakout == 1 else "SHORT"
    else:
        return None

    is_long = direction == "LONG"
    score = 0
    if vol_ratio >= 2:
        score += 25
    elif vol_ratio >= 1.5:
        score += 15
    if compression < 0.8:           # volatilidad comprimida antes del movimiento
        score += 15
    if breakout and ((breakout == 1) == is_long):
        score += 20
    if qm:
        score += 30
    if (trend == 1) == is_long:
        score += 10

    entry = float(last.close)
    sl_dist = config.SL_ATR * atr
    sl = entry - sl_dist if is_long else entry + sl_dist
    tp = entry + config.TP_RR * sl_dist if is_long else entry - config.TP_RR * sl_dist

    return {
        "symbol": symbol,
        "side": direction,
        "score": score,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "atr": atr,
        "vol_ratio": vol_ratio,
        "compression": compression,
        "qm": qm is not None,
    }


def scan(ex):
    symbols = ex.top_symbols(config.TOP_N)
    log.info("Escaneando %d pares", len(symbols))
    results = []
    for sym in symbols:
        try:
            ohlcv = ex.fetch_ohlcv(sym, config.TIMEFRAME, 150)
            sig = analyze(sym, ohlcv)
            if sig and sig["score"] >= config.MIN_SCORE:
                results.append(sig)
        except Exception as e:
            log.warning("Error en %s: %s", sym, e)
    return sorted(results, key=lambda s: s["score"], reverse=True)
