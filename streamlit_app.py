import streamlit as st

from sensei.app_comun import exigir_acceso
from sensei.ui import PAGINAS, PAGINAS_EXTRA, icono_web

st.set_page_config(page_title="Sensei", page_icon="static/sensei-64.png", layout="wide", initial_sidebar_state="expanded")
icono_web()
exigir_acceso()

paginas = [st.Page(archivo, title=titulo, url_path=slug, default=(i == 0))
           for i, (archivo, titulo, slug) in enumerate(PAGINAS + PAGINAS_EXTRA)]
st.navigation(paginas, position="hidden").run()
