# BingX QM Scanner Bot

Escanea futuros USDT-M de BingX, detecta patrones QM y movimientos con volumen,
envía señales a Telegram y opcionalmente opera.

## Despliegue en Railway
1. Sube todos los archivos a un repositorio de GitHub (sin carpetas).
2. En Railway: New Project → Deploy from GitHub repo.
3. En Variables, copia las de `.env.example` con tus valores reales.
   Pega solo el valor, sin `BINGX_API_KEY=` delante y sin comillas.
4. Si Railway no arranca el proceso, en Settings → Deploy → Start Command pon `python main.py`.
5. Empieza con `TRADE_MODE=signals`. Cuando estés conforme, pasa a `dry` y luego a `live`.

Al arrancar, el bot envía a Telegram un resumen de las claves: el nombre de la variable
y su número de caracteres. Nunca muestra el valor. Si aparece "no encontrada",
el nombre de la variable en Railway no coincide.

## Claves de BingX
- En `signals` y `dry` no se usan: el escaneo solo lee datos públicos.
- En `live` se usan para saldo, posiciones y órdenes. La key debe ser de la cuenta real
  (no demo), estar activa y tener permiso de lectura y de trading de futuros.
- Si las claves fallan en `live`, el bot avisa por Telegram con el motivo y sigue enviando señales sin operar.

## Crear el bot de Telegram
1. Habla con @BotFather, crea el bot y copia el token → `TELEGRAM_TOKEN`.
2. Envía un mensaje a tu bot, luego abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` y copia `chat.id` → `TELEGRAM_CHAT_ID`.

## Modos
- `signals`: solo envía avisos.
- `dry`: envía avisos y simula operaciones.
- `live`: opera de verdad en BingX con SL y TP.

## Aviso
Software experimental. No es asesoría financiera. Puedes perder todo lo que operes.
