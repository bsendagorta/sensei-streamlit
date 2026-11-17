from datetime import date

import pandas as pd
import streamlit as st

from sensei import apis
from sensei.app_comun import EXAMEN_POR_DEFECTO, ajustes, guardar
from sensei.modelo import PRUEBAS
from sensei.reglas import UMBRALES_POR_DEFECTO

st.title("Ajustes")
a = ajustes()


def guardar_ajustes(nuevos: dict, mensaje: str):
    def cambio(x):
        x["ajustes"] = {**(x.get("ajustes") or {}), **nuevos}
    if guardar(cambio, mensaje):
        st.success("Guardado.")

st.subheader("General")
with st.form("general"):
    examen = st.date_input("Fecha del examen (provisional)", date.fromisoformat(a["fecha_examen"]), format="DD/MM/YYYY")
    peso = st.number_input("Peso (kg), para el objetivo de proteína", 30.0, 200.0, value=None if a.get("peso_kg") is None else float(a["peso_kg"]))
    pmax = st.number_input("Puntos máximos por prueba (para la nota /10 orientativa)", 1.0, 100.0,
                           value=float(a.get("puntos_max") or 6))
    if st.form_submit_button("Guardar", type="primary"):
        guardar_ajustes({"fecha_examen": examen.isoformat(), "peso_kg": peso, "puntos_max": pmax}, "Ajustes generales")
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
st.caption("Escribe cada escalón: la marca mínima (o máxima, en las pruebas de tiempo) y los puntos que da. "
           "Tiempos en segundos (1500 m: 5:12 → 312). Como el baremo es provisional, aquí lo cambias tú.")
prueba = st.selectbox("Prueba", list(PRUEBAS), format_func=lambda p: PRUEBAS[p]["nombre"])
actual = pd.DataFrame(a["baremo"].get(prueba) or [], columns=["marca", "puntos"])
editado = st.data_editor(actual, num_rows="dynamic", width="stretch", key=f"bar_{prueba}",
                         column_config={"marca": st.column_config.NumberColumn(f"Marca ({PRUEBAS[prueba]['unidad']})"),
                                        "puntos": st.column_config.NumberColumn("Puntos")})
if st.button("Guardar baremo de esta prueba", type="primary"):
    filas = [{"marca": float(r.marca), "puntos": float(r.puntos)} for r in editado.itertuples()
             if pd.notna(r.marca) and pd.notna(r.puntos)]
    baremo = {**a["baremo"], prueba: sorted(filas, key=lambda f: f["puntos"])}
    guardar_ajustes({"baremo": baremo}, f"Baremo {prueba}")

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
