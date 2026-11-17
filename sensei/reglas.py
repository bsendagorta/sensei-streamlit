"""Semáforo diario: decide sesión completa / reducida / descanso con reglas fijas y explicadas.

Cada señal dice qué dato ha usado y con qué umbral, para que no haga falta que nadie
«reevalúe» a mano: los umbrales se cambian en Ajustes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .carga import _d, acwr, carga_diaria_garmin, carga_diaria_srpe, linea_base

VERDE, AMBAR, ROJO = 0, 1, 2
NOMBRE_NIVEL = {VERDE: "Verde", AMBAR: "Ámbar", ROJO: "Rojo"}

UMBRALES_POR_DEFECTO = {
    "fc_reposo_ambar": 5,      # lpm por encima de tu media de 28 días
    "fc_reposo_rojo": 8,
    "fc_reposo_absoluto": None,  # p. ej. 47: si se alcanza, ámbar (condición de tus planes)
    "vfc_sd_ambar": 1.0,       # desviaciones típicas por debajo de tu media
    "vfc_sd_rojo": 2.0,
    "sueno_ambar_h": 6.0,
    "sueno_rojo_h": 5.0,
    "sensacion_ambar": 4,      # 1–10, igual o por debajo
    "sensacion_rojo": 2,
    "dolor_ambar": 2,          # 0–10, igual o por encima
    "dolor_rojo": 4,
    "acwr_ambar": 1.3,
    "acwr_rojo": 1.5,
    "acwr_bajo": 0.8,
    "disposicion_ambar": 33,   # Training Readiness de Garmin (0–100)
    "ambares_para_rojo": 3,
}

RECOMENDACION = {
    VERDE: "Sesión planificada completa.",
    AMBAR: ("Versión reducida: quita un 30–40 % del volumen, sin series al máximo ni controles; "
            "técnica y calidad de movimiento."),
    ROJO: ("Descanso activo: 20–30 min de movilidad, paseo o bici suave. Nada de intensidad. "
           "Si el motivo es dolor, no cargues esa zona."),
}


@dataclass
class Senal:
    nombre: str
    nivel: int | None  # None = sin dato
    texto: str


def _por_fecha(lista, campo):
    return {_d(x["fecha"]): x.get(campo) for x in lista if x.get(campo) is not None}


def evaluar(datos: dict, hoy: date, umbrales: dict | None = None) -> dict:
    u = {**UMBRALES_POR_DEFECTO, **(umbrales or {})}
    gd = datos.get("garmin_diario", [])
    checkins = datos.get("checkins", [])
    ch_hoy = next((c for c in checkins if _d(c["fecha"]) == hoy), None)
    g_hoy = next((g for g in gd if _d(g["fecha"]) == hoy), None)
    senales: list[Senal] = []

    # Pulso en reposo
    rhr = _por_fecha(gd, "fc_reposo")
    if hoy in rhr:
        base = linea_base(rhr, hoy)
        v = rhr[hoy]
        if base:
            dif = v - base["media"]
            nivel = ROJO if dif >= u["fc_reposo_rojo"] else AMBAR if dif >= u["fc_reposo_ambar"] else VERDE
            txt = f"{v:.0f} lpm ({dif:+.0f} sobre tu media de {base['n']} días: {base['media']:.0f})."
        else:
            nivel, txt = VERDE, f"{v:.0f} lpm (aún sin 7 días para calcular tu media)."
        if u.get("fc_reposo_absoluto") and v >= u["fc_reposo_absoluto"] and nivel == VERDE:
            nivel, txt = AMBAR, txt + f" Alcanza tu límite fijo de {u['fc_reposo_absoluto']:.0f} lpm."
        senales.append(Senal("Pulso en reposo", nivel, txt))
    else:
        senales.append(Senal("Pulso en reposo", None, "Sin dato de hoy."))

    # VFC nocturna
    vfc = _por_fecha(gd, "vfc")
    if hoy in vfc:
        base = linea_base(vfc, hoy)
        v = vfc[hoy]
        if base and base["sd"] > 0:
            z = (v - base["media"]) / base["sd"]
            nivel = ROJO if z <= -u["vfc_sd_rojo"] else AMBAR if z <= -u["vfc_sd_ambar"] else VERDE
            txt = f"{v:.0f} ms ({z:+.1f} DT respecto a tu media de {base['media']:.0f} ms)."
        else:
            nivel, txt = VERDE, f"{v:.0f} ms (aún sin línea base suficiente)."
        senales.append(Senal("VFC nocturna", nivel, txt))
    else:
        senales.append(Senal("VFC nocturna", None, "Sin dato de hoy."))

    # Sueño (Garmin primero; si no, lo que anotes)
    sueno = (g_hoy or {}).get("sueno_h")
    origen = "Garmin"
    if sueno is None and ch_hoy:
        sueno, origen = ch_hoy.get("sueno_h"), "anotado"
    if sueno is not None:
        nivel = ROJO if sueno < u["sueno_rojo_h"] else AMBAR if sueno < u["sueno_ambar_h"] else VERDE
        senales.append(Senal("Sueño", nivel, f"{sueno:.1f} h ({origen})."))
    else:
        senales.append(Senal("Sueño", None, "Sin dato de hoy."))

    # Sensación subjetiva
    if ch_hoy and ch_hoy.get("sensacion") is not None:
        s = ch_hoy["sensacion"]
        nivel = ROJO if s <= u["sensacion_rojo"] else AMBAR if s <= u["sensacion_ambar"] else VERDE
        senales.append(Senal("Sensación", nivel, f"{s}/10."))
    else:
        senales.append(Senal("Sensación", None, "Haz el check-in de hoy."))

    # Molestias: hoy y persistencia en los últimos 5 días
    zonas_aviso = []
    if ch_hoy is not None:
        molestias = [m for m in ch_hoy.get("molestias", []) if m.get("intensidad")]
        if molestias:
            peor = max(molestias, key=lambda m: m["intensidad"])
            i = peor["intensidad"]
            nivel = ROJO if i >= u["dolor_rojo"] else AMBAR if i >= u["dolor_ambar"] else VERDE
            txt = ", ".join(f"{m['zona']} {m['intensidad']}/10" for m in molestias) + "."
            for m in molestias:
                dias = sum(1 for c in checkins
                           if 0 <= (hoy - _d(c["fecha"])).days < 5
                           and any(x.get("zona") == m["zona"] and (x.get("intensidad") or 0) > 0
                                   for x in c.get("molestias", [])))
                if dias >= 3:
                    zonas_aviso.append(m["zona"])
            if zonas_aviso:
                txt += f" Repite {', '.join(zonas_aviso)} ≥3 de los últimos 5 días: consúltalo con fisio."
                nivel = max(nivel, AMBAR)
            senales.append(Senal("Molestias", nivel, txt))
        else:
            senales.append(Senal("Molestias", VERDE, "Ninguna."))
    else:
        senales.append(Senal("Molestias", None, "Haz el check-in de hoy."))

    # Carga (Garmin si hay; si no, sRPE)
    c_g = carga_diaria_garmin(datos.get("garmin_actividades", []))
    c_s = carga_diaria_srpe(datos.get("sesiones", []))
    r = acwr(c_g, hoy - timedelta(days=1)) if c_g else {"ratio": None}
    fuente = "carga Garmin"
    if r["ratio"] is None:
        r, fuente = acwr(c_s, hoy - timedelta(days=1)), "sRPE"
    if r["ratio"] is not None:
        x = r["ratio"]
        nivel = ROJO if x > u["acwr_rojo"] else AMBAR if x > u["acwr_ambar"] else VERDE
        txt = f"Agudo:crónico {x:.2f} ({fuente}, hasta ayer)."
        if x < u["acwr_bajo"]:
            txt += " Carga baja respecto a tu media: puedes subir progresivamente (≤10 %/semana)."
        senales.append(Senal("Carga 7/28 días", nivel, txt))
    else:
        senales.append(Senal("Carga 7/28 días", None, r.get("motivo") or "Sin datos."))

    # Disposición para entrenar de Garmin
    disp = (g_hoy or {}).get("disposicion")
    if disp is not None:
        nivel = AMBAR if disp < u["disposicion_ambar"] else VERDE
        senales.append(Senal("Disposición Garmin", nivel, f"{disp:.0f}/100."))

    con_dato = [s for s in senales if s.nivel is not None]
    nivel = max((s.nivel for s in con_dato), default=None)
    ambares = sum(1 for s in con_dato if s.nivel == AMBAR)
    if nivel == AMBAR and ambares >= u["ambares_para_rojo"]:
        nivel = ROJO
        motivo_extra = f"{ambares} señales en ámbar a la vez."
    else:
        motivo_extra = None
    return {
        "nivel": nivel,
        "senales": senales,
        "recomendacion": RECOMENDACION.get(nivel, "Faltan datos: haz el check-in o actualiza Garmin."),
        "motivo_extra": motivo_extra,
        "faltan": [s.nombre for s in senales if s.nivel is None],
        "zonas_fisio": zonas_aviso,
    }


def fase(hoy: date, examen: date) -> str:
    d = (examen - hoy).days
    if d < 0:
        return "Examen pasado."
    if d <= 2:
        return f"Faltan {d} días: solo activación corta y descanso."
    if d <= 10:
        return f"Faltan {d} días: puesta a punto. Baja el volumen un 40–60 % y mantén la intensidad en dosis cortas."
    if d <= 28:
        return f"Faltan {d} días: bloque específico. Prioriza las pruebas con menos puntos y haz controles reales."
    return f"Faltan {d} días: construcción. Sube la carga de forma gradual (≤10 % semanal)."
