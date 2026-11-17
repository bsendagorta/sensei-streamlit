"""Lo que Sensei aprende de ti. Se reentrena con todos tus datos cada vez que abres la app.

Principios:
- Modelos pequeños y explicables (regresión ridge, tendencias lineales, medias condicionadas),
  porque con unos cientos de días un modelo grande solo memoriza ruido.
- Cada modelo se valida contra una referencia simple con validación temporal (entrena con el
  pasado, predice el día siguiente). Si no la mejora, se dice y no se usa.
- Una «mejora» solo se da por demostrada si el intervalo de confianza del 95 % excluye el cero.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

from .carga import _d, carga_diaria_garmin, carga_diaria_srpe, linea_base
from .modelo import PRUEBAS
from .prevision import prevision, puntos

T95 = {3: 12.71, 4: 4.30, 5: 3.18, 6: 2.78, 7: 2.57, 8: 2.45, 9: 2.36, 10: 2.31, 12: 2.23, 15: 2.16, 20: 2.10, 30: 2.05}


def _t95(n):
    for k in sorted(T95):
        if n <= k:
            return T95[k]
    return 1.98


def tendencia(xs: list[float], ys: list[float]) -> dict | None:
    """Pendiente por mínimos cuadrados con IC 95 %. None si hay menos de 3 puntos."""
    n = len(xs)
    if n < 3:
        return None
    x, y = np.asarray(xs, float), np.asarray(ys, float)
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    if sxx == 0:
        return None
    b = ((x - xm) * (y - ym)).sum() / sxx
    resid = y - (ym + b * (x - xm))
    se = math.sqrt((resid ** 2).sum() / (n - 2) / sxx) if n > 2 else float("inf")
    t = _t95(n)
    return {"pendiente": b, "ic": (b - t * se, b + t * se), "n": n,
            "significativa": (b - t * se) > 0 or (b + t * se) < 0}


# ---------------------------------------------------------------- dataset diario

def _carga(datos):
    g = carga_diaria_garmin(datos.get("garmin_actividades", []))
    return (g, "Garmin") if len(g) >= 10 else (carga_diaria_srpe(datos.get("sesiones", [])), "sRPE")


def dataset_diario(datos: dict) -> list[dict]:
    """Una fila por día con recuperación (relativa a tu línea base), carga y lo que anotaste."""
    gd = {_d(g["fecha"]): g for g in datos.get("garmin_diario", [])}
    ch = {_d(c["fecha"]): c for c in datos.get("checkins", [])}
    carga, _ = _carga(datos)
    if not gd and not ch:
        return []
    series = {k: {f: g.get(k) for f, g in gd.items() if g.get(k) is not None}
              for k in ("fc_reposo", "vfc", "sueno_h", "body_battery_max", "estres_medio")}
    filas = []
    for f in sorted(set(gd) | set(ch)):
        g, c = gd.get(f, {}), ch.get(f, {})
        fila = {"fecha": f}
        for k in ("fc_reposo", "vfc"):
            v = g.get(k)
            b = linea_base(series[k], f)
            fila[f"{k}_dif"] = (v - b["media"]) if v is not None and b else None
        fila["sueno_h"] = g.get("sueno_h") if g.get("sueno_h") is not None else c.get("sueno_h")
        fila["body_battery"] = g.get("body_battery_max")
        fila["estres"] = g.get("estres_medio")
        fila["carga_ayer"] = carga.get(f - timedelta(days=1), 0.0) if carga else None
        fila["carga_7d"] = (sum(carga.get(f - timedelta(days=i), 0.0) for i in range(1, 8)) / 7) if carga else None
        fila["sensacion"] = c.get("sensacion")
        mol = [m.get("intensidad") or 0 for m in c.get("molestias", [])]
        fila["dolor"] = max(mol, default=0) if c else None
        filas.append(fila)
    return filas


VARIABLES = {
    "vfc_dif": "VFC respecto a tu media",
    "fc_reposo_dif": "Pulso en reposo respecto a tu media",
    "sueno_h": "Horas de sueño",
    "body_battery": "Body Battery",
    "estres": "Estrés de Garmin",
    "carga_ayer": "Carga de ayer",
    "carga_7d": "Carga media de 7 días",
}


def _ridge(X, y, lam=2.0):
    Xb = np.column_stack([np.ones(len(X)), X])
    reg = lam * np.eye(Xb.shape[1])
    reg[0, 0] = 0
    return np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)


def modelo_sensacion(datos: dict, minimo: int = 20) -> dict:
    """Aprende qué variables de Garmin predicen cómo te sientes (check-in 1–10).

    Valida con origen móvil: para cada día desde el 15.º entrena solo con días anteriores.
    Referencia: la media de tus sensaciones anteriores."""
    filas = [f for f in dataset_diario(datos) if f["sensacion"] is not None]
    # Variables con suficiente cobertura
    usables = [k for k in VARIABLES if sum(f[k] is not None for f in filas) >= max(minimo, 0.7 * len(filas))]
    filas = [f for f in filas if all(f[k] is not None for k in usables)]
    if len(filas) < minimo or not usables:
        return {"ok": False, "n": len(filas),
                "motivo": f"Necesito {minimo} días con check-in y datos de Garmin (hay {len(filas)})."}
    X = np.array([[f[k] for k in usables] for f in filas], float)
    y = np.array([f["sensacion"] for f in filas], float)
    err_m, err_b = [], []
    inicio = max(14, len(filas) // 3)
    for i in range(inicio, len(filas)):
        mu, sd = X[:i].mean(0), X[:i].std(0) + 1e-9
        w = _ridge((X[:i] - mu) / sd, y[:i])
        pred = w[0] + ((X[i] - mu) / sd) @ w[1:]
        err_m.append(abs(pred - y[i]))
        err_b.append(abs(y[:i].mean() - y[i]))
    mae, mae_b = float(np.mean(err_m)), float(np.mean(err_b))
    mu, sd = X.mean(0), X.std(0) + 1e-9
    w = _ridge((X - mu) / sd, y)
    efectos = sorted(({"variable": k, "nombre": VARIABLES[k], "efecto": float(w[1 + j])}
                      for j, k in enumerate(usables)), key=lambda e: -abs(e["efecto"]))
    util = mae < mae_b * 0.95
    return {"ok": True, "util": util, "n": len(filas), "mae": mae, "mae_ref": mae_b,
            "mejora_pct": (1 - mae / mae_b) * 100 if mae_b else 0.0, "efectos": efectos,
            "usables": usables, "pesos": w, "mu": mu, "sd": sd}


def predecir_sensacion(modelo: dict, datos: dict, dia: date):
    if not modelo.get("ok") or not modelo.get("util"):
        return None
    fila = next((f for f in dataset_diario(datos) if f["fecha"] == dia), None)
    if not fila or any(fila[k] is None for k in modelo["usables"]):
        return None
    x = (np.array([fila[k] for k in modelo["usables"]], float) - modelo["mu"]) / modelo["sd"]
    return float(np.clip(modelo["pesos"][0] + x @ modelo["pesos"][1:], 1, 10))


# ---------------------------------------------------------------- recuperación personal

def recuperacion_personal(datos: dict, minimo_dias_duros: int = 4) -> dict:
    """Cómo responde tu cuerpo los 3 días siguientes a tus sesiones más duras (top 20 % de carga)."""
    carga, fuente = _carga(datos)
    filas = {f["fecha"]: f for f in dataset_diario(datos)}
    valores = [v for v in carga.values() if v > 0]
    if len(valores) < 15:
        return {"ok": False, "motivo": "Necesito al menos 15 días con carga registrada."}
    umbral = float(np.percentile(valores, 80))
    duros = [f for f, v in carga.items() if v >= umbral]
    if len(duros) < minimo_dias_duros:
        return {"ok": False, "motivo": f"Necesito {minimo_dias_duros} sesiones duras (hay {len(duros)})."}
    resp = []
    for k in (1, 2, 3):
        rhr = [filas[f + timedelta(days=k)]["fc_reposo_dif"] for f in duros
               if f + timedelta(days=k) in filas and filas[f + timedelta(days=k)]["fc_reposo_dif"] is not None]
        vfc = [filas[f + timedelta(days=k)]["vfc_dif"] for f in duros
               if f + timedelta(days=k) in filas and filas[f + timedelta(days=k)]["vfc_dif"] is not None]
        resp.append({"dia": k, "fc_reposo": float(np.mean(rhr)) if rhr else None, "n_fc": len(rhr),
                     "vfc": float(np.mean(vfc)) if vfc else None, "n_vfc": len(vfc)})
    normal = next((r["dia"] for r in resp
                   if (r["fc_reposo"] is None or r["fc_reposo"] < 1.5) and (r["vfc"] is None or r["vfc"] > -3)), None)
    return {"ok": True, "fuente": fuente, "umbral": umbral, "n_duros": len(duros), "respuesta": resp,
            "dias_hasta_normal": normal}


# ---------------------------------------------------------------- carrera

def eficiencia_carrera(datos: dict, semanas: int = 12) -> dict:
    """Metros por latido en tus carreras (velocidad ÷ FC media). Si sube, corres más con el mismo
    coste cardiaco: mejora aeróbica real, medida en tus entrenamientos."""
    acts = [a for a in datos.get("garmin_actividades", [])
            if "run" in str(a.get("tipo") or "") and a.get("distancia_km") and a.get("duracion_min")
            and a.get("fc_media") and a["duracion_min"] >= 15]
    if not acts:
        return {"ok": False, "motivo": "Sin carreras de 15 min o más con FC en Garmin."}
    ultima = max(_d(a["fecha"]) for a in acts)
    recientes = [a for a in acts if (ultima - _d(a["fecha"])).days <= semanas * 7]
    puntos_ = [{"fecha": a["fecha"],
                "m_por_latido": a["distancia_km"] * 1000 / (a["duracion_min"] * a["fc_media"]),
                "ritmo": a["duracion_min"] / a["distancia_km"]} for a in recientes]
    t = tendencia([(_d(p["fecha"]) - ultima).days / 7 for p in puntos_], [p["m_por_latido"] for p in puntos_])
    return {"ok": True, "puntos": sorted(puntos_, key=lambda p: p["fecha"]), "tendencia": t, "n": len(puntos_)}


# ---------------------------------------------------------------- puntos débiles

CONSEJO = {
    "dominadas": "Volumen submáximo frecuente (series a 50–70 % de tu máximo varios días/semana) y una sesión con lastre.",
    "banca": "Series de 30 s con 40 kg buscando ritmo constante; fuerza base con 3–5 rep pesadas una vez por semana.",
    "60m": "Aceleraciones de 10–30 m y lanzados con recuperación completa (2–3 min); poco volumen, máxima calidad.",
    "1500m": "Una sesión de umbral (p. ej. 3×8 min) y otra de intervalos a ritmo de prueba (p. ej. 6×300 m).",
    "cuerda": "Técnica de pies (pinza) para ahorrar brazos, más dominadas con agarre de toalla.",
    "flexibilidad": "Movilidad de isquios y cadera a diario, 10 min; mejora rápido con constancia.",
}


def puntos_debiles(datos: dict, baremo: dict, puntos_max: float = 6) -> list[dict]:
    """Ordena las pruebas por lo que más nota te puede dar, con la evidencia de cada una."""
    out = []
    for p, info in PRUEBAS.items():
        prev = prevision(p, datos.get("controles", []))
        pts = puntos(p, prev["central"], baremo.get(p)) if prev["central"] is not None else None
        hist = sorted((c for c in datos.get("controles", []) if c["prueba"] == p), key=lambda c: c["fecha"])
        t = None
        if len(hist) >= 3:
            d0 = _d(hist[0]["fecha"])
            t = tendencia([(_d(c["fecha"]) - d0).days / 7 for c in hist], [c["resultado"] for c in hist])
        mejora = None
        if t:
            signo = 1 if info["mejor"] == "mayor" else -1
            mejora = {"por_semana": signo * t["pendiente"], "demostrada": t["significativa"] and signo * t["pendiente"] > 0,
                      "empeora": t["significativa"] and signo * t["pendiente"] < 0, "n": t["n"]}
        margen = (puntos_max - pts) if pts is not None else None
        out.append({"prueba": p, "nombre": info["nombre"], "puntos": pts, "margen": margen, "prevision": prev,
                    "mejora": mejora, "consejo": CONSEJO[p],
                    "sin_datos": prev["central"] is None})
    # Sin datos primero (no sabes dónde estás), luego más margen de puntos
    return sorted(out, key=lambda x: (not x["sin_datos"], -(x["margen"] if x["margen"] is not None else -1)))
