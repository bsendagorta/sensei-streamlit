import pandas as pd
import plotly.express as px
import streamlit as st

from sensei.app_comun import ajustes, datos, estilo_grafico
from sensei.modelo import PRUEBAS, formatear
from sensei.prevision import prevision, puntos_prevision

st.title("Pruebas y previsión")
d, a = datos(), ajustes()
pmax = a.get("puntos_max") or 6
st.caption("Previsión = tus últimos 1–3 controles reales (con uno solo, ±5 %). No se suman mejoras que "
           "no hayas demostrado. Sin baremo cargado en Ajustes no se calculan puntos.")

filas = []
for p, info in PRUEBAS.items():
    prev = prevision(p, d["controles"])
    pp = puntos_prevision(prev, a["baremo"].get(p))
    filas.append((p, info, prev, pp))

# Prioridades: menos puntos primero (solo si hay baremo y marca)
con_puntos = [(p, pp["central"]) for p, _, prev, pp in filas if pp]
if con_puntos:
    orden = sorted(con_puntos, key=lambda x: x[1])
    st.markdown("**Prioridad (menos puntos):** " + " · ".join(f"{PRUEBAS[p]['nombre']} ({v:g})" for p, v in orden[:3]))
    total = sum(v for _, v in con_puntos)
    st.caption(f"Suma prevista en {len(con_puntos)} pruebas con baremo y marca: {total:g} puntos.")

for p, info, prev, pp in filas:
    with st.container(border=True):
        st.markdown(f"### {info['nombre']}")
        if prev["central"] is None:
            st.caption(prev["aviso"] + " Registra un control en «Registrar».")
            continue
        lo, hi = prev["rango"]
        mejor_lo, mejor_hi = (lo, hi) if info["mejor"] == "mayor" else (hi, lo)
        c1, c2 = st.columns(2)
        c1.metric("Previsión", formatear(p, prev["central"]),
                  help=f"Rango {formatear(p, mejor_lo)} – {formatear(p, mejor_hi)}")
        if pp:
            c2.metric("Puntos", f"{pp['central']:g}", help=f"Rango {pp['peor']:g}–{pp['mejor']:g} · "
                      f"nota orientativa {pp['central'] * 10 / pmax:.1f}/10")
        else:
            c2.metric("Puntos", "—", help="Carga el baremo en Ajustes")
        st.caption(f"{'Control' if prev['fuente'] == 'control' else 'Referencia de entrenamiento'} · "
                   f"{prev['n']} marca(s) · última {prev['fecha']}" + (f" · {prev['aviso']}" if prev["aviso"] else ""))
        hist = [c for c in d["controles"] if c["prueba"] == p]
        if len(hist) >= 2:
            df = pd.DataFrame(hist)
            df["fecha"] = pd.to_datetime(df["fecha"])
            df["tipo"] = df["protocolo_completo"].map({True: "control", False: "referencia"})
            fig = px.line(df.sort_values("fecha"), x="fecha", y="resultado", markers=True,
                          hover_data={"tipo": True})
            if info["mejor"] == "menor":
                fig.update_yaxes(autorange="reversed")
            st.plotly_chart(estilo_grafico(fig, info["unidad"]), width="stretch",
                            config={"displayModeBar": False})
