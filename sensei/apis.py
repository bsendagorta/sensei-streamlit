"""APIs abiertas y gratuitas (sin clave):

- Open-Meteo (https://open-meteo.com): previsión horaria, calidad del aire y geocodificación.
- MET Norway (https://api.met.no): previsión de respaldo si Open-Meteo no responde.
- Open Food Facts (https://world.openfoodfacts.org): composición de alimentos por nombre o código de barras.
"""
from __future__ import annotations

import socket
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import urllib3.util.connection as _conn

# En algunos servidores en la nube IPv6 cuelga las conexiones: forzamos IPv4.
_conn.allowed_gai_family = lambda: socket.AF_INET

UA = {"User-Agent": "sensei-streamlit/1.0 (preparacion pruebas fisicas; github.com/bsendagorta/sensei-streamlit)"}
TIMEOUT = 10


def geocodificar(nombre: str) -> list[dict]:
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                     params={"name": nombre, "count": 5, "language": "es", "format": "json"},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [{"nombre": f"{x['name']}, {x.get('admin1', '')} ({x.get('country_code', '')})",
             "lat": x["latitude"], "lon": x["longitude"]} for x in r.json().get("results", [])]


def tiempo_horario(lat: float, lon: float) -> list[dict]:
    """Próximas 24 h. Open-Meteo y, si falla, MET Norway."""
    try:
        return _open_meteo(lat, lon)
    except requests.RequestException:
        return _met_norway(lat, lon)


def _met_norway(lat: float, lon: float) -> list[dict]:
    r = requests.get("https://api.met.no/weatherapi/locationforecast/2.0/compact",
                     params={"lat": round(lat, 4), "lon": round(lon, 4)}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    madrid = ZoneInfo("Europe/Madrid")
    out = []
    for x in r.json()["properties"]["timeseries"][:24]:
        det = x["data"]["instant"]["details"]
        lluvia_mm = ((x["data"].get("next_1_hours") or {}).get("details") or {}).get("precipitation_amount")
        hora = datetime.fromisoformat(x["time"].replace("Z", "+00:00")).astimezone(madrid).replace(tzinfo=None)
        t = det.get("air_temperature")
        out.append({"hora": hora, "temp": t, "sensacion": t,  # MET no da sensación térmica
                    "lluvia": None if lluvia_mm is None else (80 if lluvia_mm >= 0.5 else 0),
                    "viento": None if det.get("wind_speed") is None else det["wind_speed"] * 3.6,
                    "aqi": None, "fuente": "MET Norway"})
    return out


def _open_meteo(lat: float, lon: float) -> list[dict]:
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "timezone": "Europe/Madrid", "forecast_hours": 24,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,wind_speed_10m",
    }, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    h = r.json()["hourly"]
    aqi = {}
    try:
        q = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": lat, "longitude": lon, "timezone": "Europe/Madrid", "forecast_hours": 24,
            "hourly": "european_aqi"}, headers=UA, timeout=TIMEOUT)
        q.raise_for_status()
        qh = q.json()["hourly"]
        aqi = dict(zip(qh["time"], qh["european_aqi"]))
    except requests.RequestException:
        pass
    return [{"hora": datetime.fromisoformat(t), "temp": h["temperature_2m"][i],
             "sensacion": h["apparent_temperature"][i], "lluvia": h["precipitation_probability"][i],
             "viento": h["wind_speed_10m"][i], "aqi": aqi.get(t), "fuente": "Open-Meteo"}
            for i, t in enumerate(h["time"])]


def puntuar_hora(x: dict) -> tuple[float, list[str]]:
    """Penalización (menor = mejor) y avisos para entrenar fuera a esa hora."""
    pen, avisos = 0.0, []
    st = x.get("sensacion")
    if st is not None:
        if st > 30:
            pen += (st - 30) * 3
            avisos.append(f"calor {st:.0f} °C")
        elif st < 2:
            pen += (2 - st) * 1.5
            avisos.append(f"frío {st:.0f} °C")
        pen += abs(st - 14) * 0.2
    if (x.get("lluvia") or 0) >= 50:
        pen += 6
        avisos.append(f"lluvia {x['lluvia']} %")
    if (x.get("viento") or 0) >= 25:
        pen += 4
        avisos.append(f"viento {x['viento']:.0f} km/h")
    if x.get("aqi") is not None and x["aqi"] > 60:
        pen += (x["aqi"] - 60) / 5
        avisos.append(f"aire {'malo' if x['aqi'] > 80 else 'regular'} (ICA {x['aqi']:.0f})")
    return pen, avisos


def mejores_horas(horas: list[dict], desde: int = 7, hasta: int = 22, n: int = 3) -> list[dict]:
    candidatas = [dict(x, pen=puntuar_hora(x)[0], avisos=puntuar_hora(x)[1])
                  for x in horas if desde <= x["hora"].hour <= hasta]
    return sorted(candidatas, key=lambda x: x["pen"])[:n]


def _alimento(p: dict) -> dict:
    n = p.get("nutriments", {}) or {}

    def num(k):
        v = n.get(k)
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None
    return {"codigo": p.get("code"), "nombre": (p.get("product_name") or "").strip() or "(sin nombre)",
            "marca": p.get("brands") or "", "kcal_100": num("energy-kcal_100g"),
            "prot_100": num("proteins_100g"), "hc_100": num("carbohydrates_100g"),
            "grasa_100": num("fat_100g")}


def buscar_alimentos(texto: str, n: int = 10) -> list[dict]:
    texto = texto.strip()
    campos = "code,product_name,brands,nutriments"
    if texto.isdigit() and len(texto) >= 8:
        r = requests.get(f"https://world.openfoodfacts.org/api/v2/product/{texto}.json",
                         params={"fields": campos}, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        return [_alimento(j["product"])] if j.get("status") == 1 else []
    r = requests.get("https://world.openfoodfacts.org/cgi/search.pl", params={
        "search_terms": texto, "search_simple": 1, "action": "process", "json": 1,
        "page_size": n, "fields": campos, "lc": "es", "cc": "es"}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [_alimento(p) for p in r.json().get("products", [])]
