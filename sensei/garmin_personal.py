"""API Personal oficial de Garmin Connect (clave API personal). SOLO LECTURA.

Cómo funciona (https://developer.garmin.com/gc-developer-program/personal/personal-api/):
1. Creas la clave en Garmin Connect web → Clave API personal (caduca en 30/90/180 días o 1 año).
2. La clave se cambia por un token de acceso válido 24 h (no hay token de refresco: se pide otro).
3. Con el token se leen los endpoints de https://personal.connectapi.garmin.com.

No incluye «Training Readiness»: esa señal queda vacía (None) con esta vía.
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import requests

BASE = "https://personal.connectapi.garmin.com"
URL_TOKEN = BASE + "/personalapitoken-service/personal-api/personal-api-key/token"
TROZO_DIAS = 28  # rangos cortos para no chocar con límites no documentados


class ErrorGarminPersonal(RuntimeError):
    pass


def es_clave_personal(valor: str | None) -> bool:
    """Un token de la librería antigua es JSON; la clave personal no."""
    return bool(valor) and not str(valor).strip().startswith("{")


def _extraer_token(r: requests.Response) -> tuple[str, float]:
    try:
        j = r.json()
    except ValueError:
        texto = r.text.strip().strip('"')
        if texto:
            return texto, time.time() + 23 * 3600
        raise ErrorGarminPersonal("Garmin devolvió una respuesta vacía al pedir el token.")
    if isinstance(j, str):
        return j, time.time() + 23 * 3600
    for k in ("access_token", "accessToken", "token", "personalApiToken", "value"):
        if isinstance(j.get(k), str) and j[k]:
            vida = j.get("expires_in") or j.get("expiresIn")
            caduca = time.time() + (float(vida) - 300 if vida else 23 * 3600)
            return j[k], caduca
    raise ErrorGarminPersonal(f"No encuentro el token en la respuesta de Garmin (campos: {sorted(j)[:8]}).")


class ClientePersonal:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip().strip("'\"")
        self._token, self._caduca = None, 0.0
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json", "User-Agent": "sensei-streamlit/1.0"})

    def _asegurar_token(self):
        if self._token and time.time() < self._caduca:
            return
        r = self.s.post(URL_TOKEN, headers={"Authorization": f"ApiKey {self.api_key}"}, timeout=20)
        if r.status_code in (401, 403):
            raise ErrorGarminPersonal("Garmin rechaza la clave API personal: puede haber caducado o haberse "
                                      "eliminado. Crea otra en Garmin Connect y pégala en los secretos.")
        if r.status_code >= 400:
            raise ErrorGarminPersonal(f"Garmin no dio el token (HTTP {r.status_code}).")
        self._token, self._caduca = _extraer_token(r)

    def get(self, ruta: str, params: dict | None = None):
        self._asegurar_token()
        r = self.s.get(BASE + ruta, params=params, timeout=30,
                       headers={"Authorization": f"Bearer {self._token}"})
        if r.status_code == 401:  # token caducado antes de tiempo: uno nuevo y reintento
            self._token = None
            self._asegurar_token()
            r = self.s.get(BASE + ruta, params=params, timeout=30,
                           headers={"Authorization": f"Bearer {self._token}"})
        if r.status_code == 204 or not r.content:
            return None
        if r.status_code >= 400:
            raise ErrorGarminPersonal(f"{ruta}: HTTP {r.status_code}")
        return r.json()


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _trozos(desde: date, hasta: date):
    a = desde
    while a <= hasta:
        b = min(hasta, a + timedelta(days=TROZO_DIAS - 1))
        yield a, b
        a = b + timedelta(days=1)


def _seguro(f, *a, **k):
    try:
        return f(*a, **k)
    except (ErrorGarminPersonal, requests.RequestException, ValueError):
        return None


def diarios(cli: ClientePersonal, desde: date, hasta: date) -> list[dict]:
    dias: dict[str, dict] = {}

    def dia(f):
        return dias.setdefault(f, {"fecha": f, "fc_reposo": None, "vfc": None, "vfc_estado": None,
                                   "sueno_h": None, "sueno_puntos": None, "body_battery_max": None,
                                   "estres_medio": None, "disposicion": None})

    for a, b in _trozos(desde, hasta):
        res = _seguro(cli.get, "/usersummary-service/v2/dailysummaries",
                      {"startDate": a.isoformat(), "endDate": b.isoformat()}) or {}
        for x in (res.get("data") if isinstance(res, dict) else res) or []:
            f = str(x.get("calendarDate", ""))[:10]
            if not f:
                continue
            d = dia(f)
            d["fc_reposo"] = _num((x.get("heartRate") or {}).get("restingValue"))
            d["body_battery_max"] = _num((x.get("bodyBattery") or {}).get("maxValue"))
            est = _num((x.get("stress") or {}).get("avgLevel"))
            d["estres_medio"] = est if est is not None and est >= 0 else None

        hrv = _seguro(cli.get, f"/hrv-service/hrv/daily/{a.isoformat()}/{b.isoformat()}") or {}
        for x in (hrv.get("hrvSummaries") if isinstance(hrv, dict) else hrv) or []:
            f = str(x.get("calendarDate", ""))[:10]
            if f:
                dia(f)["vfc"] = _num(x.get("lastNightAvg"))
                dia(f)["vfc_estado"] = x.get("status")

        sl = _seguro(cli.get, "/sleep-service/sleep/dailySleepSummariesByDate",
                     {"startDate": a.isoformat(), "endDate": b.isoformat()}) or []
        for x in sl if isinstance(sl, list) else []:
            f = str(x.get("calendarDate", ""))[:10]
            if not f:
                continue
            secs = _num(x.get("sleepTimeSeconds"))
            dia(f)["sueno_h"] = round(secs / 3600, 2) if secs else None
            dia(f)["sueno_puntos"] = _num(((x.get("sleepScores") or {}).get("overall") or {}).get("value"))
    return sorted(dias.values(), key=lambda d: d["fecha"])


def actividades(cli: ClientePersonal, desde: date, hasta: date) -> list[dict]:
    out, inicio = [], 0
    while True:
        lote = cli.get("/activitylist-service/activities/search/activities", {
            "startDate": desde.isoformat(), "endDate": hasta.isoformat(), "start": inicio, "limit": 100}) or []
        for a in lote:
            dur, dist = _num(a.get("duration")), _num(a.get("distance"))
            tipo = a.get("activityType") or {}
            out.append({
                "id": a.get("activityId"), "fecha": str(a.get("startTimeLocal", ""))[:10],
                "nombre": a.get("activityName"), "tipo": tipo.get("typeKey") or tipo.get("key"),
                "duracion_min": round(dur / 60, 1) if dur else None,
                "distancia_km": round(dist / 1000, 2) if dist else None,
                "fc_media": _num(a.get("averageHR")), "carga": _num(a.get("activityTrainingLoad")),
            })
        if len(lote) < 100:
            break
        inicio += 100
    return [x for x in out if x["id"] is not None and x["fecha"]]


def descargar_rango(cli: ClientePersonal, desde: date, hasta: date) -> tuple[list[dict], list[dict]]:
    return diarios(cli, desde, hasta), actividades(cli, desde, hasta)


def probar(cli: ClientePersonal) -> str:
    perfil = cli.get("/userprofile-service/userprofile/settings") or {}
    return json.dumps({k: perfil.get(k) for k in ("displayName",) if k in perfil}) or "ok"
