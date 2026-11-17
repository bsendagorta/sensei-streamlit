"""Baremo personal de Sensei.app (hombres, provisional), copiado tal cual de macos-app/UI.js.

- La marca mínima da 3 puntos y la máxima 6; entre medias, proporcional.
- Nota sobre 10 = puntos × 10 / 6 (3 puntos = 5/10), recortada a 0–6 puntos.
- Por debajo de 3 puntos: «<5», bajo mínimo.
"""
from __future__ import annotations

# id propio → (id de Sensei, mínimo = 3 pt, máximo = 6 pt)
TESTS = {
    "banca": {"sensei": "bench", "min": 28, "max": 40},
    "dominadas": {"sensei": "pull", "min": 15, "max": 25},
    "cuerda": {"sensei": "rope", "min": 12, "max": 5},
    "flexibilidad": {"sensei": "flex", "min": 17, "max": 38},
    "60m": {"sensei": "speed", "min": 10, "max": 7.5},
    "1500m": {"sensei": "endurance", "min": 371, "max": 277},
}
DE_SENSEI = {v["sensei"]: k for k, v in TESTS.items()}


def baremo(prueba: str, ajustes: dict | None = None) -> dict:
    """Mínimo y máximo de la prueba, con los cambios que hayas hecho en Ajustes."""
    b = dict(TESTS[prueba])
    propio = ((ajustes or {}).get("baremo_sensei") or {}).get(prueba) or {}
    for k in ("min", "max"):
        if propio.get(k) is not None:
            b[k] = float(propio[k])
    return b


def puntos(prueba: str, valor, ajustes: dict | None = None):
    if valor is None:
        return None
    t = baremo(prueba, ajustes)
    return (3 * (valor + t["max"]) - 6 * t["min"]) / (t["max"] - t["min"])


def nota10(prueba: str, valor, ajustes: dict | None = None):
    p = puntos(prueba, valor, ajustes)
    return None if p is None else min(6.0, max(0.0, p)) * 10 / 6


def texto_control(prueba: str, valor, ajustes: dict | None = None) -> str:
    """Como en la lista de controles de Sensei: «4,8 pt · 8/10 equivalente» o «Bajo mínimo»."""
    p = puntos(prueba, valor, ajustes)
    if p is None:
        return ""
    if p < 3:
        return "Bajo mínimo"
    return f"{num(min(6, p))} pt · {num(nota10(prueba, valor, ajustes))}/10 equivalente"


def calificar(prueba: str, rango: tuple[float, float] | None, ajustes: dict | None = None) -> dict:
    """Igual que grading() de Sensei para un rango de marca previsto."""
    if not rango:
        return {"tipo": "desconocido", "etiqueta": "Falta una marca", "detalle": "Sin control ni referencia",
                "rango": None}
    pts = sorted([puntos(prueba, rango[0], ajustes), puntos(prueba, rango[1], ajustes)])
    if pts[1] < 3:
        return {"tipo": "bajo", "etiqueta": "<5", "detalle": "Por debajo del mínimo de 3 puntos",
                "rango": (0, 5), "puntos": pts}
    n = [min(6, v) * 10 / 6 for v in pts]
    return {"tipo": "nota", "etiqueta": (n[0] + n[1]) / 2, "rango": tuple(n), "puntos": pts,
            "detalle": "Alcanza el extremo de 6 puntos" if pts[0] >= 6 else "Equivalencia proporcional sobre 10"}


def num(x, dec: int = 1) -> str:
    """Formato español como Sensei: 7,9 · 8 · 4,2."""
    if x is None:
        return "—"
    r = round(float(x), dec)
    s = f"{r:.{dec}f}".rstrip("0").rstrip(".") if dec else f"{r:.0f}"
    return s.replace(".", ",")
