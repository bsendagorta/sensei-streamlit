from datetime import date

import pandas as pd
import streamlit as st

from sensei import apis, ui
from sensei.app_comun import EXAMEN_POR_DEFECTO, ajustes, guardar
from sensei.baremo import TESTS, baremo
from sensei.modelo import PRUEBAS, formatear
from sensei.reglas import UMBRALES_POR_DEFECTO

ui.pagina("Ajustes", "ajustes")
ui.html('<div class="section-head"><div><h1>Ajustes</h1><p>Fecha del examen, lugar, baremo y umbrales del semáforo.</p></div></div>')
a = ajustes()


def guardar_ajustes(nuevos: dict, mensaje: str):
    def cambio(x):
        x["ajustes"] = {**(x.get("ajustes") or {}), **nuevos}
    if guardar(cambio, mensaje):
        st.success("Guardado.")

st.subheader("General")
with st.form("general"):
    examen = st.date_input("Fecha del examen (provisional)", date.fromisoformat(a["fecha_examen"]), format="DD/MM/YYYY")
    peso = st.number_input("Peso (kg), para las referencias de nutrición", 30.0, 200.0, value=None if a.get("peso_kg") is None else float(a["peso_kg"]))
    if st.form_submit_button("Guardar", type="primary"):
        guardar_ajustes({"fecha_examen": examen.isoformat(), "peso_kg": peso}, "Ajustes generales")
st.caption(f"Por defecto {EXAMEN_POR_DEFECTO.strftime('%d/%m/%Y')}.")

st.subheader("Lugar de entrenamiento (para el tiempo)")
st.caption(f"Ahora: {a['lugar']['nombre']}")
q = st.text_input("Buscar municipio")
if q:
    try:
        res = apis.geocodificar(q)
    except Exception as e:
        res = []
        st.warning(f"No se pudo buscar ({type(e).__name__}).")
    if res:
        i = st.selectbox("Resultado", range(len(res)), format_func=lambda i: res[i]["nombre"])
        if st.button("Usar este lugar"):
            guardar_ajustes({"lugar": res[i]}, "Lugar")

st.subheader("Baremo")
st.caption("El mismo de Sensei.app: la marca mínima da 3 puntos y la máxima 6; nota sobre 10 = puntos × 10 / 6. "
           "Tiempos en segundos (1500 m: 6:11 → 371). Como es provisional, aquí puedes cambiarlo.")
filas = pd.DataFrame([{"prueba": PRUEBAS[p]["nombre"], "mínimo (3 pt)": baremo(p, a)["min"], "máximo (6 pt)": baremo(p, a)["max"]}
                      for p in TESTS])
editado = st.data_editor(filas, disabled=["prueba"], hide_index=True, width="stretch", key="baremo_sensei")
c1, c2 = st.columns(2)
if c1.button("Guardar baremo", type="primary"):
    nuevo = {p: {"min": float(r["mínimo (3 pt)"]), "max": float(r["máximo (6 pt)"])}
             for p, (_, r) in zip(TESTS, editado.iterrows())}
    if any(v["min"] == v["max"] for v in nuevo.values()):
        st.error("Mínimo y máximo no pueden ser iguales.")
    else:
        guardar_ajustes({"baremo_sensei": nuevo}, "Baremo")
if c2.button("Volver al baremo de Sensei.app"):
    guardar_ajustes({"baremo_sensei": {}}, "Baremo por defecto")

st.subheader("Umbrales del semáforo")
st.caption("Valores por defecto prudentes. Cámbialos solo si ves que te avisan de más o de menos.")
u = a["umbrales"]
ETIQUETAS = {
    "fc_reposo_ambar": "Pulso reposo: ámbar si sube (lpm sobre tu media)",
    "fc_reposo_rojo": "Pulso reposo: rojo si sube (lpm)",
    "fc_reposo_absoluto": "Pulso reposo: límite fijo (lpm, opcional)",
    "vfc_sd_ambar": "VFC: ámbar si baja (desviaciones típicas)",
    "vfc_sd_rojo": "VFC: rojo si baja (DT)",
    "sueno_ambar_h": "Sueño: ámbar por debajo de (h)",
    "sueno_rojo_h": "Sueño: rojo por debajo de (h)",
    "sensacion_ambar": "Sensación: ámbar si ≤",
    "sensacion_rojo": "Sensación: rojo si ≤",
    "dolor_ambar": "Dolor: ámbar si ≥",
    "dolor_rojo": "Dolor: rojo si ≥",
    "acwr_ambar": "Carga agudo:crónico: ámbar si >",
    "acwr_rojo": "Carga agudo:crónico: rojo si >",
    "acwr_bajo": "Carga agudo:crónico: aviso de carga baja si <",
    "disposicion_ambar": "Disposición Garmin: ámbar si <",
    "ambares_para_rojo": "Nº de ámbar a la vez que cuenta como rojo",
}
with st.form("umbrales"):
    nuevos = {}
    for k, etiqueta in ETIQUETAS.items():
        nuevos[k] = st.number_input(etiqueta, value=None if u.get(k) is None else float(u[k]),
                                    help=f"Por defecto: {UMBRALES_POR_DEFECTO[k]}")
    c1, c2 = st.columns(2)
    if c1.form_submit_button("Guardar umbrales", type="primary"):
        guardar_ajustes({"umbrales": nuevos}, "Umbrales")
    if c2.form_submit_button("Volver a los de por defecto"):
        guardar_ajustes({"umbrales": {}}, "Umbrales por defecto")
