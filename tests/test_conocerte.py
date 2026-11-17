import random
from datetime import date, timedelta

from sensei.almacen import datos_vacios
from sensei.conocerte import categoria, modelo, respuesta_por_tipo, simular

HOY = date(2026, 11, 17)


def _datos(n=200):
    """Series al día D bajan la VFC de D+1 unos 8 ms; la fuerza no la cambia."""
    random.seed(7)
    d = datos_vacios()
    efecto = {}
    for i in range(n, -1, -1):
        f = HOY - timedelta(days=i)
        if i % 5 == 0:
            d["garmin_actividades"].append({"id": i, "fecha": f.isoformat(), "tipo": "track_running", "nombre": "Series",
                                            "duracion_min": 50, "carga": 120})
            efecto[f + timedelta(days=1)] = -8
        elif i % 5 == 2:
            d["garmin_actividades"].append({"id": i, "fecha": f.isoformat(), "tipo": "strength_training",
                                            "duracion_min": 60, "carga": 30})
    for i in range(n, -1, -1):
        f = HOY - timedelta(days=i)
        d["garmin_diario"].append({"fecha": f.isoformat(), "vfc": 70 + efecto.get(f, 0) + random.gauss(0, 2),
                                   "fc_reposo": 45 + random.gauss(0, 1), "sueno_h": 7.5, "estres_medio": 25})
    return d


def test_categoria():
    assert categoria({"tipo": "strength_training"}) == "fuerza"
    assert categoria({"tipo": "running", "nombre": "Series 4x800"}) == "series"
    assert categoria({"tipo": "running", "nombre": "Rodaje"}) == "carrera"
    assert categoria({"tipo": "hiking"}) == "otro"


def test_aprende_el_efecto_de_las_series():
    d = _datos()
    m = modelo(d, "vfc")
    assert m["ok"] and m["util"] and m["mae"] < m["mae_media"]
    series = next(e for e in m["efectos"] if e["variable"] == "carga_series")
    fuerza = next(e for e in m["efectos"] if e["variable"] == "carga_fuerza")
    assert series["efecto"] < -5 and abs(fuerza["efecto"]) < 2
    r = {x["tipo"]: x for x in respuesta_por_tipo(d)}
    assert r["series"]["vfc_d1"]["media"] < -5 and abs(r["series"]["vfc_d1"]["media"]) > r["series"]["vfc_d1"]["ic"]


def test_simular_series_peor_que_descanso():
    d = _datos()
    ms = {"vfc": modelo(d, "vfc")}
    assert simular(d, ms, HOY, "series", 50)["vfc"]["dif"] < simular(d, ms, HOY, None, 0)["vfc"]["dif"] - 4


def test_pocos_datos_no_inventa():
    assert not modelo(_datos(n=30), "vfc")["ok"]


def test_recomendacion_respeta_recuperacion_y_molestias():
    from sensei.evaluacion import recomendar_manana
    d = _datos()
    ms = {"vfc": modelo(d, "vfc")}
    rec = recomendar_manana(d, HOY, ms, {})
    assert rec["recomendacion"]["pasos"]
    d["checkins"].append({"fecha": HOY.isoformat(), "sensacion": 5,
                          "molestias": [{"zona": "Rodilla izq.", "intensidad": 5}]})
    rec2 = recomendar_manana(d, HOY, ms, {})
    assert rec2["recomendacion"]["clave"] not in ("series_1500", "velocidad", "carrera_suave")
