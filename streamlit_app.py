##################################################
# AnaSofIA - Version Streamlit                   #
##################################################
#
# Este archivo es EXTRA, para tu presentacion/entrega. Le pone una interfaz
# de chat en Streamlit al agente de agente_economico.py, con las mismas 8
# herramientas economicas de advanced_tools.py, mas:
#   - generar_grafica (graficas en pantalla)
#   - memoria a largo plazo (long_term_memory.py): guardar_dato_usuario,
#     olvidar_dato_usuario y buscar_conversaciones_anteriores. Se guarda en
#     Supabase si existen SUPABASE_URL y SUPABASE_KEY (en el .env o en los
#     Secrets de Streamlit Cloud); si no, en memoria_largo_plazo.json.
#
# NO reemplaza a agente_economico.py: ese sigue siendo el que subes al
# portal del curso para el Paso 10.
#
# Como correrlo:
#   1. Instala Streamlit y pandas una sola vez (con el entorno virtual activado):
#        python -m pip install streamlit pandas
#   2. Corre:
#        streamlit run streamlit_app.py
#   3. Se abre solo en tu navegador (normalmente http://localhost:8501)

import json
import os
import re
import uuid

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from basic_memory import BasicMemory
from advanced_tools import AdvancedTools
from long_term_memory import LongTermMemory, SupabaseLongTermMemory

# ------------------------------------------------------------------
# Configuracion de la pagina
# ------------------------------------------------------------------
st.set_page_config(
    page_title="AnaSofIA",
    page_icon="💜",
    layout="centered",
)

# Cargar variables de entorno #
load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")

MEMORY_MAX_MESSAGES = 10

# ------------------------------------------------------------------
# SYSTEM PROMPT y TOOLS: identicos a los de agente_economico.py
# ------------------------------------------------------------------
SYSTEM_PROMPT = """
Eres "AnaSofIA", un agente economico que habla en español, cuyo OBJETIVO especifico
es ayudar al usuario a entender y tomar decisiones informadas sobre:
- Tipos de cambio de divisas.
- Conversion de montos entre monedas.
- Tendencias recientes del tipo de cambio.
- Precios de criptomonedas (individuales y el top del mercado).
- Indicadores macroeconomicos de un pais (inflacion, PIB, PIB per capita, desempleo,
  poblacion, tasa de interes de prestamo).

Herramientas disponibles:
- consultar_tipo_cambio_api: da el tipo de cambio actual de una moneda base contra el
  quetzal (GTQ), el dolar (USD) y el euro (EUR). Requiere la moneda base.
- convertir_moneda: convierte un monto de una moneda a otra. Requiere monto, moneda_origen
  y moneda_destino. No soporta GTQ como moneda de entrada o salida.
- consultar_tendencia_cambiaria: da el historial del tipo de cambio de los ultimos N dias
  entre dos monedas, util para ver si una moneda sube o baja. Requiere moneda_origen y
  moneda_destino; dias es opcional (por defecto 7). No soporta GTQ.
- consultar_precio_cripto: da el precio actual de una criptomoneda (usa el id de CoinGecko
  en minusculas, ej. bitcoin, ethereum, solana) en la moneda de referencia indicada
  (por defecto usd).
- consultar_indicador_economico: da un indicador macroeconomico (inflacion, pib, desempleo
  o poblacion) de un pais, usando su codigo ISO de 2 letras (ej. GT, US, MX).
- consultar_pib_per_capita_pais: da el PIB per capita (en USD) de un pais, usando su
  codigo ISO de 2 letras.
- consultar_top_criptomonedas: da las N criptomonedas mas grandes por capitalizacion de
  mercado, con su precio y variacion en 24 horas (por defecto 5).
- consultar_tasa_interes_pais: da la tasa de interes de prestamo de un pais, usando su
  codigo ISO de 2 letras (ej. GT, US, MX).
- generar_grafica: genera una grafica de barras o de lineas para visualizar datos
  numericos. Usala siempre que el usuario pida explicitamente una grafica, un grafico
  o una visualizacion de cualquier tema. Si los datos vienen de otra herramienta (tipo
  de cambio, PIB, cripto, inflacion, etc.), usa esos datos reales. Si el usuario pide
  graficar algo que ninguna otra herramienta cubre, puedes usar tu propio conocimiento
  general para dar valores aproximados.
- guardar_dato_usuario: guarda en tu memoria a largo plazo un dato duradero del usuario
  (por ejemplo su nombre, pais, profesion, la moneda que usa o los temas que le interesan).
- olvidar_dato_usuario: borra de tu memoria a largo plazo un dato que el usuario te pida
  olvidar.
- buscar_conversaciones_anteriores: busca por palabras clave en las conversaciones
  anteriores con el usuario (por ejemplo "bitcoin", "inflacion Guatemala", "euro").

Reglas:
- Responde siempre en español, de forma breve y clara, basado en los datos que regresan
  las herramientas.
- Si falta un dato obligatorio para llamar una herramienta, preguntalo antes de inventarlo.
- Si una herramienta regresa un error, explicaselo al usuario en una sola frase y sugiere
  como corregirlo (por ejemplo, usar otro codigo de moneda).
- No des asesoria financiera personalizada ni garantices ganancias; solo reporta datos.
- Si el usuario pregunta quien te creo, te programo o te desarrollo, responde que fuiste
  creado por Ana Sofia Oliva Luna.
- Cuando uses generar_grafica con datos que NO provienen de una de las otras herramientas
  (es decir, que usaste tu propio conocimiento general), acláralo en tu respuesta de texto,
  dejando claro que son valores aproximados y no datos en tiempo real.
- Nunca incluyas sintaxis de imagenes en Markdown (como ![texto](url)) en tus respuestas.
  La grafica ya se muestra aparte, generada automaticamente por la aplicacion cuando usas
  generar_grafica; tu solo describe los datos en texto, no intentes "dibujar" la grafica
  tu mismo.
- Cuando el usuario te cuente un dato duradero sobre si mismo, guardalo con
  guardar_dato_usuario sin preguntarle. No guardes preguntas sueltas ni datos de mercado.
- Si el usuario te pide olvidar algo, usa olvidar_dato_usuario.
- Si el usuario menciona algo de una conversacion anterior ("la otra vez", "lo que te
  pregunte ayer", "te acuerdas..."), usa buscar_conversaciones_anteriores antes de
  responder. Los datos de mercado de conversaciones anteriores pueden estar desactualizados:
  si el usuario quiere el dato de hoy, vuelve a consultar la herramienta correspondiente.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_tipo_cambio_api",
            "description": (
                "Consulta el tipo de cambio actual de una moneda base contra el quetzal "
                "(GTQ), el dolar (USD) y el euro (EUR)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "moneda": {
                        "type": "string",
                        "description": "Codigo de la moneda base a consultar, por ejemplo USD",
                    }
                },
                "required": ["moneda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convertir_moneda",
            "description": (
                "Convierte un monto de una moneda a otra usando tasas de cambio actualizadas. "
                "No soporta GTQ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "monto": {
                        "type": "number",
                        "description": "Cantidad a convertir",
                    },
                    "moneda_origen": {
                        "type": "string",
                        "description": "Codigo de la moneda de origen, por ejemplo USD",
                    },
                    "moneda_destino": {
                        "type": "string",
                        "description": "Codigo de la moneda de destino, por ejemplo EUR",
                    },
                },
                "required": ["monto", "moneda_origen", "moneda_destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_tendencia_cambiaria",
            "description": (
                "Obtiene el historial del tipo de cambio de los ultimos N dias entre dos "
                "monedas, para analizar si una moneda ha subido o bajado. No soporta GTQ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "moneda_origen": {
                        "type": "string",
                        "description": "Codigo de la moneda de origen, por ejemplo USD",
                    },
                    "moneda_destino": {
                        "type": "string",
                        "description": "Codigo de la moneda de destino, por ejemplo EUR",
                    },
                    "dias": {
                        "type": "integer",
                        "description": "Numero de dias hacia atras a consultar (por defecto 7)",
                    },
                },
                "required": ["moneda_origen", "moneda_destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_precio_cripto",
            "description": (
                "Consulta el precio actual de una criptomoneda en la moneda de referencia "
                "indicada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "criptomoneda": {
                        "type": "string",
                        "description": (
                            "Id de la criptomoneda en CoinGecko, en minusculas, "
                            "por ejemplo bitcoin, ethereum, solana"
                        ),
                    },
                    "moneda_referencia": {
                        "type": "string",
                        "description": "Moneda de referencia para el precio, por ejemplo usd (por defecto usd)",
                    },
                },
                "required": ["criptomoneda"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_indicador_economico",
            "description": (
                "Consulta un indicador macroeconomico de un pais: inflacion, pib, desempleo "
                "o poblacion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 2 letras del pais, por ejemplo GT, US, MX",
                    },
                    "indicador": {
                        "type": "string",
                        "description": "Uno de: inflacion, pib, desempleo, poblacion",
                    },
                },
                "required": ["pais", "indicador"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_pib_per_capita_pais",
            "description": "Consulta el PIB per capita (en USD) de un pais.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 2 letras del pais, por ejemplo GT, US, MX",
                    }
                },
                "required": ["pais"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_top_criptomonedas",
            "description": (
                "Consulta las criptomonedas mas grandes por capitalizacion de mercado, con "
                "su precio actual y variacion en las ultimas 24 horas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cantidad": {
                        "type": "integer",
                        "description": "Cuantas criptomonedas mostrar, entre 1 y 20 (por defecto 5)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_tasa_interes_pais",
            "description": "Consulta la tasa de interes de prestamo (lending rate) de un pais.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 2 letras del pais, por ejemplo GT, US, MX",
                    }
                },
                "required": ["pais"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generar_grafica",
            "description": (
                "Genera una grafica de barras o de lineas para visualizar datos numericos "
                "de cualquier tema que el usuario pida. Si los datos salen de otra "
                "herramienta usalos tal cual; si no hay herramienta que los cubra, puedes "
                "usar tu propio conocimiento general para dar valores aproximados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "Tipo de grafica: 'barras' o 'lineas'",
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Titulo corto que describe lo que se esta graficando",
                    },
                    "categorias": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Etiquetas del eje X, una por cada valor (ej. paises, años, "
                            "monedas, nombres)"
                        ),
                    },
                    "valores": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Valores numericos a graficar, en el mismo orden que categorias",
                    },
                },
                "required": ["tipo", "categorias", "valores"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guardar_dato_usuario",
            "description": (
                "Guarda en la memoria a largo plazo un dato duradero del usuario, para "
                "recordarlo en conversaciones futuras."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dato": {
                        "type": "string",
                        "description": (
                            "El dato en una frase corta, por ejemplo: 'Se llama Ana', "
                            "'Vive en Guatemala', 'Le interesa el bitcoin'"
                        ),
                    }
                },
                "required": ["dato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "olvidar_dato_usuario",
            "description": "Borra de la memoria a largo plazo los datos que contengan el texto indicado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dato": {
                        "type": "string",
                        "description": "Texto del dato a olvidar, por ejemplo 'bitcoin' o 'Se llama'",
                    }
                },
                "required": ["dato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_conversaciones_anteriores",
            "description": (
                "Busca por palabras clave en las conversaciones anteriores con el usuario y "
                "regresa lo que pregunto y lo que se le respondio, con la fecha."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": "Palabras clave a buscar, por ejemplo 'bitcoin' o 'inflacion Guatemala'",
                    }
                },
                "required": ["consulta"],
            },
        },
    },
]

TOOL_SOURCES = {
    "consultar_tipo_cambio_api": "open.er-api.com",
    "convertir_moneda": "api.frankfurter.app",
    "consultar_tendencia_cambiaria": "api.frankfurter.app",
    "consultar_precio_cripto": "api.coingecko.com",
    "consultar_indicador_economico": "api.worldbank.org",
    "consultar_pib_per_capita_pais": "api.worldbank.org",
    "consultar_top_criptomonedas": "api.coingecko.com",
    "consultar_tasa_interes_pais": "api.worldbank.org",
    "buscar_conversaciones_anteriores": "memoria a largo plazo",
}

# Preguntas rapidas (una por herramienta), iguales a las del botones de la version web
QUICK_QUESTIONS = [
    ("💱", "Tipo de cambio", "¿Cuál es el tipo de cambio del dólar?"),
    ("🔁", "Convertir moneda", "Convierte 200 dólares a euros"),
    ("📈", "Tendencia cambiaria", "¿Cómo ha estado el euro frente al dólar en los últimos 10 días?"),
    ("🪙", "Precio cripto", "¿Cuál es el precio del bitcoin en dólares?"),
    ("📊", "Inflación", "¿Cuál es la inflación de Guatemala?"),
    ("🌎", "PIB per cápita", "¿Cuál es el PIB per cápita de Guatemala?"),
    ("🏆", "Top criptomonedas", "Dame el top 5 de criptomonedas por capitalización de mercado"),
    ("🏦", "Tasa de interés", "¿Cuál es la tasa de interés de préstamo en Guatemala?"),
]


# ------------------------------------------------------------------
# Cliente de Groq y herramientas (se crean una sola vez por sesion de servidor)
# ------------------------------------------------------------------
@st.cache_resource
def get_client():
    return Groq(api_key=api_key)


@st.cache_resource
def get_tools():
    return AdvancedTools()


def leer_secreto(nombre):
    """Busca primero en el .env / variables de entorno y luego en los Secrets
    de Streamlit Cloud."""
    valor = os.environ.get(nombre)
    if valor:
        return valor
    try:
        return st.secrets[nombre]
    except Exception:
        return None


@st.cache_resource
def get_long_memory():
    url = leer_secreto("SUPABASE_URL")
    key = leer_secreto("SUPABASE_KEY")

    # Si hay datos de Supabase, la memoria se guarda alla (permanente)
    if url and key:
        try:
            memoria = SupabaseLongTermMemory(url=url, key=key)
            print("Memoria a largo plazo: Supabase")
            return memoria
        except Exception as e:
            print(f"No se pudo conectar a Supabase, se usara el archivo JSON. Error: {e}")

    # Si no, se usa el archivo memoria_largo_plazo.json junto a este .py
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_largo_plazo.json")
    print("Memoria a largo plazo: archivo JSON")
    return LongTermMemory(ruta_archivo=ruta)


client = get_client()
tools = get_tools()
long_memory = get_long_memory()


def generar_grafica(tipo, categorias, valores, titulo="Datos"):
    """
    Herramienta "generica" de graficacion: no llama a ninguna API, solo
    empaqueta los datos que el modelo ya decidio (de otra herramienta o de
    su propio conocimiento) en un formato que build_chart_df() sabe graficar.
    """
    print(f"Herramienta generar_grafica llamada con tipo: {tipo}, titulo: {titulo}")

    if not categorias or not valores or len(categorias) != len(valores):
        return "Error: Debes dar 'categorias' y 'valores' con la misma cantidad de elementos."

    tipo_norm = (tipo or "").strip().lower()
    tipo_final = "line" if tipo_norm in ("lineas", "linea", "line", "lines") else "bar"

    return {
        "tipo_grafica": tipo_final,
        "titulo": titulo or "Datos",
        "categorias": categorias,
        "valores": valores,
    }


# ------------------------------------------------------------------
# Estado de la sesion: memoria del agente (igual a BasicMemory) + lo que
# se muestra en pantalla (incluye graficas y fuentes, que BasicMemory no
# guarda porque solo le interesa al LLM el texto).
# ------------------------------------------------------------------
if "memory" not in st.session_state:
    st.session_state.memory = BasicMemory(max_messages=MEMORY_MAX_MESSAGES)

if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Identificador de la conversacion actual dentro de la memoria a largo plazo
if "conversacion_id" not in st.session_state:
    st.session_state.conversacion_id = uuid.uuid4().hex


def build_chart_df(name, args, result):
    """
    Misma logica que build_chart() en app_web.py, pero en vez de armar un
    diccionario para Chart.js, arma un DataFrame de pandas para graficarse
    de forma nativa con st.line_chart / st.bar_chart.
    Regresa (tipo, dataframe) o (None, None) si no aplica.
    """
    try:
        if name == "consultar_tendencia_cambiaria" and isinstance(result, dict):
            historial = result.get("historial")
            destino = (result.get("moneda_destino") or args.get("moneda_destino") or "").upper()
            if isinstance(historial, dict) and destino:
                fechas = sorted(historial.keys())
                valores = [historial[f].get(destino) for f in fechas]
                if any(v is not None for v in valores):
                    columna = f"{result.get('moneda_origen', '')} a {destino}"
                    df = pd.DataFrame({columna: valores}, index=pd.Index(fechas, name="fecha"))
                    return "line", df

        if name == "consultar_top_criptomonedas" and isinstance(result, list) and result:
            nombres = [c.get("nombre") or c.get("simbolo") for c in result]
            precios = [c.get("precio_usd") for c in result]
            df = pd.DataFrame({"Precio (USD)": precios}, index=pd.Index(nombres, name="cripto"))
            return "bar", df

        if name == "generar_grafica" and isinstance(result, dict) and "categorias" in result:
            titulo = result.get("titulo") or "Datos"
            categorias = result.get("categorias")
            valores = result.get("valores")
            if categorias and valores and len(categorias) == len(valores):
                df = pd.DataFrame({titulo: valores}, index=pd.Index(categorias, name="categoria"))
                tipo_final = result.get("tipo_grafica", "bar")
                return tipo_final, df
    except Exception as e:
        print(f"No se pudo armar la grafica para {name}: {e}")

    return None, None


def process_response(user_text):
    # El SYSTEM_PROMPT se arma en cada pregunta para incluir lo que hay en la
    # memoria a largo plazo (datos del usuario y conversaciones anteriores)
    conversacion_id = st.session_state.conversacion_id
    system_prompt = SYSTEM_PROMPT + long_memory.contexto_para_prompt(excluir_id=conversacion_id)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(st.session_state.memory.messages())
    messages.append({"role": "user", "content": user_text})

    last_chart = None  # tupla (tipo, dataframe) o None
    used_sources = []

    while True:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=TOOLS,
        )

        msg = resp.choices[0].message

        # Si no hay llamados a herramientas, entonces ya regresamos la respuesta
        if not getattr(msg, "tool_calls", None):
            sources = list(dict.fromkeys(used_sources))
            return msg.content or "", last_chart, sources

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            }
        )

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")

            if name == "consultar_tipo_cambio_api":
                result = tools.consultar_tipo_cambio_api(moneda=args.get("moneda"))
            elif name == "convertir_moneda":
                result = tools.convertir_moneda(
                    monto=args.get("monto"),
                    moneda_origen=args.get("moneda_origen"),
                    moneda_destino=args.get("moneda_destino"),
                )
            elif name == "consultar_tendencia_cambiaria":
                result = tools.consultar_tendencia_cambiaria(
                    moneda_origen=args.get("moneda_origen"),
                    moneda_destino=args.get("moneda_destino"),
                    dias=args.get("dias", 7),
                )
            elif name == "consultar_precio_cripto":
                result = tools.consultar_precio_cripto(
                    criptomoneda=args.get("criptomoneda"),
                    moneda_referencia=args.get("moneda_referencia", "usd"),
                )
            elif name == "consultar_indicador_economico":
                result = tools.consultar_indicador_economico(
                    pais=args.get("pais"),
                    indicador=args.get("indicador"),
                )
            elif name == "consultar_pib_per_capita_pais":
                result = tools.consultar_pib_per_capita_pais(pais=args.get("pais"))
            elif name == "consultar_top_criptomonedas":
                result = tools.consultar_top_criptomonedas(cantidad=args.get("cantidad", 5))
            elif name == "consultar_tasa_interes_pais":
                result = tools.consultar_tasa_interes_pais(pais=args.get("pais"))
            elif name == "generar_grafica":
                result = generar_grafica(
                    tipo=args.get("tipo"),
                    categorias=args.get("categorias"),
                    valores=args.get("valores"),
                    titulo=args.get("titulo", "Datos"),
                )
            elif name == "guardar_dato_usuario":
                result = long_memory.guardar_dato(dato=args.get("dato"))
            elif name == "olvidar_dato_usuario":
                result = long_memory.olvidar_dato(dato=args.get("dato"))
            elif name == "buscar_conversaciones_anteriores":
                result = long_memory.buscar_conversaciones(
                    consulta=args.get("consulta"),
                    excluir_id=conversacion_id,
                )
            else:
                print(f"Se intento llamar a una herramienta desconocida {name}")
                result = {"error": f"Herramienta desconocida: {name}"}

            chart_type, chart_df = build_chart_df(name, args, result)
            if chart_type:
                last_chart = (chart_type, chart_df)

            source = TOOL_SOURCES.get(name)
            if source:
                used_sources.append(source)

            # Agregar a los mensajes el resultado del llamado de la herramienta
            # Esto lo recibira el modelo al continuar la iteracion
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )


def quitar_imagenes_markdown(texto):
    """
    Red de seguridad: por si el modelo igual intenta 'dibujar' la grafica el
    mismo insertando una imagen en Markdown (![..](..)), la quitamos del
    texto antes de mostrarla. La grafica real ya se muestra aparte.
    """
    if not texto:
        return texto
    limpio = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", texto)
    # Quitar lineas que quedaron vacias de mas (maximo una linea en blanco seguida)
    limpio = re.sub(r"\n{3,}", "\n\n", limpio)
    return limpio.strip()


def enviar_pregunta(texto):
    """Corre una pregunta a traves del agente y la guarda en el historial
    que se muestra (display_messages) y en la memoria real (BasicMemory)."""
    texto = (texto or "").strip()
    if not texto:
        return

    st.session_state.display_messages.append({"role": "user", "content": texto})

    with st.spinner("AnaSofIA está pensando..."):
        try:
            assistant_text, chart, sources = process_response(texto)
            assistant_text = quitar_imagenes_markdown(assistant_text)
        except Exception as e:
            print(f"Error en process_response: {e}")
            assistant_text = "Hubo un problema al consultar al agente. Revisa la terminal."
            chart, sources = None, []

    st.session_state.display_messages.append(
        {"role": "assistant", "content": assistant_text, "chart": chart, "sources": sources}
    )

    st.session_state.memory.add("user", texto)
    st.session_state.memory.add("assistant", assistant_text)

    # Memoria a largo plazo: guardar la conversacion en el archivo JSON
    try:
        long_memory.agregar_mensaje(st.session_state.conversacion_id, "user", texto)
        long_memory.agregar_mensaje(st.session_state.conversacion_id, "assistant", assistant_text)
    except Exception as e:
        print(f"No se pudo guardar en la memoria a largo plazo: {e}")


# ------------------------------------------------------------------
# Avatares personalizados (iguales en espiritu al circulo "AS" de la
# version web): imagenes PNG en la carpeta avatars/, junto a este archivo.
# ------------------------------------------------------------------
AVATAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")
AVATAR_AI = os.path.join(AVATAR_DIR, "avatar_ai.png")
AVATAR_USER = os.path.join(AVATAR_DIR, "avatar_user.png")


def avatar_para(role):
    """Regresa la ruta del avatar si existe el archivo, si no deja que
    Streamlit use su icono por defecto (para que nunca truene si falta)."""
    ruta = AVATAR_AI if role == "assistant" else AVATAR_USER
    return ruta if os.path.isfile(ruta) else None


# ------------------------------------------------------------------
# Estilos: paleta lila + rosado pastel, igual a la version web.
# Las burbujas del chat y los botones de la barra lateral se re-estilizan
# con selectores data-testid de Streamlit, que son mas estables que las
# clases autogeneradas.
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    .anasofia-title { font-size: 2rem; font-weight: 700; color: #5b3a6b; margin-bottom: 0; }
    .anasofia-subtitle { color: #9678a8; margin-top: 0; }
    .source-chip {
        display: inline-block;
        background: rgba(180, 143, 217, 0.15);
        color: #5b3a6b;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.78rem;
        margin-top: 6px;
    }

    /* Avatares redondos (ya vienen circulares del PNG, esto es por si acaso) */
    [data-testid="stChatMessageAvatarUser"] img,
    [data-testid="stChatMessageAvatarAssistant"] img {
        border-radius: 50%;
    }

    /* Burbuja del agente: tarjeta blanca con borde suave */
    [data-testid="stChatMessageContent"] {
        background: #ffffff;
        border: 1px solid #f0d5e8;
        border-radius: 16px;
        padding: 12px 16px;
    }

    /* Burbuja del usuario: morado solido, texto blanco, alineada a la derecha */
    div[data-testid="stChatMessage"]:has(
        > [data-testid="stChatMessageContent"][aria-label="Chat message from user"]
    ) {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] {
        background: #c9a9e8;
        border: none;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] p {
        color: #ffffff;
    }

    /* Botones de la barra lateral (preguntas rapidas): pastilla color lila claro */
    [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        background: rgba(180, 143, 217, 0.12);
        border: 1px solid rgba(180, 143, 217, 0.35);
        border-radius: 12px;
        color: #5b3a6b;
        justify-content: flex-start;
    }
    [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background: rgba(180, 143, 217, 0.28);
        border-color: #b48fd9;
        color: #5b3a6b;
    }

    /* Boton de "Limpiar conversacion": pastilla morada solida, como en la version web */
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        border-radius: 999px;
        background: #b48fd9;
        border: none;
    }
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {
        background: #a07ac9;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Barra lateral: branding, preguntas rapidas, reset
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown('<p class="anasofia-title">AnaSofIA</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="anasofia-subtitle">Análisis macroeconómico en tiempo real</p>',
        unsafe_allow_html=True,
    )

    if st.button("🗑️ Nueva conversación", use_container_width=True, type="primary"):
        # La conversacion anterior NO se borra: queda guardada en la memoria a
        # largo plazo y el agente puede buscarla despues.
        st.session_state.memory = BasicMemory(max_messages=MEMORY_MAX_MESSAGES)
        st.session_state.display_messages = []
        st.session_state.conversacion_id = uuid.uuid4().hex
        st.rerun()

    with st.expander("🧠 Memoria a largo plazo"):
        hechos = long_memory.hechos()
        if hechos:
            st.markdown("**Lo que recuerdo de ti:**")
            for hecho in hechos:
                st.markdown(f"- {hecho}")
        else:
            st.caption("Todavía no recuerdo datos tuyos. Cuéntame tu nombre o qué te interesa.")

        total = long_memory.total_conversaciones(excluir_id=st.session_state.conversacion_id)
        st.caption(f"Conversaciones anteriores guardadas: {total}")
        donde = "Supabase" if isinstance(long_memory, SupabaseLongTermMemory) else "archivo local"
        st.caption(f"Guardado en: {donde}")

        if st.button("Borrar toda la memoria", use_container_width=True, key="borrar_memoria"):
            long_memory.borrar_todo()
            st.rerun()

    st.markdown("---")
    st.caption("Preguntas rápidas, una por herramienta:")

    for icono, etiqueta, pregunta in QUICK_QUESTIONS:
        if st.button(f"{icono} {etiqueta}", use_container_width=True, key=f"quick_{etiqueta}"):
            st.session_state.pending_prompt = pregunta

    st.markdown("---")
    st.caption(
        "Fuentes: open.er-api.com · api.frankfurter.app · api.coingecko.com · "
        "api.worldbank.org\n\nModelo: openai/gpt-oss-120b (Groq)"
    )

# ------------------------------------------------------------------
# Panel principal: historial del chat
# ------------------------------------------------------------------
st.markdown('<p class="anasofia-title">Panel de consultas</p>', unsafe_allow_html=True)

if not st.session_state.display_messages:
    st.chat_message("assistant", avatar=avatar_para("assistant")).markdown(
        "¡Hola! Soy **AnaSofIA**. Pregúntame sobre tipos de cambio, conversión de monedas, "
        "tendencias cambiarias, criptomonedas o indicadores macroeconómicos de cualquier país."
    )

for mensaje in st.session_state.display_messages:
    with st.chat_message(mensaje["role"], avatar=avatar_para(mensaje["role"])):
        st.markdown(mensaje["content"])

        chart = mensaje.get("chart")
        if chart:
            tipo, df = chart
            if tipo == "line":
                st.line_chart(df, color="#b48fd9")
            elif tipo == "bar":
                st.bar_chart(df, color="#b48fd9")

        sources = mensaje.get("sources")
        if sources:
            chips = "".join(f'<span class="source-chip">Fuente: {s}</span> ' for s in sources)
            st.markdown(chips, unsafe_allow_html=True)

# Si se presiono un boton de pregunta rapida, procesarlo como si lo hubieran escrito
if st.session_state.pending_prompt:
    pregunta = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    enviar_pregunta(pregunta)
    st.rerun()

# Caja de texto para escribir libremente
texto_usuario = st.chat_input("Escribe tu pregunta sobre tipos de cambio, cripto, PIB...")
if texto_usuario:
    enviar_pregunta(texto_usuario)
    st.rerun()
