import streamlit as st

from sensei import ui
from sensei.app_comun import ajustes, datos, guardar
from sensei.baremo import texto_control
from sensei.modelo import PRUEBAS, formatear, formatear_marca

ui.pagina("Controles", "controles")
d, a = datos(), ajustes()
esc, H = ui.esc, ui.html

H('<div class="section-head"><div><h1>Una marca real cambia la previsión.</h1><p>Registra la prueba completa con el '
  'botón superior. Cada control actualiza su previsión y su equivalencia de nota.</p></div></div>'
  '<p class="info-note">Banca: 40 kg y 30 s. Dominadas: 30 s. Cuerda: 6 m. Velocidad: 60 m medidos. Fondo: 1500 m '
  'continuos. Solo tu baremo personal.</p>')

controles = sorted(d["controles"], key=lambda c: c["fecha"], reverse=True)
if controles:
    filas = []
    for c in controles:
        t = PRUEBAS[c["prueba"]]
        tipo = "" if c.get("protocolo_completo") else " · referencia de entrenamiento"
        filas.append(f'<div class="control-row"><div><strong>{esc(t["nombre"])}</strong><p>{ui.fecha_es(c["fecha"])}'
                     f'{tipo}{" · " + esc(c["notas"]) if c.get("notas") else ""}</p></div>'
                     f'<div class="control-result"><strong>{formatear_marca(c["prueba"], c["resultado"])}</strong>'
                     f'<span>{esc(texto_control(c["prueba"], c["resultado"], a))}</span></div></div>')
    H(f'<section class="panel"><h2>Tus controles</h2>{"".join(filas)}</section>')

    with st.expander("Eliminar un control"):
        idx = st.selectbox("Control", range(len(controles)), format_func=lambda i: (
            f'{ui.fecha_es(controles[i]["fecha"])} · {PRUEBAS[controles[i]["prueba"]]["nombre"]} · '
            f'{formatear(controles[i]["prueba"], controles[i]["resultado"])}'))
        ok = st.checkbox("Confirmo que quiero eliminarlo (queda en el historial del repositorio de datos)")
        if st.button("Eliminar", disabled=not ok):
            objetivo = controles[idx]["id"]
            if guardar(lambda x: x.update(controles=[c for c in x["controles"] if c.get("id") != objetivo]),
                       "Control eliminado"):
                st.rerun()
else:
    H('<section class="panel"><h2>Tus controles</h2><div class="empty-state">Aún no has registrado un control completo.'
      '<br>Usa el botón «Registrar control» de la parte superior.</div></section>')

ui.pie()
