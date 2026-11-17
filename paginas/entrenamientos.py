import streamlit as st

from sensei import ui
from sensei.app_comun import datos, hoy
from sensei.baremo import num

ui.pagina("Entrenamientos", "entrenamientos")
d, h = datos(), hoy()
esc, H = ui.esc, ui.html
TIPOS = {"strength_training": "Fuerza", "running": "Carrera", "treadmill_running": "Cinta", "track_running": "Pista",
         "indoor_cycling": "Bici indoor", "cycling": "Bici", "hiking": "Senderismo", "walking": "Caminata",
         "lap_swimming": "Natación", "other": "Otro", "hiit": "HIIT", "indoor_cardio": "Cardio"}

c1, c2 = st.columns([4, 1.4], vertical_alignment="bottom")
with c1:
    H('<div class="section-head"><div><h1>El orden también se entrena.</h1><p>Sesiones realizadas y futuras, con bloques '
      'y ejercicios en su secuencia.</p></div></div>')
with c2, st.container(key="btnlink_ses"):
    st.page_link("paginas/registrar.py", label="＋ Planificar / registrar sesión")

# Une sesiones propias (con bloques) y actividades de Garmin no vinculadas
vinculadas = {str(s.get("garmin_id")) for s in d["sesiones"] if s.get("garmin_id")}
garmin = {str(a["id"]): a for a in d["garmin_actividades"]}
items = []
for s in d["sesiones"]:
    g = garmin.get(str(s.get("garmin_id"))) if s.get("garmin_id") else None
    items.append({"fecha": s["fecha"], "nombre": s.get("nombre") or s.get("tipo") or "Sesión",
                  "tipo": TIPOS.get(s.get("tipo"), s.get("tipo") or ""), "estado": s.get("estado", "completed"),
                  "min": s.get("duracion_min") or (g or {}).get("duracion_min"),
                  "km": s.get("distancia_km") or (g or {}).get("distancia_km"), "fc": (g or {}).get("fc_media"),
                  "carga": (g or {}).get("carga"), "rpe": s.get("rpe"), "notas": s.get("notas") or "",
                  "bloques": s.get("bloques") or [], "origen": "propia"})
for k, a in garmin.items():
    if k in vinculadas:
        continue
    items.append({"fecha": a["fecha"], "nombre": a.get("nombre") or "Actividad", "tipo": TIPOS.get(a.get("tipo"), a.get("tipo") or ""),
                  "estado": "completed", "min": a.get("duracion_min"), "km": a.get("distancia_km"), "fc": a.get("fc_media"),
                  "carga": a.get("carga"), "rpe": None, "notas": "", "bloques": [], "origen": "garmin"})
items.sort(key=lambda x: x["fecha"], reverse=True)

c1, c2 = st.columns([4, 1.4], vertical_alignment="bottom")
q = c1.text_input("Buscar sesión", placeholder="Nombre, fecha, tipo…")
mostrar = c2.selectbox("Mostrar", ["Realizadas", "Planificadas", "Todas", "Con bloques", "Solo Garmin"])
if q:
    ql = q.lower()
    items = [x for x in items if ql in f'{x["nombre"]} {x["fecha"]} {x["tipo"]} {x["notas"]}'.lower()]
items = [x for x in items if mostrar == "Todas" or (mostrar == "Realizadas" and x["estado"] == "completed")
         or (mostrar == "Planificadas" and x["estado"] == "planned") or (mostrar == "Con bloques" and x["bloques"])
         or (mostrar == "Solo Garmin" and x["origen"] == "garmin")]

POR_PAGINA = 12
paginas = max(1, -(-len(items) // POR_PAGINA))
pag = min(st.session_state.get("pag_ent", 1), paginas)


def ejercicio(i, j, e):
    lineas = [f'<strong>{esc(e.get("name"))}</strong>']
    if e.get("dose"):
        lineas.append(f'<p>{esc(e["dose"])}</p>')
    if e.get("reps"):
        reps = e["reps"] if isinstance(e["reps"], str) else " · ".join(num(r) for r in e["reps"])
        lineas.append(f'<p class="result">Reps: {esc(reps)}</p>')
    if e.get("result"):
        lineas.append(f'<p class="result">{esc(e["result"])}</p>')
    return f'<div class="exercise"><span class="exercise-order">{i}.{j}</span><div>{"".join(lineas)}</div></div>'


def tarjeta(x):
    badge = ('<span class="badge blue">Planificado</span>' if x["estado"] == "planned"
             else '<span class="badge">Realizado</span>')
    meta = [ui.fecha_es(x["fecha"]), x["tipo"]]
    if x["min"]:
        meta.append(f'{num(x["min"])} min')
    if x["km"]:
        meta.append(f'{num(x["km"], 2)} km')
    if x["fc"]:
        meta.append(f'FC {num(x["fc"], 0)}')
    if x["carga"]:
        meta.append(f'carga {num(x["carga"], 0)}')
    if x["rpe"] is not None:
        meta.append(f'RPE {x["rpe"]}')
    bloques = ""
    if x["bloques"]:
        partes = []
        for i, b in enumerate(x["bloques"], 1):
            ej = "".join(ejercicio(i, j, e) for j, e in enumerate(b.get("exercises", []), 1))
            rondas = b.get("rounds") or 1
            partes.append(f'<div class="exercise-block"><div class="block-head"><strong>{i} · {esc(b.get("title"))}</strong>'
                          f'<span>{esc(b.get("mode") or (str(rondas) + (" series" if rondas > 1 else " serie")))}</span></div>{ej}</div>')
        bloques = f'<details><summary>Bloques de la sesión</summary><div class="blocks">{"".join(partes)}</div></details>'
    notas = f'<p class="session-notes">{esc(x["notas"])}</p>' if x["notas"] else ""
    return (f'<article class="session"><div class="session-heading"><div>{badge}<h3>{esc(x["nombre"])}</h3>'
            f'<p>{esc(" · ".join(m for m in meta if m))}</p></div></div>{notas}{bloques}</article>')


if not items:
    H('<div class="empty-state">No hay sesiones con ese filtro.</div>')
else:
    trozo = items[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]
    H(f'<div class="session-list">{"".join(tarjeta(x) for x in trozo)}</div>')
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
    if c1.button("← Anteriores", disabled=pag <= 1, use_container_width=True):
        st.session_state["pag_ent"] = pag - 1
        st.rerun()
    c2.markdown(f'<div class="sensei"><p class="subtle" style="text-align:center">Página {pag} de {paginas} · '
                f'{len(items)} sesiones</p></div>', unsafe_allow_html=True)
    if c3.button("Siguientes →", disabled=pag >= paginas, use_container_width=True):
        st.session_state["pag_ent"] = pag + 1
        st.rerun()

ui.pie()
