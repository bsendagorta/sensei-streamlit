"""Definición de las pruebas y conversión de marcas. Sin dependencias de Streamlit."""
from __future__ import annotations

import re

PRUEBAS: dict[str, dict] = {
    "dominadas": {"nombre": "Dominadas (30 s)", "unidad": "rep", "mejor": "mayor", "ayuda": "Repeticiones, p. ej. 14"},
    "banca": {"nombre": "Press de banca 40 kg (30 s)", "unidad": "rep", "mejor": "mayor", "ayuda": "Repeticiones, p. ej. 28"},
    "60m": {"nombre": "Velocidad 60 m", "unidad": "s", "mejor": "menor", "ayuda": "Segundos, p. ej. 7,85"},
    "1500m": {"nombre": "Fondo 1500 m", "unidad": "min:s", "mejor": "menor", "ayuda": "min:s, p. ej. 5:12"},
    "cuerda": {"nombre": "Trepa de cuerda 6 m", "unidad": "s", "mejor": "menor", "ayuda": "Segundos, p. ej. 6,4"},
    "flexibilidad": {"nombre": "Flexibilidad", "unidad": "cm", "mejor": "mayor", "ayuda": "Centímetros, p. ej. 32"},
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
        return f"{int(round(valor))} rep"
    if u == "s":
        return f"{valor:.2f} s".replace(".", ",")
    return f"{valor:g} cm".replace(".", ",")


def es_mejor(prueba: str, a: float, b: float) -> bool:
    """¿a es mejor marca que b?"""
    return a > b if PRUEBAS[prueba]["mejor"] == "mayor" else a < b
