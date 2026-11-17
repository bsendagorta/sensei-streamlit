"""Definición de las pruebas y conversión de marcas. Sin dependencias de Streamlit."""
from __future__ import annotations

import re

PRUEBAS: dict[str, dict] = {  # mismo orden, nombres y protocolos que Sensei.app
    "banca": {"nombre": "Press de banca", "protocolo": "30 segundos · 40 kg", "unidad": "rep", "mejor": "mayor",
              "ayuda": "Repeticiones, p. ej. 35"},
    "dominadas": {"nombre": "Dominadas", "protocolo": "Repeticiones válidas en 30 segundos", "unidad": "rep",
                  "mejor": "mayor", "ayuda": "Repeticiones, p. ej. 21"},
    "cuerda": {"nombre": "Trepa de cuerda", "protocolo": "6 metros de altura", "unidad": "s", "mejor": "menor",
               "ayuda": "Segundos, p. ej. 5,9"},
    "flexibilidad": {"nombre": "Flexibilidad", "protocolo": "Protocolo de la convocatoria", "unidad": "cm",
                     "mejor": "mayor", "ayuda": "Centímetros, p. ej. 26"},
    "60m": {"nombre": "Velocidad 60 m", "protocolo": "60 metros medidos · salida de examen", "unidad": "s",
            "mejor": "menor", "ayuda": "Segundos, p. ej. 7,85"},
    "1500m": {"nombre": "Fondo 1500 m", "protocolo": "1500 metros continuos", "unidad": "min:s", "mejor": "menor",
              "ayuda": "min:s, p. ej. 5:34"},
}

ZONAS_MOLESTIA = [
    "Rodilla izq.", "Rodilla dcha.", "Tobillo / Aquiles izq.", "Tobillo / Aquiles dcho.",
    "Gemelo / sóleo", "Isquiotibiales", "Cuádriceps", "Cadera / ingle", "Lumbar",
    "Hombro izq.", "Hombro dcho.", "Codo", "Muñeca / mano", "Cuello", "Otra",
]

TIPOS_SESION = ["Fuerza", "Carrera continua", "Series / intervalos", "Velocidad", "Cuerda / trepa",
                "Movilidad / flexibilidad", "Circuito", "Otro"]


def parse_resultado(prueba: str, texto) -> float:
    """Convierte lo que escribe el usuario en un número (reps, segundos o cm).

    1500 m admite «5:12» (min:s) o segundos («312»). La coma vale como decimal.
    Lanza ValueError con un mensaje en español si no se entiende.
    """
    if prueba not in PRUEBAS:
        raise ValueError(f"Prueba desconocida: {prueba}")
    if texto is None:
        raise ValueError("Escribe un resultado.")
    s = str(texto).strip().replace(",", ".")
    if not s:
        raise ValueError("Escribe un resultado.")
    if ":" in s:
        m = re.fullmatch(r"(\d+):([0-5]?\d(?:\.\d+)?)", s)
        if not m:
            raise ValueError("Formato min:s no válido (p. ej. 5:12).")
        valor = int(m.group(1)) * 60 + float(m.group(2))
    else:
        try:
            valor = float(s)
        except ValueError:
            raise ValueError(f"No entiendo «{texto}». {PRUEBAS[prueba]['ayuda']}.") from None
    if valor <= 0 and prueba != "flexibilidad":
        raise ValueError("El resultado debe ser mayor que 0.")
    if PRUEBAS[prueba]["unidad"] == "rep" and valor != int(valor):
        raise ValueError("Las repeticiones deben ser un número entero.")
    return float(valor)


def formatear(prueba: str, valor) -> str:
    if valor is None:
        return "—"
    u = PRUEBAS[prueba]["unidad"]
    if u == "min:s":
        m, s = divmod(round(float(valor), 1), 60)
        seg = f"{int(s):02d}" if s == int(s) else f"{s:04.1f}".replace(".", ",")
        return f"{int(m)}:{seg}"
    if u == "rep":
        return f"{int(round(valor))} reps"
    if u == "s":
        return f"{round(valor, 2):g} s".replace(".", ",")
    return f"{round(valor, 1):g} cm".replace(".", ",")


def es_mejor(prueba: str, a: float, b: float) -> bool:
    """¿a es mejor marca que b?"""
    return a > b if PRUEBAS[prueba]["mejor"] == "mayor" else a < b


def formatear_marca(prueba: str, valor, con_unidad: bool = True) -> str:
    """Como mark() de Sensei: 1500 en m:ss sin decimales, segundos con 1 decimal, reps enteras."""
    if valor is None:
        return "—"
    u = PRUEBAS[prueba]["unidad"]
    if u == "min:s":
        m, s = divmod(round(float(valor)), 60)
        return f"{m}:{s:02d}" + (" min:s" if con_unidad else "")
    if u == "rep":
        return f"{round(valor)}" + (" reps" if con_unidad else "")
    txt = f"{round(float(valor), 1):g}".replace(".", ",")
    return txt + ((" s" if u == "s" else " cm") if con_unidad else "")


def formatear_rango(prueba: str, a, b) -> str:
    lo, hi = sorted([a, b])
    return f"{formatear_marca(prueba, lo, False)}–{formatear_marca(prueba, hi)}"
