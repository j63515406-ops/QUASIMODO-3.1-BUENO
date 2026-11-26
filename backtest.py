"""
Backtest de la estrategia: sin mirar al futuro, con comisiones y deslizamiento.

Uso (desde tu PC, con las dependencias instaladas):
    python backtest.py              # 15 pares, 6000 velas de 15 m
    python backtest.py 25 10000     # 25 pares, 10000 velas

No necesita claves: solo lee velas públicas de BingX.
"""
import itertools
import sys
from dataclasses import replace

import config
from exchange import BingX
from strategy import compute_signals, params_from_config, simulate, summarize

GRID = {
    "setups": [("QM", "BRK"), ("QM",), ("BRK",)],
    "min_score": [60.0, 70.0, 80.0],
    "sl_atr": [1.0, 1.5, 2.0],
    "tp_rr": [1.5, 2.0, 3.0],
    "max_cost_r": [0.2, 0.35, 99.0],
}
IS_FRAC = 0.7    # primer 70 % de cada par = dentro de muestra; el resto = fuera de muestra
MIN_IS = 30      # operaciones mínimas dentro de muestra para elegir un ajuste
MIN_OOS = 20     # operaciones mínimas fuera de muestra para opinar


def combos(grid):
    keys = list(grid)
    for vals in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, vals))


def evaluate(sigs, splits, p):
    ist, oos = [], []
    for sym, sig in sigs.items():
        for tr in simulate(sig, p):
            (oos if tr["e"] >= splits[sym] else ist).append(tr)
    return summarize(ist), summarize(oos)


def run_backtest(data, base, grid=GRID):
    sigs = {s: compute_signals(df, base.pivot_len, base.min_sweep_atr) for s, df in data.items()}
    splits = {s: int(len(df) * IS_FRAC) for s, df in data.items()}
    rows = []
    for combo in combos(grid):
        p = replace(base, **combo)
        ist, oos = evaluate(sigs, splits, p)
        rows.append({"p": p, "is": ist, "oos": oos})
    base_is, base_oos = evaluate(sigs, splits, base)
    return rows, {"is": base_is, "oos": base_oos}


def good_oos(m):
    return m["n"] >= MIN_OOS and m["avgR"] > 0 and m["PF"] >= 1.1 and m["t"] >= 1.5


def fmt(m):
    if m["n"] == 0:
        return "sin operaciones"
    return (f"n={m['n']:<4} acierto={m['win'] * 100:4.1f}%  R medio={m['avgR']:+.3f}  "
            f"t={m['t']:+.1f}  PF={m['PF']:.2f}  peor racha={m['maxDD']:.1f}R")


def describe(p):
    return (f"setups={'+'.join(p.setups)} score>={p.min_score:.0f} SL={p.sl_atr}xATR "
            f"TP={p.tp_rr}R coste<={p.max_cost_r}R")


def report(rows, base_res, base):
    elig = sorted((r for r in rows if r["is"]["n"] >= MIN_IS), key=lambda r: r["is"]["avgR"], reverse=True)
    good = sum(1 for r in rows if good_oos(r["oos"]))
    print("\n== Tu configuración actual ==")
    print(" ", describe(base))
    print("  dentro de muestra:", fmt(base_res["is"]))
    print("  fuera de muestra: ", fmt(base_res["oos"]))
    print("\n== Mejores ajustes elegidos SOLO con datos dentro de muestra (top 5) ==")
    for r in elig[:5]:
        print(" ", describe(r["p"]))
        print("    dentro:", fmt(r["is"]))
        print("    fuera: ", fmt(r["oos"]))
    print(f"\nDe {len(rows)} configuraciones, {good} salen buenas también fuera de muestra.")
    print("Si salen muchas por casualidad, el resultado es ruido.")
    if not elig:
        print("\nVEREDICTO: faltan operaciones. Descarga más velas o más pares.")
    elif good_oos(elig[0]["oos"]):
        print("\nVEREDICTO: hay indicios de ventaja fuera de muestra. Siguiente paso: dry 2-4 semanas.")
    else:
        print("\nVEREDICTO: sin ventaja fuera de muestra demostrable. No pases a live con esta estrategia.")


def main():
    n_sym = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    n_bars = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    ex = BingX()
    ex.load()
    data = {}
    for sym in ex.top_symbols(n_sym):
        try:
            df = ex.history(sym, config.TIMEFRAME, n_bars)
            if len(df) >= 300:
                data[sym] = df
                print(f"  {sym}: {len(df)} velas")
        except Exception as e:
            print(f"  {sym}: sin datos ({e})")
    if not data:
        print("No se descargaron datos.")
        return
    base = params_from_config(config)
    rows, base_res = run_backtest(data, base)
    report(rows, base_res, base)


if __name__ == "__main__":
    main()
