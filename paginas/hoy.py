import streamlit as st

from sensei import apis
from sensei import garmin as gm
from sensei.app_comun import (ESTADO, ajustes, autosincronizar, datos, fecha_examen, garmin_configurado,
                              hoy, sincronizar_garmin)
from sensei.reglas import NOMBRE_NIVEL, evaluar, fase

autosincronizar()
d, a, h = datos(), ajustes(), hoy()
examen = fecha_examen()

st.title("Hoy")
st.caption(f"{h.strftime('%d/%m/%Y')} · examen {examen.strftime('%d/%m/%Y')} (provisional) · "
           f"faltan **{(examen - h).days} días**")

r = evaluar(d, h, a["umbrales"])
icono, _ = ESTADO[r["nivel"]]
nombre = NOMBRE_NIVEL.get(r["nivel"], "Sin datos")
with st.container(border=True):
    st.subheader(f"{icono} {nombre}")
    st.markdown(f"**{r['recomendacion']}**")
    if r["motivo_extra"]:
        st.caption(r["motivo_extra"])
    if r["zonas_fisio"]:
        st.warning(f"Molestia repetida en {', '.join(r['zonas_fisio'])}: pide cita con fisio antes de cargar esa zona.")
    if r["faltan"]:
        st.caption("Sin dato: " + ", ".join(r["faltan"]) + ".")

with st.expander("Por qué (señales y umbrales)", expanded=r["nivel"] not in (0, None)):
    for s in r["senales"]:
        st.markdown(f"{ESTADO[s.nivel][0]} **{s.nombre}** — {s.texto}")
    st.caption("Umbrales en Ajustes. Una señal roja manda; 3 ámbar juntas también cuentan como rojo.")

st.info(fase(h, examen), icon="🗓️")

if not any(c["fecha"] == h.isoformat() for c in d["checkins"]):
    st.page_link("paginas/registrar.py", label="Hacer el check-in de hoy (20 s)", icon="✍️")

# Tiempo para entrenar fuera
st.subheader("¿Cuándo entrenar fuera?")
lugar = a["lugar"]


@st.cache_data(ttl=1800, show_spinner=False)
def _tiempo(lat, lon):
    return apis.tiempo_horario(lat, lon)


try:
    horas = _tiempo(lugar["lat"], lugar["lon"])
    mejores = apis.mejores_horas(horas)
    cols = st.columns(len(mejores) or 1)
    for col, x in zip(cols, mejores):
        with col:
            st.metric(x["hora"].strftime("%a %H:%M"), f"{x['sensacion']:.0f} °C",
                      help=f"Temperatura {x['temp']:.0f} °C · lluvia {x['lluvia']} % · viento {x['viento']:.0f} km/h"
                           + (f" · ICA {x['aqi']:.0f}" if x.get("aqi") is not None else ""))
            st.caption(", ".join(x["avisos"]) or "buenas condiciones")
    st.caption(f"{lugar['nombre']} · Open-Meteo (sensación térmica, lluvia, viento y calidad del aire).")
except Exception as e:
    st.caption(f"No se pudo consultar el tiempo ({type(e).__name__}).")

# Garmin
st.subheader("Garmin")
g = next((x for x in d["garmin_diario"] if x["fecha"] == h.isoformat()), None)
if g:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pulso reposo", f"{g['fc_reposo']:.0f}" if g.get("fc_reposo") else "—")
    c2.metric("VFC", f"{g['vfc']:.0f} ms" if g.get("vfc") else "—")
    c3.metric("Sueño", f"{g['sueno_h']:.1f} h" if g.get("sueno_h") else "—")
    c4.metric("Body Battery", f"{g['body_battery_max']:.0f}" if g.get("body_battery_max") else "—")
ultima = d.get("garmin_ultima_sync")
st.caption(f"Última descarga: {ultima.replace('T', ' ')[:16] if ultima else 'nunca'}")
if garmin_configurado():
    if st.button("Actualizar Garmin", icon="🔄"):
        with st.spinner("Descargando de Garmin (solo lectura)…"):
            try:
                st.success(sincronizar_garmin())
                st.rerun()
            except gm.ErrorGarmin as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Garmin no responde ({type(e).__name__}). Registra a mano y prueba más tarde.")
else:
    st.caption("Garmin no está conectado: mira el README para pegar tu token en los secretos.")
