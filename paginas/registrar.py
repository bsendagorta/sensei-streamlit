import uuid

import streamlit as st

from sensei import ui
from sensei.app_comun import ahora, datos, guardar, hoy
from sensei.modelo import PRUEBAS, TIPOS_SESION, ZONAS_MOLESTIA, formatear, parse_resultado

ui.pagina("Check-in y sesiones", "registrar")
ui.html('<div class="section-head"><div><h1>Cómo llegas hoy.</h1><p>El check-in de 20 s enseña a Sensei qué te afecta y '
        'activa el semáforo. Las sesiones con esfuerzo percibido alimentan la carga.</p></div></div>')
d = datos()
t_check, t_ses, t_ctrl = st.tabs(["Check-in diario", "Sesión hecha", "Control / medición"])


def _id():
    return uuid.uuid4().hex[:10]


with t_check:
    st.caption("Al levantarte. Lo que no sepas, déjalo vacío.")
    fecha = st.date_input("Fecha", hoy(), max_value=hoy(), key="ci_fecha", format="DD/MM/YYYY")
    existente = next((c for c in d["checkins"] if c["fecha"] == fecha.isoformat()), None)
    sensacion = st.slider("¿Cómo te sientes para entrenar? (1 = fatal, 10 = genial)", 1, 10,
                          (existente or {}).get("sensacion") or 7)
    sueno = st.number_input("Horas de sueño (solo si Garmin no lo registró)", 0.0, 14.0, value=None, step=0.25,
                            key="ci_sueno")
    zonas = st.multiselect("Molestias", ZONAS_MOLESTIA,
                           default=[m["zona"] for m in (existente or {}).get("molestias", []) if m["zona"] in ZONAS_MOLESTIA])
    molestias = []
    for z in zonas:
        previa = next((m["intensidad"] for m in (existente or {}).get("molestias", []) if m["zona"] == z), 2)
        molestias.append({"zona": z, "intensidad": st.slider(f"{z}: dolor 0–10", 0, 10, previa, key=f"ci_{z}")})
    notas = st.text_input("Notas", (existente or {}).get("notas", ""), key="ci_notas")
    sustituir = True
    if existente:
        sustituir = st.checkbox("Ya hay un check-in de ese día: sustituirlo por este", key="ci_sust")
    if st.button("Guardar check-in", type="primary", disabled=not sustituir, key="ci_ok"):
        nuevo = {"id": (existente or {}).get("id") or _id(), "fecha": fecha.isoformat(), "sensacion": sensacion,
                 "sueno_h": sueno, "molestias": molestias, "notas": notas.strip(),
                 "registrado": ahora().isoformat(timespec="seconds")}

        def cambio(x):
            x["checkins"] = [c for c in x["checkins"] if c["fecha"] != nuevo["fecha"]] + [nuevo]
            x["checkins"].sort(key=lambda c: c["fecha"])
        if guardar(cambio, f"Check-in {nuevo['fecha']}"):
            st.success("Check-in guardado.")

with t_ses:
    st.caption("La carga (sRPE = minutos × esfuerzo) avisa de subidas bruscas. Si Garmin ya registró la "
               "actividad, añade igualmente el esfuerzo percibido: es lo que mejor predice la fatiga.")
    with st.form("sesion", clear_on_submit=True):
        fecha = st.date_input("Fecha", hoy(), max_value=hoy(), format="DD/MM/YYYY")
        tipo = st.selectbox("Tipo", TIPOS_SESION)
        dur = st.number_input("Duración (min)", 1, 400, value=None)
        rpe = st.slider("Esfuerzo percibido de la sesión (0 = reposo · 5 = duro · 10 = máximo)", 0, 10, 5)
        dolor = st.slider("Dolor máximo durante la sesión (0–10)", 0, 10, 0)
        notas = st.text_area("Qué hiciste / notas", placeholder="p. ej. 5×4 dominadas lastre 5 kg, 6×200 m a 36 s")
        if st.form_submit_button("Guardar sesión", type="primary"):
            if dur is None:
                st.error("Indica la duración.")
            else:
                s = {"id": _id(), "fecha": fecha.isoformat(), "tipo": tipo, "duracion_min": dur, "rpe": rpe,
                     "dolor_max": dolor, "notas": notas.strip()}
                if guardar(lambda x: x["sesiones"].append(s), f"Sesión {s['fecha']} {tipo}"):
                    st.success(f"Sesión guardada · carga {dur * rpe:.0f} UA.")
                    if dolor >= 4:
                        st.warning("Dolor ≥ 4 durante la sesión: mañana el semáforo lo tendrá en cuenta si lo "
                                   "anotas en el check-in. Si persiste al día siguiente, no cargues esa zona.")

with t_ctrl:
    st.caption("Un control con el protocolo completo del examen manda sobre cualquier estimación. "
               "Si es una medición de entrenamiento (otro peso, otra distancia, cansado…), desmarca la casilla: "
               "contará como referencia orientativa.")
    with st.form("control", clear_on_submit=True):
        prueba = st.selectbox("Prueba", list(PRUEBAS), format_func=lambda p: PRUEBAS[p]["nombre"])
        fecha = st.date_input("Fecha", hoy(), max_value=hoy(), format="DD/MM/YYYY")
        texto = st.text_input("Resultado", placeholder="reps, segundos (7,85), min:s (5:12) o cm")
        completo = st.checkbox("Protocolo completo del examen", value=True)
        notas = st.text_input("Notas (calzado, condiciones…)")
        if st.form_submit_button("Guardar control", type="primary"):
            try:
                valor = parse_resultado(prueba, texto)
            except ValueError as e:
                st.error(str(e))
            else:
                c = {"id": _id(), "fecha": fecha.isoformat(), "prueba": prueba, "resultado": valor,
                     "protocolo_completo": completo, "notas": notas.strip()}
                if guardar(lambda x: x["controles"].append(c), f"Control {prueba} {c['fecha']}"):
                    st.success(f"{PRUEBAS[prueba]['nombre']}: {formatear(prueba, valor)} "
                               f"({'control' if completo else 'referencia'}) guardado.")
