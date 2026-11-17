import streamlit as st

from sensei import garmin as gm
from sensei import ui
from sensei.app_comun import ajustes, datos, garmin_configurado, hoy, importar_historial
from sensei.aprendizaje import eficiencia_carrera, modelo_sensacion, predecir_sensacion, puntos_debiles, recuperacion_personal
from sensei.baremo import calificar, num
from sensei.graficos import linea
from sensei.lectura import leer
from sensei.modelo import PRUEBAS
from sensei.prevision import prevision

ui.pagina("Rendimiento", "rendimiento")
d, a, h = datos(), ajustes(), hoy()
esc, H = ui.esc, ui.html

con_ref = sum(1 for p in PRUEBAS if prevision(p, d["controles"])["central"] is not None)
completos = sum(1 for c in d["controles"] if c.get("protocolo_completo"))
H(f'<div class="section-head"><div><h1>Rendimiento</h1><p>{con_ref} de 6 pruebas con alguna referencia · {completos} '
  f'controles completos</p></div></div>')

L = leer(d, h, a["peso_kg"])
tarjetas = "".join(f'<div class="insight-card {t["estado"]}"><small>{esc(t["titulo"])}</small><strong>{esc(t["valor"])}</strong>'
                   f'<small>{esc(t["linea1"])}</small><small class="insight-note">{esc(t["linea2"])}</small></div>'
                   for t in L["tarjetas"])
props = "".join(f'<div class="proposal"><span class="badge {"green" if cat == "Recuperación" else "blue"}">{esc(cat)}</span>'
                f'<div><strong>{esc(tit)}</strong><p>{esc(txt)}</p></div></div>' for cat, tit, txt in L["propuestas"]) \
    or '<p>Nada que cambiar: tus métricas están en tu rango habitual.</p>'
H(f'''<section class="panel" id="insight-panel"><div class="panel-head"><div><h2>Lectura de tus métricas</h2>
<p>Últimos 7 días frente a tus 4 semanas anteriores ({L["dias"]} días con datos de Garmin). Son propuestas razonadas, no
diagnósticos: cada una dice de qué dato sale.</p></div>{'<span class="badge">Vigila la recuperación</span>' if L["vigilar"] else '<span class="badge green">En tu rango</span>'}</div>
<div class="insight-grid">{tarjetas}</div><h3 style="margin-top:23px">Propuestas</h3><div class="proposal-list">{props}</div></section>''')

# ---------------------------------------------------------------- evolución por prueba
filas = []
for x in puntos_debiles(d, {}, 6):
    prev = x["prevision"]
    g = calificar(x["prueba"], prev["rango"], a) if prev["central"] is not None else None
    if g is None:
        lado, sub = '<span class="badge warn">Sin marca</span>', "Sin control completo"
    elif g["tipo"] == "bajo":
        lado, sub = '<span class="badge warn">Bajo mínimo</span>', f'Último: {ui.fecha_es(prev["fecha"])}'
    else:
        lado, sub = f'<span class="badge green">{num(g["etiqueta"])}/10</span>', f'Último: {ui.fecha_es(prev["fecha"])}'
    m = x["mejora"]
    tendencia = ("Mejora demostrada" if m and m["demostrada"] else "Empeora" if m and m["empeora"]
                 else f"Sin tendencia clara ({m['n']} marcas)" if m else "Menos de 3 marcas: sin tendencia")
    nota = g["etiqueta"] if g and g["tipo"] == "nota" else (0 if g else -1)
    filas.append((nota, f'<div class="priority-row"><span class="prio-rank">{{n}}</span><div><strong>{esc(x["nombre"])}</strong>'
                        f'<p>{esc(tendencia)}. {esc(x["consejo"])}</p></div><div class="prio-side">{lado}<small>{esc(sub)}'
                        f'</small></div></div>'))
filas.sort(key=lambda t: t[0])
panel_puntos = (f'<section class="panel"><h2>Dónde están tus puntos</h2><p>De menos a más nota: primero lo que no está '
                f'medido o queda bajo el mínimo. Una mejora solo cuenta como demostrada con un IC del 95 % que excluya el '
                f'cero.</p><div class="priority-list">{"".join(f.replace("{n}", str(i)) for i, (_, f) in enumerate(filas, 1))}'
                f'</div></section>')

# ---------------------------------------------------------------- lo que aprende
m = modelo_sensacion(d)
if not m["ok"]:
    sens = f'<p>{esc(m["motivo"])} Haz el check-in cada mañana: es lo que le enseña.</p>'
else:
    pred = predecir_sensacion(m, d, h)
    efectos = "".join(f'<div class="evidence"><span>{esc(e["nombre"])}</span><strong>{"+" if e["efecto"] > 0 else "−"}'
                      f'{num(abs(e["efecto"]), 2)}</strong></div>' for e in m["efectos"])
    sens = (f'<p>{"Predice" if m["util"] else "Aún no predice mejor que tu media:"} error medio {num(m["mae"])} puntos '
            f'(sin modelo {num(m["mae_ref"])}) con {m["n"]} días.{f" Sensación esperada hoy: {num(pred)}/10." if pred else ""}</p>{efectos}')
r = recuperacion_personal(d)
if r["ok"]:
    filas_r = "".join(f'<div class="evidence"><span>Día +{x["dia"]}</span><strong>FC {num(x["fc_reposo"], 1) if x["fc_reposo"] is not None else "—"} '
                      f'lpm · VFC {num(x["vfc"], 1) if x["vfc"] is not None else "—"} ms</strong></div>' for x in r["respuesta"])
    concl = (f"Vuelves a tu normalidad en {r['dias_hasta_normal']} día(s): deja {r['dias_hasta_normal'] - 1} día(s) suave(s) "
             "entre sesiones duras." if r["dias_hasta_normal"] and r["dias_hasta_normal"] > 1 else
             "Al día siguiente ya estás en tu normalidad." if r["dias_hasta_normal"] == 1 else
             "A los 3 días aún no vuelves a tu normalidad: espacia más las sesiones duras.")
    recu = (f'<p>{r["n_duros"]} sesiones duras (carga ≥ {num(r["umbral"], 0)}, {esc(r["fuente"])}). Diferencia frente a tu '
            f'media de 28 días:</p>{filas_r}<p class="hint" style="margin-top:12px">{esc(concl)}</p>')
else:
    recu = f'<p>{esc(r["motivo"])}</p>'
H(f'<div class="lower-grid">{panel_puntos}<section class="panel"><h2>Qué influye en cómo te sientes</h2>{sens}'
  f'<h3 style="margin-top:20px">Cómo te recuperas de las sesiones duras</h3>{recu}</section></div>')

e = eficiencia_carrera(d)
if e["ok"]:
    t = e["tendencia"]
    serie = [p["m_por_latido"] for p in e["puntos"]]
    etiq = [ui.fecha_es(p["fecha"])[:6] for p in e["puntos"]]
    concl = ("Mejora aeróbica demostrada: más metros por latido." if t and t["significativa"] and t["pendiente"] > 0 else
             "Tu eficiencia baja: revisa fatiga, calor o intensidad media." if t and t["significativa"] else
             "Sin tendencia demostrada todavía: la variación entre días es mayor que el cambio.")
    H(f'<section class="panel" style="margin-top:23px"><div class="panel-head"><div><h2>Eficiencia de carrera</h2><p>Metros '
      f'por latido (velocidad ÷ FC media) en tus {e["n"]} carreras de ≥15 min de las últimas 12 semanas.</p></div></div>'
      f'<div class="chart">{linea(serie, etiq, "m/latido")}</div><p class="hint">{esc(concl)}</p></section>')

if garmin_configurado():
    if st.button("Traer más historial de Garmin", help="Añade el bloque anterior a lo que ya tienes (120 días)."):
        with st.spinner("Descargando historial…"):
            try:
                st.toast(importar_historial())
                st.rerun()
            except gm.ErrorGarmin as ex:
                st.error(str(ex))
ui.pie()
