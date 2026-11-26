import logging
import time

import ccxt
import pandas as pd

import config
from strategy import tf_minutes

log = logging.getLogger("exchange")

# Límite de peticiones de BingX: código 100410 ("pide de nuevo más tarde") o excepción de ccxt
_RATE_TEXT = ("100410", "请稍后")
_RATE_TYPES = tuple(getattr(ccxt, n) for n in ("RateLimitExceeded", "DDoSProtection") if hasattr(ccxt, n))


def _is_rate_limit(e):
    return isinstance(e, _RATE_TYPES) or any(t in str(e) for t in _RATE_TEXT)


def _client(with_keys):
    opts = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
    if with_keys:
        opts["apiKey"] = config.BINGX_API_KEY
        opts["secret"] = config.BINGX_SECRET
    ex = ccxt.bingx(opts)
    # ccxt también pediría la lista de monedas (petición privada firmada). No hace falta: se desactiva.
    ex.has["fetchCurrencies"] = False
    return ex


class BingX:
    """pub: datos públicos, sin claves. priv: saldo, posiciones y órdenes; solo en modo live."""

    def __init__(self):
        self.pub = _client(with_keys=False)
        self.priv = None
        if config.TRADE_MODE == "live" and config.BINGX_API_KEY and config.BINGX_SECRET:
            self.priv = _client(with_keys=True)

    def load(self):
        self.pub.load_markets()

    def sent_interval(self):
        """Intervalo tal como llega a BingX (para diagnóstico)."""
        return getattr(self.pub, "timeframes", {}).get(config.TIMEFRAME, config.TIMEFRAME)

    def check_private(self):
        if self.priv is None:
            return False, "faltan BINGX_API_KEY o BINGX_SECRET en Railway"
        try:
            self.priv.load_markets()
            self.priv.fetch_balance()
            return True, "claves válidas"
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            if "100413" in str(e):
                detail += (". BingX no reconoce la API key: confirma que sea de la cuenta real "
                           "(no demo), que esté activa y que tenga permiso de lectura y de futuros")
            return False, detail

    def top_symbols(self, n):
        tickers = self.pub.fetch_tickers()
        rows = []
        for sym, t in tickers.items():
            m = self.pub.markets.get(sym)
            if not m or not m.get("swap") or m.get("quote") != "USDT" or m.get("active") is False:
                continue
            rows.append((t.get("quoteVolume") or 0, sym))
        rows.sort(reverse=True)
        return [s for _, s in rows[:n]]

    def fetch_ohlcv(self, symbol, timeframe, limit, since=None):
        """Velas con reintento si BingX pide esperar. Los demás errores se lanzan tal cual."""
        for attempt in range(3):
            try:
                return self.pub.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            except Exception as e:
                if attempt == 2 or not _is_rate_limit(e):
                    raise
                log.info("BingX pide esperar (%s). Reintento %d", str(e)[:80], attempt + 1)
                time.sleep(2 * (attempt + 1))

    def history(self, symbol, timeframe, bars):
        """Últimas `bars` velas cerradas (sin la que se está formando), paginando hacia atrás."""
        tf_ms = tf_minutes(timeframe) * 60_000
        now = self.pub.milliseconds()
        since = now - (bars + 2) * tf_ms
        rows = {}
        for _ in range(200):  # tope de seguridad
            batch = self.fetch_ohlcv(symbol, timeframe, 500, since=since)
            if not batch:
                break
            for r in batch:
                rows[r[0]] = r
            last = batch[-1][0]
            if len(batch) < 500 or last >= now - 2 * tf_ms:
                break
            since = last + tf_ms
        df = pd.DataFrame(sorted(rows.values()), columns=["ts", "open", "high", "low", "close", "volume"])
        df = df[df["ts"] + tf_ms <= now].tail(bars).copy()
        df.index = pd.to_datetime(df["ts"], unit="ms")
        return df[["open", "high", "low", "close", "volume"]].astype(float)

    def balance_usdt(self):
        return float(self.priv.fetch_balance()["total"].get("USDT", 0) or 0)

    def open_positions(self):
        return [p for p in self.priv.fetch_positions() if float(p.get("contracts") or 0) > 0]

    def place_trade(self, sig):
        # AVISO: el envío de SL y TP con estos params todavía no está verificado contra BingX.
        sym, is_long = sig["symbol"], sig["side"] == "LONG"
        equity = self.balance_usdt()
        if equity <= 0:
            log.warning("Saldo 0: no se abre %s", sym)
            return None
        sl_frac = abs(sig["entry"] - sig["sl"]) / sig["entry"]
        # tamaño por riesgo, con tope: el margen total no pasa del 90 % del saldo
        notional = min(equity * config.RISK_PCT / 100 / sl_frac,
                       equity * config.LEVERAGE * 0.9 / config.MAX_OPEN)
        amount = float(self.priv.amount_to_precision(sym, notional / sig["entry"]))
        if amount <= 0:
            log.warning("Cantidad demasiado pequeña para %s", sym)
            return None
        sl = float(self.priv.price_to_precision(sym, sig["sl"]))
        tp = float(self.priv.price_to_precision(sym, sig["tp"]))
        self.priv.set_leverage(config.LEVERAGE, sym)
        order = self.priv.create_order(sym, "market", "buy" if is_long else "sell", amount, None,
                                       {"stopLossPrice": sl, "takeProfitPrice": tp})
        log.info("Orden %s %s cantidad=%s: %s", sym, sig["side"], amount, order.get("id"))
        return order
