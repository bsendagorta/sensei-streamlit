from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from sensei.app_comun import datos, estilo_grafico, hoy
from sensei.carga import acwr, carga_diaria_garmin, carga_diaria_srpe

st.title("Carga y recuperación")
d, h = datos(), hoy()
dias = st.segmented_control("Periodo", [14, 28, 60, 120], default=28, format_func=lambda x: f"{x} días")
desde = h - timedelta(days=(dias or 28) - 1)

# Carga
st.subheader("Carga de entrenamiento")
for nombre, carga in (("Garmin", carga_diaria_garmin(d["garmin_actividades"])),
                      ("sRPE (tus sesiones)", carga_diaria_srpe(d["sesiones"]))):
    if not carga:
        continue
    r = acwr(carga, h)
    serie = pd.DataFrame({"fecha": pd.date_range(desde, h)})
    serie["carga"] = [carga.get(f.date(), 0.0) for f in serie["fecha"]]
    st.markdown(f"**{nombre}** · agudo:crónico "
                + (f"**{r['ratio']:.2f}**" if r["ratio"] is not None else f"— ({r['motivo']})"))
    fig = px.bar(serie, x="fecha", y="carga")
    fig.update_traces(marker_color="#2a78d6")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=200, xaxis_title=None, yaxis_title="UA",
                      bargap=0.15)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
st.caption("Zona habitual del ratio 0,8–1,3. Por encima de 1,5 el riesgo de lesión sube: reparte la carga. "
           "Es una guía, no un diagnóstico.")

# Recuperación
st.subheader("Recuperación (Garmin)")
g = pd.DataFrame([x for x in d["garmin_diario"] if x["fecha"] >= desde.isoformat()])
if g.empty:
    st.caption("Sin datos de Garmin en este periodo.")
else:
    g["fecha"] = pd.to_datetime(g["fecha"])
    for campo, titulo, unidad in (("fc_reposo", "Pulso en reposo", "lpm"), ("vfc", "VFC nocturna", "ms"),
                                  ("sueno_h", "Sueño", "h"), ("body_battery_max", "Body Battery máx.", ""),
                                  ("estres_medio", "Estrés medio", "")):
        if campo not in g or g[campo].isna().all():
            continue
        st.markdown(f"**{titulo}**")
        sub = g[["fecha", campo]].dropna()
        fig = px.line(sub, x="fecha", y=campo, markers=True)
        if len(sub) >= 7:
            sub = sub.assign(media7=sub[campo].rolling(7, min_periods=4).mean())
            fig.add_scatter(x=sub["fecha"], y=sub["media7"], mode="lines", name="media 7 d",
                            line=dict(width=2, color="#8a8a85", dash="dot"))
        estilo_grafico(fig, unidad)
        if len(fig.data) > 1:
            fig.data[1].update(line=dict(width=2, color="#8a8a85", dash="dot"), mode="lines")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Línea de puntos: media de 7 días.")

# Molestias
mol = [{"fecha": c["fecha"], "zona": m["zona"], "dolor": m["intensidad"]}
       for c in d["checkins"] if c["fecha"] >= desde.isoformat() for m in c.get("molestias", []) if m.get("intensidad")]
if mol:
    st.subheader("Molestias anotadas")
    st.dataframe(pd.DataFrame(mol).sort_values("fecha", ascending=False), hide_index=True, width="stretch")
