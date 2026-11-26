import os

# Caracteres invisibles que a veces se cuelan al copiar desde una web
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)

# Nombres aceptados para las claves de BingX
_KEY_NAMES = ["BINGX_API_KEY", "BINGX_APIKEY", "BINGX_KEY"]
_SECRET_NAMES = ["BINGX_SECRET", "BINGX_API_SECRET", "BINGX_SECRET_KEY", "BINGX_APISECRET"]
_ALL_NAMES = _KEY_NAMES + _SECRET_NAMES


def _clean(raw):
    """Limpia un valor pegado en Railway. Devuelve (valor, notas). Las notas nunca contienen el valor."""
    notes = []
    v = raw.translate(_INVISIBLE)
    if v != raw:
        notes.append("caracteres invisibles")
    s = v.strip()
    if s != v:
        notes.append("espacios o saltos de línea sobrantes")
    v = s
    for n in _ALL_NAMES:
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


def _num(name, default, cast):
    raw = os.getenv(name, "").strip()
    return cast(raw) if raw else cast(default)


def _float(name, default):
    return _num(name, default, float)


def _int(name, default):
    return _num(name, default, int)


# Claves de BingX: solo se usan en modo live (el escaneo es público)
BINGX_API_KEY, _KEY_VAR, _KEY_NOTES = _read(_KEY_NAMES)
BINGX_SECRET, _SECRET_VAR, _SECRET_NOTES = _read(_SECRET_NAMES)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Modo de operación: signals (solo avisos) | dry (simula) | live (opera de verdad)
TRADE_MODE = os.getenv("TRADE_MODE", "signals").strip().lower()

# Escaneo
TIMEFRAME = os.getenv("TIMEFRAME", "15m").strip()
SCAN_INTERVAL = _int("SCAN_INTERVAL", 300)        # segundos entre escaneos
TOP_N = _int("TOP_N", 80)                         # cuántos pares por volumen revisar
MIN_SCORE = _float("MIN_SCORE", 70)               # puntuación mínima para señal (0-100)
COOLDOWN_MIN = _int("COOLDOWN_MIN", 120)          # minutos sin repetir señal del mismo par

# Patrón QM
PIVOT_LEN = _int("PIVOT_LEN", 5)
MIN_SWEEP_ATR = _float("MIN_SWEEP_ATR", 0.1)

# Gestión de riesgo
RISK_USDT = _float("RISK_USDT", 10)               # margen por operación
LEVERAGE = _int("LEVERAGE", 3)
MAX_OPEN = _int("MAX_OPEN", 3)                    # posiciones abiertas simultáneas
DAILY_LOSS_LIMIT = _float("DAILY_LOSS_LIMIT", 20) # pérdida diaria máxima en USDT
SL_ATR = _float("SL_ATR", 1.5)                    # stop loss = X * ATR
TP_RR = _float("TP_RR", 2.0)                      # take profit = X veces el riesgo


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
