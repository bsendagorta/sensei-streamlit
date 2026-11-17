"""Previsión de marca y puntos por prueba. Solo usa marcas reales; no extrapola tendencias.

Reglas (las mismas que Sensei para Mac):
- Con controles de protocolo completo: rango de los últimos 1–3 controles; con uno solo, ±5 %.
- Sin controles completos: igual pero con las mediciones de entrenamiento (protocolo
  incompleto), marcadas como «referencia» y con aviso.
- Sin nada: sin previsión. Nunca se inventa una mejora.
"""
from __future__ import annotations

from .modelo import PRUEBAS


def puntos(prueba: str, valor, baremo: list[dict] | None):
    """Puntos según un baremo escalonado [{marca, puntos}, ...].

    Devuelve None si no hay baremo o valor. Devuelve 0 si no se llega a la primera marca.
    """
    if valor is None or not baremo:
        return None
    filas = [f for f in baremo if f.get("marca") is not None and f.get("puntos") is not None]
    if not filas:
        return None
    mayor = PRUEBAS[prueba]["mejor"] == "mayor"
    alcanzados = [float(f["puntos"]) for f in filas
                  if (valor >= float(f["marca"]) if mayor else valor <= float(f["marca"]))]
    return max(alcanzados) if alcanzados else 0.0


def prevision(prueba: str, controles: list[dict]) -> dict:
    """Previsión de una prueba a partir de la lista de controles del usuario."""
    propios = sorted((c for c in controles if c.get("prueba") == prueba and c.get("resultado") is not None),
                     key=lambda c: c["fecha"])
    completos = [c for c in propios if c.get("protocolo_completo")]
    usados, fuente = (completos, "control") if completos else (propios, "referencia")
    if not usados:
        return {"prueba": prueba, "fuente": None, "n": 0, "central": None, "rango": None,
                "fecha": None, "aviso": "Sin marcas registradas: no hay previsión."}
    ultimos = usados[-3:]
    valores = [float(c["resultado"]) for c in ultimos]
    central = valores[-1]
    if len(valores) == 1:
        rango = (central * 0.95, central * 1.05)
    else:
        rango = (min(valores), max(valores))
    aviso = None
    if fuente == "referencia":
        aviso = ("Basada en mediciones de entrenamiento sin protocolo completo: orientativa. "
                 "Un control real la sustituye.")
    elif len(valores) == 1:
        aviso = "Un solo control: rango ±5 %."
    return {"prueba": prueba, "fuente": fuente, "n": len(valores), "central": central,
            "rango": rango, "fecha": ultimos[-1]["fecha"], "aviso": aviso}


def puntos_prevision(prev: dict, baremo: list[dict] | None):
    """(puntos central, peor, mejor) para una previsión. None si no se puede calcular."""
    if prev.get("central") is None or not baremo:
        return None
    p = prev["prueba"]
    lo, hi = prev["rango"]
    candidatos = [puntos(p, lo, baremo), puntos(p, hi, baremo)]
    return {"central": puntos(p, prev["central"], baremo),
            "peor": min(candidatos), "mejor": max(candidatos)}
