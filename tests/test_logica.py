from datetime import date, timedelta

import pytest

from sensei.carga import acwr, carga_diaria_srpe, linea_base
from sensei.garmin import fusionar
from sensei.almacen import AlmacenLocal, datos_vacios
from sensei.modelo import formatear, parse_resultado
from sensei.prevision import prevision, puntos, puntos_prevision
from sensei.reglas import AMBAR, ROJO, VERDE, evaluar

HOY = date(2026, 11, 17)


def test_parse_resultado():
    assert parse_resultado("1500m", "5:12") == 312
    assert parse_resultado("1500m", "312") == 312
    assert parse_resultado("60m", "7,85") == pytest.approx(7.85)
    assert parse_resultado("dominadas", "14") == 14
    with pytest.raises(ValueError):
        parse_resultado("dominadas", "14,5")
    with pytest.raises(ValueError):
        parse_resultado("1500m", "5:75")
    with pytest.raises(ValueError):
        parse_resultado("60m", "rápido")


def test_formatear():
    assert formatear("1500m", 312) == "5:12"
    assert formatear("1500m", 312.5) == "5:12,5"
    assert formatear("60m", 7.85) == "7,85 s" and formatear("dominadas", 21) == "21 reps"
    assert formatear("dominadas", None) == "—"


BAREMO_DOM = [{"marca": 8, "puntos": 1}, {"marca": 12, "puntos": 3}, {"marca": 18, "puntos": 6}]
BAREMO_60 = [{"marca": 8.4, "puntos": 1}, {"marca": 7.9, "puntos": 3}, {"marca": 7.4, "puntos": 6}]


def test_puntos_mayor_y_menor():
    assert puntos("dominadas", 13, BAREMO_DOM) == 3
    assert puntos("dominadas", 5, BAREMO_DOM) == 0
    assert puntos("60m", 7.85, BAREMO_60) == 3
    assert puntos("60m", 8.6, BAREMO_60) == 0
    assert puntos("60m", 7.85, []) is None


def test_prevision_prefiere_controles_y_no_extrapola():
    controles = [
        {"fecha": "2026-10-01", "prueba": "dominadas", "resultado": 10, "protocolo_completo": True},
        {"fecha": "2026-11-01", "prueba": "dominadas", "resultado": 12, "protocolo_completo": True},
        {"fecha": "2026-11-10", "prueba": "dominadas", "resultado": 15, "protocolo_completo": False},
    ]
    p = prevision("dominadas", controles)
    assert p["fuente"] == "control" and p["central"] == 12 and p["rango"] == (10, 12)
    solo_ref = prevision("dominadas", [controles[2]])
    assert solo_ref["fuente"] == "referencia" and solo_ref["aviso"]
    assert solo_ref["rango"] == pytest.approx((14.25, 15.75))
    assert prevision("cuerda", controles)["central"] is None
    pp = puntos_prevision(p, BAREMO_DOM)
    assert pp == {"central": 3, "peor": 1, "mejor": 3}


def test_acwr_requiere_historial():
    ses = [{"fecha": (HOY - timedelta(days=i)).isoformat(), "duracion_min": 60, "rpe": 5} for i in range(10)]
    assert acwr(carga_diaria_srpe(ses), HOY)["ratio"] is None
    ses = [{"fecha": (HOY - timedelta(days=i)).isoformat(), "duracion_min": 60, "rpe": 5} for i in range(28)]
    assert acwr(carga_diaria_srpe(ses), HOY)["ratio"] == pytest.approx(1.0)
    pico = ses + [{"fecha": (HOY - timedelta(days=i)).isoformat(), "duracion_min": 60, "rpe": 8} for i in range(7)]
    assert acwr(carga_diaria_srpe(pico), HOY)["ratio"] > 1.3


def test_linea_base_excluye_hoy():
    serie = {HOY - timedelta(days=i): 45.0 for i in range(1, 15)}
    serie[HOY] = 60.0
    assert linea_base(serie, HOY)["media"] == 45.0


def _datos_base():
    d = datos_vacios()
    for i in range(1, 21):
        f = (HOY - timedelta(days=i)).isoformat()
        d["garmin_diario"].append({"fecha": f, "fc_reposo": 45 + (i % 2), "vfc": 70 + (i % 3) * 2, "sueno_h": 7.5})
    return d


def test_semaforo_verde():
    d = _datos_base()
    d["garmin_diario"].append({"fecha": HOY.isoformat(), "fc_reposo": 45, "vfc": 72, "sueno_h": 7.8})
    d["checkins"].append({"fecha": HOY.isoformat(), "sensacion": 7, "molestias": []})
    r = evaluar(d, HOY)
    assert r["nivel"] == VERDE


def test_semaforo_pulso_alto_y_dolor():
    d = _datos_base()
    d["garmin_diario"].append({"fecha": HOY.isoformat(), "fc_reposo": 54, "vfc": 72, "sueno_h": 7.8})
    d["checkins"].append({"fecha": HOY.isoformat(), "sensacion": 7, "molestias": []})
    assert evaluar(d, HOY)["nivel"] == ROJO
    d["garmin_diario"][-1]["fc_reposo"] = 45
    d["checkins"][-1]["molestias"] = [{"zona": "Rodilla izq.", "intensidad": 3}]
    assert evaluar(d, HOY)["nivel"] == AMBAR
    d["checkins"][-1]["molestias"] = [{"zona": "Rodilla izq.", "intensidad": 5}]
    assert evaluar(d, HOY)["nivel"] == ROJO


def test_molestia_persistente_pide_fisio():
    d = _datos_base()
    for i in range(3):
        d["checkins"].append({"fecha": (HOY - timedelta(days=i)).isoformat(), "sensacion": 7,
                              "molestias": [{"zona": "Lumbar", "intensidad": 1}]})
    r = evaluar(d, HOY)
    assert r["zonas_fisio"] == ["Lumbar"]
    assert next(s for s in r["senales"] if s.nombre == "Molestias").nivel == AMBAR


def test_tres_ambares_es_rojo():
    d = _datos_base()
    d["garmin_diario"].append({"fecha": HOY.isoformat(), "fc_reposo": 51, "vfc": 72, "sueno_h": 5.5})
    d["checkins"].append({"fecha": HOY.isoformat(), "sensacion": 4, "molestias": []})
    r = evaluar(d, HOY)
    assert r["nivel"] == ROJO and r["motivo_extra"]


def test_sin_datos_no_inventa():
    r = evaluar(datos_vacios(), HOY)
    assert r["nivel"] is None and "Sensación" in r["faltan"]


def test_fusionar_garmin_no_borra():
    d = datos_vacios()
    d["checkins"].append({"fecha": "2026-11-16", "sensacion": 6, "molestias": []})
    fusionar(d, [{"fecha": "2026-11-16", "fc_reposo": 46, "vfc": None}], [{"id": 1, "fecha": "2026-11-16", "carga": 80}], "t1")
    fusionar(d, [{"fecha": "2026-11-16", "fc_reposo": None, "vfc": 70}], [], "t2")
    g = d["garmin_diario"][0]
    assert g["fc_reposo"] == 46 and g["vfc"] == 70
    assert len(d["checkins"]) == 1 and d["garmin_actividades"][0]["carga"] == 80


def test_almacen_local(tmp_path):
    a = AlmacenLocal(str(tmp_path / "datos.json"))
    a.modificar(lambda d: d["controles"].append({"fecha": "2026-11-01", "prueba": "banca", "resultado": 25}), "x")
    assert a.cargar()["controles"][0]["resultado"] == 25


def test_reimportar_no_pisa_ediciones_ni_borrados():
    from sensei.importar_sensei import importar
    copia = {"schema": "rumbo-enero-backup-v1", "state": {"nutrition": {"weight": 92, "days": {}, "entries": [
        {"id": "a", "date": "2026-11-17", "meal": "Cena", "name": "Tortilla", "quantity": 1, "basis": "portion",
         "kcal": 280, "protein": 19, "carbs": 1, "fat": 22},
        {"id": "b", "date": "2026-11-17", "meal": "Cena", "name": "Bacon", "quantity": 1, "basis": "portion",
         "kcal": 280, "protein": 14, "carbs": 1, "fat": 25}]}}}
    d = datos_vacios()
    importar(d, copia)
    t = next(c for c in d["comidas"] if c["id"] == "sensei-a")
    t.update(nombre="Tortilla con bacon", kcal=560, origen="web")
    d["comidas"] = [c for c in d["comidas"] if c["id"] != "sensei-b"]
    d["borrados_sensei"] = ["sensei-b"]
    importar(d, copia)
    assert [c["nombre"] for c in d["comidas"]] == ["Tortilla con bacon"]
