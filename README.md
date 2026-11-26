# BingX QM Scanner Bot

Escanea futuros USDT-M de BingX, detecta señales (patrón QM y ruptura) y, si lo activas, opera.
Antes de arriesgar dinero, mide la estrategia con el backtest.

## 1. Medir antes de operar
Desde tu PC, con Python 3.10 o superior:

    pip install -r requirements.txt
    python backtest.py              # 15 pares, 6000 velas de 15 m
    python backtest.py 25 10000     # más pares y más historia = resultados más fiables

No necesita claves. Simula cada señal con comisiones y deslizamiento, prueba 243 ajustes,
los elige con datos de dentro de muestra y solo juzga el resultado de fuera de muestra.

Lee el VEREDICTO:
- "hay indicios de ventaja": prueba en dry 2-4 semanas con los parámetros del mejor ajuste.
- "sin ventaja fuera de muestra": no pases a live con esta estrategia.

Los ajustes se ponen en Railway con las variables SETUPS, MIN_SCORE, SL_ATR, TP_RR y MAX_COST_R.

## 2. Despliegue en Railway
1. Sube los archivos a un repositorio de GitHub (sin carpetas).
2. En Railway: New Project → Deploy from GitHub repo.
3. En Variables, copia las de `.env.example`. Pega solo el valor, sin `NOMBRE=` ni comillas.
4. Si Railway no arranca el proceso, en Settings → Deploy → Start Command pon `python main.py`.
5. Orden recomendado: `TRADE_MODE=signals`, luego `dry`, y solo después `live`, empezando con `RISK_PCT=0.5`.

Al arrancar, el bot manda a Telegram:
- Un resumen de las claves: nombre de la variable y número de caracteres, nunca el valor.
- Un aviso por cada valor de Railway que no pudo usar tal cual, con el valor exacto que recibió.

## 3. TIMEFRAME
BingX acepta: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M.
`1M` es un mes. Recomendado: `15m`.

El bot entiende formas como `15`, `15min` o `15M` (las convierte en 15m). Si el valor no tiene
forma válida, usa 15m y te lo avisa en Telegram.

Si ves el aviso "Ningún par devolvió velas", el mensaje incluye el intervalo que llega a BingX
y el error exacto. Corrige la variable TIMEFRAME en Railway y vuelve a desplegar.

## 4. Claves de BingX
- Solo se usan en `live`.
- Deben ser de la cuenta real (no demo), estar activas y tener permiso de lectura y de trading de futuros.

## 5. Lo que todavía no está verificado
- El envío de SL y TP junto a la orden de entrada no se ha comprobado contra BingX.
  Antes de live, abre una operación mínima y mira en la app que el stop y el objetivo aparecen.

## Modos
- `signals`: solo envía avisos.
- `dry`: envía avisos y simula operaciones.
- `live`: opera de verdad.

## Aviso
Software experimental. No es asesoría financiera. Puedes perder todo lo que operes.
