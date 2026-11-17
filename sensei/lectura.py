"""«Lectura de tus métricas» (vista Rendimiento): últimos 7 días frente a tus 4 semanas anteriores.

Cada tarjeta dice de qué dato sale; las propuestas son reglas fijas, no diagnósticos.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

CARRERA = ("run", "track", "treadmill")


def _media(vals):
    v = [x for x in vals if x is not None]
    return statistics.fmean(v) if v else None


def _rango(gd, campo, hoy, desde, hasta):
    return [g.get(campo) for g in gd if desde <= (hoy - date.fromisoformat(g["fecha"])).days <= hasta]


def leer(d: dict, hoy: date, peso: float | None) -> dict:
    gd = d.get("garmin_diario", [])
    acts = d.get("garmin_actividades", [])
    tarjetas, propuestas = [], []

    def comparar(campo, titulo, unidad, mejor_alto, dec=0):
        a7, ref = _media(_rango(gd, campo, hoy, 0, 6)), _media(_rango(gd, campo, hoy, 7, 34))
        if a7 is None:
            return None
        if ref is None:
            tarjetas.append({"titulo": titulo, "valor": f"{a7:.{dec}f} {unidad}", "linea1": "Sin referencia aún",
                             "linea2": "", "estado": ""})
            return None
        dif = a7 - ref
        pct = dif / ref * 100 if ref else 0
        malo = (dif < 0) if mejor_alto else (dif > 0)
        estado = "watch" if malo and abs(pct) >= 5 else "good"
        tarjetas.append({"titulo": titulo, "valor": f"{a7:.{dec}f} {unidad}".replace(".", ","),
                         "linea1": f"Referencia {ref:.{dec}f} {unidad} · {pct:+.0f} %".replace(".", ","),
                         "linea2": "", "estado": estado, "pct": pct})
        return pct

    p_vfc = comparar("vfc", "VFC nocturna · 7 días", "ms", True)
    estados = [g.get("vfc_estado") for g in gd if (hoy - date.fromisoformat(g["fecha"])).days <= 6 and g.get("vfc_estado")]
    if estados and tarjetas:
        tarjetas[-1]["linea2"] = "Garmin: " + {"BALANCED": "equilibrada", "UNBALANCED": "desequilibrada",
                                               "LOW": "baja", "POOR": "muy baja"}.get(estados[-1], estados[-1].lower())
    p_fc = comparar("fc_reposo", "FC en reposo · 7 días", "ppm", False, 1)
    if tarjetas and p_fc is not None:
        tarjetas[-1]["linea2"] = "Más alta que tu referencia = más fatiga"
    comparar("sueno_h", "Sueño · 7 días", "h", True, 1)
    disp7 = [x for x in _rango(gd, "disposicion", hoy, 0, 6) if x is not None]
    if disp7:
        bajos = sum(1 for x in disp7 if x < 50)
        ref = _media(_rango(gd, "disposicion", hoy, 7, 34))
        tarjetas.append({"titulo": "Disposición · 7 días", "valor": f"{_media(disp7):.0f} /100",
                         "linea1": f"Referencia {ref:.0f}" if ref else "Sin referencia",
                         "linea2": f"{bajos} día(s) por debajo de 50", "estado": "watch" if bajos >= 2 else "good"})
    else:
        bajos = 0

    def minutos(desde, hasta, filtro=None):
        return sum(a.get("duracion_min") or 0 for a in acts
                   if desde <= (hoy - date.fromisoformat(a["fecha"])).days <= hasta and (filtro is None or filtro(a)))
    m7 = minutos(0, 6)
    previa = minutos(7, 27) / 3
    rel = m7 / previa if previa else None
    tarjetas.append({"titulo": "Carga · 7 días", "valor": f"{m7:.0f} min", "linea1": f"Media semanal previa {previa:.0f} min",
                     "linea2": (f"Relación {rel:.2f} · " + ("semana más ligera que las 3 anteriores" if rel < 0.8 else
                                "semana más cargada" if rel > 1.3 else "en tu rango")).replace(".", ",") if rel else "",
                     "estado": "watch" if rel and rel > 1.3 else "good"})
    es_carrera = lambda a: any(k in str(a.get("tipo") or "") for k in CARRERA)  # noqa: E731
    es_fuerza = lambda a: "strength" in str(a.get("tipo") or "")  # noqa: E731
    n_c = sum(1 for a in acts if (hoy - date.fromisoformat(a["fecha"])).days <= 13 and es_carrera(a))
    n_f = sum(1 for a in acts if (hoy - date.fromisoformat(a["fecha"])).days <= 13 and es_fuerza(a))
    tarjetas.append({"titulo": "Carrera / fuerza · 14 días", "valor": f"{n_c} / {n_f}", "linea1": "Sesiones registradas",
                     "linea2": "Poca carrera para el 1500" if n_c < 4 else "Frecuencia de carrera suficiente",
                     "estado": "watch" if n_c < 4 else "good"})
    if peso:
        dias = [f for f in d.get("dias_nutricion_completos", []) if 0 <= (hoy - date.fromisoformat(f)).days <= 13]
        prot = [sum(c.get("prot") or 0 for c in d.get("comidas", []) if c["fecha"] == f) for f in dias]
        if prot:
            gkg = _media(prot) / peso
            tarjetas.append({"titulo": "Proteína · 14 días", "valor": f"{gkg:.1f} g/kg".replace(".", ","),
                             "linea1": f"{len(dias)} día(s) completos registrados", "linea2": "Referencia 1,4–2,0 g/kg",
                             "estado": "alert" if gkg < 1.4 else "good"})
            if gkg < 1.4:
                propuestas.append(("Nutrición", "Sube la proteína", f"Media de {gkg:.1f} g/kg en tus días completos; la "
                                   "referencia para fuerza y recuperación es 1,4–2,0 g/kg. Reparte 25–40 g en 4 comidas."))

    vigilar = (p_vfc is not None and p_vfc <= -7) or (p_fc is not None and p_fc >= 3) or bajos >= 2
    if vigilar:
        por = []
        if p_vfc is not None and p_vfc <= -7:
            por.append(f"VFC {p_vfc:+.0f} % frente a tus 4 semanas anteriores")
        if p_fc is not None and p_fc >= 3:
            por.append(f"FC en reposo {p_fc:+.0f} %")
        if bajos >= 2:
            por.append(f"{bajos} días con disposición por debajo de 50")
        propuestas.insert(0, ("Recuperación", "Mantén el plan, sin ir al fallo",
                              "Haz la sesión prevista, pero corta la serie si el ritmo o las repeticiones caen, y no añadas "
                              "volumen extra hasta que la VFC vuelva a tu media. Por qué: " + " · ".join(por) + "."))
    if n_c < 4:
        propuestas.append(("Entrenamiento", "Añade una sesión de umbral para el 1500",
                           f"Solo {n_c} carreras en 14 días. Una sesión semanal de umbral o intervalos largos "
                           "(p. ej. 4–5 × 1000 m con 2 min de pausa) es lo que más mueve el fondo."))
    if rel and rel > 1.3:
        propuestas.append(("Carga", "Frena la subida de carga",
                           f"Esta semana llevas {m7:.0f} min frente a {previa:.0f} de media: sube como mucho un 10 % por semana."))
    dias_datos = len({g["fecha"] for g in gd if (hoy - date.fromisoformat(g["fecha"])).days <= 34})
    return {"tarjetas": tarjetas, "propuestas": propuestas, "vigilar": vigilar, "dias": dias_datos}
