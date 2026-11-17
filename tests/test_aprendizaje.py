import random
from datetime import date, timedelta

from sensei.almacen import datos_vacios
from sensei.aprendizaje import (eficiencia_carrera, modelo_sensacion, predecir_sensacion, puntos_debiles,
                                recuperacion_personal, tendencia)

HOY = date(2026, 11, 17)


def _sintetico(n=90, senal=True):
    random.seed(3)
    d = datos_vacios()
    for i in range(n, -1, -1):
        f = HOY - timedelta(days=i)
        duro = i % 4 == 0
        vfc = 70 + random.gauss(0, 6)
        d["garmin_diario"].append({"fecha": f.isoformat(), "fc_reposo": 45 + random.gauss(0, 1) + (3 if (i + 1) % 4 == 0 else 0),
                                   "vfc": vfc, "sueno_h": 7 + random.gauss(0, 0.6)})
        d["garmin_actividades"].append({"id": i, "fecha": f.isoformat(), "tipo": "running", "carga": 200 if duro else 60,
                                        "distancia_km": 8, "duracion_min": 45 - (n - i) * 0.03, "fc_media": 150})
        sens = 6 + ((vfc - 70) / 6 if senal else 0) + random.gauss(0, 0.5 if senal else 1.5)
        d["checkins"].append({"fecha": f.isoformat(), "sensacion": round(min(10, max(1, sens))), "molestias": []})
    return d


def test_tendencia_ic():
    t = tendencia([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    assert t["pendiente"] == 1 and t["significativa"]
    assert tendencia([0, 1], [1, 2]) is None
    ruido = tendencia([0, 1, 2, 3], [10, 12, 9, 11])
    assert not ruido["significativa"]


def test_modelo_aprende_y_se_valida():
    d = _sintetico()
    m = modelo_sensacion(d)
    assert m["ok"] and m["util"] and m["mae"] < m["mae_ref"]
    assert m["efectos"][0]["variable"] == "vfc_dif" and m["efectos"][0]["efecto"] > 0
    assert 1 <= predecir_sensacion(m, d, HOY) <= 10


def test_modelo_sin_senal_no_se_usa():
    m = modelo_sensacion(_sintetico(senal=False))
    assert m["ok"] and not m["util"]


def test_modelo_pocos_datos():
    assert not modelo_sensacion(_sintetico(n=10))["ok"]


def test_recuperacion_y_eficiencia():
    d = _sintetico()
    r = recuperacion_personal(d)
    assert r["ok"] and r["respuesta"][0]["fc_reposo"] > 2
    e = eficiencia_carrera(d)
    assert e["ok"] and e["tendencia"]["significativa"] and e["tendencia"]["pendiente"] > 0


def test_puntos_debiles_orden():
    d = datos_vacios()
    d["controles"] = [{"fecha": "2026-11-01", "prueba": "dominadas", "resultado": 10, "protocolo_completo": True},
                      {"fecha": "2026-11-01", "prueba": "banca", "resultado": 30, "protocolo_completo": True}]
    baremo = {"dominadas": [{"marca": 8, "puntos": 1}, {"marca": 18, "puntos": 6}],
              "banca": [{"marca": 20, "puntos": 1}, {"marca": 30, "puntos": 5}]}
    r = puntos_debiles(d, baremo)
    assert r[0]["sin_datos"]  # pruebas sin marcas primero
    con = [x for x in r if not x["sin_datos"]]
    assert con[0]["prueba"] == "dominadas"
