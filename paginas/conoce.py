import json

import streamlit as st

from sensei import ui
from sensei.app_comun import datos, guardar, hoy
from sensei.aprendizaje import modelo_sensacion, predecir_sensacion
from sensei.baremo import num
from sensei.conocerte import OBJETIVOS, TIPOS, resumen_aprendizaje, simular
from sensei.graficos import linea

ui.pagina("Sensei te conoce", "conoce")
d, h = datos(), hoy()
esc, H = ui.esc, ui.html


@st.cache_data(show_spinner=False, max_entries=4)
def _aprender(clave: str, texto: str, dia: str):
    return resumen_aprendizaje(json.loads(texto), h)


clave = f'{len(d["garmin_diario"])}-{len(d["garmin_actividades"])}-{d.get("garmin_ultima_sync")}-{len(d["checkins"])}'
with st.spinner("Reentrenando con tus datos…"):
    R = _aprender(clave, json.dumps({k: d[k] for k in ("garmin_diario", "garmin_actividades")}), h.isoformat())
M = R["modelos"]
validos = [m for m in M.values() if m.get("ok")]
utiles = [m for m in validos if m["util"]]

# Historial del aprendizaje: una foto al día para ver si mejora con el tiempo
foto = {"fecha": h.isoformat(), "dias": R["filas"], **{o: round(m["mae"], 2) for o, m in M.items() if m.get("ok")}}
historial = d.get("aprendizaje_historial", [])
if validos and (not historial or historial[-1]["fecha"] != foto["fecha"]):
    guardar(lambda x: x.setdefault("aprendizaje_historial", []).append(foto), "Aprendizaje: foto diaria")
    historial = d.get("aprendizaje_historial", [])

mejora_media = sum(m["mejora_pct"] for m in utiles) / len(utiles) if utiles else 0
H(f'''<div id="view-overview"><section class="hero"><div><div class="eyebrow">Tu modelo personal</div><h1>Sensei te conoce</h1>
<p style="margin-top:8px">Aprendido de {R["filas"]} días de Garmin y {len(d["garmin_actividades"])} actividades tuyas. Se reentrena
cada vez que entra un dato nuevo y solo usa lo que acierta mejor que no tener modelo.</p></div>
<div class="exam-box"><div class="days">{len(utiles)}/{len(OBJETIVOS)}</div><div class="days-label">modelos que ya te
predicen mejor que tu media</div><small>{"+" + num(mejora_media, 0) + " % de acierto medio" if utiles else "Aún aprendiendo"}</small></div></section></div>''')

# ---------------------------------------------------------------- simulador
H('<div class="section-head" style="margin-top:27px"><div><h2>Mañana, si hoy…</h2><p>Elige qué piensas hacer hoy y '
  'Sensei calcula cómo amanecerás mañana según lo que ha aprendido de ti. La carga de cada tipo sale de la mediana de tus '
  'propias sesiones.</p></div></div>')
c1, c2 = st.columns([1.3, 2])
opciones = {"descanso": "Descanso"} | {k: v for k, v in TIPOS.items() if k in R["tasa"]}
tipo = c1.selectbox("Hoy voy a hacer", list(opciones), format_func=opciones.get)
minutos = c2.slider("Minutos", 10, 120, 50, 5, disabled=tipo == "descanso")
sim = simular(d, M, h, None if tipo == "descanso" else tipo, minutos)
desc = simular(d, M, h, None, 0)
if not sim:
    H('<p class="info-note">Necesito la lectura de Garmin de hoy para simular mañana. Pulsa «Actualizar Garmin».</p>')
else:
    tarjetas = []
    for obj, (nombre, unidad, alto_mejor) in OBJETIVOS.items():
        p = sim.get(obj)
        if not p:
            continue
        frente = p["dif"] - desc[obj]["dif"] if obj in desc else 0
        malo = (p["dif"] < -2) if alto_mejor else (p["dif"] > 1)
        cls = "alert" if malo and abs(p["dif"]) > (8 if unidad == "/100" else 3) else "watch" if malo else "good"
        tarjetas.append(f'<div class="insight-card {cls}"><small>{esc(nombre)}</small><strong>{num(p["abs"], 0)} '
                        f'{esc(unidad)}</strong><small>{"+" if p["dif"] >= 0 else ""}{num(p["dif"], 1)} frente a tu media</small>'
                        f'<small class="insight-note">{"" if tipo == "descanso" else ("+" if frente >= 0 else "") + num(frente, 1) + " frente a descansar"}</small></div>')
    m_ok = [M[o] for o in sim]
    err = " · ".join(f'{OBJETIVOS[o][0].split(" de ")[0]} ±{num(M[o]["mae"], 0)}' for o in sim)
    H(f'<section class="panel"><div class="insight-grid">{"".join(tarjetas)}</div><p class="hint" style="margin-top:14px">'
      f'Error medio de cada predicción (validado día a día con tu pasado): {esc(err)}. Es una estimación, no una '
      f'garantía; un control real o el semáforo de mañana mandan.</p></section>')

# ---------------------------------------------------------------- respuesta por tipo
filas = []
for r in R["respuesta"]:
    def celda(obj, dia, unidad, alto_mejor=True):
        v = r.get(f"{obj}_{dia}")
        if not v:
            return "<td>—</td>"
        claro = abs(v["media"]) > v["ic"]
        mal = (v["media"] < 0) == alto_mejor
        color = ("#a14436" if mal else "#315f4d") if claro else "#6c7a72"
        return (f'<td style="color:{color};font-weight:{600 if claro else 400}">{"+" if v["media"] >= 0 else ""}'
                f'{num(v["media"], 1)} {unidad}<br><small style="color:#6c7a72">±{num(v["ic"], 1)} · n={v["n"]}</small></td>')
    filas.append(f'<tr><td><strong>{esc(r["nombre"])}</strong><br><small style="color:#6c7a72">{r["n"]} días</small></td>'
                 f'{celda("vfc", "d1", "ms")}{celda("vfc", "d2", "ms")}{celda("fc_reposo", "d1", "lpm", False)}'
                 f'{celda("fc_reposo", "d2", "lpm", False)}{celda("disposicion", "d1", "")}</tr>')
H(f'''<section class="panel" style="margin-top:23px"><div class="panel-head"><div><h2>Cómo te afecta cada entrenamiento</h2>
<p>Cómo amaneces, respecto a tu media de 28 días, la mañana siguiente (D+1) y a los dos días (D+2) según el tipo de sesión
principal del día. En color solo lo que tus datos demuestran (IC 95 % sin cruzar el cero); en gris, lo que aún no.</p></div></div>
<div class="table-scroll"><table><thead><tr><th>Tipo de día</th><th>VFC D+1</th><th>VFC D+2</th><th>Pulso reposo D+1</th>
<th>Pulso reposo D+2</th><th>Disposición D+1</th></tr></thead><tbody>{"".join(filas)}</tbody></table></div></section>''')

# ---------------------------------------------------------------- qué te mueve
paneles = []
for obj, (nombre, unidad, alto_mejor) in OBJETIVOS.items():
    m = M[obj]
    if not m.get("ok"):
        paneles.append(f'<section class="panel"><h3>{esc(nombre)}</h3><p>{esc(m["motivo"])}</p></section>')
        continue
    lineas = []
    for e in m["efectos"][:5]:
        bueno = (e["efecto"] > 0) == alto_mejor
        poca = e.get("n_sesiones") is not None and e["n_sesiones"] < 10
        paso = "" if e["variable"].startswith("carga_") and e["n_sesiones"] and "típica" in e["nombre"] else \
            f' (por cada {num(e["paso"], 0)})'
        lineas.append(f'<div class="evidence"><span>{esc(e["nombre"])}{esc(paso)}'
                      f'{"<br><small>poca evidencia: " + str(e["n_sesiones"]) + " sesiones</small>" if poca else ""}</span>'
                      f'<strong style="color:{"#315f4d" if bueno else "#a14436"}">{"+" if e["efecto"] >= 0 else ""}'
                      f'{num(e["efecto"], 1)} {esc(unidad)}</strong></div>')
    estado = (f'<span class="badge green">Acierta un {num(m["mejora_pct"], 0)} % más</span>' if m["util"]
              else '<span class="badge">Aún no bate a tu media</span>')
    paneles.append(f'<section class="panel"><div class="panel-head"><h3>{esc(nombre)}</h3>{estado}</div>'
                   f'<p>Lo que más lo mueve, según {m["n"]} días tuyos:</p>{"".join(lineas)}</section>')
H(f'<div class="section-head" style="margin-top:27px"><div><h2>Qué mueve tu recuperación</h2><p>Efecto de cada cosa '
  f'manteniendo las demás igual. Es asociación aprendida de tus datos, no una ley fisiológica.</p></div></div>'
  f'<div class="dashboard-grid" style="margin-top:0">{"".join(paneles)}</div>')

# ---------------------------------------------------------------- ¿aprende de verdad?
bloques = []
for obj, (nombre, unidad, _) in OBJETIVOS.items():
    m = M[obj]
    if not m.get("ok") or len(m["curva"]) < 2:
        continue
    c = m["curva"]
    svg = linea([x["mae"] for x in c], [x["periodo"] for x in c], unidad, media=[x["ref"] for x in c])
    bloques.append(f'<section class="panel"><h3>{esc(nombre)}</h3><p>Error medio del modelo (línea) frente a no tener modelo '
                   f'(puntos), por trimestre. Más bajo = mejor.</p><div class="chart">{svg}</div><p class="hint">Validado en '
                   f'{m["n_validados"]} días: error {num(m["mae"], 1)} {esc(unidad)} frente a {num(min(m["mae_media"], m["mae_persistencia"]), 1)} '
                   f'sin modelo.</p></section>')
if bloques:
    H(f'<div class="section-head" style="margin-top:27px"><div><h2>¿Aprende de verdad?</h2><p>Cada día se entrena solo con el '
      f'pasado y se comprueba con el día siguiente, sin trampas. Si deja de acertar más que tu media, lo verás aquí.</p>'
      f'</div></div><div class="dashboard-grid" style="margin-top:0">{"".join(bloques)}</div>')

# ---------------------------------------------------------------- check-ins
ms = modelo_sensacion(d)
if ms["ok"]:
    pred = predecir_sensacion(ms, d, h)
    txt = (f'Con {ms["n"]} check-ins predice tu sensación con un error de {num(ms["mae"])} puntos (sin modelo '
           f'{num(ms["mae_ref"])}).' + (f' Hoy esperaría un {num(pred)}/10.' if pred else ""))
else:
    txt = f'{ms["motivo"]} Cada check-in (sensación y molestias, 20 s) le enseña cómo te sientes tú, no solo lo que mide el reloj.'
H(f'<section class="panel" style="margin-top:23px"><h2>Lo que solo tú le puedes enseñar</h2><p>{esc(txt)}</p></section>')
st.page_link("paginas/registrar.py", label="Hacer el check-in de hoy", icon="✍️")
ui.pie()
