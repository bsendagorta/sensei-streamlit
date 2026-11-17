import uuid
from datetime import timedelta

import pandas as pd
import streamlit as st

from sensei import apis
from sensei.app_comun import ajustes, datos, guardar, hoy

st.title("Nutrición")
d, a = datos(), ajustes()
fecha = st.date_input("Día", hoy(), max_value=hoy(), format="DD/MM/YYYY")
f = fecha.isoformat()

st.subheader("Añadir alimento")
st.caption("Busca por nombre o código de barras (Open Food Facts) o escribe los valores a mano.")


@st.cache_data(ttl=86400, show_spinner=False)
def _buscar(q):
    return apis.buscar_alimentos(q)


q = st.text_input("Buscar", placeholder="p. ej. yogur griego, avena, 8410… (código de barras)")
elegido = None
if q:
    try:
        res = _buscar(q)
    except Exception as e:
        res = []
        st.warning(f"Open Food Facts no responde ({type(e).__name__}). Usa la entrada manual.")
    if res:
        idx = st.selectbox("Resultado", range(len(res)), format_func=lambda i: (
            f"{res[i]['nombre']} · {res[i]['marca']} — "
            f"{res[i]['prot_100'] if res[i]['prot_100'] is not None else '?'} g prot / "
            f"{res[i]['kcal_100'] if res[i]['kcal_100'] is not None else '?'} kcal por 100 g"))
        elegido = res[idx]
    elif q:
        st.caption("Sin resultados.")

with st.form("comida", clear_on_submit=True):
    nombre = st.text_input("Alimento", value=(elegido or {}).get("nombre", ""))
    gramos = st.number_input("Cantidad (g o ml)", 1.0, 3000.0, value=100.0, step=10.0)
    c1, c2, c3, c4 = st.columns(4)
    kcal = c1.number_input("kcal/100", 0.0, 1000.0, value=(elegido or {}).get("kcal_100"))
    prot = c2.number_input("Prot/100", 0.0, 100.0, value=(elegido or {}).get("prot_100"))
    hc = c3.number_input("HC/100", 0.0, 100.0, value=(elegido or {}).get("hc_100"))
    grasa = c4.number_input("Grasa/100", 0.0, 100.0, value=(elegido or {}).get("grasa_100"))
    if st.form_submit_button("Añadir", type="primary"):
        if not nombre.strip():
            st.error("Escribe el nombre del alimento.")
        else:
            k = gramos / 100

            def x(v):
                return None if v is None else round(v * k, 1)  # desconocido = vacío, no 0
            c = {"id": uuid.uuid4().hex[:10], "fecha": f, "nombre": nombre.strip(), "gramos": gramos,
                 "kcal": x(kcal), "prot": x(prot), "hc": x(hc), "grasa": x(grasa),
                 "codigo": (elegido or {}).get("codigo")}
            if guardar(lambda dd: dd["comidas"].append(c), f"Comida {f}"):
                st.success("Añadido.")

st.subheader("Resumen del día")
del_dia = [c for c in d["comidas"] if c["fecha"] == f]
if del_dia:
    df = pd.DataFrame(del_dia)[["nombre", "gramos", "kcal", "prot", "hc", "grasa"]]
    st.dataframe(df, hide_index=True, width="stretch")

    def suma(col):
        vals = [c[col] for c in del_dia if c.get(col) is not None]
        faltan = len(del_dia) - len(vals)
        return sum(vals), faltan
    p, fp = suma("prot")
    kc, fk = suma("kcal")
    c1, c2 = st.columns(2)
    c1.metric("Proteína", f"{p:.0f} g", help=f"{fp} alimento(s) sin dato de proteína" if fp else None)
    c2.metric("Energía", f"{kc:.0f} kcal", help=f"{fk} alimento(s) sin dato de kcal" if fk else None)
    peso = a.get("peso_kg")
    if peso:
        lo, hi = 1.6 * peso, 2.2 * peso
        completo = f in d["dias_nutricion_completos"]
        estado = ("en rango" if lo <= p <= hi else "por debajo" if p < lo else "por encima") if completo else "día sin cerrar"
        st.caption(f"Objetivo de proteína para fuerza: {lo:.0f}–{hi:.0f} g/día (1,6–2,2 g/kg, {peso:g} kg) · {estado}.")
    else:
        st.caption("Pon tu peso en Ajustes para ver el objetivo de proteína.")
else:
    st.caption("Nada registrado este día.")

if f not in d["dias_nutricion_completos"]:
    if st.button("He registrado todo el día"):
        guardar(lambda dd: dd["dias_nutricion_completos"].append(f), f"Nutrición {f} completa")
        st.rerun()
else:
    st.caption("✅ Día marcado como completo.")

# Últimos 7 días cerrados
cerrados = [x for x in sorted(d["dias_nutricion_completos"]) if x >= (hoy() - timedelta(days=6)).isoformat()]
if cerrados:
    prot7 = [sum(c["prot"] or 0 for c in d["comidas"] if c["fecha"] == x) for x in cerrados]
    st.caption(f"Proteína media en {len(cerrados)} día(s) completos de la última semana: "
               f"{sum(prot7) / len(prot7):.0f} g.")
