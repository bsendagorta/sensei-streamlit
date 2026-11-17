"""Lectura de Garmin Connect con la librería `garminconnect` (no oficial). SOLO LECTURA.

La app nunca usa tu contraseña: usa un token que generas una vez en tu Mac con
`herramientas/exportar_token_garmin.py` y pegas en los secretos de Streamlit.
Garmin renueva el token de vez en cuando; si `guardar_token_renovado` está activo, el token
renovado se guarda en tu repositorio PRIVADO de datos (`privado/garmin_token.json`) para que
no caduque. Puedes desactivarlo en los secretos.
"""
from __future__ import annotations

from datetime import date, timedelta

RUTA_TOKEN = "privado/garmin_token.json"


class ErrorGarmin(RuntimeError):
    pass


def conectar(token_json: str):
    try:
        from garminconnect import Garmin
    except ImportError as e:  # pragma: no cover
        raise ErrorGarmin("Falta la librería garminconnect.") from e
    api = Garmin()
    try:
        api.login(tokenstore=token_json)
    except Exception as e:
        raise ErrorGarmin(
            "No se pudo entrar en Garmin con el token. Genera uno nuevo en tu Mac con "
            "herramientas/exportar_token_garmin.py y pégalo en los secretos de la app. "
            f"Detalle: {type(e).__name__}") from e
    return api


def token_actual(api) -> str:
    return api.client.dumps()


def _seguro(f, *a):
    try:
        return f(*a)
    except Exception:
        return None


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def resumen_dia(api, dia: date) -> dict:
    """Un día de recuperación. Lo que Garmin no tenga queda en None (nunca 0)."""
    f = dia.isoformat()
    out = {"fecha": f, "fc_reposo": None, "vfc": None, "vfc_estado": None, "sueno_h": None,
           "sueno_puntos": None, "body_battery_max": None, "estres_medio": None, "disposicion": None}
    st = _seguro(api.get_stats, f) or {}
    out["fc_reposo"] = _num(st.get("restingHeartRate"))
    out["body_battery_max"] = _num(st.get("bodyBatteryHighestValue"))
    est = _num(st.get("averageStressLevel"))
    out["estres_medio"] = est if est is not None and est >= 0 else None
    hrv = _seguro(api.get_hrv_data, f) or {}
    s = (hrv or {}).get("hrvSummary") or {}
    out["vfc"] = _num(s.get("lastNightAvg"))
    out["vfc_estado"] = s.get("status")
    sl = (_seguro(api.get_sleep_data, f) or {}).get("dailySleepDTO") or {}
    secs = _num(sl.get("sleepTimeSeconds"))
    out["sueno_h"] = round(secs / 3600, 2) if secs else None
    out["sueno_puntos"] = _num(((sl.get("sleepScores") or {}).get("overall") or {}).get("value"))
    tr = _seguro(api.get_training_readiness, f)
    if isinstance(tr, list) and tr:
        out["disposicion"] = _num(tr[0].get("score"))
    elif isinstance(tr, dict):
        out["disposicion"] = _num(tr.get("score"))
    return out


def actividades(api, desde: date, hasta: date) -> list[dict]:
    lista = _seguro(api.get_activities_by_date, desde.isoformat(), hasta.isoformat()) or []
    out = []
    for a in lista:
        dur = _num(a.get("duration"))
        dist = _num(a.get("distance"))
        out.append({
            "id": a.get("activityId"),
            "fecha": str(a.get("startTimeLocal", ""))[:10],
            "nombre": a.get("activityName"),
            "tipo": (a.get("activityType") or {}).get("typeKey"),
            "duracion_min": round(dur / 60, 1) if dur else None,
            "distancia_km": round(dist / 1000, 2) if dist else None,
            "fc_media": _num(a.get("averageHR")),
            "carga": _num(a.get("activityTrainingLoad")),
        })
    return [x for x in out if x["id"] is not None and x["fecha"]]


def descargar(api, dias: int, hoy: date) -> tuple[list[dict], list[dict]]:
    return descargar_rango(api, hoy - timedelta(days=dias - 1), hoy)


def descargar_rango(api, desde: date, hasta: date) -> tuple[list[dict], list[dict]]:
    n = (hasta - desde).days + 1
    diarios = [resumen_dia(api, hasta - timedelta(days=i)) for i in range(n)]
    return diarios, actividades(api, desde, hasta)


def fusionar(datos: dict, diarios: list[dict], acts: list[dict], marca_tiempo: str) -> None:
    """Añade lo de Garmin sin tocar nada de lo que registras tú.

    Un día ya guardado solo se actualiza con valores no vacíos (un fallo puntual de Garmin no
    borra datos que ya tenías)."""
    por_fecha = {g["fecha"]: g for g in datos["garmin_diario"]}
    for d in diarios:
        if all(v is None for k, v in d.items() if k != "fecha"):
            continue
        previo = por_fecha.get(d["fecha"], {"fecha": d["fecha"]})
        previo.update({k: v for k, v in d.items() if v is not None})
        por_fecha[d["fecha"]] = previo
    datos["garmin_diario"] = sorted(por_fecha.values(), key=lambda g: g["fecha"])
    por_id = {a["id"]: a for a in datos["garmin_actividades"]}
    for a in acts:
        por_id[a["id"]] = {**por_id.get(a["id"], {}), **{k: v for k, v in a.items() if v is not None}}
    datos["garmin_actividades"] = sorted(por_id.values(), key=lambda a: (a["fecha"], str(a["id"])))
    datos["garmin_ultima_sync"] = marca_tiempo
