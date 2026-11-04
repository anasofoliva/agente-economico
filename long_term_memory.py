##############################
# Agente Economico De IA     #
# Memoria a largo plazo      #
##############################
#
# A diferencia de BasicMemory (que solo guarda los ultimos mensajes mientras
# la pagina esta abierta), esta memoria se guarda en un archivo JSON, asi que
# sobrevive aunque recargues la pagina, cierres el navegador o reinicies la app.
#
# Guarda dos cosas:
#   1. "hechos": datos duraderos del usuario (nombre, pais, moneda que usa...).
#      Se le pasan al modelo en el SYSTEM_PROMPT en cada conversacion.
#   2. "conversaciones": todas las conversaciones anteriores, mensaje por
#      mensaje, para que el agente pueda buscar en ellas con una herramienta.

import json
import os
import re
import threading
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_HORARIA = ZoneInfo("America/Guatemala")

# Palabras muy comunes que no sirven para buscar
PALABRAS_VACIAS = {
    "que", "cual", "cuales", "como", "cuando", "donde", "quien", "para", "por",
    "con", "sin", "los", "las", "una", "uno", "unos", "unas", "del", "al", "el",
    "la", "lo", "le", "les", "mi", "me", "te", "tu", "su", "sus", "es", "son",
    "fue", "era", "esta", "este", "eso", "esa", "ese", "y", "o", "de", "en",
    "a", "se", "si", "no", "mas", "muy", "ya", "hay", "dijiste", "dije",
    "hablamos", "pregunte", "preguntaste", "vez", "antes", "anterior",
}


def _normalizar(texto):
    """Minusculas y sin tildes, para que 'Inflación' encuentre 'inflacion'."""
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _recortar(texto, limite=300):
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[:limite].rstrip() + "..."


class LongTermMemory:

    def __init__(self, ruta_archivo="memoria_largo_plazo.json"):
        self.ruta = ruta_archivo
        self._lock = threading.Lock()
        self.data = self._cargar()

    # ------------------------------------------------------------------
    # Lectura y escritura del archivo
    # ------------------------------------------------------------------
    def _cargar(self):
        if os.path.isfile(self.ruta):
            try:
                with open(self.ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("hechos", [])
                data.setdefault("conversaciones", [])
                return data
            except Exception as e:
                print(f"No se pudo leer la memoria a largo plazo ({self.ruta}): {e}")
        return {"hechos": [], "conversaciones": []}

    def _guardar(self):
        # Se escribe primero a un archivo temporal para no corromper la memoria
        # si la app se cierra a medio guardar.
        temporal = self.ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(temporal, self.ruta)

    @staticmethod
    def _ahora():
        return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------
    # 1) Hechos sobre el usuario
    # ------------------------------------------------------------------
    def guardar_dato(self, dato: str):
        print(f"Herramienta guardar_dato_usuario llamada con dato: {dato}")

        dato = (dato or "").strip()
        if not dato:
            return "Error: Se requiere el dato que se desea recordar."

        with self._lock:
            for hecho in self.data["hechos"]:
                if _normalizar(hecho["dato"]) == _normalizar(dato):
                    return {"guardado": False, "mensaje": "Ese dato ya estaba guardado."}

            self.data["hechos"].append({"dato": dato, "fecha": self._ahora()})
            self._guardar()

        return {"guardado": True, "dato": dato}

    def olvidar_dato(self, dato: str):
        print(f"Herramienta olvidar_dato_usuario llamada con dato: {dato}")

        buscado = _normalizar(dato).strip()
        if not buscado:
            return "Error: Se requiere el dato que se desea olvidar."

        with self._lock:
            antes = len(self.data["hechos"])
            self.data["hechos"] = [
                h for h in self.data["hechos"] if buscado not in _normalizar(h["dato"])
            ]
            borrados = antes - len(self.data["hechos"])
            if borrados:
                self._guardar()

        if not borrados:
            return {"borrados": 0, "mensaje": f"No encontre ningun dato guardado sobre '{dato}'."}
        return {"borrados": borrados}

    def hechos(self):
        return [h["dato"] for h in self.data["hechos"]]

    # ------------------------------------------------------------------
    # 2) Conversaciones anteriores
    # ------------------------------------------------------------------
    def agregar_mensaje(self, conversacion_id: str, role: str, content: str):
        """Guarda un mensaje en la conversacion indicada (la crea si no existe)."""
        with self._lock:
            conversacion = next(
                (c for c in self.data["conversaciones"] if c["id"] == conversacion_id), None
            )
            if conversacion is None:
                conversacion = {"id": conversacion_id, "inicio": self._ahora(), "mensajes": []}
                self.data["conversaciones"].append(conversacion)

            conversacion["mensajes"].append(
                {"role": role, "content": content, "fecha": self._ahora()}
            )
            self._guardar()

    def buscar_conversaciones(self, consulta: str, excluir_id: str = None, max_resultados: int = 5):
        print(f"Herramienta buscar_conversaciones_anteriores llamada con consulta: {consulta}")

        palabras = [
            p for p in re.findall(r"\w+", _normalizar(consulta))
            if len(p) > 2 and p not in PALABRAS_VACIAS
        ]
        if not palabras:
            return "Error: Se requiere una palabra clave para buscar (ej. bitcoin, inflacion, euro)."

        encontrados = []
        for conversacion in self.data["conversaciones"]:
            if conversacion["id"] == excluir_id:
                continue

            mensajes = conversacion["mensajes"]
            for i, mensaje in enumerate(mensajes):
                if mensaje["role"] != "user":
                    continue

                respuesta = ""
                if i + 1 < len(mensajes) and mensajes[i + 1]["role"] == "assistant":
                    respuesta = mensajes[i + 1]["content"]

                texto = _normalizar(mensaje["content"] + " " + respuesta)
                puntaje = sum(1 for p in palabras if p in texto)
                if puntaje:
                    encontrados.append(
                        {
                            "puntaje": puntaje,
                            "fecha": mensaje.get("fecha", conversacion["inicio"]),
                            "usuario_pregunto": _recortar(mensaje["content"]),
                            "agente_respondio": _recortar(respuesta),
                        }
                    )

        if not encontrados:
            return {
                "resultados": [],
                "mensaje": f"No encontre conversaciones anteriores sobre: {consulta}",
            }

        # Primero los que mas coinciden; si empatan, los mas recientes
        encontrados.sort(key=lambda r: (r["puntaje"], r["fecha"]), reverse=True)
        for r in encontrados:
            del r["puntaje"]

        return {"consulta": consulta, "resultados": encontrados[:max_resultados]}

    def resumen_conversaciones(self, excluir_id: str = None, cantidad: int = 5):
        """Fecha y primera pregunta de las ultimas conversaciones (para el prompt)."""
        anteriores = [
            c for c in self.data["conversaciones"]
            if c["id"] != excluir_id and c["mensajes"]
        ]
        resumen = []
        for c in anteriores[-cantidad:]:
            primera = next((m["content"] for m in c["mensajes"] if m["role"] == "user"), "")
            resumen.append(f"{c['inicio']}: {_recortar(primera, 120)}")
        return resumen

    def total_conversaciones(self, excluir_id: str = None):
        return sum(
            1 for c in self.data["conversaciones"] if c["id"] != excluir_id and c["mensajes"]
        )

    # ------------------------------------------------------------------
    # Bloque de texto que se agrega al SYSTEM_PROMPT
    # ------------------------------------------------------------------
    def contexto_para_prompt(self, excluir_id: str = None):
        hechos = self.hechos()
        resumen = self.resumen_conversaciones(excluir_id=excluir_id)

        partes = ["\nMEMORIA A LARGO PLAZO (de conversaciones anteriores):"]

        if hechos:
            partes.append("Datos que recuerdas del usuario:")
            partes.extend(f"- {h}" for h in hechos)
        else:
            partes.append("Todavia no tienes datos guardados del usuario.")

        if resumen:
            partes.append(
                "Ultimas conversaciones anteriores (fecha: primera pregunta). "
                "Para ver detalles usa buscar_conversaciones_anteriores:"
            )
            partes.extend(f"- {r}" for r in resumen)
        else:
            partes.append("No hay conversaciones anteriores guardadas.")

        return "\n".join(partes)

    def borrar_todo(self):
        with self._lock:
            self.data = {"hechos": [], "conversaciones": []}
            self._guardar()


##################################################################
# Version con Supabase                                           #
##################################################################
#
# Hace exactamente lo mismo que LongTermMemory, pero en vez de guardar en
# memoria_largo_plazo.json guarda en dos tablas de Supabase (hechos y
# mensajes). Asi la memoria NO se pierde aunque Streamlit Cloud reinicie
# la app. Las tablas se crean con supabase_setup.sql.

class SupabaseLongTermMemory(LongTermMemory):

    # Cuantos mensajes recientes se leen de la base de datos para buscar
    MAX_MENSAJES = 1000

    def __init__(self, url: str, key: str):
        from supabase import create_client  # solo se necesita en este modo

        self.db = create_client(url, key)
        self._lock = threading.Lock()
        self.data = self._cargar()

    # ------------------------------------------------------------------
    # Leer todo de Supabase y armarlo con la misma forma que el JSON
    # ------------------------------------------------------------------
    def _cargar(self):
        hechos = (
            self.db.table("hechos").select("id, dato, fecha").order("id").execute().data
        )
        # Los mas recientes primero (por el limite) y luego se voltean
        mensajes = (
            self.db.table("mensajes")
            .select("id, conversacion_id, role, content, fecha")
            .order("id", desc=True)
            .limit(self.MAX_MENSAJES)
            .execute()
            .data
        )
        mensajes.reverse()

        conversaciones = {}
        for m in mensajes:
            conversacion = conversaciones.setdefault(
                m["conversacion_id"],
                {"id": m["conversacion_id"], "inicio": m["fecha"], "mensajes": []},
            )
            conversacion["mensajes"].append(
                {"role": m["role"], "content": m["content"], "fecha": m["fecha"]}
            )

        return {"hechos": hechos, "conversaciones": list(conversaciones.values())}

    def _guardar(self):
        # En Supabase cada cambio se guarda en el momento, no hay archivo
        pass

    def _recargar(self):
        try:
            self.data = self._cargar()
        except Exception as e:
            print(f"No se pudo leer la memoria de Supabase: {e}")

    # ------------------------------------------------------------------
    # Hechos
    # ------------------------------------------------------------------
    def guardar_dato(self, dato: str):
        print(f"Herramienta guardar_dato_usuario llamada con dato: {dato}")

        dato = (dato or "").strip()
        if not dato:
            return "Error: Se requiere el dato que se desea recordar."

        with self._lock:
            self._recargar()
            for hecho in self.data["hechos"]:
                if _normalizar(hecho["dato"]) == _normalizar(dato):
                    return {"guardado": False, "mensaje": "Ese dato ya estaba guardado."}

            try:
                fila = (
                    self.db.table("hechos")
                    .insert({"dato": dato, "fecha": self._ahora()})
                    .execute()
                    .data
                )
                self.data["hechos"].extend(fila)
            except Exception as e:
                print(f"Error al guardar dato en Supabase: {e}")
                return "ERROR: No se pudo guardar el dato en la memoria."

        return {"guardado": True, "dato": dato}

    def olvidar_dato(self, dato: str):
        print(f"Herramienta olvidar_dato_usuario llamada con dato: {dato}")

        buscado = _normalizar(dato).strip()
        if not buscado:
            return "Error: Se requiere el dato que se desea olvidar."

        with self._lock:
            self._recargar()
            ids = [h["id"] for h in self.data["hechos"] if buscado in _normalizar(h["dato"])]
            if not ids:
                return {"borrados": 0, "mensaje": f"No encontre ningun dato guardado sobre '{dato}'."}

            try:
                self.db.table("hechos").delete().in_("id", ids).execute()
                self.data["hechos"] = [h for h in self.data["hechos"] if h["id"] not in ids]
            except Exception as e:
                print(f"Error al borrar dato en Supabase: {e}")
                return "ERROR: No se pudo borrar el dato de la memoria."

        return {"borrados": len(ids)}

    # ------------------------------------------------------------------
    # Conversaciones
    # ------------------------------------------------------------------
    def agregar_mensaje(self, conversacion_id: str, role: str, content: str):
        fecha = self._ahora()
        self.db.table("mensajes").insert(
            {
                "conversacion_id": conversacion_id,
                "role": role,
                "content": content,
                "fecha": fecha,
            }
        ).execute()

        with self._lock:
            conversacion = next(
                (c for c in self.data["conversaciones"] if c["id"] == conversacion_id), None
            )
            if conversacion is None:
                conversacion = {"id": conversacion_id, "inicio": fecha, "mensajes": []}
                self.data["conversaciones"].append(conversacion)
            conversacion["mensajes"].append({"role": role, "content": content, "fecha": fecha})

    def buscar_conversaciones(self, consulta: str, excluir_id: str = None, max_resultados: int = 5):
        self._recargar()
        return super().buscar_conversaciones(consulta, excluir_id, max_resultados)

    def contexto_para_prompt(self, excluir_id: str = None):
        # Se lee de nuevo de Supabase en cada pregunta, por si hubo cambios
        self._recargar()
        return super().contexto_para_prompt(excluir_id)

    def borrar_todo(self):
        with self._lock:
            # Supabase pide un filtro para borrar; id >= 0 incluye todas las filas
            self.db.table("hechos").delete().gte("id", 0).execute()
            self.db.table("mensajes").delete().gte("id", 0).execute()
            self.data = {"hechos": [], "conversaciones": []}
