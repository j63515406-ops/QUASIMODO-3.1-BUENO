"""
Script de prueba rápida de API Keys de BingX.
Úsalo en Railway o localmente para verificar si las keys funcionan.

Cómo usarlo:
1. Asegúrate de tener BINGX_API_KEY y BINGX_SECRET en las variables de entorno
2. Ejecuta: python test_keys.py
"""

import os
import sys
import ccxt

def main():
    api_key = os.getenv("BINGX_API_KEY", "").strip()
    secret = os.getenv("BINGX_SECRET", "").strip()

    print("=" * 50)
    print("  TEST DE API KEYS — BingX")
    print("=" * 50)

    if not api_key or not secret:
        print("\n❌ FALTAN VARIABLES")
        print("   BINGX_API_KEY o BINGX_SECRET están vacías.")
        print("   Configúralas en Railway → Variables.")
        sys.exit(1)

    print(f"\nKey (primeros 8): {api_key[:8]}...")
    print(f"Secret (primeros 4): {secret[:4]}...")

    try:
        ex = ccxt.bingx({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })

        print("\n1. Cargando mercados...")
        ex.load_markets()
        print(f"   ✅ Mercados OK ({len(ex.markets)} mercados)")

        print("\n2. Probando autenticación (fetch_balance)...")
        bal = ex.fetch_balance()
        usdt = bal.get("total", {}).get("USDT", 0)
        print(f"   ✅ Autenticación OK")
        print(f"   Balance USDT: {usdt}")

        print("\n3. Probando posiciones...")
        pos = ex.fetch_positions()
        open_pos = [p for p in pos if float(p.get("contracts") or 0) > 0]
        print(f"   ✅ Posiciones OK ({len(open_pos)} abiertas)")

        print("\n" + "=" * 50)
        print("  ✅ TODO CORRECTO — Las API keys funcionan")
        print("=" * 50)
        print("\nYa puedes poner TRADE_MODE=live o dry")

    except ccxt.AuthenticationError as e:
        print("\n" + "=" * 50)
        print("  ❌ AUTHENTICATION ERROR")
        print("=" * 50)
        print(f"\nDetalle: {e}")
        print("\nQué hacer:")
        print("  1. Ve a https://bingx.com/en/account/api")
        print("  2. Crea una NUEVA API Key")
        print("  3. Activa permisos de Futures / Swap")
        print("  4. NO actives restricción de IP")
        print("  5. Copia Key y Secret SIN espacios")
        print("  6. Actualiza las variables en Railway y redeploy")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error inesperado: {type(e).__name__}")
        print(f"   {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
