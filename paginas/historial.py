import json

import pandas as pd
import streamlit as st

from sensei.app_comun import almacen, datos, guardar, recargar
from sensei.modelo import PRUEBAS, formatear

st.title("Historial")
d = datos()
c1, c2 = st.columns(2)
if c1.button("Recargar datos", icon="🔄"):
    recargar()
    st.rerun()
c2.download_button("Descargar copia (.json)", json.dumps(d, ensure_ascii=False, indent=1),
                   file_name="sensei-datos.json", mime="application/json")
st.caption(f"Datos guardados en: {almacen().descripcion}. Cada cambio queda como commit (historial en git).")

TABLAS = {
    "Controles": ("controles", lambda c: {"fecha": c["fecha"], "prueba": PRUEBAS[c["prueba"]]["nombre"],
                                           "marca": formatear(c["prueba"], c["resultado"]),
                                           "tipo": "control" if c.get("protocolo_completo") else "referencia",
                                           "notas": c.get("notas", "")}),
    "Sesiones": ("sesiones", lambda s: {"fecha": s["fecha"], "tipo": s["tipo"], "min": s.get("duracion_min"),
                                         "RPE": s.get("rpe"), "dolor": s.get("dolor_max"), "notas": s.get("notas", "")}),
    "Check-ins": ("checkins", lambda c: {"fecha": c["fecha"], "sensación": c.get("sensacion"),
                                          "sueño": c.get("sueno_h"),
                                          "molestias": ", ".join(f"{m['zona']} {m['intensidad']}" for m in c.get("molestias", [])),
                                          "notas": c.get("notas", "")}),
    "Comidas": ("comidas", lambda c: {"fecha": c["fecha"], "alimento": c["nombre"], "g": c["gramos"],
                                       "prot": c.get("prot"), "kcal": c.get("kcal")}),
    "Actividades Garmin": ("garmin_actividades", lambda a: {"fecha": a["fecha"], "nombre": a.get("nombre"),
                                                            "tipo": a.get("tipo"), "min": a.get("duracion_min"),
                                                            "km": a.get("distancia_km"), "FC": a.get("fc_media"),
                                                            "carga": a.get("carga")}),
}

tabla = st.segmented_control("Ver", list(TABLAS), default="Controles")
clave, fila = TABLAS[tabla or "Controles"]
items = sorted(d[clave], key=lambda x: x["fecha"], reverse=True)
if not items:
    st.caption("Vacío.")
else:
    st.dataframe(pd.DataFrame([fila(x) for x in items]), hide_index=True, width="stretch")
    if clave != "garmin_actividades":
        with st.expander("Borrar un registro"):
            idx = st.selectbox("Registro", range(len(items)), format_func=lambda i: " · ".join(
                str(v) for v in list(fila(items[i]).values())[:4]))
            ok = st.checkbox("Confirmo que quiero borrarlo (queda en el historial de git del repo de datos)")
            if st.button("Borrar", type="secondary", disabled=not ok):
                objetivo = items[idx]

                def cambio(x):
                    x[clave] = [y for y in x[clave] if y != objetivo and (not y.get("id") or y.get("id") != objetivo.get("id"))]
                if guardar(cambio, f"Borrado en {clave} ({objetivo['fecha']})"):
                    st.success("Borrado.")
                    st.rerun()
