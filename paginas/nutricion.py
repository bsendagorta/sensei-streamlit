import uuid

import streamlit as st

from sensei import apis, ui
from sensei.app_comun import (CARGAS_DIA, COMIDAS, HC_POR_CARGA, PROTEINA_GKG, ajustes, datos, dia_nutricion, guardar,
                              hoy, totales)
from sensei.baremo import num

ui.pagina("Nutrición", "nutricion")
d, a, h = datos(), ajustes(), hoy()
esc, H = ui.esc, ui.html


@st.cache_data(ttl=86400, show_spinner=False)
def _buscar(q):
    return apis.buscar_alimentos(q)


@st.dialog("Añadir alimento", width="large")
def anadir(fecha: str):
    q = st.text_input("Buscar en Open Food Facts", placeholder="Nombre o código de barras")
    elegido = {}
    if q:
        try:
            res = _buscar(q)
        except Exception as e:
            res = []
            st.warning(f"Open Food Facts no responde ({type(e).__name__}). Escribe los valores a mano.")
        if res:
            i = st.selectbox("Resultado", range(len(res)), format_func=lambda i: (
                f'{res[i]["nombre"]} · {res[i]["marca"]} — {res[i]["prot_100"] if res[i]["prot_100"] is not None else "?"} g '
                f'prot / {res[i]["kcal_100"] if res[i]["kcal_100"] is not None else "?"} kcal por 100 g'))
            elegido = res[i]
    c1, c2, c3 = st.columns([2, 1, 1])
    nombre = c1.text_input("Alimento", value=elegido.get("nombre", ""))
    comida = c2.selectbox("Comida", COMIDAS)
    hora = c3.text_input("Hora", placeholder="08:00")
    base = st.radio("Los valores son de…", ["100 g / 100 ml", "toda la cantidad"], horizontal=True)
    gramos = st.number_input("Cantidad (g o ml)", 1.0, 3000.0, 100.0, 10.0) if base == "100 g / 100 ml" else None
    c = st.columns(4)
    kcal = c[0].number_input("kcal", 0.0, 5000.0, value=elegido.get("kcal_100"))
    prot = c[1].number_input("Proteínas (g)", 0.0, 500.0, value=elegido.get("prot_100"))
    hc = c[2].number_input("Hidratos (g)", 0.0, 1000.0, value=elegido.get("hc_100"))
    gr = c[3].number_input("Grasas (g)", 0.0, 500.0, value=elegido.get("grasa_100"))
    st.caption("Lo que no sepas, déjalo vacío: cuenta como desconocido, no como 0.")
    if st.button("Añadir", type="primary"):
        if not nombre.strip():
            st.error("Escribe el nombre del alimento.")
            return
        k = (gramos / 100) if gramos else 1

        def x(v):
            return None if v is None else round(v * k, 1)
        e = {"id": uuid.uuid4().hex[:10], "fecha": fecha, "comida": comida, "nombre": nombre.strip(),
             "cantidad": f"{num(gramos, 0)} g" if gramos else "1 ración", "gramos": gramos, "hora": hora.strip() or None,
             "kcal": x(kcal), "prot": x(prot), "hc": x(hc), "grasa": x(gr), "codigo": elegido.get("codigo")}
        if guardar(lambda dd: dd["comidas"].append(e), f"Comida {fecha}"):
            st.rerun()


c1, c2 = st.columns([4, 1.4], vertical_alignment="bottom")
with c1:
    H('<div class="section-head"><div><h1>Nutrición</h1></div></div>')

with st.container(key="panel_nutri"):
    t1, t2, t3, t4 = st.columns([1.2, 1.2, 1, 1.2], vertical_alignment="bottom")
    fecha = t1.date_input("Día del registro", h, max_value=h, format="DD/MM/YYYY").isoformat()
    dia = dia_nutricion(d, fecha)
    carga = t2.selectbox("Carga del día", list(CARGAS_DIA), index=list(CARGAS_DIA).index(dia["carga"]),
                         format_func=CARGAS_DIA.get)
    peso = t3.number_input("Peso actual (kg)", 30.0, 250.0, float(a["peso_kg"]), 0.5)
    completo = t4.checkbox("He registrado todo el día", value=dia["completo"])

if carga != dia["carga"] or completo != dia["completo"] or peso != a["peso_kg"]:
    def cambio(x):
        x.setdefault("dias_nutricion", {}).setdefault(fecha, {})["carga"] = carga
        s = set(x.get("dias_nutricion_completos", []))
        (s.add if completo else s.discard)(fecha)
        x["dias_nutricion_completos"] = sorted(s)
        x.setdefault("ajustes", {})["peso_kg"] = peso
    if guardar(cambio, f"Nutrición {fecha}: día"):
        st.rerun()

with c2:
    if st.button("＋ Añadir alimento", type="primary", use_container_width=True):
        anadir(fecha)

H('<p class="info-note">«Referencias cubiertas» indica que, al cerrar el día, alcanzas las referencias de proteína e '
  'hidratos. No evalúa por sí solo energía, vitaminas ni la calidad global de la dieta.</p>')

entradas = [c for c in d["comidas"] if c["fecha"] == fecha]
t = totales(entradas)
g = next((x for x in d["garmin_diario"] if x["fecha"] == fecha), {})
gasto = g.get("kcal_total")
p_lo, p_hi = PROTEINA_GKG[0] * peso, PROTEINA_GKG[1] * peso
h_lo, h_hi = (v * peso for v in HC_POR_CARGA[carga])
parcial = fecha >= h.isoformat()
H(f'''<div class="nutrition-stats">
<div class="panel"><h3>Ingesta registrada</h3><strong>{num(t["kcal"], 0)} <small>kcal</small></strong><p>{t["kcal_conocidos"]}/{t["n"]} alimentos con calorías</p></div>
<div class="panel"><h3>Gasto total Garmin</h3><strong>{num(gasto, 0)} <small>kcal</small></strong><p>{"Día parcial · sin balance final" if parcial else "Día cerrado"}</p></div>
<div class="panel"><h3>Proteínas registradas</h3><strong>{num(t["prot"], 0)} <small>g</small></strong><p>Referencia: {p_lo:.0f}–{p_hi:.0f} g/día</p></div>
<div class="panel"><h3>Hidratos registrados</h3><strong>{num(t["hc"], 0)} <small>g</small></strong><p>Referencia: {h_lo:.0f}–{h_hi:.0f} g/día</p></div></div>''')

if not t["n"]:
    lectura = "Añade lo que comes para empezar a valorar el día."
elif not completo:
    lectura = "Día abierto: registra el resto de comidas antes de sacar conclusiones."
elif t["kcal_conocidos"] != t["n"]:
    lectura = "Faltan calorías en algunos alimentos. La ingesta conocida es solo un mínimo."
elif not gasto or parcial:
    lectura = "Ingesta completa. Falta un gasto de Garmin de día cerrado para comparar energía."
else:
    dif = t["kcal"] - gasto
    lectura = f"Diferencia estimada: {dif:+.0f} kcal frente a Garmin. Revisa varios días, peso y hambre antes de cambiar nada."
H(f'<div class="load-summary"><strong>Lectura del día</strong><span>{esc(lectura)}</span><span class="subtle">Las '
  f'referencias son rangos generales para orientar tu preparación; la carga se elige manualmente.</span></div>')

paneles = []
for comida in COMIDAS:
    es = [e for e in entradas if (e.get("comida") or "Otros") == comida]
    if not es:
        continue
    filas = "".join(
        f'<div class="food-row"><div><strong>{esc(e["nombre"])}</strong><p><small>{esc(e.get("cantidad") or "")}'
        f'{" · " + esc(e["hora"]) if e.get("hora") else " · Sin hora"}{" · " + esc(e["fuente"]) if e.get("fuente") else ""}'
        f'</small></p></div><small>{num(e.get("kcal"), 0)} kcal · {num(e.get("prot"), 0)} g prot</small></div>' for e in es)
    paneles.append(f'<section class="panel meal-panel"><h3>{esc(comida)}</h3>{filas}</section>')
lista = "".join(paneles) or '<div class="empty-state">Nada registrado este día.</div>'


def barra(valor, hi):
    pct = 0 if valor is None else min(100, valor / hi * 100)
    return f'<progress max="100" value="{pct:.0f}"></progress>'


objetivo = (f'<section class="panel"><h2>Tu objetivo: rendir al máximo</h2><p>Priorizamos cubrir el entrenamiento y la '
            f'recuperación, sin fijar un déficit de peso.</p><div class="macro-track"><strong>Proteínas</strong>'
            f'{barra(t["prot"], p_hi)}<small>{num(t["prot"], 0)} g de {p_lo:.0f}–{p_hi:.0f} g</small></div>'
            f'<div class="macro-track"><strong>Hidratos</strong>{barra(t["hc"], h_hi)}<small>{num(t["hc"], 0)} g de '
            f'{h_lo:.0f}–{h_hi:.0f} g</small></div></section>')
H(f'<h2 style="font-size:22px;margin-top:28px">Tus comidas, en orden</h2><div class="nutrition-columns"><div>{lista}</div>'
  f'<div>{objetivo}</div></div>')

if entradas:
    with st.expander("Borrar un alimento de este día"):
        i = st.selectbox("Alimento", range(len(entradas)),
                         format_func=lambda i: f'{entradas[i].get("comida")} · {entradas[i]["nombre"]}')
        if st.button("Borrar", disabled=not st.checkbox("Confirmo el borrado")):
            objetivo_id = entradas[i]["id"]
            if guardar(lambda x: x.update(comidas=[c for c in x["comidas"] if c.get("id") != objetivo_id]), "Comida borrada"):
                st.rerun()
ui.pie()
