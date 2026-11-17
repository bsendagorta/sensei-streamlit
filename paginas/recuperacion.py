from datetime import date, timedelta

import streamlit as st

from sensei import ui
from sensei.app_comun import datos, hoy
from sensei.baremo import num
from sensei.graficos import AZUL, VERDE, barras, linea, rangos

ui.pagina("Recuperación", "recuperacion")
d, h = datos(), hoy()
esc, H = ui.esc, ui.html
gd = {g["fecha"]: g for g in d["garmin_diario"]}

c1, c2 = st.columns([4, 1.4], vertical_alignment="bottom")
with c1:
    H('<div class="section-head"><div><h1>Recuperación, día a día.</h1><p>Sueño, energía y pulso: tus lecturas de Garmin '
      'en un mismo lugar.</p></div></div>')
with c2:
    import csv
    import io
    campos = ["fecha", "sueno_h", "sueno_puntos", "fc_reposo", "vfc", "vfc_estado", "body_battery_max",
              "body_battery_min", "estres_medio", "disposicion", "pasos", "kcal_total"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, delimiter=";", extrasaction="ignore")
    w.writeheader()
    for g in d["garmin_diario"]:
        w.writerow(g)
    st.download_button("Exportar registro diario", buf.getvalue(), file_name="recuperacion.csv", mime="text/csv",
                       use_container_width=True)

if not gd:
    H('<div class="well-empty">Aún no hay datos de Garmin. Pulsa «Actualizar Garmin».</div>')
    st.stop()

fechas = sorted(gd)
H(f'<div class="well-meta"><span><strong>{len(fechas)}</strong> días con datos · {ui.fecha_es(fechas[0])} – '
  f'{ui.fecha_es(fechas[-1])}</span><span>Importado: {ui.fecha_es((d.get("garmin_ultima_sync") or fechas[-1])[:10])}</span></div>')

if "rec_dia" not in st.session_state:
    st.session_state["rec_dia"] = min(h, date.fromisoformat(fechas[-1]))
c1, c2, c3, c4 = st.columns([1.3, 1.3, 1, 1], vertical_alignment="bottom")
dia = c1.date_input("Día consultado", key="rec_dia", max_value=h, format="DD/MM/YYYY")
periodo = c2.selectbox("Periodo del gráfico", [14, 30, 60, 90, 180, 365], index=1, format_func=lambda x: f"{x} días")
def mover(n):
    st.session_state["rec_dia"] = st.session_state["rec_dia"] + timedelta(days=n)


c3.button("← Día anterior", use_container_width=True, on_click=mover, args=(-1,))
c4.button("Día siguiente →", use_container_width=True, disabled=dia >= h, on_click=mover, args=(1,))

g = gd.get(dia.isoformat(), {})
aviso = "Día en curso: las lecturas diarias todavía pueden cambiar." if dia == h else (
    "Sin lecturas de Garmin este día." if not g else "Día cerrado.")
H(f'<p class="info-note"><strong>{ui.fecha_es(dia)}</strong> · {esc(aviso)}</p>')


def hm(horas):
    if not horas:
        return "—"
    return f'{int(horas)} h {round((horas % 1) * 60):02d} min'


vfc_txt = {"BALANCED": "Equilibrada", "UNBALANCED": "Desequilibrada", "LOW": "Baja", "POOR": "Muy baja"}
bb_desp = g.get("body_battery_despertar", g.get("body_battery_max"))
H(f'''<div class="well-kpis">
<div class="well-stat"><div class="well-stat-label">Sueño</div><strong>{hm(g.get("sueno_h"))}</strong>
<p>Puntuación: {num(g.get("sueno_puntos"), 0)} /100</p></div>
<div class="well-stat"><div class="well-stat-label">Batería al despertar</div><strong>{num(bb_desp, 0)}<span>/100</span></strong>
<p>Mín.–máx.: {num(g.get("body_battery_min"), 0)}–{num(g.get("body_battery_max"), 0)} · Última: {num(g.get("body_battery_ultima"), 0)}</p></div>
<div class="well-stat"><div class="well-stat-label">FC en reposo</div><strong>{num(g.get("fc_reposo"), 0)}<span>lpm</span></strong>
<p>Mín.: {num(g.get("fc_min"), 0)} · Máx.: {num(g.get("fc_max"), 0)} lpm</p></div>
<div class="well-stat"><div class="well-stat-label">Disposición para entrenar</div><strong>{num(g.get("disposicion"), 0)}<span>/100</span></strong>
<p>HRV: {num(g.get("vfc"), 0)} ms · {esc(vfc_txt.get(g.get("vfc_estado"), "—"))}</p></div></div>''')

rango = [dia - timedelta(days=periodo - 1 - i) for i in range(periodo)]
fila = [gd.get(f.isoformat(), {}) for f in rango]
etiq = [f.strftime("%d/%m") for f in rango]
titulos = [ui.fecha_es(f) for f in rango]


def media_movil(v, n=7):
    out = []
    for i in range(len(v)):
        ventana = [x for x in v[max(0, i - n + 1):i + 1] if x is not None]
        out.append(sum(ventana) / len(ventana) if len(ventana) >= 3 else None)
    return out


sueno = [x.get("sueno_h") for x in fila]
vfc = [x.get("vfc") for x in fila]
fc = [x.get("fc_reposo") for x in fila]


def panel(titulo, unidad, texto, svg):
    return (f'<section class="panel"><div class="panel-head"><h3>{titulo}</h3><span class="well-unit">{unidad}</span></div>'
            f'<p>{texto}</p><div class="well-chart">{svg}</div></section>')


H('<div class="well-chart-grid">'
  + panel("Horas de sueño", "horas", f"Valores diarios · {sum(1 for v in sueno if v)} noches con lectura de {periodo} días.",
          barras(sueno, etiq, AZUL, "h", titulos))
  + panel("Batería corporal", "0–100", "Mínimo–máximo del día y último valor disponible.",
          rangos([x.get("body_battery_min") for x in fila], [x.get("body_battery_max") for x in fila],
                 [x.get("body_battery_ultima") for x in fila], etiq, VERDE))
  + panel("VFC nocturna", "ms", "Línea de puntos: media de 7 días.", linea(vfc, etiq, "ms", media_movil(vfc)))
  + panel("FC en reposo", "lpm", "Línea de puntos: media de 7 días.", linea(fc, etiq, "lpm", media_movil(fc)))
  + '</div>')

mol = [(c["fecha"], m["zona"], m["intensidad"]) for c in d["checkins"] for m in c.get("molestias", []) if m.get("intensidad")]
if mol:
    filas = "".join(f'<tr><td>{ui.fecha_es(f)}</td><td>{esc(z)}</td><td>{i}/10</td></tr>' for f, z, i in sorted(mol, reverse=True)[:30])
    H(f'<section class="panel" style="margin-top:20px"><h3>Molestias anotadas</h3><div class="table-scroll"><table>'
      f'<thead><tr><th>Día</th><th>Zona</th><th>Dolor</th></tr></thead><tbody>{filas}</tbody></table></div></section>')
ui.pie()
