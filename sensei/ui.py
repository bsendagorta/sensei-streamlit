"""Aspecto de Sensei.app en Streamlit.

Usa la hoja de estilos de la app de Mac (assets/sensei.css = macos-app/UI.css) sin cambios, limitada al
contenedor `.sensei` para que no choque con los estilos de Streamlit, y ajusta los controles de Streamlit
(barra lateral, botones, campos) a los mismos colores y formas.
"""
from __future__ import annotations

import html as _html
import re
from datetime import date  # noqa: F401  (usado por las páginas como ui.date)
from functools import lru_cache
from pathlib import Path

import streamlit as st

CSS_SENSEI = Path(__file__).parent / "assets" / "sensei.css"
PREFIJO = "div.sensei"

PAGINAS = [  # (archivo, título, slug)
    ("paginas/prevision.py", "Mi previsión", "prevision"),
    ("paginas/conoce.py", "Sensei te conoce", "conoce"),
    ("paginas/entrenamientos.py", "Entrenamientos", "entrenamientos"),
    ("paginas/controles.py", "Controles", "controles"),
    ("paginas/rendimiento.py", "Rendimiento", "rendimiento"),
    ("paginas/recuperacion.py", "Recuperación", "recuperacion"),
    ("paginas/nutricion.py", "Nutrición", "nutricion"),
]
PAGINAS_EXTRA = [
    ("paginas/registrar.py", "Check-in y sesiones", "registrar"),
    ("paginas/ajustes.py", "Ajustes", "ajustes"),
    ("paginas/historial.py", "Datos y copias", "historial"),
]

MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre"]
ESTADO_ICONO = {0: "🟢", 1: "🟡", 2: "🔴", None: "⚪"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def esc(x) -> str:
    return _html.escape("" if x is None else str(x))


def hora_actual():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None, minute=0, second=0, microsecond=0)


def fecha_es(f) -> str:
    d = f if isinstance(f, date) else date.fromisoformat(str(f)[:10])
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


# --------------------------------------------------------------------------- CSS

def _scope(css: str) -> str:
    out, i, n = [], 0, len(css)
    while i < n:
        if css.startswith("/*", i):
            i = css.index("*/", i) + 2
            continue
        j = css.find("{", i)
        if j < 0:
            break
        cabecera = css[i:j].strip()
        if cabecera.startswith("@media") or cabecera.startswith("@supports"):
            prof, k = 1, j + 1
            while prof:
                prof += {"{": 1, "}": -1}.get(css[k], 0)
                k += 1
            out.append(cabecera + "{" + _scope(css[j + 1:k - 1]) + "}")
            i = k
            continue
        k = css.index("}", j)
        cuerpo = css[j + 1:k]
        sels = []
        for s in cabecera.split(","):
            s = s.strip()
            if s in (":root", "html", "body"):
                sels.append(PREFIJO)
            elif s:
                sels.append(f"{PREFIJO} {s}")
        out.append(",".join(sels) + "{" + cuerpo + "}")
        i = k + 1
    return "".join(out)


AJUSTES_STREAMLIT = """
:root{--ink:#203239;--muted:#6c7a72;--green:#315f4d;--line:#dce4dc;--navy:#172e35;--lime:#d8eca3}
html,body,[data-testid="stApp"],[data-testid="stMain"]{background:#f4f5f2!important;color:#203239;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
[data-testid="stApp"] :is(p,div,label,input,button,h1,h2,h3,li,td,th,textarea,small,strong,a):not([data-testid="stIconMaterial"]){font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
[data-testid="stHeader"]{background:transparent}
[data-testid="stDecoration"],[data-testid="stSidebarNav"],[data-testid="stToolbarActions"],[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],[data-testid="stHeaderActionElements"],.stDeployButton{display:none!important}
[data-testid="stToolbar"]{background:transparent}
[data-testid="stMainBlockContainer"]{max-width:1550px;padding:27px 34px 40px}
@media(max-width:850px){[data-testid="stMainBlockContainer"]{padding:56px 15px 30px}}
div.sensei{font-size:15px;color:#203239;background:transparent!important}
section[data-testid="stSidebar"],section[data-testid="stSidebar"]>div{width:215px!important;min-width:215px!important;max-width:215px!important}
[data-testid="stSidebar"] div.sensei .wordmark{color:#e8eee7}
div.sensei h1,div.sensei h2,div.sensei h3{padding:0;margin:0;font-family:inherit;color:inherit;line-height:1.2}
div.sensei p{margin-bottom:0}
div.sensei a.anchor-link{display:none}
[data-testid="stMarkdownContainer"]:has(div.sensei){margin-bottom:0}
/* Barra lateral */
[data-testid="stSidebar"]{background:#172e35!important}
[data-testid="stSidebar"]>div:first-child{background:#172e35}
[data-testid="stSidebarContent"]{padding:20px 20px}
[data-testid="stSidebar"] [data-testid="stPageLink"] a{border-radius:10px;padding:11px 17px;background:none}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover{background:#ffffff0a}
[data-testid="stSidebar"] [data-testid="stPageLink"] p,[data-testid="stSidebar"] [data-testid="stPageLink"] span{
 color:#c3d0c7!important;font-size:14px;font-weight:400}
[data-testid="stSidebar"] [class*="st-key-navsel_"] a{background:#ffffff12}
[data-testid="stSidebar"] [class*="st-key-navsel_"] p{color:#d8eca3!important}
[data-testid="stSidebar"] [class*="st-key-navx"] p{font-size:12px!important;color:#adc0b4!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:4px}
[data-testid="stSidebarCollapseButton"]{visibility:visible!important}
[data-testid="stSidebarCollapseButton"] button{background:#ffffff14;border-radius:9px}
[data-testid="stSidebarCollapseButton"] *{color:#e8eee7!important}
[data-testid="stExpandSidebarButton"]{background:#172e35!important;color:#e8eee7!important;border-radius:11px!important;
  padding:6px 13px 6px 9px!important;height:auto!important;width:auto!important;box-shadow:0 4px 14px #0f1f2433;gap:6px;display:inline-flex!important;align-items:center}
[data-testid="stExpandSidebarButton"] *{color:#e8eee7!important}
[data-testid="stExpandSidebarButton"]::after{content:"Menú";font:600 13px/1 Inter,system-ui,sans-serif;color:#e8eee7}
/* Botones */
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"],[data-testid="stDownloadButton"] button{
 background:#fff;border:1px solid #dce4dc;border-radius:9px;color:#203239;min-height:40px}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{
 background:#172e35!important;border:1px solid #172e35!important;border-radius:9px;color:#fff!important;min-height:40px}
[data-testid="stBaseButton-secondary"] p,[data-testid="stBaseButton-primary"] p,[data-testid="stDownloadButton"] p,
[data-testid*="FormSubmit"] p{font-size:12px;font-weight:600}
[data-testid="stBaseButton-tertiary"] p{color:#315f4d;font-size:12px;font-weight:600}
[data-testid="stBaseButton-secondary"]:hover,[data-testid="stDownloadButton"] button:hover{border-color:#b9c7bc;color:#203239}
/* Campos */
[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] label{font-size:12px!important;color:#6c7a72!important}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{border-radius:9px!important;
 border-color:#dce4dc!important;background:#fff!important}
[data-baseweb="input"] input,[data-baseweb="textarea"] textarea{background:#fff!important;color:#203239;font-size:13px}
[data-testid="stCheckbox"] p{font-size:12px;color:#6c7a72}
[class*="st-key-btnlink"] a{background:#172e35;border-radius:9px;min-height:40px;justify-content:center;padding:8px 15px}
[class*="st-key-btnlink"] a p{color:#fff!important;font-size:12px;font-weight:600}
/* Contenedores con aspecto de panel */
[class*="st-key-panel"]{background:#fff;border:1px solid #dce4dc;border-radius:18px;padding:23px}
[class*="st-key-topbar"]{margin-bottom:6px}
[data-testid="stExpander"] details{background:#fff;border:1px solid #dce4dc;border-radius:14px}
[data-testid="stExpander"] summary p{font-size:13px;font-weight:600;color:#315f4d}
[data-testid="stTabs"] button p{font-size:13px}
[data-testid="stDialog"] [role="dialog"]{border-radius:21px}
[data-testid="stDialog"] h2{font-size:22px;letter-spacing:-.5px;font-weight:600}
[data-testid="stAlert"]{border-radius:10px}
[data-testid="stDataFrame"]{border:1px solid #dce4dc;border-radius:12px;overflow:hidden}
"""


@lru_cache(maxsize=1)
def _css() -> str:
    return _scope(CSS_SENSEI.read_text(encoding="utf-8")) + AJUSTES_STREAMLIT


def html(contenido: str) -> None:
    """Pinta HTML con las clases de Sensei. Sin saltos de línea para que Markdown no lo toque."""
    limpio = re.sub(r">\s+<", "><", contenido.strip())
    limpio = re.sub(r"\n\s*", " ", limpio)
    st.markdown(f'<div class="sensei">{limpio}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- Marco de página

def _barra_lateral(actual: str):
    with st.sidebar:
        st.markdown('<div class="sensei"><div class="wordmark" style="color:#e8eee7;margin:4px 8px 26px">Sensei'
                    '</div></div>', unsafe_allow_html=True)
        for archivo, titulo, slug in PAGINAS:
            with st.container(key=("navsel_" if slug == actual else "nav_") + slug):
                st.page_link(archivo, label=titulo)
        st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
        for archivo, titulo, slug in PAGINAS_EXTRA:
            with st.container(key=("navsel_navx" if slug == actual else "navx_") + slug):
                st.page_link(archivo, label=titulo)


def pagina(titulo: str, slug: str) -> None:
    """Estilos, barra lateral, barra superior (Actualizar Garmin · Guardar copia · Registrar control) y el aviso
    de «Nutrición hoy», como en todas las vistas de Sensei.app."""
    from . import app_comun as ac  # import tardío: app_comun usa streamlit.secrets

    st.html(f"<style>{_css()}</style>")
    _barra_lateral(slug)

    with st.container(key="topbar"):
        c1, c2, c3, c4 = st.columns([5, 1.45, 1.3, 1.75], vertical_alignment="center")
        with c1:
            html(f'<div class="eyebrow">Sensei · preparación física</div><div class="top-caption">{esc(titulo)}</div>')
        with c2:
            if st.button("Actualizar Garmin", use_container_width=True, key="top_garmin"):
                with st.spinner("Descargando de Garmin (solo lectura)…"):
                    try:
                        st.toast(ac.sincronizar_garmin())
                    except Exception as e:
                        st.toast(f"Garmin no responde: {e}")
                st.rerun()
        with c3:
            import json
            st.download_button("Guardar copia", json.dumps(ac.datos(), ensure_ascii=False, indent=1),
                               file_name=f"sensei-copia-{ac.hoy().isoformat()}.json", mime="application/json",
                               use_container_width=True, key="top_copia")
        with c4:
            if st.button("＋ Registrar control", type="primary", use_container_width=True, key="top_control"):
                dialogo_control()

    estado = ac.estado_nutricion(ac.hoy())
    html(f'<div class="daily-status"><div class="daily-status-item"><span>Nutrición hoy</span>'
         f'<strong>{esc(estado)}</strong></div></div>')


@st.dialog("Registrar control", width="large")
def dialogo_control():
    from . import app_comun as ac
    from .baremo import baremo, texto_control
    from .modelo import PRUEBAS, formatear, parse_resultado
    import uuid

    prueba = st.selectbox("Prueba", list(PRUEBAS), format_func=lambda p: PRUEBAS[p]["nombre"])
    info, b = PRUEBAS[prueba], baremo(prueba, ac.ajustes())
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha (ya realizada)", ac.hoy(), max_value=ac.hoy(), format="DD/MM/YYYY")
    texto = c2.text_input(f"Resultado ({'min:s' if info['unidad'] == 'min:s' else info['unidad']})",
                          placeholder=info["ayuda"])
    notas = st.text_input("Notas", placeholder="Condiciones, calzado, actividad de Garmin…")
    completo = st.checkbox("Protocolo completo del examen", value=True,
                           help="Desmárcalo si es una medición de entrenamiento: contará como referencia orientativa.")
    html(f'<p class="hint">{esc(info["protocolo"])}. Tu baremo: {formatear(prueba, b["min"])} = 3 puntos · '
         f'{formatear(prueba, b["max"])} = 6 puntos.</p>')
    if st.button("Guardar control", type="primary"):
        try:
            valor = parse_resultado(prueba, texto)
        except ValueError as e:
            st.error(str(e))
            return
        c = {"id": uuid.uuid4().hex[:10], "fecha": fecha.isoformat(), "prueba": prueba, "resultado": valor,
             "protocolo_completo": completo, "notas": notas.strip()}
        if ac.guardar(lambda x: x["controles"].append(c), f"Control {prueba} {c['fecha']}"):
            st.success(f"{info['nombre']}: {formatear(prueba, valor)} · {texto_control(prueba, valor, ac.ajustes())}")
            st.rerun()


def pie() -> None:
    from . import app_comun as ac
    d = ac.datos()
    ultima = d.get("garmin_ultima_sync")
    acts = [a["fecha"] for a in d["garmin_actividades"]]
    texto_g = (f"Garmin: descargado el {fecha_es(ultima)} a las {ultima[11:16]}"
               + (f" · última actividad {fecha_es(max(acts))}" if acts else "")) if ultima else "Garmin: sin descargar"
    html(f'<div class="footer"><span>Guardado en tu repositorio privado</span><span>{esc(texto_g)}</span>'
         f'<span>Sensei · datos y planificación personales</span></div>')


ICONO_JS = """
<script>
(function () {
  // En Streamlit Cloud la app vive en /~/+/ y los estáticos en /~/+/app/static/; en local, en /app/static/.
  var base = location.origin + (location.pathname.indexOf('/~/+') === 0 ? '/~/+/app/static/' : '/app/static/');
  function poner(doc) {
    if (!doc || !doc.head || doc.getElementById('sensei-icono')) return;
    var etiquetas = [
      ['link', {id: 'sensei-icono', rel: 'apple-touch-icon', sizes: '180x180', href: base + 'sensei-180.png'}],
      ['link', {rel: 'icon', type: 'image/png', sizes: '192x192', href: base + 'sensei-192.png'}],
      ['link', {rel: 'manifest', href: base + 'manifest.json'}],
      ['meta', {name: 'apple-mobile-web-app-title', content: 'Sensei'}],
      ['meta', {name: 'application-name', content: 'Sensei'}],
      ['meta', {name: 'apple-mobile-web-app-capable', content: 'yes'}],
      ['meta', {name: 'mobile-web-app-capable', content: 'yes'}],
      ['meta', {name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent'}],
      ['meta', {name: 'theme-color', content: '#172e35'}]
    ];
    doc.querySelectorAll('link[rel="apple-touch-icon"],link[rel="manifest"],meta[name="apple-mobile-web-app-title"]')
       .forEach(function (n) { n.remove(); });
    etiquetas.forEach(function (e) {
      var n = doc.createElement(e[0]);
      Object.keys(e[1]).forEach(function (k) { n.setAttribute(k, e[1][k]); });
      doc.head.appendChild(n);
    });
  }
  poner(document);
  // En el móvil, al elegir una pestaña del menú lateral, se cierra solo para ver la página.
  if (!window.__senseiMenu) {
    window.__senseiMenu = true;
    document.addEventListener('click', function (ev) {
      if (window.innerWidth > 768) return;
      var a = ev.target.closest && ev.target.closest('[data-testid="stSidebar"] [data-testid="stPageLink"] a');
      if (!a) return;
      setTimeout(function () {
        var b = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
        if (b) b.click();
      }, 150);
    }, true);
  }
  try { if (window.parent && window.parent !== window) poner(window.parent.document); } catch (e) {}
  try { if (window.top && window.top !== window) poner(window.top.document); } catch (e) {}
})();
</script>
"""


def icono_web() -> None:
    """Icono de Sensei.app en el móvil (Añadir a pantalla de inicio) y en la pestaña del navegador."""
    st.html(ICONO_JS, unsafe_allow_javascript=True)
