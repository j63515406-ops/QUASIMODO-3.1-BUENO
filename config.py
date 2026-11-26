import os

# Caracteres invisibles que a veces se cuelan al copiar desde una web
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)

# Nombres aceptados para las claves de BingX
_KEY_NAMES = ["BINGX_API_KEY", "BINGX_APIKEY", "BINGX_KEY"]
_SECRET_NAMES = ["BINGX_SECRET", "BINGX_API_SECRET", "BINGX_SECRET_KEY", "BINGX_APISECRET"]
_ALL_NAMES = _KEY_NAMES + _SECRET_NAMES

# Intervalos de vela que acepta BingX para futuros (1M = un mes)
BINGX_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h",
                    "1d", "3d", "1w", "1M")
TRADE_MODES = ("signals", "dry", "live")
SETUP_NAMES = ("QM", "BRK")

# Palabras que se convierten en unidades: "15min" -> "15m", "4hours" -> "4h"
_UNIT_WORDS = (("minutes", "m"), ("minute", "m"), ("mins", "m"), ("min", "m"),
               ("hours", "h"), ("hour", "h"), ("hrs", "h"), ("hr", "h"),
               ("days", "d"), ("day", "d"), ("weeks", "w"), ("week", "w"))

# Avisos sobre valores de Railway que no se pudieron usar tal cual. El bot los manda a Telegram al arrancar.
CONFIG_NOTES = []


def _clean(raw, names=_ALL_NAMES):
    """Limpia un valor pegado en Railway. Devuelve (valor, notas). Las notas nunca contienen el valor."""
    notes = []
    v = raw.translate(_INVISIBLE)
    if v != raw:
        notes.append("caracteres invisibles")
    s = v.strip()
    if s != v:
        notes.append("espacios o saltos de línea sobrantes")
    v = s
    for n in names:
        if v.upper().startswith(n + "="):
            v = v[len(n) + 1:].strip()
            notes.append(f"se quitó el prefijo '{n}='")
            break
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].strip()
        notes.append("se quitaron las comillas")
    if "\n" in v or "\r" in v:
        notes.append("hay un salto de línea dentro del valor")
    return v, notes


def _read(names):
    """Devuelve (valor, nombre_de_la_variable, notas) con la primera variable definida y no vacía."""
    for name in names:
        raw = os.environ.get(name)
        if raw is None:
            continue
        value, notes = _clean(raw)
        if value:
            return value, name, notes
    return "", None, []


def _text(name, default=""):
    return _clean(os.getenv(name, default), [name])[0]


def normalize_timeframe(raw):
    """
    Devuelve (intervalo, nota). La nota es None si el valor ya era correcto.
    Acepta formas habituales ("15", "15min", "15M", "1H", "\"15m\""). Si no hay forma válida, usa 15m.
    """
    value, _ = _clean(raw, ["TIMEFRAME"])
    s = value.replace(" ", "")
    if not s:
        return "15m", None
    if s in BINGX_TIMEFRAMES:
        return s, (None if raw == s else f"TIMEFRAME recibido {raw!r} se usa como {s}")
    low = s.lower()
    for word, unit in _UNIT_WORDS:
        if low.endswith(word) and low[: -len(word)].isdigit():
            low = low[: -len(word)] + unit
            break
    if low.isdigit():
        low += "m"
    if low in BINGX_TIMEFRAMES:
        return low, f"TIMEFRAME recibido {raw!r} se usa como {low}"
    return "15m", (f"TIMEFRAME recibido {raw!r} no es válido. Valores aceptados: "
                   f"{', '.join(BINGX_TIMEFRAMES)}. Usando 15m")


def _num(name, default, cast):
    raw = _text(name)
    if cast is float:
        raw = raw.replace(",", ".")
    if not raw:
        return cast(default)
    try:
        return cast(raw)
    except ValueError:
        CONFIG_NOTES.append(f"{name} recibido {raw!r} no es un número. Usando {default}")
        return cast(default)


def _float(name, default):
    return _num(name, default, float)


def _int(name, default):
    return _num(name, default, int)


# Claves de BingX: solo se usan en modo live
BINGX_API_KEY, _KEY_VAR, _KEY_NOTES = _read(_KEY_NAMES)
BINGX_SECRET, _SECRET_VAR, _SECRET_NOTES = _read(_SECRET_NAMES)

TELEGRAM_TOKEN = _text("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = _text("TELEGRAM_CHAT_ID")

# Modo: signals (solo avisos) | dry (simula) | live (opera de verdad)
TRADE_MODE = _text("TRADE_MODE", "signals").lower() or "signals"
if TRADE_MODE not in TRADE_MODES:
    CONFIG_NOTES.append(f"TRADE_MODE recibido {os.getenv('TRADE_MODE', '')!r} no es válido "
                        "(signals, dry o live). Usando signals")
    TRADE_MODE = "signals"

# Intervalo de vela (ver normalize_timeframe)
TIMEFRAME, _tf_note = normalize_timeframe(os.getenv("TIMEFRAME", ""))
if _tf_note:
    CONFIG_NOTES.append(_tf_note)

# Escaneo
TOP_N = _int("TOP_N", 80)
SCAN_INTERVAL = _int("SCAN_INTERVAL", 300)     # segundos entre escaneos
COOLDOWN_MIN = _int("COOLDOWN_MIN", 120)

# Estrategia: lo que valida el backtest (python backtest.py)
_setups = tuple(s.strip().upper() for s in _text("SETUPS", "QM,BRK").split(",") if s.strip())
_bad_setups = [s for s in _setups if s not in SETUP_NAMES]
if _bad_setups:
    CONFIG_NOTES.append(f"SETUPS contiene valores no válidos {_bad_setups}. Aceptados: QM, BRK")
SETUPS = tuple(s for s in _setups if s in SETUP_NAMES) or SETUP_NAMES
MIN_SCORE = _float("MIN_SCORE", 70)
SL_ATR = _float("SL_ATR", 1.5)
TP_RR = _float("TP_RR", 2.0)
MAX_COST_R = _float("MAX_COST_R", 0.25)        # descarta señales cuyo coste ida y vuelta supera esta fracción de 1R
MAX_HOLD_BARS = _int("MAX_HOLD_BARS", 96)      # cierre por tiempo (96 velas de 15 m = 24 h)
PIVOT_LEN = _int("PIVOT_LEN", 5)
MIN_SWEEP_ATR = _float("MIN_SWEEP_ATR", 0.1)

# Costes reales en % por lado. Pon la comisión de tu cuenta de BingX.
FEE_PCT = _float("FEE_PCT", 0.05)
SLIP_PCT = _float("SLIP_PCT", 0.05)

# Riesgo
RISK_PCT = _float("RISK_PCT", 1.0)             # % de la cuenta que arriesgas por operación
LEVERAGE = _int("LEVERAGE", 3)
MAX_OPEN = _int("MAX_OPEN", 3)
DAILY_LOSS_LIMIT = _float("DAILY_LOSS_LIMIT", 20)  # pérdida diaria máxima en USDT


def credentials_report():
    """Resumen seguro para logs y Telegram: nombres de variables y longitudes, nunca los valores."""
    out = []
    for label, val, var, notes in (
        ("API key", BINGX_API_KEY, _KEY_VAR, _KEY_NOTES),
        ("secret", BINGX_SECRET, _SECRET_VAR, _SECRET_NOTES),
    ):
        if not val:
            out.append(f"{label}: no encontrada (revisa el nombre de la variable en Railway)")
        else:
            txt = f"{label}: variable {var}, {len(val)} caracteres"
            if notes:
                txt += " · ajustes automáticos: " + ", ".join(notes)
            out.append(txt)
    return " | ".join(out)
