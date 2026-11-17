"""Paneles compartidos: «Hoy, evaluado» y «Mañana te recomiendo» (Mi previsión y Sensei te conoce)."""
from __future__ import annotations

from .baremo import num
from .ui import esc, fecha_es

NIVEL = {0: ("good", "Llegarás bien"), 1: ("watch", "Llegarás algo cargado"), 2: ("alert", "Llegarás con poca recuperación")}


def panel_recomendacion(rec: dict, grande: bool = True) -> str:
    r = rec["recomendacion"]
    cls, estado = NIVEL[r["nivel_previsto"]]
    pasos = "".join(f'<div class="next-step"><span>{i}</span><div><p style="margin:0;color:#203239">{esc(p)}</p></div></div>'
                    for i, p in enumerate(r["pasos"], 1))
    plan = ""
    if r.get("plan"):
        plan = (f'<p class="hint" style="margin-top:12px"><strong>Tienes planificado «{esc(r["plan"])}».</strong> '
                f'{esc(r["plan_veredicto"])}</p>')
    por = "; ".join(r["motivos"]) or "equilibrio de la semana"
    razones = " ".join(rec["razones"])
    alternativas = ""
    if grande and rec["alternativas"]:
        alternativas = '<h3 style="margin-top:20px;font-size:14px">Otras opciones</h3>' + "".join(
            f'<div class="evidence"><span>{esc(a["nombre"])}<br><small>{esc(a["motivo"])}</small></span>'
            f'<strong style="color:{"#315f4d" if a["apta"] else "#a14436"}">{"Válida" if a["apta"] else "Mejor no"}</strong></div>'
            for a in rec["alternativas"])
    return (f'<section class="panel"><div class="panel-head"><div><span class="eyebrow">Mañana · {fecha_es(rec["fecha"])}</span>'
            f'<h2 style="margin-top:6px">{esc(r["nombre"])}</h2></div><span class="badge {"green" if cls == "good" else ""}">'
            f'{esc(estado)}</span></div><p>Por qué: {esc(por)}. {esc(razones)}</p><div style="margin-top:8px">{pasos}</div>'
            f'{plan}{alternativas}</section>')


def panel_hoy(ev: dict, hoy) -> str:
    if ev["sesiones"]:
        ses = "".join(f'<div class="evidence"><span><strong>{esc(s["nombre"])}</strong>{"" if s["nombre"] == s["tipo"] else " · " + esc(s["tipo"])}'
                      f'<br><small>{esc(s["juicio"])}</small></span><strong>{num(s["min"], 0)} min'
                      f'{" · carga " + num(s["carga"], 0) if s["carga"] else ""}{" · FC " + num(s["fc"], 0) if s["fc"] else ""}'
                      f'</strong></div>' for s in ev["sesiones"])
    else:
        ses = '<p>Hoy aún no hay actividades en Garmin. Se evaluará sola en cuanto se descargue.</p>'
    r = ev["acwr"]
    semana = (f'Carga de la semana: {num(r["ratio"], 2)} veces tu media de 4 semanas '
              f'({"baja" if r["ratio"] < 0.8 else "en tu rango" if r["ratio"] <= 1.3 else "alta: no subas más"}).'
              if r.get("ratio") else "")
    m = ev["manana"]
    manana = ""
    if m:
        partes = []
        if "disposicion" in m:
            partes.append(f'disposición {num(m["disposicion"]["abs"], 0)}/100')
        if "vfc" in m:
            partes.append(f'VFC {num(m["vfc"]["abs"], 0)} ms ({"+" if m["vfc"]["dif"] >= 0 else ""}{num(m["vfc"]["dif"], 0)})')
        if "fc_reposo" in m:
            partes.append(f'pulso en reposo {num(m["fc_reposo"]["abs"], 0)} lpm')
        manana = f'<p class="hint" style="margin-top:12px">Con lo que has hecho hoy, mañana amanecerías con {", ".join(partes)}.</p>'
    n = ev["nutricion"]
    carga_txt = {"light": "descanso o suave", "moderate": "moderada", "endurance": "de resistencia"}[n["carga"]]
    nut = "".join(f'<li>{esc(c)}</li>' for c in n["consejos"]) or "<li>Registra lo que comes para valorarlo.</li>"
    return (f'<section class="panel"><div class="panel-head"><div><span class="eyebrow">Hoy · {fecha_es(hoy)}</span>'
            f'<h2 style="margin-top:6px">Tu día, evaluado</h2></div><span class="badge">Se actualiza solo</span></div>'
            f'<h3 style="margin-top:16px;font-size:14px">Entrenamiento</h3>{ses}<p>{esc(semana)}</p>{manana}'
            f'<h3 style="margin-top:18px;font-size:14px">Nutrición · día de carga {carga_txt} · {esc(n["estado"])}</h3>'
            f'<p>Referencia de hoy: ≥ {n["prot_min"]:.0f} g de proteína y ≥ {n["hc_min"]:.0f} g de hidratos.</p>'
            f'<ul style="margin:8px 0 0 18px;font-size:12px;line-height:1.8;color:#55665d">{nut}</ul></section>')
