"""Sensei te conoce: modelos personales que aprenden de TUS entrenamientos y se reentrenan con cada día nuevo.

Qué aprende (todo con tus datos de Garmin, tus sesiones y tus check-ins):
1. Cómo te afecta cada tipo de entrenamiento (fuerza, carrera, series/pista…) a la mañana siguiente y a los dos días.
2. Un modelo que predice tu VFC, tu pulso en reposo y tu disposición de mañana a partir de lo que haces hoy, de cómo
   llegas y de la carga acumulada.
3. Si cada vez acierta más: validación temporal estricta (entrena solo con el pasado y predice el día siguiente) y su
   error comparado con dos referencias sin modelo («mañana igual que hoy» y «mañana en tu media»).

Principios: modelos pequeños y explicables (ridge), nada se da por aprendido si no bate a las referencias, y
cada conclusión lleva su número de casos.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

TIPOS = {
    "fuerza": "Fuerza",
    "carrera": "Carrera continua",
    "series": "Series, pista y velocidad",
    "otro": "Otros (bici, caminar…)",
}
PALABRAS_SERIES = ("serie", "interval", "pista", "track", "1500", "800", "400", "200", "60 m", "velocidad", "fartlek",
                   "umbral", "tempo", "control")


def categoria(act: dict) -> str:
    t = str(act.get("tipo") or "").lower()
    n = str(act.get("nombre") or "").lower()
    if "strength" in t or "fuerza" in n or "gimnasio" in n:
        return "fuerza"
    if "track" in t or any(p in n for p in PALABRAS_SERIES):
        return "series"
    if "run" in t or "carrera" in n or "rodaje" in n:
        return "carrera"
    return "otro"


def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _base(serie: dict, f: date, dias=28, minimo=7):
    vals = [v for k, v in serie.items() if v is not None and 1 <= (f - k).days <= dias]
    if len(vals) < minimo:
        return None
    return statistics.fmean(vals)


# ------------------------------------------------------------------ dataset

def dataset(d: dict) -> list[dict]:
    """Una fila por día D con lo que hiciste ese día y cómo llegaste, y lo que pasó la mañana siguiente (D+1)."""
    gd = {_d(g["fecha"]): g for g in d.get("garmin_diario", [])}
    if not gd:
        return []
    series = {k: {f: g.get(k) for f, g in gd.items() if g.get(k) is not None}
              for k in ("vfc", "fc_reposo", "disposicion", "body_battery_despertar")}
    carga = defaultdict(lambda: defaultdict(float))
    minutos = defaultdict(float)
    tasa = defaultdict(list)  # carga por minuto de cada tipo, para estimar actividades sin carga
    for a in d.get("garmin_actividades", []):
        if a.get("carga") and a.get("duracion_min"):
            tasa[categoria(a)].append(a["carga"] / a["duracion_min"])
    tasa_med = {k: statistics.median(v) for k, v in tasa.items() if v}
    for a in d.get("garmin_actividades", []):
        f, cat = _d(a["fecha"]), categoria(a)
        c = a.get("carga")
        if c is None and a.get("duracion_min") and cat in tasa_med:
            c = a["duracion_min"] * tasa_med[cat]
        if c:
            carga[f][cat] += c
        minutos[f] += a.get("duracion_min") or 0
    total = {f: sum(v.values()) for f, v in carga.items()}

    filas = []
    for f in sorted(gd):
        g, g1 = gd[f], gd.get(f + timedelta(days=1))
        if not g1:
            continue
        fila = {"fecha": f}
        for cat in TIPOS:
            fila[f"carga_{cat}"] = carga[f].get(cat, 0.0)
        fila["carga_7d"] = sum(total.get(f - timedelta(days=i), 0) for i in range(1, 8)) / 7
        fila["carga_ayer"] = total.get(f - timedelta(days=1), 0.0)
        for k in ("vfc", "fc_reposo"):
            b = _base(series[k], f)
            fila[f"{k}_hoy_dif"] = (g.get(k) - b) if g.get(k) is not None and b is not None else None
        fila["sueno_hoy"] = g.get("sueno_h")
        fila["estres_hoy"] = g.get("estres_medio")
        for k in ("vfc", "fc_reposo", "disposicion", "body_battery_despertar"):
            b = _base(series[k], f + timedelta(days=1))
            v = g1.get(k)
            fila[f"y_{k}"] = (v - b) if v is not None and b is not None else None
            fila[f"y_{k}_abs"] = v
            fila[f"base_{k}"] = b
        filas.append(fila)
    return filas


VARIABLES = {
    "carga_fuerza": ("Carga de fuerza de hoy", 100),
    "carga_carrera": ("Carga de carrera continua de hoy", 100),
    "carga_series": ("Carga de series/pista de hoy", 100),
    "carga_otro": ("Carga de otras actividades de hoy", 100),
    "carga_7d": ("Carga media de los 7 días anteriores", 25),
    "carga_ayer": ("Carga de ayer", 100),
    "vfc_hoy_dif": ("Tu VFC de hoy respecto a tu media", 5),
    "fc_reposo_hoy_dif": ("Tu pulso en reposo de hoy respecto a tu media", 2),
    "sueno_hoy": ("Horas de sueño de anoche", 1),
    "estres_hoy": ("Estrés medio de hoy (Garmin)", 10),
}
OBJETIVOS = {
    "vfc": ("VFC de mañana", "ms", True),
    "fc_reposo": ("Pulso en reposo de mañana", "lpm", False),
    "disposicion": ("Disposición de mañana", "/100", True),
    "body_battery_despertar": ("Body Battery al despertar mañana", "/100", True),
}


def _ridge(X, y, lam):
    Xb = np.column_stack([np.ones(len(X)), X])
    reg = lam * np.eye(Xb.shape[1])
    reg[0, 0] = 0
    return np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y)


def modelo(d: dict, objetivo: str = "vfc", minimo: int = 60, lam: float = 5.0, filas=None) -> dict:
    filas = filas if filas is not None else dataset(d)
    y_k = f"y_{objetivo}"
    disponibles = [f for f in filas if f[y_k] is not None]
    usables = [k for k in VARIABLES if sum(f[k] is not None for f in disponibles) >= 0.8 * max(1, len(disponibles))]
    filas_ok = [f for f in disponibles if all(f[k] is not None for k in usables)]
    if len(filas_ok) < minimo:
        return {"ok": False, "objetivo": objetivo, "n": len(filas_ok),
                "motivo": f"Necesito {minimo} días con datos (hay {len(filas_ok)})."}
    X = np.array([[f[k] for k in usables] for f in filas_ok], float)
    y = np.array([f[y_k] for f in filas_ok], float)
    pers = np.array([f.get(f"{objetivo}_hoy_dif") if f.get(f"{objetivo}_hoy_dif") is not None else 0.0
                     for f in filas_ok], float)
    inicio = max(40, len(filas_ok) // 4)
    err_m, err_media, err_pers, fechas = [], [], [], []
    for i in range(inicio, len(filas_ok)):
        Xt, yt = X[:i], y[:i]
        mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        w = _ridge((Xt - mu) / sd, yt, lam)
        pred = w[0] + ((X[i] - mu) / sd) @ w[1:]
        err_m.append(abs(pred - y[i]))
        err_media.append(abs(y[i]))                     # «mañana en tu media»
        err_pers.append(abs(pers[i] - y[i]))            # «mañana igual que hoy»
        fechas.append(filas_ok[i]["fecha"])
    mae, mae_media, mae_pers = (float(np.mean(e)) for e in (err_m, err_media, err_pers))
    ref = min(mae_media, mae_pers)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    w = _ridge((X - mu) / sd, y, lam)
    efectos = []
    for j, k in enumerate(usables):
        nombre, paso = VARIABLES[k]
        if k.startswith("carga_") and k not in ("carga_7d", "carga_ayer"):
            nz = [v for v in X[:, j] if v > 0]
            if len(nz) >= 5:  # efecto de UNA sesión típica tuya de ese tipo
                paso = float(np.median(nz))
                nombre = nombre.replace("Carga de ", "Una sesión típica de ").replace(" de hoy", " hoy")
        efectos.append({"variable": k, "nombre": nombre, "paso": paso, "efecto": float(w[1 + j] / sd[j] * paso),
                        "n_sesiones": int(sum(1 for v in X[:, j] if v > 0)) if k.startswith("carga_") else None})
    efectos.sort(key=lambda e: -abs(e["efecto"]))
    # curva de aprendizaje: error por trimestre de validación
    curva = defaultdict(lambda: [[], [], []])
    for f, a, b, c in zip(fechas, err_m, err_media, err_pers):
        clave = f"{f.year}-T{(f.month - 1) // 3 + 1}"
        curva[clave][0].append(a)
        curva[clave][1].append(b)
        curva[clave][2].append(c)
    curva_l = [{"periodo": k, "mae": float(np.mean(v[0])), "ref": float(min(np.mean(v[1]), np.mean(v[2]))), "n": len(v[0])}
               for k, v in sorted(curva.items()) if len(v[0]) >= 15]
    return {"ok": True, "objetivo": objetivo, "n": len(filas_ok), "n_validados": len(err_m), "usables": usables,
            "mae": mae, "mae_media": mae_media, "mae_persistencia": mae_pers, "mejora_pct": (1 - mae / ref) * 100,
            "util": mae < ref * 0.97, "efectos": efectos, "pesos": w, "mu": mu, "sd": sd, "curva": curva_l,
            "desde": filas_ok[0]["fecha"], "hasta": filas_ok[-1]["fecha"]}


def predecir(m: dict, fila: dict) -> float | None:
    if not m.get("ok") or any(fila.get(k) is None for k in m["usables"]):
        return None
    x = (np.array([fila[k] for k in m["usables"]], float) - m["mu"]) / m["sd"]
    return float(m["pesos"][0] + x @ m["pesos"][1:])


def fila_hoy(d: dict, hoy: date) -> dict | None:
    """Fila de hoy aunque no exista aún el día de mañana (para simular)."""
    gd = {_d(g["fecha"]): g for g in d.get("garmin_diario", [])}
    if hoy not in gd:
        return None
    falso = dict(d)
    falso["garmin_diario"] = list(d.get("garmin_diario", [])) + [{"fecha": (hoy + timedelta(days=1)).isoformat()}]
    filas = [f for f in dataset(falso) if f["fecha"] == hoy]
    return filas[0] if filas else None


def carga_tipica(d: dict) -> dict:
    """Carga por minuto mediana de cada tipo, aprendida de tus actividades."""
    tasa = defaultdict(list)
    for a in d.get("garmin_actividades", []):
        if a.get("carga") and a.get("duracion_min"):
            tasa[categoria(a)].append(a["carga"] / a["duracion_min"])
    return {k: statistics.median(v) for k, v in tasa.items() if len(v) >= 3}


def simular(d: dict, modelos: dict, hoy: date, tipo: str | None, minutos: float) -> dict:
    """¿Cómo estarás mañana si hoy haces `minutos` de `tipo` (None = descanso)?"""
    f = fila_hoy(d, hoy)
    if f is None:
        return {}
    tasa = carga_tipica(d)
    for cat in TIPOS:
        f[f"carga_{cat}"] = 0.0
    if tipo:
        f[f"carga_{tipo}"] = minutos * tasa.get(tipo, 1.5)
    out = {}
    for obj, m in modelos.items():
        if m.get("ok") and m.get("util"):
            p = predecir(m, f)
            if p is not None:
                base = f.get(f"base_{obj}")
                out[obj] = {"dif": p, "abs": (base + p) if base is not None else None}
    return out


# ------------------------------------------------------------------ respuesta por tipo de entrenamiento

def respuesta_por_tipo(d: dict, filas=None) -> list[dict]:
    """Media de cómo amaneces (respecto a tu media) tras cada tipo de sesión, frente a los días de descanso."""
    filas = filas if filas is not None else dataset(d)
    por_fecha = {f["fecha"]: f for f in filas}
    out = []
    grupos = {"descanso": []}
    for f in filas:
        cargas = {c: f[f"carga_{c}"] for c in TIPOS}
        if sum(cargas.values()) == 0:
            grupos["descanso"].append(f)
        else:
            principal = max(cargas, key=cargas.get)
            grupos.setdefault(principal, []).append(f)
    for grupo, fs in grupos.items():
        if len(fs) < 5:
            continue
        r = {"tipo": grupo, "nombre": TIPOS.get(grupo, "Descanso"), "n": len(fs)}
        for obj in ("vfc", "fc_reposo", "disposicion"):
            v1 = [f[f"y_{obj}"] for f in fs if f[f"y_{obj}"] is not None]
            v2 = [por_fecha[f["fecha"] + timedelta(days=1)][f"y_{obj}"] for f in fs
                  if f["fecha"] + timedelta(days=1) in por_fecha and por_fecha[f["fecha"] + timedelta(days=1)][f"y_{obj}"] is not None]
            for clave, v in (("d1", v1), ("d2", v2)):
                if len(v) >= 5:
                    m, s = statistics.fmean(v), statistics.stdev(v)
                    r[f"{obj}_{clave}"] = {"media": m, "ic": 1.96 * s / math.sqrt(len(v)), "n": len(v)}
        out.append(r)
    orden = ["descanso"] + list(TIPOS)
    return sorted(out, key=lambda r: orden.index(r["tipo"]))


def resumen_aprendizaje(d: dict, hoy: date) -> dict:
    filas = dataset(d)
    modelos = {obj: modelo(d, obj, filas=filas) for obj in OBJETIVOS}
    return {"filas": len(filas), "modelos": modelos, "respuesta": respuesta_por_tipo(d, filas),
            "hoy": fila_hoy(d, hoy), "tasa": carga_tipica(d)}
