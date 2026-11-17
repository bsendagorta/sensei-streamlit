from datetime import timedelta

import streamlit as st

from sensei import apis, ui
from sensei.app_comun import ajustes, autosincronizar, datos, evaluacion_y_recomendacion, fecha_examen, hoy
from sensei.paneles import panel_hoy, panel_recomendacion
from sensei.baremo import baremo, calificar, num
from sensei.carga import acwr, carga_diaria_garmin
from sensei.graficos import linea
from sensei.modelo import PRUEBAS, formatear_marca, formatear_rango
from sensei.prevision import prevision
from sensei.reglas import NOMBRE_NIVEL, RECOMENDACION, evaluar, fase

ui.pagina("Mi previsión", "prevision")
autosincronizar()
d, a, h = datos(), ajustes(), hoy()
examen = fecha_examen()
esc, H = ui.esc, ui.html

# ---------------------------------------------------------------- cabecera
H(f'''<div id="view-overview"><section class="hero"><div><div class="eyebrow">Tu horizonte: {ui.MESES_LARGOS[examen.month - 1]} de {examen.year}</div>
<h1>Mi previsión</h1></div><div class="exam-box"><div class="days">{(examen - h).days}</div>
<div class="days-label">días hasta tu fecha objetivo</div><label style="color:#bdcdc2">Fecha del examen</label>
<input value="{examen.strftime("%d/%m/%Y")}" readonly><small>{examen.day} de {ui.MESES_LARGOS[examen.month - 1]}: fecha provisional</small></div></section>''')

realizadas = len([s for s in d["sesiones"] if s.get("estado", "completed") == "completed"])
garmin_sin_vincular = len({str(x["id"]) for x in d["garmin_actividades"]}
                          - {str(s.get("garmin_id")) for s in d["sesiones"] if s.get("garmin_id")})
planificadas = len([s for s in d["sesiones"] if s.get("estado") == "planned" and s["fecha"] >= h.isoformat()])
completos = len([c for c in d["controles"] if c.get("protocolo_completo")])
H(f'''<div class="stats"><div class="stat"><strong>{realizadas + garmin_sin_vincular}</strong><span>entrenamientos<br>realizados</span></div>
<div class="stat"><strong>{planificadas}</strong><span>sesiones<br>planificadas</span></div>
<div class="stat"><strong>{completos}</strong><span>controles completos<br>de las pruebas</span></div></div></div>''')

# ---------------------------------------------------------------- estado físico y recuperación
r = evaluar(d, h, a["umbrales"])
g_hoy = next((g for g in reversed(d["garmin_diario"]) if g["fecha"] <= h.isoformat()), {})
nivel = r["nivel"]
pill = {0: "Verde", 1: "Ámbar", 2: "Rojo", None: "Sin datos"}[nivel]
con_dato = [s for s in r["senales"] if s.nivel is not None]
disp = g_hoy.get("disposicion")
ring = disp if disp is not None else (round(100 * sum(1 for s in con_dato if s.nivel == 0) / len(con_dato))
                                       if con_dato else 0)
nivel_disp = {"HIGH": "Alta", "PRIME": "Óptima", "MODERATE": "Moderada", "LOW": "Baja", "POOR": "Mala"}
vfc_txt = {"BALANCED": "Equilibrada", "UNBALANCED": "Desequilibrada", "LOW": "Baja", "POOR": "Muy baja"}
titulo_ring = "Disposición Garmin" if disp is not None else "Semáforo Sensei"
h3_ring = nivel_disp.get(g_hoy.get("disposicion_nivel"), NOMBRE_NIVEL.get(nivel, "Sin datos")) if disp is not None \
    else NOMBRE_NIVEL.get(nivel, "Sin datos")

desde7 = (h - timedelta(days=6)).isoformat()
min7 = sum(x.get("duracion_min") or 0 for x in d["garmin_actividades"] if x["fecha"] >= desde7)
sueno = g_hoy.get("sueno_h")
sueno_txt = f'{int(sueno)}<small> h </small>{round((sueno % 1) * 60):02d}<small> min</small>' if sueno else "—"
bb = g_hoy.get("body_battery_ultima", g_hoy.get("body_battery_max"))
carga = carga_diaria_garmin(d["garmin_actividades"])
rat = acwr(carga, h)
agudo = sum(carga.get(h - timedelta(days=i), 0) for i in range(7)) if carga else None
if rat["ratio"] is None:
    etiqueta_carga, pos = "Sin datos", 0
else:
    x = rat["ratio"]
    etiqueta_carga = "Baja" if x < 0.8 else "Óptima" if x <= 1.3 else "Alta" if x <= 1.5 else "Muy alta"
    pos = min(100, x / 2 * 100)

vfc_serie = [next((g.get("vfc") for g in d["garmin_diario"] if g["fecha"] == (h - timedelta(days=27 - i)).isoformat()), None)
             for i in range(28)]
etiq = [(h - timedelta(days=27 - i)).strftime("%d/%m") for i in range(28)]
fechas_g = {g["fecha"] for g in d["garmin_diario"]}
H(f'''<section class="panel body-dashboard" style="margin-top:4px"><div class="body-heading"><div><h2>Estado físico y recuperación</h2>
<p class="subtle">{ui.fecha_es(g_hoy["fecha"]) if g_hoy else "Sin lecturas"} · última lectura</p></div>
<div class="state-pill"><i></i>{esc(pill)}</div></div>
<div class="body-top"><div class="readiness-card"><div class="state-ring" style="--progress:{ring}%"><div><strong>{ring}</strong><small>de 100</small></div></div>
<div><span class="metric-label">{titulo_ring}</span><h3>{esc(h3_ring)}</h3><p>{esc(RECOMENDACION.get(nivel, "Haz el check-in y actualiza Garmin."))}</p></div></div>
<div class="body-metrics"><article><span class="metric-label">Batería corporal</span><strong>{num(bb, 0)}<small>/100</small></strong>
<div class="mini-meter"><i style="width:{bb or 0}%"></i></div></article>
<article><span class="metric-label">Sueño</span><strong>{sueno_txt}</strong><span class="metric-foot">Última noche</span></article>
<article><span class="metric-label">Actividad · 7 días</span><strong>{num(min7, 0)}<small> min</small></strong><span class="metric-foot">Sesiones registradas</span></article></div></div>
<div class="body-details"><div><span>FC en reposo</span><strong>{num(g_hoy.get("fc_reposo"), 0)} <small>ppm</small></strong></div>
<div><span>VFC nocturna</span><strong>{num(g_hoy.get("vfc"), 0)} <small>ms</small></strong></div>
<div><span>Peso</span><strong>{num(a["peso_kg"], 1)} <small>kg</small></strong></div>
<div><span>Estado VFC Garmin</span><strong class="productive-label">{esc(vfc_txt.get(g_hoy.get("vfc_estado"), "—"))}</strong></div></div>
<div class="body-bottom"><div class="body-trend"><div class="body-subhead"><h3>Tu VFC nocturna</h3><span>Últimos 28 días</span></div>
{linea(vfc_serie, etiq, "ms")}<div class="chart-key"><i></i>VFC nocturna (ms)<span>{sum(1 for v in vfc_serie if v)} noches con dato</span></div></div>
<div class="body-load"><div class="body-subhead"><h3>Carga de entrenamiento</h3></div>
<div class="load-main"><strong>{num(agudo, 0)}</strong><span>Carga aguda</span><b>{esc(etiqueta_carga)}</b></div>
<div class="load-track"><i style="left:40%;width:25%"></i><b style="left:{pos}%"></b></div>
<div class="load-scale"><span>0</span><span>0,8</span><span>1,3</span><span>2,0</span></div>
<div class="load-comparison"><div><span>Agudo:crónico</span><strong>{num(rat["ratio"], 2) if rat["ratio"] else "—"}</strong></div>
<div><span>Media diaria 28 d</span><strong>{num(rat["cronico"], 0) if rat.get("cronico") else "—"}</strong></div></div></div></div>
<details class="projection-how"><summary>Por qué el semáforo dice «{esc(pill)}»</summary><ul>{"".join(
    f"<li>{ui.ESTADO_ICONO[s.nivel]} <b>{esc(s.nombre)}</b> — {esc(s.texto)}</li>" for s in r["senales"])}</ul>
{f'<p class="hint" style="margin-top:10px">{esc(r["motivo_extra"])}</p>' if r["motivo_extra"] else ""}</details>
<p class="body-footnote">{esc(fase(h, examen))} {"Molestia repetida en " + esc(", ".join(r["zonas_fisio"])) + ": consulta con fisio." if r["zonas_fisio"] else ""}</p></section>''')

ev, rec = evaluacion_y_recomendacion()
H(f'<div class="lower-grid">{panel_recomendacion(rec, grande=False)}{panel_hoy(ev, h)}</div>')

if not any(c["fecha"] == h.isoformat() for c in d["checkins"]):
    st.page_link("paginas/registrar.py", label="Hacer el check-in de hoy (20 s): sensación y molestias", icon="✍️")

# ---------------------------------------------------------------- nivel por prueba
H('<div class="section-head" style="margin-top:27px"><div><h2>Tu nivel hoy, sobre 10</h2><p>Con tus controles, sin '
  'suponer mejoras. Un control real cambia la previsión.</p></div></div>')
tarjetas = []
for i, (p, info) in enumerate(PRUEBAS.items()):
    prev = prevision(p, d["controles"])
    b = baremo(p, a)
    unidad = "min:s" if info["unidad"] == "min:s" else info["unidad"] + ("s" if info["unidad"] == "rep" else "")
    if prev["central"] is None:
        g = calificar(p, None, a)
        badge, cls = "Sin marca", ""
        nivel_txt = "Falta una marca"
    else:
        lo, hi = prev["rango"]
        g = calificar(p, (lo, hi), a)
        badge, cls = ("Control completo", "green") if prev["fuente"] == "control" else ("Referencia", "")
        nivel_txt = formatear_rango(p, lo, hi)
    if g["tipo"] == "nota":
        grade = f'<div class="grade">{num(g["etiqueta"])}<span>/10</span></div><p class="grade-detail">' \
                f'{num(g["rango"][0])}–{num(g["rango"][1])}/10</p>'
    elif g["tipo"] == "bajo":
        grade = f'<div class="grade">&lt;5<span>/10</span></div><p class="grade-detail">{esc(g["detalle"])}</p>'
    else:
        grade = '<div class="grade unknown">Sin nota fiable</div><p class="grade-detail">Registra un control</p>'
    ultimo = f'Último control: {ui.fecha_es(prev["fecha"])}' if prev.get("fecha") else "Sin control completo"
    tarjetas.append(f'''<article class="test-card"><div class="card-top"><span>{i + 1:02d}</span><span class="badge {cls}">{badge}</span></div>
<h3>{esc(info["nombre"])}</h3><p class="protocol">{esc(info["protocolo"])}</p>{grade}
<div class="predicted"><span>Nivel actual estimado</span><strong>{esc(nivel_txt)}</strong></div>
<div class="benchmarks"><span>Mínimo <b>{formatear_marca(p, b["min"])}</b></span><span>Máximo <b>{formatear_marca(p, b["max"])}</b></span></div>
<p class="text-btn">{esc(ultimo)}{" · " + esc(prev["aviso"]) if prev.get("aviso") and prev["fuente"] == "referencia" else ""}</p></article>''')
H(f'<div class="forecast-grid">{"".join(tarjetas)}</div>')

# ---------------------------------------------------------------- tiempo
lugar = a["lugar"]


@st.cache_data(ttl=1800, show_spinner=False)
def _tiempo(lat, lon):
    return apis.tiempo_horario(lat, lon)


proximas = sorted((c for c in d.get("citas", []) if c["fecha"] >= h.isoformat()), key=lambda c: c["fecha"])[:4]
citas_html = "".join(f'<div class="next-step"><span>{ui.fecha_es(c["fecha"])}</span><div><strong>{esc(c.get("nombre"))}'
                     f'</strong><p>{esc(c.get("hora") or "")}</p></div></div>' for c in proximas) or "<p>Sin citas próximas.</p>"
try:
    ahora = ui.hora_actual()
    horas = [x for x in _tiempo(lugar["lat"], lugar["lon"]) if x["hora"] > ahora]
    mejores = apis.mejores_horas(horas)
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    filas = "".join(f'<div class="next-step"><span>{dias[x["hora"].weekday()]} {x["hora"]:%H:%M}</span><div><strong>'
                    f'{x["sensacion"]:.0f} °C</strong><p>{esc(", ".join(x["avisos"]) or "buenas condiciones")}</p></div></div>'
                    for x in mejores)
    fuente = horas[0].get("fuente", "Open-Meteo") if horas else "Open-Meteo"
    tiempo_html = (f'<h2>¿Cuándo entrenar fuera?</h2><p>{esc(lugar["nombre"])} · {esc(fuente)}. Mejores horas de las '
                   f'próximas 24 h por temperatura, lluvia, viento y calidad del aire.</p>{filas}')
except Exception as e:
    tiempo_html = f'<h2>¿Cuándo entrenar fuera?</h2><p>No se pudo consultar el tiempo ({esc(type(e).__name__)}).</p>'
H(f'<div class="lower-grid"><section class="panel">{tiempo_html}</section>'
  f'<section class="panel"><h2>Próximas citas</h2>{citas_html}</section></div>')

ui.pie()
