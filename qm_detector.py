from config import PIVOT_LEN, MIN_SWEEP_ATR


def pivots(highs, lows, n=PIVOT_LEN):
    """Swings confirmados (no repintan): (indice, 1=maximo/-1=minimo, precio), alternados."""
    raw = []
    for i in range(n, len(highs) - n):
        if highs[i] == max(highs[i - n:i + n + 1]):
            raw.append((i, 1, highs[i]))
        if lows[i] == min(lows[i - n:i + n + 1]):
            raw.append((i, -1, lows[i]))

    alt = []
    for p in raw:
        if alt and alt[-1][1] == p[1]:
            # dos del mismo tipo seguidos: me quedo con el mas extremo
            if (p[1] == 1 and p[2] > alt[-1][2]) or (p[1] == -1 and p[2] < alt[-1][2]):
                alt[-1] = p
        else:
            alt.append(p)
    return alt


def detect_qm(highs, lows, closes, atr, recent_bars=40):
    """
    Bajista: maximo (hombro izq.) -> minimo -> maximo mas alto (cabeza) -> cierre bajo el minimo intermedio (BOS).
    Alcista: el espejo.
    Devuelve dict o None.
    """
    sw = pivots(highs, lows)
    if len(sw) < 3 or atr <= 0:
        return None

    (ia, ta, pa), (im, tm, pm), (ih, th, ph) = sw[-3:]
    last_close = closes[-1]
    n = len(highs)

    # la cabeza tiene que ser reciente
    if ih < n - recent_bars:
        return None

    if ta == 1 and th == 1 and pm < pa and ph > pa + MIN_SWEEP_ATR * atr and last_close < pm:
        return {"dir": "SHORT", "ls": pa, "mid": pm, "head": ph, "qml": pa}

    if ta == -1 and th == -1 and pm > pa and ph < pa - MIN_SWEEP_ATR * atr and last_close > pm:
        return {"dir": "LONG", "ls": pa, "mid": pm, "head": ph, "qml": pa}

    return None
