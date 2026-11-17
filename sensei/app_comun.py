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
    from .ui import _css
    st.html(f"<style>{_css()}</style>")
    st.markdown('<div class="sensei"><div class="eyebrow" style="margin-top:40px">Sensei · preparación física</div>'
                '<div class="section-head" style="margin-top:10px"><div><h1>Sensei</h1><p>Entra con tu contraseña.</p>'
                '</div></div></div>', unsafe_allow_html=True)
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
    if a.get("peso_kg") is None:
        a["peso_kg"] = 92.0  # valor por defecto de Sensei.app; cámbialo en Nutrición o Ajustes
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


def _cliente_personal(clave: str):
    # Sin caché: un objeto cacheado sobrevive a los redespliegues con el código viejo.
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
    aviso = (" Avisos: " + " | ".join(dict.fromkeys(gp.ERRORES))[:300]) if gp.ERRORES else ""
    return f"Garmin actualizado: {con_datos} días con datos de recuperación y {len(acts)} actividades.{aviso}"


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
            st.warning(f"Garmin no responde ahora ({type(e).__name__}: {e}). Puedes registrar a mano.")


def estilo_grafico(fig, titulo_y: str = ""):
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=260, showlegend=False,
                      yaxis_title=titulo_y, xaxis_title=None, hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    fig.update_traces(line=dict(width=2, color=AZUL), marker=dict(size=8, color=AZUL))
    return fig


# ---------------- Nutrición (mismas reglas que Nutrition.js de Sensei.app) ----------------

CARGAS_DIA = {"light": "Descanso / suave", "moderate": "Moderada · ~1 h", "endurance": "Resistencia · 1–3 h"}
HC_POR_CARGA = {"light": (3, 5), "moderate": (5, 7), "endurance": (6, 10)}
PROTEINA_GKG = (1.4, 2.0)
COMIDAS = ["Desayuno", "Media mañana", "Comida", "Merienda", "Cena", "Otros"]


def dia_nutricion(d: dict, fecha: str) -> dict:
    """La carga del día la eliges tú; si no, se deduce de lo que Garmin registró ese día."""
    from .evaluacion import carga_auto_dia
    info = (d.get("dias_nutricion") or {}).get(fecha) or {}
    manual = info.get("carga")
    return {"carga": manual or carga_auto_dia(d, fecha), "carga_auto": manual is None,
            "completo": fecha in d.get("dias_nutricion_completos", [])}


def totales(entradas: list[dict]) -> dict:
    out = {"n": len(entradas)}
    for k in ("kcal", "prot", "hc", "grasa"):
        conocidos = [e[k] for e in entradas if e.get(k) is not None]
        out[k] = sum(conocidos) if conocidos else None
        out[k + "_conocidos"] = len(conocidos)
    return out


def estado_nutricion(fecha) -> str:
    d, f = datos(), str(fecha)
    entradas = [c for c in d["comidas"] if c["fecha"] == f]
    t, dia, peso = totales(entradas), dia_nutricion(d, f), ajustes()["peso_kg"]
    if not t["n"]:
        return "Sin comidas registradas"
    if not dia["completo"]:
        return "Registro en curso"
    if any(t[k + "_conocidos"] != t["n"] for k in ("kcal", "prot", "hc", "grasa")):
        return "Registro incompleto"
    hc_min = peso * HC_POR_CARGA[dia["carga"]][0]
    return "Referencias cubiertas" if t["prot"] >= peso * 1.4 and t["hc"] >= hc_min else "Revisar aporte"


# ---------------- Aprendizaje compartido entre páginas (se recalcula cuando cambian tus datos) ----------------

@st.cache_data(show_spinner=False, max_entries=4)
def _aprender(clave: str, texto: str, dia: str):
    import json
    from .aprendizaje import recuperacion_personal
    from .conocerte import resumen_aprendizaje
    d = json.loads(texto)
    R = resumen_aprendizaje(d, date.fromisoformat(dia))
    R["recuperacion"] = recuperacion_personal(d)
    return R


def aprendizaje() -> dict:
    import json
    d = datos()
    clave = (f'{len(d["garmin_diario"])}-{len(d["garmin_actividades"])}-{d.get("garmin_ultima_sync")}-'
             f'{len(d["checkins"])}-{len(d["sesiones"])}')
    texto = json.dumps({k: d[k] for k in ("garmin_diario", "garmin_actividades", "sesiones", "checkins")})
    with st.spinner("Sensei está aprendiendo de tus datos…"):
        return _aprender(clave, texto, hoy().isoformat())


def evaluacion_y_recomendacion() -> tuple[dict, dict]:
    from .evaluacion import evaluar_hoy, recomendar_manana
    d, a, h = datos(), ajustes(), hoy()
    R = aprendizaje()
    f = h.isoformat()
    nut = {"totales": totales([c for c in d["comidas"] if c["fecha"] == f]), "carga": dia_nutricion(d, f)["carga"]}
    ev = evaluar_hoy(d, h, R["modelos"], a["peso_kg"], nut)
    rec = recomendar_manana(d, h, R["modelos"], a, R.get("recuperacion"), fecha_examen())
    return ev, rec


# ---------------- Edición genérica (cualquier registro) ----------------

def editar_registro(clave: str, rid: str, cambios: dict, mensaje: str) -> bool:
    """Cambia campos de un registro. Lo que venía de Sensei pasa a ser tuyo y la reimportación ya no lo pisa."""
    def cambio(x):
        for r in x.get(clave, []):
            if r.get("id") == rid:
                r.update(cambios)
                if r.get("origen") == "sensei":
                    r["origen"] = "web"
    return guardar(cambio, mensaje)


def borrar_registros(clave: str, ids: list[str], mensaje: str) -> bool:
    def cambio(x):
        x[clave] = [r for r in x.get(clave, []) if r.get("id") not in ids]
        x.setdefault("borrados_sensei", []).extend(i for i in ids if str(i).startswith("sensei-"))
    return guardar(cambio, mensaje)
