"""Piezas compartidas por las páginas: acceso, datos, ajustes y Garmin."""
from __future__ import annotations

import hmac
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from . import garmin as gm
from . import garmin_personal as gp
from .almacen import AlmacenGitHub, AlmacenLocal, ErrorAlmacen
from .reglas import UMBRALES_POR_DEFECTO

TZ = ZoneInfo("Europe/Madrid")
EXAMEN_POR_DEFECTO = date(2027, 1, 15)
AZUL = "#2a78d6"
ESTADO = {0: ("🟢", "#0ca30c"), 1: ("🟡", "#fab219"), 2: ("🔴", "#d03b3b"), None: ("⚪", "#8a8a85")}


def ahora() -> datetime:
    return datetime.now(TZ)


def hoy() -> date:
    return ahora().date()


def _secreto(seccion: str, clave: str, defecto=None):
    try:
        return st.secrets[seccion][clave]
    except (KeyError, FileNotFoundError, AttributeError):
        return defecto
    except Exception:
        return defecto


def modo_github() -> bool:
    return bool(_secreto("github", "token") and _secreto("github", "repo"))


@st.cache_resource
def almacen():
    if modo_github():
        return AlmacenGitHub(_secreto("github", "token"), _secreto("github", "repo"),
                             _secreto("github", "ruta", "datos.json"))
    return AlmacenLocal()


def exigir_acceso() -> None:
    """Pide la contraseña de la app. Sin contraseña configurada solo funciona en modo local."""
    clave = _secreto("app", "password")
    if not clave:
        if modo_github():
            st.error("Falta `[app] password` en los secretos. Por seguridad la app no se abre sin contraseña.")
            st.stop()
        st.info("Modo local de prueba: datos en `datos_local/` y sin contraseña.", icon="💻")
        return
    if st.session_state.get("acceso_ok"):
        return
    st.title("Sensei")
    with st.form("acceso"):
        intento = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(intento.encode(), str(clave).encode()):
                st.session_state["acceso_ok"] = True
                st.rerun()
            st.error("Contraseña incorrecta.")
    st.stop()


def datos() -> dict:
    if "datos" not in st.session_state:
        try:
            st.session_state["datos"] = almacen().cargar()
        except (ErrorAlmacen, ValueError) as e:
            st.error(f"No se pudieron leer tus datos: {e}")
            st.stop()
    return st.session_state["datos"]


def guardar(cambio, mensaje: str) -> bool:
    try:
        st.session_state["datos"] = almacen().modificar(cambio, mensaje)
        return True
    except ErrorAlmacen as e:
        st.error(str(e))
    except Exception as e:  # red, GitHub caído…
        st.error(f"No se ha guardado: {type(e).__name__}: {e}")
    return False


def recargar() -> None:
    st.session_state.pop("datos", None)


def ajustes() -> dict:
    a = dict(datos().get("ajustes") or {})
    a.setdefault("fecha_examen", EXAMEN_POR_DEFECTO.isoformat())
    a.setdefault("lugar", {"nombre": "Madrid", "lat": 40.4168, "lon": -3.7038})
    a.setdefault("peso_kg", None)
    a.setdefault("puntos_max", 6)
    a.setdefault("baremo", {})
    a["umbrales"] = {**UMBRALES_POR_DEFECTO, **(a.get("umbrales") or {})}
    return a


def fecha_examen() -> date:
    return date.fromisoformat(ajustes()["fecha_examen"])


# ---------------- Garmin ----------------

def garmin_configurado() -> bool:
    return bool(_secreto("garmin", "api_key") or _secreto("garmin", "token"))


def _clave_personal() -> str | None:
    """Clave API personal oficial: `[garmin] api_key`, o `token` si lo pegado no es JSON."""
    k = _secreto("garmin", "api_key")
    if k:
        return str(k)
    t = _secreto("garmin", "token")
    return str(t) if gp.es_clave_personal(t) else None


@st.cache_resource
def _cliente_personal(clave: str):
    return gp.ClientePersonal(clave)


def _descargar(desde: date, hasta: date):
    """(diarios, actividades, api_antigua_o_None) por la vía que esté configurada."""
    clave = _clave_personal()
    if clave:
        try:
            d, a = gp.descargar_rango(_cliente_personal(clave), desde, hasta)
        except gp.ErrorGarminPersonal as e:
            raise gm.ErrorGarmin(str(e)) from e
        return d, a, None, None
    token = _token_garmin()
    if not token:
        raise gm.ErrorGarmin("Garmin no está configurado (falta `[garmin] api_key` en los secretos).")
    api = gm.conectar(token)
    d, a = gm.descargar_rango(api, desde, hasta)
    return d, a, api, token


def _token_garmin() -> str | None:
    guardado = None
    if _secreto("garmin", "guardar_token_renovado", True):
        try:
            guardado = almacen().leer_archivo(gm.RUTA_TOKEN)
        except Exception:
            guardado = None
    return guardado or _secreto("garmin", "token")


def sincronizar_garmin(dias: int | None = None) -> str:
    """Descarga de Garmin y añade a tus datos. Devuelve un mensaje para mostrar."""
    if not garmin_configurado():
        return "Garmin no está configurado (falta `[garmin] api_key` en los secretos)."
    d = datos()
    if dias is None:
        ultima = d.get("garmin_ultima_sync")
        if ultima:
            dias = min(30, max(3, (ahora() - datetime.fromisoformat(ultima)).days + 2))
        else:
            dias = 30
    diarios, acts, api, token = _descargar(hoy() - timedelta(days=dias - 1), hoy())
    marca = ahora().isoformat(timespec="seconds")
    if not guardar(lambda x: gm.fusionar(x, diarios, acts, marca), f"Garmin: {dias} días"):
        return "Se descargó de Garmin pero no se pudo guardar."
    nuevo = gm.token_actual(api) if api else None
    if nuevo and nuevo != token and _secreto("garmin", "guardar_token_renovado", True):
        try:
            almacen().escribir_archivo(gm.RUTA_TOKEN, nuevo, "Garmin: token renovado")
        except Exception:
            pass
    con_datos = sum(1 for x in diarios if x.get("fc_reposo") or x.get("vfc") or x.get("sueno_h"))
    return f"Garmin actualizado: {con_datos} días con datos de recuperación y {len(acts)} actividades."


def importar_historial(bloque: int | None = None) -> str:
    """Trae días más antiguos de Garmin, por bloques, para que el aprendizaje tenga historia."""
    if not garmin_configurado():
        return "Garmin no está configurado."
    bloque = bloque or (120 if _clave_personal() else 45)
    fechas = [g["fecha"] for g in datos()["garmin_diario"]]
    hasta = (date.fromisoformat(min(fechas)) if fechas else hoy()) - timedelta(days=1)
    desde = hasta - timedelta(days=bloque - 1)
    diarios, acts, _, _ = _descargar(desde, hasta)
    ultima = datos().get("garmin_ultima_sync") or ahora().isoformat(timespec="seconds")
    if not guardar(lambda x: gm.fusionar(x, diarios, acts, ultima), f"Garmin: historial {desde}–{hasta}"):
        return "No se pudo guardar."
    con = sum(1 for x in diarios if x.get("fc_reposo") or x.get("vfc"))
    return f"Importado {desde.strftime('%d/%m/%Y')}–{hasta.strftime('%d/%m/%Y')}: {con} días con datos, {len(acts)} actividades."


def autosincronizar() -> None:
    """Como Sensei: si hace más de 6 h de la última descarga, actualiza una vez por sesión."""
    if not garmin_configurado() or st.session_state.get("autosync_hecho"):
        return
    st.session_state["autosync_hecho"] = True
    ultima = datos().get("garmin_ultima_sync")
    if ultima and ahora() - datetime.fromisoformat(ultima) < timedelta(hours=6):
        return
    with st.spinner("Actualizando Garmin…"):
        try:
            st.toast(sincronizar_garmin())
        except gm.ErrorGarmin as e:
            st.warning(str(e))
        except Exception as e:
            st.warning(f"Garmin no responde ahora ({type(e).__name__}). Puedes registrar a mano.")


def estilo_grafico(fig, titulo_y: str = ""):
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=260, showlegend=False,
                      yaxis_title=titulo_y, xaxis_title=None, hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    fig.update_traces(line=dict(width=2, color=AZUL), marker=dict(size=8, color=AZUL))
    return fig
