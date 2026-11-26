import logging
import ccxt

import config

log = logging.getLogger("exchange")


def _client(with_keys):
    opts = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
    if with_keys:
        opts["apiKey"] = config.BINGX_API_KEY
        opts["secret"] = config.BINGX_SECRET
    ex = ccxt.bingx(opts)
    # Al cargar mercados, ccxt también pide la lista de monedas: en BingX es una petición
    # privada firmada con la key. Para escanear u operar no hace falta, así que se desactiva.
    ex.has["fetchCurrencies"] = False
    return ex


class BingX:
    """
    pub:  solo datos públicos (mercados, tickers, velas). Sin claves: un problema con
          las claves nunca impide escanear.
    priv: saldo, posiciones y órdenes. Solo existe en modo live y con claves.
    """

    def __init__(self):
        self.pub = _client(with_keys=False)
        self.priv = None
        if config.TRADE_MODE == "live" and config.BINGX_API_KEY and config.BINGX_SECRET:
            self.priv = _client(with_keys=True)

    def load(self):
        self.pub.load_markets()

    def check_private(self):
        """Comprueba las claves con llamadas privadas. Devuelve (ok, detalle)."""
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
            # descarta solo los mercados marcados como inactivos (ccxt puede devolver None)
            if not m or not m.get("swap") or m.get("quote") != "USDT" or m.get("active") is False:
                continue
            qv = t.get("quoteVolume") or 0
            rows.append((qv, sym))
        rows.sort(reverse=True)
        return [s for _, s in rows[:n]]

    def fetch_ohlcv(self, symbol, timeframe, limit):
        return self.pub.fetch_ohlcv(symbol, timeframe, limit=limit)

    def balance_usdt(self):
        bal = self.priv.fetch_balance()
        return float(bal["total"].get("USDT", 0) or 0)

    def open_positions(self):
        pos = self.priv.fetch_positions()
        return [p for p in pos if float(p.get("contracts") or 0) > 0]

    def place_trade(self, sig):
        sym = sig["symbol"]
        is_long = sig["side"] == "LONG"
        notional = config.RISK_USDT * config.LEVERAGE
        amount = float(self.priv.amount_to_precision(sym, notional / sig["entry"]))
        sl = float(self.priv.price_to_precision(sym, sig["sl"]))
        tp = float(self.priv.price_to_precision(sym, sig["tp"]))

        self.priv.set_leverage(config.LEVERAGE, sym)
        params = {"stopLossPrice": sl, "takeProfitPrice": tp}
        order = self.priv.create_order(sym, "market", "buy" if is_long else "sell", amount, None, params)
        log.info("Orden enviada %s %s: %s", sym, sig["side"], order.get("id"))
        return order
