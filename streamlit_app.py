import streamlit as st

from sensei.app_comun import exigir_acceso

st.set_page_config(page_title="Sensei", page_icon="🔥", layout="centered")
exigir_acceso()

paginas = st.navigation([
    st.Page("paginas/hoy.py", title="Hoy", icon="🚦", default=True),
    st.Page("paginas/registrar.py", title="Registrar", icon="✍️"),
    st.Page("paginas/aprende.py", title="Aprende de ti", icon="🧠"),
    st.Page("paginas/pruebas.py", title="Pruebas y previsión", icon="🎯"),
    st.Page("paginas/recuperacion.py", title="Carga y recuperación", icon="📈"),
    st.Page("paginas/nutricion.py", title="Nutrición", icon="🍽️"),
    st.Page("paginas/historial.py", title="Historial", icon="🗂️"),
    st.Page("paginas/ajustes.py", title="Ajustes", icon="⚙️"),
])
paginas.run()
