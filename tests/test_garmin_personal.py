from datetime import date

import pytest

from sensei import garmin_personal as gp


class Resp:
    def __init__(self, status=200, data=None, text=None):
        self.status_code, self._data = status, data
        self.text = text if text is not None else ("" if data is None else "x")
        self.content = b"x" if (data is not None or text) else b""

    def json(self):
        if self._data is None:
            raise ValueError
        return self._data


class SesionFalsa:
    def __init__(self, token_resp):
        self.headers, self.token_resp, self.llamadas = {}, token_resp, []

    def post(self, url, headers=None, timeout=None):
        assert headers["Authorization"].startswith("ApiKey ")
        return self.token_resp

    def get(self, url, params=None, timeout=None, headers=None):
        assert headers["Authorization"] == "Bearer TOK"
        self.llamadas.append((url, params))
        ruta = url.replace(gp.BASE, "")
        if ruta.startswith("/usersummary-service/v2/dailysummaries"):
            return Resp(data={"data": [{"calendarDate": "2026-11-16", "heartRate": {"restingValue": 46},
                                        "bodyBattery": {"maxValue": 88}, "stress": {"avgLevel": -1}}]})
        if ruta.startswith("/hrv-service/hrv/daily/"):
            return Resp(data={"hrvSummaries": [{"calendarDate": "2026-11-16", "lastNightAvg": 71, "status": "BALANCED"}]})
        if ruta.startswith("/sleep-service/"):
            return Resp(data=[{"calendarDate": "2026-11-16", "sleepTimeSeconds": 27000,
                               "sleepScores": {"overall": {"value": 81}}}])
        if ruta.startswith("/activitylist-service/"):
            return Resp(data=[{"activityId": 9, "startTimeLocal": "2026-11-16 18:00:00", "activityName": "Series",
                               "activityType": {"typeKey": "running"}, "duration": 2700, "distance": 8000,
                               "averageHR": 152, "activityTrainingLoad": 110}])
        return Resp(status=404)


def _cliente(token_resp):
    c = gp.ClientePersonal("'clave'")
    c.s = SesionFalsa(token_resp)
    return c


@pytest.mark.parametrize("resp", [Resp(data={"access_token": "TOK", "expires_in": 86400}),
                                  Resp(data={"accessToken": "TOK"}), Resp(text='"TOK"')])
def test_token_formatos(resp):
    c = _cliente(resp)
    d, a = gp.descargar_rango(c, date(2026, 11, 16), date(2026, 11, 16))
    assert d[0]["fc_reposo"] == 46 and d[0]["vfc"] == 71 and d[0]["sueno_h"] == 7.5
    assert d[0]["estres_medio"] is None  # -1 de Garmin = sin dato, nunca 0
    assert d[0]["disposicion"] is None
    assert a[0]["tipo"] == "running" and a[0]["carga"] == 110 and a[0]["duracion_min"] == 45


def test_clave_rechazada():
    c = _cliente(Resp(status=401, data={}))
    with pytest.raises(gp.ErrorGarminPersonal):
        c.get("/x")


def test_trozos_de_28_dias():
    c = _cliente(Resp(data={"access_token": "TOK"}))
    gp.diarios(c, date(2026, 8, 1), date(2026, 11, 16))
    rangos = [p for u, p in c.s.llamadas if "dailysummaries" in u]
    assert len(rangos) == 4 and rangos[0]["startDate"] == "2026-08-01"


def test_es_clave_personal():
    assert gp.es_clave_personal("abc-123.def")
    assert not gp.es_clave_personal('{"di_token": "x"}')
    assert not gp.es_clave_personal(None)
