import streamlit as st

from sensei import ui
from sensei.app_comun import aprendizaje, datos, evaluacion_y_recomendacion, guardar, hoy
from sensei.aprendizaje import modelo_sensacion, predecir_sensacion
from sensei.baremo import num
from sensei.conocerte import OBJETIVOS, TIPOS, frases, simular
from sensei.graficos import linea
from sensei.paneles import panel_hoy, panel_recomendacion

ui.pagina("Sensei te conoce", "conoce")
d, h = datos(), hoy()
esc, H = ui.esc, ui.html

R = aprendizaje()
M = R["modelos"]
ev, rec = evaluacion_y_recomendacion()
utiles = [m for m in M.values() if m.get("ok") and m["util"]]

# Foto diaria del acierto, para ver con el tiempo si de verdad mejora
if utiles:
    foto = {"fecha": h.isoformat(), "dias": R["filas"], **{o: round(m["mae"], 2) for o, m in M.items() if m.get("ok")}}
    hist = d.get("aprendizaje_historial", [])
    if not hist or hist[-1]["fecha"] != foto["fecha"]:
        guardar(lambda x: x.setdefault("aprendizaje_historial", []).append(foto), "Aprendizaje: foto diaria")

H(f'''<div id="view-overview"><section class="hero"><div><div class="eyebrow">Tu modelo personal</div><h1>Sensei te conoce</h1>
<p style="margin-top:8px">Ha aprendido de {R["filas"]} días de Garmin y {len(d["garmin_actividades"])} actividades tuyas, y se
reentrena solo con cada dato nuevo. Arriba, lo que debes hacer; abajo, lo que sabe de ti.</p></div>
<div class="exam-box"><div class="days">{len(utiles)}/{len(OBJETIVOS)}</div><div class="days-label">predicciones que ya
aciertan más que tu media</div></div></section></div>''')

# 1. Lo que importa: qué hacer mañana y cómo ha ido hoy
H(f'<div class="lower-grid">{panel_recomendacion(rec)}{panel_hoy(ev, h)}</div>')

# 2. Lo que sabe de ti, en frases
lista = frases(R, R.get("recuperacion"))
if lista:
    H('<div class="section-head" style="margin-top:27px"><div><h2>Lo que sé de ti</h2><p>Conclusiones sacadas de tus datos. '
      'Las marcadas «se está confirmando» tienen aún pocos casos.</p></div></div><section class="panel">'
      + "".join(f'<div class="next-step"><span style="font-size:20px">{f["icono"]}</span><div><strong style="font-size:14px;'
                f'font-weight:500;line-height:1.6">{esc(f["texto"])}</strong><p>{"Demostrado" if f["solida"] else "Se está confirmando"}'
                f'{" · " + str(f["n"]) + " casos" if f.get("n") else ""}</p></div></div>' for f in lista) + '</section>')

# 3. Probar otras opciones
H('<div class="section-head" style="margin-top:27px"><div><h2>¿Y si mañana hago otra cosa?</h2><p>Elige un plan y mira cómo '
  'amanecerías pasado mañana según lo que he aprendido de ti.</p></div></div>')
c1, c2 = st.columns([1.3, 2])
opciones = {"descanso": "Descanso"} | {k: v for k, v in TIPOS.items() if k in R["tasa"]}
tipo = c1.selectbox("Si mañana hago…", list(opciones), format_func=opciones.get)
minutos = c2.slider("Minutos", 10, 120, 50, 5, disabled=tipo == "descanso")
sim = simular(d, M, h, None if tipo == "descanso" else tipo, minutos)
desc = simular(d, M, h, None, 0)
if sim:
    tarjetas = []
    for obj, (nombre, unidad, alto_mejor) in OBJETIVOS.items():
        p = sim.get(obj)
        if not p or p["abs"] is None:
            continue
        frente = p["dif"] - desc[obj]["dif"]
        peor = (frente < -1) if alto_mejor else (frente > 0.5)
        cls = "alert" if peor and abs(frente) > (10 if unidad == "/100" else 3) else "watch" if peor else "good"
        tarjetas.append(f'<div class="insight-card {cls}"><small>{esc(nombre.replace(" de mañana", "").replace(" mañana", ""))}'
                        f'</small><strong>{num(p["abs"], 0)} {esc(unidad)}</strong><small class="insight-note">'
                        f'{"igual que descansando" if tipo == "descanso" or abs(frente) < 0.5 else ("+" if frente > 0 else "") + num(frente, 0) + " frente a descansar"}'
                        f'</small></div>')
    H(f'<section class="panel"><div class="insight-grid">{"".join(tarjetas)}</div><p class="subtle" style="margin-top:12px">'
      f'Estimación con margen de error (± a la derecha en los detalles). El semáforo de cada mañana manda.</p></section>')
else:
    H('<p class="info-note">Necesito la lectura de Garmin de hoy para simular. Pulsa «Actualizar Garmin».</p>')

# 4. Lo que solo tú le puedes enseñar
ms = modelo_sensacion(d)
if ms["ok"]:
    pred = predecir_sensacion(ms, d, h)
    txt = (f'Con {ms["n"]} check-ins predice tu sensación con un error de {num(ms["mae"])} puntos (sin modelo '
           f'{num(ms["mae_ref"])}).' + (f' Hoy esperaría un {num(pred)}/10.' if pred else ""))
else:
    txt = (f'{ms["motivo"]} Cada check-in de 20 s (sensación y molestias) le enseña cómo te sientes tú, no solo lo que '
           'mide el reloj, y evita recomendarte series con una molestia.')
H(f'<section class="panel" style="margin-top:23px"><h2>Lo que solo tú le puedes enseñar</h2><p>{esc(txt)}</p></section>')
st.page_link("paginas/registrar.py", label="Hacer el check-in de hoy", icon="✍️")

# 5. Detalles técnicos, plegados
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
efectos = []
for obj, (nombre, unidad, alto_mejor) in OBJETIVOS.items():
    m = M[obj]
    if not m.get("ok"):
        continue
    lin = "".join(f'<div class="evidence"><span>{esc(e["nombre"])}</span><strong style="color:'
                  f'{"#315f4d" if (e["efecto"] > 0) == alto_mejor else "#a14436"}">{"+" if e["efecto"] >= 0 else ""}'
                  f'{num(e["efecto"], 1)} {esc(unidad)}</strong></div>' for e in m["efectos"][:5])
    curva = ""
    if len(m["curva"]) >= 2:
        curva = (f'<div class="chart">{linea([x["mae"] for x in m["curva"]], [x["periodo"] for x in m["curva"]], unidad, media=[x["ref"] for x in m["curva"]])}'
                 f'</div><p class="subtle">Error por trimestre: modelo (línea) frente a no tener modelo (puntos).</p>')
    efectos.append(f'<section class="panel"><div class="panel-head"><h3>{esc(nombre)}</h3><span class="badge '
                   f'{"green" if m["util"] else ""}">±{num(m["mae"], 1)} · {"+" if m["mejora_pct"] >= 0 else ""}{num(m["mejora_pct"], 0)} %</span></div>'
                   f'<p>Validado en {m["n_validados"]} días.</p>{lin}{curva}</section>')
H(f'''<details class="projection-how" style="margin-top:27px"><summary>Ver los detalles del modelo</summary>
<section class="panel" style="margin-top:14px"><h3>Cómo amaneces tras cada tipo de día</h3><p>Respecto a tu media de 28 días, al
día siguiente (D+1) y a los dos días (D+2). En color, lo demostrado (IC 95 %); en gris, lo que aún no.</p><div class="table-scroll">
<table><thead><tr><th>Tipo de día</th><th>VFC D+1</th><th>VFC D+2</th><th>Pulso D+1</th><th>Pulso D+2</th><th>Disposición D+1</th>
</tr></thead><tbody>{"".join(filas)}</tbody></table></div></section>
<div class="dashboard-grid">{"".join(efectos)}</div></details>''')
ui.pie()
