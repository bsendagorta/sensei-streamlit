import streamlit as st

from sensei import ui
from sensei.app_comun import ajustes, borrar_registros, datos, editar_registro, hoy
from sensei.modelo import parse_resultado
from sensei.baremo import texto_control
from sensei.modelo import PRUEBAS, formatear, formatear_marca

ui.pagina("Controles", "controles")
d, a = datos(), ajustes()
esc, H = ui.esc, ui.html

H('<div class="section-head"><div><h1>Una marca real cambia la previsión.</h1><p>Registra la prueba completa con el '
  'botón superior. Cada control actualiza su previsión y su equivalencia de nota.</p></div></div>'
  '<p class="info-note">Banca: 40 kg y 30 s. Dominadas: 30 s. Cuerda: 6 m. Velocidad: 60 m medidos. Fondo: 1500 m '
  'continuos. Solo tu baremo personal.</p>')



@st.dialog("Editar control", width="large")
def editar_control(c: dict):
    claves = list(PRUEBAS)
    prueba = st.selectbox("Prueba", claves, index=claves.index(c["prueba"]), format_func=lambda p: PRUEBAS[p]["nombre"])
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha", ui.date.fromisoformat(c["fecha"]), max_value=hoy(), format="DD/MM/YYYY")
    texto = c2.text_input("Resultado", formatear_marca(c["prueba"], c["resultado"], False))
    completo = st.checkbox("Protocolo completo del examen", value=bool(c.get("protocolo_completo")))
    notas = st.text_area("Notas", c.get("notas") or "")
    b1, b2 = st.columns(2)
    if b1.button("Guardar cambios", type="primary", use_container_width=True):
        try:
            valor = parse_resultado(prueba, texto)
        except ValueError as e:
            st.error(str(e))
            return
        if editar_registro("controles", c["id"], {"prueba": prueba, "fecha": fecha.isoformat(), "resultado": valor,
                                                  "protocolo_completo": completo, "notas": notas.strip()}, "Control editado"):
            st.rerun()
    if b2.checkbox("Quiero eliminarlo") and b2.button("Eliminar control", use_container_width=True):
        if borrar_registros("controles", [c["id"]], "Control eliminado"):
            st.rerun()


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

    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    idx = c1.selectbox("Control", range(len(controles)), format_func=lambda i: (
        f'{ui.fecha_es(controles[i]["fecha"])} · {PRUEBAS[controles[i]["prueba"]]["nombre"]} · '
        f'{formatear_marca(controles[i]["prueba"], controles[i]["resultado"])}'))
    if c2.button("Editar control", use_container_width=True):
        editar_control(controles[idx])
else:
    H('<section class="panel"><h2>Tus controles</h2><div class="empty-state">Aún no has registrado un control completo.'
      '<br>Usa el botón «Registrar control» de la parte superior.</div></section>')

ui.pie()
