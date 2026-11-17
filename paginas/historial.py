import json

import streamlit as st

from sensei import ui
from sensei.app_comun import almacen, datos, guardar, recargar
from sensei.importar_sensei import ErrorImportacion, importar

ui.pagina("Datos y copias", "historial")
d = datos()
esc, H = ui.esc, ui.html

H(f'''<div class="section-head"><div><h1>Datos y copias</h1><p>Tus datos están en {esc(almacen().descripcion)}. Cada
cambio queda como un commit, así que el historial completo está en git.</p></div></div>
<div class="stats"><div class="stat"><strong>{len(d["controles"])}</strong><span>controles</span></div>
<div class="stat"><strong>{len(d["sesiones"])}</strong><span>sesiones propias</span></div>
<div class="stat"><strong>{len(d["garmin_diario"])}</strong><span>días de Garmin</span></div></div>''')

with st.container(key="panel_import"):
    H('<h2>Importar desde Sensei.app</h2><p class="subtle">En la app del Mac: Archivo → «Guardar copia…» (⌘S) y sube '
      'aquí el .json. Se importan controles, sesiones con bloques, citas, nutrición, peso, fecha del examen y el '
      'histórico de Garmin. Lo que hayas creado en la web no se toca; lo que vino de Sensei se actualiza con la copia '
      'nueva; los días de Garmin solo rellenan huecos.</p>')
    archivo = st.file_uploader("Copia de Sensei (.json)", type=["json"])
    if archivo is not None:
        try:
            copia = json.load(archivo)
        except ValueError:
            copia = None
            st.error("El archivo no es un JSON válido.")
        if copia is not None and st.button("Importar esta copia", type="primary"):
            resumen = {}

            def cambio(x):
                resumen.update(importar(x, copia))
            try:
                if guardar(cambio, "Importación desde Sensei.app"):
                    st.success(f'Importado: {resumen["controles"]} controles, {resumen["sesiones"]} sesiones, '
                               f'{resumen["comidas"]} alimentos, {resumen["citas"]} citas, '
                               f'{resumen["dias_garmin_nuevos"]} días de Garmin nuevos y '
                               f'{resumen["actividades_nuevas"]} actividades nuevas.')
            except ErrorImportacion as e:
                st.error(str(e))

c1, c2 = st.columns(2)
if c1.button("Recargar datos", icon="🔄", use_container_width=True):
    recargar()
    st.rerun()
c2.download_button("Descargar todo (.json)", json.dumps(d, ensure_ascii=False), file_name="sensei-datos.json",
                   mime="application/json", use_container_width=True)

with st.expander("Editar check-ins y citas"):
    import pandas as pd
    from sensei.app_comun import borrar_registros, editar_registro
    t = st.radio("Qué editar", ["Check-ins", "Citas"], horizontal=True)
    if t == "Check-ins":
        regs = sorted(d["checkins"], key=lambda c: c["fecha"], reverse=True)
        df = pd.DataFrame([{"id": c.get("id"), "fecha": c["fecha"], "sensación": c.get("sensacion"), "sueño (h)": c.get("sueno_h"),
                            "molestias": "; ".join(f'{m["zona"]} {m["intensidad"]}' for m in c.get("molestias", [])),
                            "notas": c.get("notas", "")} for c in regs])
    else:
        regs = sorted(d.get("citas", []), key=lambda c: c["fecha"], reverse=True)
        df = pd.DataFrame([{"id": c.get("id"), "fecha": c["fecha"], "hora": c.get("hora") or "", "nombre": c.get("nombre") or "",
                            "notas": c.get("notas") or ""} for c in regs])
    if df.empty:
        st.caption("Vacío.")
    else:
        st.caption("Edita las celdas y pulsa Guardar. Molestias: «Zona intensidad; Zona intensidad», p. ej. «Lumbar 2».")
        ed = st.data_editor(df, hide_index=True, width="stretch", disabled=["id", "fecha"], key=f"ed_{t}")
        if st.button("Guardar cambios", type="primary"):
            ok = True
            for antes, ahora in zip(df.to_dict("records"), ed.to_dict("records")):
                if antes == ahora:
                    continue
                if t == "Check-ins":
                    mol = []
                    for trozo in str(ahora["molestias"] or "").split(";"):
                        partes = trozo.strip().rsplit(" ", 1)
                        if len(partes) == 2 and partes[1].isdigit():
                            mol.append({"zona": partes[0], "intensidad": int(partes[1])})
                    cambios = {"sensacion": ahora["sensación"], "sueno_h": ahora["sueño (h)"], "molestias": mol,
                               "notas": ahora["notas"]}
                    ok &= editar_registro("checkins", ahora["id"], cambios, f'Check-in {ahora["fecha"]} editado')
                else:
                    ok &= editar_registro("citas", ahora["id"], {"hora": ahora["hora"], "nombre": ahora["nombre"],
                                                                 "notas": ahora["notas"]}, f'Cita {ahora["fecha"]} editada')
            if ok:
                st.success("Guardado.")
                st.rerun()

with st.expander("Borrar un registro"):
    tipos = {"Check-ins": "checkins", "Sesiones": "sesiones", "Citas": "citas"}
    t = st.selectbox("Tipo", list(tipos))
    clave = tipos[t]
    items = sorted(d.get(clave, []), key=lambda x: x["fecha"], reverse=True)
    if items:
        i = st.selectbox("Registro", range(len(items)), format_func=lambda i: (
            f'{ui.fecha_es(items[i]["fecha"])} · {items[i].get("nombre") or items[i].get("tipo") or items[i].get("notas") or ""}'))
        if st.button("Borrar", disabled=not st.checkbox("Confirmo el borrado (queda en el historial de git)")):
            objetivo = items[i].get("id")
            if guardar(lambda x: x.update({clave: [y for y in x.get(clave, []) if y.get("id") != objetivo]}),
                       f"Borrado en {clave}"):
                st.rerun()
    else:
        st.caption("Vacío.")
ui.pie()
