import uuid

import streamlit as st

from sensei import apis, ui
from sensei.app_comun import (CARGAS_DIA, COMIDAS, HC_POR_CARGA, PROTEINA_GKG, ajustes, borrar_registros, datos,
                              dia_nutricion, editar_registro, guardar, hoy, totales)
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
    carga = t2.selectbox("Carga del día" + (" (deducida de Garmin)" if dia["carga_auto"] else ""), list(CARGAS_DIA), index=list(CARGAS_DIA).index(dia["carga"]),
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



@st.dialog("Editar alimento", width="large")
def editar(e: dict):
    c1, c2, c3 = st.columns([2, 1, 1])
    nombre = c1.text_input("Alimento", e["nombre"])
    comida = c2.selectbox("Comida", COMIDAS, index=COMIDAS.index(e.get("comida")) if e.get("comida") in COMIDAS else 5)
    hora = c3.text_input("Hora", e.get("hora") or "")
    c1, c2 = st.columns([1, 2])
    fecha_n = c1.date_input("Día", ui.date.fromisoformat(e["fecha"]), max_value=h, format="DD/MM/YYYY")
    cantidad = c2.text_input("Cantidad (texto libre)", e.get("cantidad") or "")
    st.caption("Valores de la cantidad que comiste (no por 100 g). Vacío = desconocido.")
    c = st.columns(4)
    kcal = c[0].number_input("kcal", 0.0, 5000.0, value=e.get("kcal"))
    prot = c[1].number_input("Proteínas (g)", 0.0, 500.0, value=e.get("prot"))
    hc = c[2].number_input("Hidratos (g)", 0.0, 1000.0, value=e.get("hc"))
    gr = c[3].number_input("Grasas (g)", 0.0, 500.0, value=e.get("grasa"))
    nota = st.text_input("Nota / de dónde sale", e.get("fuente") or "")
    b1, b2 = st.columns(2)
    if b1.button("Guardar cambios", type="primary", use_container_width=True):
        if not nombre.strip():
            st.error("El nombre no puede quedar vacío.")
            return
        if editar_registro("comidas", e["id"], {"nombre": nombre.strip(), "comida": comida, "hora": hora.strip() or None,
                                                "fecha": fecha_n.isoformat(), "cantidad": cantidad.strip(), "kcal": kcal,
                                                "prot": prot, "hc": hc, "grasa": gr, "fuente": nota.strip() or None},
                           f"Comida editada: {nombre.strip()}"):
            st.rerun()
    if b2.checkbox("Quiero borrarlo") and b2.button("Borrar alimento", use_container_width=True):
        if borrar_registros("comidas", [e["id"]], f"Comida borrada: {e['nombre']}"):
            st.rerun()


@st.dialog("Unir alimentos en un solo plato", width="large")
def unir(entradas: list[dict]):
    st.caption("Suma kcal y macros de los alimentos elegidos y los deja como un único plato.")
    elegidos = st.multiselect("Alimentos", range(len(entradas)), format_func=lambda i: (
        f'{entradas[i].get("comida")} · {entradas[i]["nombre"]} ({num(entradas[i].get("kcal"), 0)} kcal)'))
    if len(elegidos) >= 2:
        sel = [entradas[i] for i in elegidos]
        nombre = st.text_input("Nombre del plato", " con ".join(x["nombre"] for x in sel))

        def suma(k):
            v = [x.get(k) for x in sel]
            return None if any(x is None for x in v) else round(sum(v), 1)
        st.markdown(f"**Resultado:** {num(suma('kcal'), 0)} kcal · {num(suma('prot'), 0)} g proteína · "
                    f"{num(suma('hc'), 0)} g hidratos · {num(suma('grasa'), 0)} g grasas")
        if st.button("Unir", type="primary"):
            principal, resto = sel[0], [x["id"] for x in sel[1:]]
            cambios = {"nombre": nombre.strip(), "kcal": suma("kcal"), "prot": suma("prot"), "hc": suma("hc"),
                       "grasa": suma("grasa"), "cantidad": "1 plato",
                       "fuente": " + ".join(x.get("fuente") or x["nombre"] for x in sel)}

            def cambio(x):
                for r in x["comidas"]:
                    if r["id"] == principal["id"]:
                        r.update(cambios)
                        r["origen"] = "web"
                x["comidas"] = [r for r in x["comidas"] if r["id"] not in resto]
                x.setdefault("borrados_sensei", []).extend(i for i in resto if str(i).startswith("sensei-"))
            if guardar(cambio, f"Comidas unidas: {nombre.strip()}"):
                st.rerun()


H('<h2 style="font-size:22px;margin-top:28px">Tus comidas, en orden</h2>')
izq, der = st.columns([1.6, 1], gap="large")
with izq:
    if not entradas:
        H('<div class="empty-state">Nada registrado este día.</div>')
    for n_comida, comida in enumerate(COMIDAS):
        es = [e for e in entradas if (e.get("comida") or "Otros") == comida]
        if not es:
            continue
        with st.container(key=f"panel_meal_{n_comida}"):
            H(f'<h3 style="font-size:18px;font-weight:600;border-bottom:1px solid #e4e9e4;padding-bottom:12px">{esc(comida)}</h3>')
            for e in es:
                c1, c2 = st.columns([5, 1], vertical_alignment="center")
                with c1:
                    H(f'<div class="food-row" style="border:0;padding:6px 0"><div><strong>{esc(e["nombre"])}</strong><p><small>'
                      f'{esc(e.get("cantidad") or "")}{" · " + esc(e["hora"]) if e.get("hora") else " · Sin hora"} · '
                      f'{num(e.get("kcal"), 0)} kcal · {num(e.get("prot"), 0)} g prot · {num(e.get("hc"), 0)} g HC · '
                      f'{num(e.get("grasa"), 0)} g grasa{" · " + esc(e["fuente"]) if e.get("fuente") else ""}</small></p></div></div>')
                if c2.button("Editar", key=f"ed_{e['id']}", use_container_width=True):
                    editar(e)
    if len(entradas) >= 2 and st.button("Unir alimentos en un plato", icon="🔗"):
        unir(entradas)


def barra(valor, hi):
    pct = 0 if valor is None else min(100, valor / hi * 100)
    return f'<progress max="100" value="{pct:.0f}"></progress>'


with der:
    H(f'<section class="panel"><h2>Tu objetivo: rendir al máximo</h2><p>Priorizamos cubrir el entrenamiento y la '
      f'recuperación, sin fijar un déficit de peso.</p><div class="macro-track"><strong>Proteínas</strong>'
      f'{barra(t["prot"], p_hi)}<small>{num(t["prot"], 0)} g de {p_lo:.0f}–{p_hi:.0f} g</small></div>'
      f'<div class="macro-track"><strong>Hidratos</strong>{barra(t["hc"], h_hi)}<small>{num(t["hc"], 0)} g de '
      f'{h_lo:.0f}–{h_hi:.0f} g</small></div></section>')
ui.pie()
