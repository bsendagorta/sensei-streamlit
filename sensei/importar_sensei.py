"""Importa una «copia» de Sensei.app (schema rumbo-enero-backup-v1) a los datos de la web.

Reglas:
- Lo que viene de Sensei lleva id `sensei-…`. Al reimportar, esos registros se actualizan con la versión
  nueva de Sensei; lo que has creado en la web no se toca nunca.
- Los días de Garmin solo RELLENAN huecos: un dato que ya está no se sustituye.
- Faltantes = None, nunca 0.
"""
from __future__ import annotations

from .baremo import DE_SENSEI

CAMPOS_BIENESTAR = {  # Sensei (base.wellness.days) → web (garmin_diario)
    "restingHeartRate": "fc_reposo", "hrvNight": "vfc", "hrvStatus": "vfc_estado", "sleepScore": "sueno_puntos",
    "bodyBatteryHigh": "body_battery_max", "bodyBatteryLow": "body_battery_min",
    "bodyBatteryWake": "body_battery_despertar", "bodyBatteryLast": "body_battery_ultima",
    "stressAvg": "estres_medio", "readiness": "disposicion", "readinessLevel": "disposicion_nivel",
    "totalKilocalories": "kcal_total", "steps": "pasos", "minHeartRate": "fc_min", "maxHeartRate": "fc_max",
    "sleepNeedMinutes": "sueno_necesidad_min", "deepSeconds": "sueno_profundo_s", "remSeconds": "sueno_rem_s",
    "lightSeconds": "sueno_ligero_s", "awakeSeconds": "sueno_despierto_s",
}


class ErrorImportacion(ValueError):
    pass


def _num(x):
    try:
        return None if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return None


def _reemplazar(lista: list[dict], nuevos: list[dict]) -> tuple[list[dict], int]:
    ids = {n["id"] for n in nuevos}
    resto = [x for x in lista if x.get("id") not in ids]
    return sorted(resto + nuevos, key=lambda x: (x.get("fecha", ""), str(x.get("id")))), len(nuevos)


def importar(d: dict, copia: dict) -> dict:
    """Aplica la copia sobre `d` (modifica `d`). Devuelve un resumen."""
    if copia.get("schema") != "rumbo-enero-backup-v1" or "state" not in copia:
        raise ErrorImportacion("No es una copia de Sensei.app (falta schema rumbo-enero-backup-v1).")
    s, base = copia["state"], copia.get("base") or {}
    resumen = {}

    controles = []
    for c in s.get("controls", []):
        prueba = DE_SENSEI.get(c.get("test"))
        if not prueba or _num(c.get("value")) is None:
            continue
        controles.append({"id": f"sensei-{c['id']}", "fecha": c["date"], "prueba": prueba,
                          "resultado": float(c["value"]), "protocolo_completo": bool(c.get("protocol")),
                          "notas": c.get("notes") or "", "origen": "sensei"})
    d["controles"], resumen["controles"] = _reemplazar(d["controles"], controles)

    sesiones = []
    for x in s.get("sessions", []):
        dist = _num(x.get("distance"))
        sesiones.append({"id": f"sensei-{x['id']}", "fecha": x["date"], "nombre": x.get("name"),
                         "tipo": x.get("type"), "estado": x.get("status", "completed"),
                         "duracion_min": _num(x.get("minutes")), "distancia_km": round(dist / 1000, 2) if dist else None,
                         "rpe": None, "notas": x.get("notes") or "", "bloques": x.get("blocks") or [],
                         "garmin_id": x.get("garminId"), "origen": "sensei"})
    d["sesiones"], resumen["sesiones"] = _reemplazar(d["sesiones"], sesiones)

    citas = [{"id": f"sensei-{a['id']}", "fecha": a["date"], "nombre": a.get("name"), "hora": a.get("time"),
              "tipo": a.get("type"), "lugar": a.get("location"), "notas": a.get("notes"), "origen": "sensei"}
             for a in s.get("appointments", [])]
    d["citas"], resumen["citas"] = _reemplazar(d.get("citas", []), citas)

    n = s.get("nutrition") or {}
    comidas = []
    for e in n.get("entries", []):
        k = 1 if e.get("basis") == "portion" else (_num(e.get("quantity")) or 0) / 100

        def val(campo):
            v = _num(e.get(campo))
            return None if v is None else round(v * k, 1)
        comidas.append({"id": f"sensei-{e['id']}", "fecha": e["date"], "comida": e.get("meal", "Otros"),
                        "nombre": e.get("name"), "cantidad": f"{e.get('quantity', '')} {e.get('unit') or ''}".strip(),
                        "gramos": _num(e.get("quantity")) if e.get("basis") in ("100g", "100ml") else None,
                        "hora": e.get("time"), "kcal": val("kcal"), "prot": val("protein"), "hc": val("carbs"),
                        "grasa": val("fat"), "fuente": e.get("source"), "origen": "sensei"})
    d["comidas"], resumen["comidas"] = _reemplazar(d["comidas"], comidas)
    dias = d.setdefault("dias_nutricion", {})
    completos = set(d.get("dias_nutricion_completos", []))
    for f, info in (n.get("days") or {}).items():
        if info.get("load"):
            dias.setdefault(f, {})["carga"] = info["load"]
        if info.get("complete"):
            completos.add(f)
    d["dias_nutricion_completos"] = sorted(completos)

    aj = d.setdefault("ajustes", {})
    if _num(n.get("weight")):
        aj["peso_kg"] = float(n["weight"])
    if s.get("examDate"):
        aj["fecha_examen"] = s["examDate"]

    # Garmin: días de bienestar (solo rellenan huecos)
    por_fecha = {g["fecha"]: g for g in d["garmin_diario"]}
    nuevos_dias = 0
    for w in (base.get("wellness") or {}).get("days", []):
        if not w.get("hasData"):
            continue
        g = por_fecha.get(w["date"])
        if g is None:
            g = por_fecha[w["date"]] = {"fecha": w["date"]}
            nuevos_dias += 1
        for src, dst in CAMPOS_BIENESTAR.items():
            if g.get(dst) is None and w.get(src) is not None:
                g[dst] = w[src]
        if g.get("sueno_h") is None and _num(w.get("sleepSeconds")):
            g["sueno_h"] = round(float(w["sleepSeconds"]) / 3600, 2)
    d["garmin_diario"] = sorted(por_fecha.values(), key=lambda g: g["fecha"])
    resumen["dias_garmin_nuevos"] = nuevos_dias

    por_id = {str(a["id"]): a for a in d["garmin_actividades"]}
    nuevas = 0
    for a in base.get("sessions", []):
        clave = str(a.get("id"))
        if not clave or clave == "None":
            continue
        dist = _num(a.get("distance"))
        extra = {"fecha": a.get("date"), "nombre": a.get("name"), "tipo": a.get("type"),
                 "duracion_min": _num(a.get("minutes")), "distancia_km": round(dist / 1000, 2) if dist else None,
                 "fc_media": _num(a.get("hr"))}
        if clave not in por_id:
            por_id[clave] = {"id": a.get("id"), "carga": None, **extra}
            nuevas += 1
        else:
            for k, v in extra.items():
                if por_id[clave].get(k) is None and v is not None:
                    por_id[clave][k] = v
    d["garmin_actividades"] = sorted(por_id.values(), key=lambda a: (a.get("fecha") or "", str(a["id"])))
    resumen["actividades_nuevas"] = nuevas
    return resumen
