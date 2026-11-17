import pandas as pd
import plotly.express as px
import streamlit as st

from sensei import garmin as gm
from sensei.aprendizaje import (eficiencia_carrera, modelo_sensacion, predecir_sensacion, puntos_debiles,
                                recuperacion_personal)
from sensei.app_comun import ajustes, datos, estilo_grafico, garmin_configurado, hoy, importar_historial
from sensei.modelo import PRUEBAS, formatear

st.title("Lo que Sensei aprende de ti")
st.caption("Se reentrena con todos tus datos cada vez que abres esta página. Cada conclusión lleva su "
           "evidencia; lo que tus datos no demuestran se dice tal cual.")
d, a = datos(), ajustes()
n_dias = len(d["garmin_diario"])
c1, c2, c3 = st.columns(3)
c1.metric("Días de Garmin", n_dias)
c2.metric("Check-ins", len(d["checkins"]))
c3.metric("Controles", len(d["controles"]))

if garmin_configurado():
    if st.button("Traer más historial de Garmin", icon="⬇️",
                 help="Trae el bloque anterior a lo que ya tienes (120 días con la clave API personal). Repite hasta cubrir el tiempo que quieras."):
        with st.spinner("Descargando historial (puede tardar 1–2 min)…"):
            try:
                st.success(importar_historial())
                st.rerun()
            except gm.ErrorGarmin as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Garmin no responde ({type(e).__name__}). Prueba más tarde.")

# 1. Puntos débiles
st.header("1 · Puntos débiles y margen de mejora")
pd_ = puntos_debiles(d, a["baremo"], a.get("puntos_max") or 6)
for x in pd_:
    with st.container(border=True):
        cab = f"**{x['nombre']}**"
        if x["sin_datos"]:
            st.markdown(cab + " — sin ninguna marca: haz un control para saber dónde estás.")
            continue
        partes = [f"previsión {formatear(x['prueba'], x['prevision']['central'])}"]
        if x["puntos"] is not None:
            partes.append(f"{x['puntos']:g} puntos · margen {x['margen']:g}")
        m = x["mejora"]
        if m:
            unidad = {"rep": "rep", "s": "s", "min:s": "s", "cm": "cm"}[PRUEBAS[x["prueba"]]["unidad"]]
            if m["demostrada"]:
                partes.append(f"✅ mejora demostrada: {abs(m['por_semana']):.2f} {unidad}/semana ({m['n']} marcas)")
            elif m["empeora"]:
                partes.append(f"⚠️ empeora: {abs(m['por_semana']):.2f} {unidad}/semana")
            else:
                partes.append(f"sin tendencia clara aún ({m['n']} marcas)")
        else:
            partes.append("menos de 3 marcas: sin tendencia")
        st.markdown(cab + " — " + " · ".join(partes))
        st.caption("Para mejorarla: " + x["consejo"])
if not a["baremo"]:
    st.caption("Carga el baremo en Ajustes para que ordene por puntos que puedes ganar.")

# 2. Qué te afecta
st.header("2 · Qué influye en cómo te sientes")
m = modelo_sensacion(d)
if not m["ok"]:
    st.info(m["motivo"] + " Haz el check-in cada mañana: es lo que le enseña.", icon="⏳")
else:
    if m["util"]:
        st.markdown(f"Con {m['n']} días aprendidos, predice tu sensación con un error medio de "
                    f"**{m['mae']:.1f} puntos** (sin modelo: {m['mae_ref']:.1f}; un {m['mejora_pct']:.0f} % mejor).")
        pred = predecir_sensacion(m, d, hoy())
        if pred is not None:
            st.metric("Sensación esperada hoy según tus datos", f"{pred:.1f}/10")
    else:
        st.warning(f"Con {m['n']} días aún no predice mejor que tu media ({m['mae']:.1f} vs {m['mae_ref']:.1f}): "
                   "no se usa para decidir. Sigue registrando.")
    ef = pd.DataFrame(m["efectos"])
    ef["sentido"] = ef["efecto"].map(lambda v: "te hace sentir mejor" if v > 0 else "te hace sentir peor")
    fig = px.bar(ef.iloc[::-1], x="efecto", y="nombre", orientation="h", hover_data={"sentido": True})
    fig.update_traces(marker_color="#2a78d6")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=40 * len(ef) + 60, xaxis_title=
                      "Efecto en la sensación (puntos por cada desviación típica)", yaxis_title=None)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Barras a la derecha: cuando esa variable sube, te sientes mejor. Es asociación, no causa.")

# 3. Recuperación personal
st.header("3 · Cómo te recuperas de las sesiones duras")
r = recuperacion_personal(d)
if not r["ok"]:
    st.info(r["motivo"], icon="⏳")
else:
    st.markdown(f"Sesión dura = carga ≥ {r['umbral']:.0f} ({r['fuente']}); analizadas **{r['n_duros']}**.")
    filas = [{"Día después": f"+{x['dia']}",
              "Pulso reposo vs media": f"{x['fc_reposo']:+.1f} lpm" if x["fc_reposo"] is not None else "—",
              "VFC vs media": f"{x['vfc']:+.1f} ms" if x["vfc"] is not None else "—",
              "n": max(x["n_fc"], x["n_vfc"])} for x in r["respuesta"]]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    if r["dias_hasta_normal"] == 1:
        st.success("Al día siguiente ya estás en tu normalidad: toleras bien dos días seguidos de calidad.")
    elif r["dias_hasta_normal"]:
        st.warning(f"Tardas unos {r['dias_hasta_normal']} días en volver a tu normalidad: deja "
                   f"{r['dias_hasta_normal'] - 1} día(s) suave(s) entre sesiones duras.")
    else:
        st.warning("A los 3 días aún no vuelves a tu normalidad: tus sesiones duras están siendo demasiado "
                   "seguidas o demasiado duras.")

# 4. Eficiencia de carrera
st.header("4 · Eficiencia de carrera (fondo 1500 m)")
e = eficiencia_carrera(d)
if not e["ok"]:
    st.info(e["motivo"], icon="⏳")
else:
    t = e["tendencia"]
    df = pd.DataFrame(e["puntos"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    fig = px.line(df, x="fecha", y="m_por_latido", markers=True)
    st.plotly_chart(estilo_grafico(fig, "metros por latido"), width="stretch",
                    config={"displayModeBar": False})
    if t and t["significativa"] and t["pendiente"] > 0:
        st.success(f"Mejora aeróbica demostrada en tus {e['n']} carreras de 12 semanas: "
                   f"+{t['pendiente'] * 4:.3f} m/latido cada 4 semanas.")
    elif t and t["significativa"]:
        st.warning("Tu eficiencia baja: fatiga acumulada, calor o más intensidad media. Revisa la carga.")
    else:
        st.caption("Sin tendencia demostrada todavía (la variación entre días es mayor que el cambio).")
    st.caption("Velocidad ÷ FC media de cada carrera ≥15 min. Mezcla rodajes y series: compara mejor "
               "rodajes parecidos.")
