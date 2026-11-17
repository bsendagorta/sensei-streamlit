from sensei.baremo import calificar, num, texto_control


def test_coincide_con_sensei_app():
    # Valores de la pantalla «Controles» de Sensei.app (17/11/2026)
    assert texto_control("banca", 35) == "4,8 pt · 7,9/10 equivalente"
    assert texto_control("dominadas", 21) == "4,8 pt · 8/10 equivalente"
    assert texto_control("1500m", 334.1) == "4,2 pt · 7/10 equivalente"
    assert texto_control("flexibilidad", 26) == "4,3 pt · 7,1/10 equivalente"
    assert texto_control("cuerda", 5.9) == "5,6 pt · 9,4/10 equivalente"
    assert texto_control("dominadas", 12) == "Bajo mínimo"


def test_calificar_rango():
    g = calificar("banca", (33.25, 36.75))
    assert g["tipo"] == "nota" and num(g["etiqueta"]) == "7,9" and num(g["rango"][0]) == "7,2"
    assert calificar("banca", (20, 25))["etiqueta"] == "<5"
    assert calificar("banca", None)["tipo"] == "desconocido"
