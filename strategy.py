"""
Señales compartidas por el bot en vivo y por el backtest.
Regla: la señal de una vela solo usa esa vela y las anteriores (sin mirar al futuro).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

RECENT_BARS = 40  # la cabeza del QM debe ser de las últimas 40 velas


TF_UNIT_MIN = {"m": 1, "h": 60, "d": 1440, "w": 10080, "M": 43200}


def tf_minutes(tf):
    return int(tf[:-1]) * TF_UNIT_MIN[tf[-1]]


@dataclass(frozen=True)
class Params:
    setups: tuple = ("QM", "BRK")
    min_score: float = 70.0
    sl_atr: float = 1.5
    tp_rr: float = 2.0
    max_cost_r: float = 0.25
    fee_pct: float = 0.05
    slip_pct: float = 0.05
    cooldown_bars: int = 8
    max_hold_bars: int = 96
    pivot_len: int = 5
    min_sweep_atr: float = 0.1


def params_from_config(cfg):
    return Params(
        setups=tuple(cfg.SETUPS), min_score=cfg.MIN_SCORE, sl_atr=cfg.SL_ATR, tp_rr=cfg.TP_RR,
        max_cost_r=cfg.MAX_COST_R, fee_pct=cfg.FEE_PCT, slip_pct=cfg.SLIP_PCT,
        cooldown_bars=max(1, round(cfg.COOLDOWN_MIN / tf_minutes(cfg.TIMEFRAME))),
        max_hold_bars=cfg.MAX_HOLD_BARS, pivot_len=cfg.PIVOT_LEN, min_sweep_atr=cfg.MIN_SWEEP_ATR,
    )


def _push_swing(sw, typ, price, idx):
    """Swings alternados: si dos seguidos son del mismo tipo, se queda el más extremo."""
    if sw and sw[-1][0] == typ:
        if (typ == 1 and price > sw[-1][1]) or (typ == -1 and price < sw[-1][1]):
            sw[-1] = (typ, price, idx)
    else:
        sw.append((typ, price, idx))


def compute_signals(df, pivot_len=5, min_sweep_atr=0.1):
    """Señal que daría el bot si cada vela fuera la última cerrada. Devuelve un DataFrame alineado con df."""
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    o = df["open"].to_numpy(dtype=float)
    v = df["volume"].to_numpy(dtype=float)
    n, P = len(df), pivot_len
    with np.errstate(invalid="ignore", divide="ignore"):
        prev_c = np.concatenate([[np.nan], c[:-1]])
        tr = np.fmax(np.fmax(h - l, np.abs(h - prev_c)), np.abs(l - prev_c))
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        compression = atr / pd.Series(atr).rolling(50, min_periods=20).mean().to_numpy()
        vs = pd.Series(v)
        vol_ratio = (vs.rolling(3).mean() / vs.shift(3).rolling(20).mean().clip(lower=1e-9)).to_numpy()
        prev_hi = pd.Series(h).shift(1).rolling(20).max().to_numpy()
        prev_lo = pd.Series(l).shift(1).rolling(20).min().to_numpy()
        brk = np.where(c > prev_hi, 1, np.where(c < prev_lo, -1, 0))
        ema9 = pd.Series(c).ewm(span=9, adjust=False).mean().to_numpy()
        ema21 = pd.Series(c).ewm(span=21, adjust=False).mean().to_numpy()
        trend = np.where(ema9 > ema21, 1, -1)

    # QM: un swing en la vela t-P solo se confirma en la vela t
    qm = np.zeros(n, dtype=int)
    sw, last_head = [], -1
    for t in range(n):
        ci = t - P
        if ci >= P:
            if h[ci] == h[ci - P: ci + P + 1].max():
                _push_swing(sw, 1, h[ci], ci)
            if l[ci] == l[ci - P: ci + P + 1].min():
                _push_swing(sw, -1, l[ci], ci)
        if len(sw) < 3 or not atr[t] > 0:
            continue
        ta, pa, _ = sw[-3]
        _, pm, _ = sw[-2]
        th, ph, ih = sw[-1]
        if t - ih >= RECENT_BARS or ih == last_head:
            continue
        thr = min_sweep_atr * atr[t]
        if ta == 1 and th == 1 and pm < pa and ph > pa + thr and c[t] < pm:
            qm[t], last_head = -1, ih
        elif ta == -1 and th == -1 and pm > pa and ph < pa - thr and c[t] > pm:
            qm[t], last_head = 1, ih

    side = np.where(qm != 0, qm, brk).astype(int)
    setup = np.where(qm != 0, "QM", np.where(brk != 0, "BRK", "")).astype(object)
    with np.errstate(invalid="ignore"):
        score = (np.where(vol_ratio >= 2, 25, np.where(vol_ratio >= 1.5, 15, 0))
                 + np.where(compression < 0.8, 15, 0)
                 + np.where((side != 0) & (brk == side), 20, 0)
                 + np.where(qm != 0, 30, 0)
                 + np.where((side != 0) & (trend == side), 10, 0)).astype(float)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v, "atr": atr,
                         "vol_ratio": vol_ratio, "compression": compression, "side": side,
                         "setup": setup, "score": score, "trend": trend}, index=df.index)


def _evaluate(side, setup, score, atr, price, p):
    """Filtros y SL/TP, igual en vivo y en backtest. Devuelve (side, sl, tp, coste_en_R) o None."""
    if side == 0 or setup not in p.setups or not atr > 0 or score < p.min_score:
        return None
    sl_dist = p.sl_atr * atr
    cost_r = 2.0 * (p.fee_pct + p.slip_pct) / (sl_dist / price * 100.0)
    if cost_r > p.max_cost_r:
        return None
    return side, price - side * sl_dist, price + side * p.tp_rr * sl_dist, cost_r


def last_signal(df, p):
    """Señal de la última vela cerrada (uso en vivo). None si no hay señal válida."""
    r = compute_signals(df, p.pivot_len, p.min_sweep_atr).iloc[-1]
    ev = _evaluate(int(r["side"]), str(r["setup"]), float(r["score"]), float(r["atr"]), float(r["close"]), p)
    if ev is None:
        return None
    side, sl, tp, cost_r = ev
    return {"side": "LONG" if side == 1 else "SHORT", "setup": str(r["setup"]),
            "qm": str(r["setup"]) == "QM", "score": float(r["score"]), "entry": float(r["close"]),
            "sl": sl, "tp": tp, "atr": float(r["atr"]), "cost_r": cost_r,
            "vol_ratio": float(r["vol_ratio"]), "compression": float(r["compression"]),
            "bar_ts": str(df.index[-1])}


def simulate(sig, p):
    """Opera las señales de una serie, una a la vez por par. Entra al open siguiente con deslizamiento.
    Sale por SL o TP dentro de la vela; si ambos caen en la misma vela, cuenta como SL."""
    o = sig["open"].to_numpy(dtype=float)
    h = sig["high"].to_numpy(dtype=float)
    l = sig["low"].to_numpy(dtype=float)
    c = sig["close"].to_numpy(dtype=float)
    side_a = sig["side"].to_numpy(dtype=int)
    setup_a = sig["setup"].to_numpy(dtype=object)
    score_a = sig["score"].to_numpy(dtype=float)
    atr_a = sig["atr"].to_numpy(dtype=float)
    ts_a = sig.index.to_numpy()
    n, slip = len(sig), p.slip_pct / 100.0
    trades, busy_until, last_sig = [], -1, -10**9
    for t in np.flatnonzero(side_a != 0):
        if t >= n - 1 or t < busy_until or t - last_sig < p.cooldown_bars:
            continue
        ev = _evaluate(int(side_a[t]), str(setup_a[t]), float(score_a[t]), float(atr_a[t]), float(c[t]), p)
        if ev is None:
            continue
        s, sl, tp, cost_r = ev
        e = int(t) + 1
        fill = o[e] * (1 + s * slip)
        if (s == 1 and fill <= sl) or (s == -1 and fill >= sl):
            continue
        risk_pct = abs(fill - sl) / fill * 100.0
        last = min(n - 1, e + p.max_hold_bars - 1)
        exit_px, reason, exit_j = None, "TIME", last
        for j in range(e, last + 1):
            if s == 1:
                if l[j] <= sl:
                    exit_px, reason = min(o[j], sl), "SL"
                elif h[j] >= tp:
                    exit_px, reason = max(o[j], tp), "TP"
            else:
                if h[j] >= sl:
                    exit_px, reason = max(o[j], sl), "SL"
                elif l[j] <= tp:
                    exit_px, reason = min(o[j], tp), "TP"
            if exit_px is not None:
                exit_j = j
                break
        if exit_px is None:
            exit_px = c[last]
        net_pct = s * (exit_px * (1 - s * slip) - fill) / fill * 100.0 - 2.0 * p.fee_pct
        trades.append({"ts": ts_a[e], "e": e, "exit": int(exit_j), "side": s, "setup": str(setup_a[t]),
                       "reason": reason, "R": net_pct / risk_pct, "bars": int(exit_j - e + 1),
                       "cost_r": cost_r})
        busy_until, last_sig = exit_j, int(t)
    return trades


def summarize(trades):
    """Métricas en R (1R = riesgo planificado de cada operación, con costes incluidos)."""
    if not trades:
        return {"n": 0, "win": 0.0, "avgR": 0.0, "t": 0.0, "PF": 0.0, "totR": 0.0, "maxDD": 0.0}
    trades = sorted(trades, key=lambda t: t["ts"])
    R = np.array([t["R"] for t in trades], dtype=float)
    n = len(R)
    sd = R.std(ddof=1) if n > 1 else 0.0
    losses = -R[R <= 0].sum()
    eq = np.cumsum(R)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return {"n": n, "win": float((R > 0).mean()), "avgR": float(R.mean()),
            "t": float(R.mean() / (sd / np.sqrt(n))) if sd > 0 else 0.0,
            "PF": float(R[R > 0].sum() / losses) if losses > 0 else float("inf"),
            "totR": float(eq[-1]), "maxDD": float((peak - eq).max())}
