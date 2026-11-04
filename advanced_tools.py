#############################
# Agente Economico De IA    #
# Herramientas Avanzadas    #
#############################
#
# Practica 1 - Agente IA (Paso 08 / Paso 10)
# 5 herramientas para un agente economico, todas usan APIs publicas
# que NO requieren autenticacion (API key):
#
#   1. consultar_tipo_cambio_api        -> https://open.er-api.com
#   2. convertir_moneda                 -> https://api.frankfurter.app
#   3. consultar_tendencia_cambiaria    -> https://api.frankfurter.app (serie historica)
#   4. consultar_precio_cripto          -> https://api.coingecko.com
#   5. consultar_indicador_economico    -> https://api.worldbank.org
#   6. consultar_pib_per_capita_pais    -> https://api.worldbank.org
#   7. consultar_top_criptomonedas      -> https://api.coingecko.com
#   8. consultar_tasa_interes_pais      -> https://api.worldbank.org
 
import requests
from datetime import date, timedelta
 
 
class AdvancedTools:
 
    def __init__(self):
        pass
 
    # ------------------------------------------------------------------
    # 1) Tipo de cambio actual de una moneda base contra todas las demas
    # ------------------------------------------------------------------
    def consultar_tipo_cambio_api(self, moneda: str):
        print(f"Herramienta consultar_tipo_cambio_api llamada con moneda: {moneda}")
 
        if not moneda:
            return "Error: Se requiere el codigo de la moneda base (ej. USD)."
 
        url = f"https://open.er-api.com/v6/latest/{moneda.upper()}"
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if data.get("result") != "success":
                return f"ERROR: La API no pudo calcular el tipo de cambio para {moneda}"
 
            return {
                "moneda_base": data.get("base_code"),
                "fecha_actualizacion": data.get("time_last_update_utc"),
                "gtq": data.get("rates", {}).get("GTQ"),
                "usd": data.get("rates", {}).get("USD"),
                "eur": data.get("rates", {}).get("EUR"),
            }
        except Exception as e:
            print(f"Error al consultar_tipo_cambio_api: {moneda}. Error: {e}")
            return f"ERROR: No se pudo obtener el tipo de cambio para la moneda: {moneda}"
 
    # ------------------------------------------------------------------
    # 2) Convertir un monto entre dos monedas
    # ------------------------------------------------------------------
    def convertir_moneda(self, monto: float, moneda_origen: str, moneda_destino: str):
        print(
            f"Herramienta convertir_moneda llamada con monto: {monto}, "
            f"moneda_origen: {moneda_origen}, moneda_destino: {moneda_destino}"
        )
 
        if monto is None or not moneda_origen or not moneda_destino:
            return "Error: Se requiere monto, moneda_origen y moneda_destino."
 
        url = (
            f"https://api.frankfurter.app/latest"
            f"?amount={monto}&from={moneda_origen.upper()}&to={moneda_destino.upper()}"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            return {
                "monto_original": data.get("amount"),
                "moneda_origen": data.get("base"),
                "fecha": data.get("date"),
                "resultado": data.get("rates", {}).get(moneda_destino.upper()),
                "moneda_destino": moneda_destino.upper(),
            }
        except Exception as e:
            print(f"Error al convertir_moneda: {moneda_origen} -> {moneda_destino}. Error: {e}")
            return (
                f"ERROR: No se pudo convertir {monto} de {moneda_origen} a {moneda_destino}. "
                "Nota: esta API no soporta GTQ; usa monedas como USD, EUR, MXN, etc."
            )
 
    # ------------------------------------------------------------------
    # 3) Tendencia del tipo de cambio en los ultimos N dias
    # ------------------------------------------------------------------
    def consultar_tendencia_cambiaria(
        self, moneda_origen: str, moneda_destino: str, dias: int = 7
    ):
        print(
            f"Herramienta consultar_tendencia_cambiaria llamada con "
            f"moneda_origen: {moneda_origen}, moneda_destino: {moneda_destino}, dias: {dias}"
        )
 
        if not moneda_origen or not moneda_destino:
            return "Error: Se requiere moneda_origen y moneda_destino."
 
        if not dias:
            dias = 7
 
        fecha_fin = date.today()
        fecha_inicio = fecha_fin - timedelta(days=int(dias))
 
        url = (
            f"https://api.frankfurter.app/{fecha_inicio.isoformat()}..{fecha_fin.isoformat()}"
            f"?from={moneda_origen.upper()}&to={moneda_destino.upper()}"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            return {
                "moneda_origen": data.get("base"),
                "moneda_destino": moneda_destino.upper(),
                "desde": data.get("start_date"),
                "hasta": data.get("end_date"),
                "historial": data.get("rates"),
            }
        except Exception as e:
            print(
                f"Error al consultar_tendencia_cambiaria: {moneda_origen} -> {moneda_destino}. "
                f"Error: {e}"
            )
            return (
                f"ERROR: No se pudo obtener la tendencia de {moneda_origen} a {moneda_destino}. "
                "Nota: esta API no soporta GTQ; usa monedas como USD, EUR, MXN, etc."
            )
 
    # ------------------------------------------------------------------
    # 4) Precio actual de una criptomoneda
    # ------------------------------------------------------------------
    def consultar_precio_cripto(self, criptomoneda: str, moneda_referencia: str = "usd"):
        print(
            f"Herramienta consultar_precio_cripto llamada con "
            f"criptomoneda: {criptomoneda}, moneda_referencia: {moneda_referencia}"
        )
 
        if not criptomoneda:
            return "Error: Se requiere el id de la criptomoneda (ej. bitcoin, ethereum)."
 
        if not moneda_referencia:
            moneda_referencia = "usd"
 
        cripto_id = criptomoneda.lower().strip()
        ref = moneda_referencia.lower().strip()
 
        url = (
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={cripto_id}&vs_currencies={ref}"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if cripto_id not in data:
                return (
                    f"ERROR: No se encontro la criptomoneda '{criptomoneda}'. "
                    "Usa el id de CoinGecko, por ejemplo: bitcoin, ethereum, solana."
                )
 
            return {
                "criptomoneda": cripto_id,
                "moneda_referencia": ref,
                "precio": data[cripto_id].get(ref),
            }
        except Exception as e:
            print(f"Error al consultar_precio_cripto: {criptomoneda}. Error: {e}")
            return f"ERROR: No se pudo obtener el precio de la criptomoneda: {criptomoneda}"
 
    # ------------------------------------------------------------------
    # 5) Indicador macroeconomico de un pais (Banco Mundial)
    # ------------------------------------------------------------------
    INDICADORES = {
        "inflacion": "FP.CPI.TOTL.ZG",   # Inflacion anual, precios al consumidor (%)
        "pib": "NY.GDP.MKTP.CD",         # PIB total (USD actuales)
        "desempleo": "SL.UEM.TOTL.ZS",   # Tasa de desempleo (% de la fuerza laboral)
        "poblacion": "SP.POP.TOTL",      # Poblacion total
    }
 
    def consultar_indicador_economico(self, pais: str, indicador: str):
        print(
            f"Herramienta consultar_indicador_economico llamada con "
            f"pais: {pais}, indicador: {indicador}"
        )
 
        if not pais or not indicador:
            return (
                "Error: Se requiere pais (codigo ISO de 2 letras, ej. GT) e indicador "
                f"(uno de: {', '.join(self.INDICADORES.keys())})."
            )
 
        codigo_indicador = self.INDICADORES.get(indicador.lower().strip())
        if not codigo_indicador:
            return (
                f"ERROR: Indicador '{indicador}' no reconocido. "
                f"Usa uno de: {', '.join(self.INDICADORES.keys())}"
            )
 
        url = (
            f"https://api.worldbank.org/v2/country/{pais.upper()}/indicator/"
            f"{codigo_indicador}?format=json&per_page=5&mrnev=1"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                return f"ERROR: No hay datos de '{indicador}' para el pais: {pais}"
 
            registro = data[1][0]
            return {
                "pais": registro.get("country", {}).get("value"),
                "indicador": registro.get("indicator", {}).get("value"),
                "anio": registro.get("date"),
                "valor": registro.get("value"),
            }
        except Exception as e:
            print(f"Error al consultar_indicador_economico: {pais}, {indicador}. Error: {e}")
            return f"ERROR: No se pudo obtener el indicador '{indicador}' para el pais: {pais}"
 
    # ------------------------------------------------------------------
    # 6) PIB per capita de un pais (Banco Mundial)
    # ------------------------------------------------------------------
    def consultar_pib_per_capita_pais(self, pais: str):
        print(f"Herramienta consultar_pib_per_capita_pais llamada con pais: {pais}")
 
        if not pais:
            return "Error: Se requiere el codigo ISO de 2 letras del pais (ej. GT, US, MX)."
 
        url = (
            f"https://api.worldbank.org/v2/country/{pais.upper()}/indicator/"
            f"NY.GDP.PCAP.CD?format=json&per_page=5&mrnev=1"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                return f"ERROR: No hay datos de PIB per capita para el pais: {pais}"
 
            registro = data[1][0]
            return {
                "pais": registro.get("country", {}).get("value"),
                "anio": registro.get("date"),
                "pib_per_capita_usd": registro.get("value"),
            }
        except Exception as e:
            print(f"Error al consultar_pib_per_capita_pais: {pais}. Error: {e}")
            return f"ERROR: No se pudo obtener el PIB per capita para el pais: {pais}"
 
    # ------------------------------------------------------------------
    # 7) Top N criptomonedas por capitalizacion de mercado
    # ------------------------------------------------------------------
    def consultar_top_criptomonedas(self, cantidad: int = 5):
        print(f"Herramienta consultar_top_criptomonedas llamada con cantidad: {cantidad}")
 
        try:
            cantidad = int(cantidad) if cantidad else 5
        except (TypeError, ValueError):
            cantidad = 5
 
        cantidad = max(1, min(cantidad, 20))
 
        url = (
            f"https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&order=market_cap_desc&per_page={cantidad}&page=1&sparkline=false"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if not isinstance(data, list) or not data:
                return "ERROR: No se pudo obtener el top de criptomonedas."
 
            return [
                {
                    "nombre": c.get("name"),
                    "simbolo": c.get("symbol"),
                    "precio_usd": c.get("current_price"),
                    "cambio_24h_pct": c.get("price_change_percentage_24h"),
                }
                for c in data
            ]
        except Exception as e:
            print(f"Error al consultar_top_criptomonedas: {cantidad}. Error: {e}")
            return "ERROR: No se pudo obtener el top de criptomonedas."
 
    # ------------------------------------------------------------------
    # 8) Tasa de interes de prestamo de un pais (Banco Mundial)
    # ------------------------------------------------------------------
    def consultar_tasa_interes_pais(self, pais: str):
        print(f"Herramienta consultar_tasa_interes_pais llamada con pais: {pais}")
 
        if not pais:
            return "Error: Se requiere el codigo ISO de 2 letras del pais (ej. GT, US, MX)."
 
        url = (
            f"https://api.worldbank.org/v2/country/{pais.upper()}/indicator/"
            f"FR.INR.LEND?format=json&per_page=5&mrnev=1"
        )
 
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
 
            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                return f"ERROR: No hay datos de tasa de interes para el pais: {pais}"
 
            registro = data[1][0]
            return {
                "pais": registro.get("country", {}).get("value"),
                "anio": registro.get("date"),
                "tasa_interes_prestamo_pct": registro.get("value"),
            }
        except Exception as e:
            print(f"Error al consultar_tasa_interes_pais: {pais}. Error: {e}")
            return f"ERROR: No se pudo obtener la tasa de interes para el pais: {pais}"
            