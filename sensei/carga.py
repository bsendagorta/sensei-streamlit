"""Carga de entrenamiento: series diarias, ratio agudo:crónico (ACWR) y líneas base."""
from __future__ import annotations

import statistics
from datetime import date, timedelta


def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def carga_diaria_srpe(sesiones: list[dict]) -> dict[date, float]:
    """sRPE = duración (min) × RPE (1–10). Sesiones sin RPE o sin duración no cuentan."""
    out: dict[date, float] = {}
    for s in sesiones:
        if s.get("duracion_min") is None or s.get("rpe") is None:
            continue
        f = _d(s["fecha"])
        out[f] = out.get(f, 0.0) + float(s["duracion_min"]) * float(s["rpe"])
    return out


def carga_diaria_garmin(actividades: list[dict]) -> dict[date, float]:
    """Carga de entrenamiento que calcula Garmin para cada actividad (activityTrainingLoad)."""
    out: dict[date, float] = {}
    for a in actividades:
        if a.get("carga") is None:
            continue
        f = _d(a["fecha"])
        out[f] = out.get(f, 0.0) + float(a["carga"])
    return out


def acwr(carga: dict[date, float], hoy: date, agudo: int = 7, cronico: int = 28) -> dict:
    """Ratio agudo:crónico con medias móviles acopladas (días sin entreno = 0).

    Exige al menos `cronico` días de historial desde el primer registro; si no, devuelve
    ratio None (con pocos datos el cociente engaña).
    """
    if not carga:
        return {"ratio": None, "agudo": None, "cronico": None, "motivo": "Sin datos de carga."}
    primero = min(carga)
    if (hoy - primero).days + 1 < cronico:
        return {"ratio": None, "agudo": None, "cronico": None,
                "motivo": f"Hacen falta {cronico} días de historial (hay {(hoy - primero).days + 1})."}

    def media(n):
        return sum(carga.get(hoy - timedelta(days=i), 0.0) for i in range(n)) / n

    a, c = media(agudo), media(cronico)
    if c <= 0:
        return {"ratio": None, "agudo": a, "cronico": c, "motivo": "Carga crónica 0."}
    return {"ratio": a / c, "agudo": a, "cronico": c, "motivo": None}


def linea_base(serie: dict[date, float], hoy: date, dias: int = 28, minimo: int = 7) -> dict | None:
    """Media y desviación de los `dias` anteriores a hoy (sin incluir hoy)."""
    vals = [v for f, v in serie.items() if v is not None and 1 <= (hoy - f).days <= dias]
    if len(vals) < minimo:
        return None
    return {"media": statistics.fmean(vals), "sd": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "n": len(vals)}
