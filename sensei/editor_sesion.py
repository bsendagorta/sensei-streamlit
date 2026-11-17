"""Crear y editar sesiones con bloques y ejercicios (mismo modelo que Sensei.app: bloques → ejercicios)."""
from __future__ import annotations

import uuid
from datetime import date

import pandas as pd
import streamlit as st

from .app_comun import borrar_registros, editar_registro, guardar, hoy

TIPOS = {"strength_training": "Fuerza", "running": "Carrera", "track_running": "Pista / series",
         "treadmill_running": "Cinta", "other": "Otro", "mobility": "Movilidad"}
COLUMNAS = ["bloque", "rondas", "ejercicio", "dosis", "descanso", "reps", "resultado"]


def _a_tabla(bloques: list[dict]) -> pd.DataFrame:
    filas = []
    for b in bloques or []:
        for e in b.get("exercises", []) or [{}]:
            reps = e.get("reps")
            filas.append({"bloque": b.get("title", ""), "rondas": b.get("rounds") or 1, "ejercicio": e.get("name", ""),
                          "dosis": e.get("dose", ""), "descanso": e.get("rest", ""),
                          "reps": ", ".join(str(r) for r in reps) if isinstance(reps, list) else (reps or ""),
                          "resultado": e.get("result", "")})
    return pd.DataFrame(filas or [{"bloque": "", "rondas": 1, "ejercicio": "", "dosis": "", "descanso": "", "reps": "",
                                   "resultado": ""}], columns=COLUMNAS)


def _a_bloques(df: pd.DataFrame, originales: list[dict]) -> list[dict]:
    """Agrupa filas consecutivas con el mismo nombre de bloque, en el orden que dejes en la tabla."""
    modos = {b.get("title"): b.get("mode") for b in originales or []}
    bloques = []
    for r in df.fillna("").to_dict("records"):
        if not str(r["ejercicio"]).strip():
            continue
        titulo = str(r["bloque"]).strip() or "Bloque"
        if not bloques or bloques[-1]["title"] != titulo:
            try:
                rondas = max(1, int(float(r["rondas"] or 1)))
            except ValueError:
                rondas = 1
            bloques.append({"title": titulo, "rounds": rondas, "exercises": [],
                            **({"mode": modos[titulo]} if modos.get(titulo) else {})})
        e = {"name": str(r["ejercicio"]).strip(), "dose": str(r["dosis"]).strip(), "rest": str(r["descanso"]).strip(),
             "result": str(r["resultado"]).strip()}
        if str(r["reps"]).strip():
            e["reps"] = str(r["reps"]).strip()
        bloques[-1]["exercises"].append(e)
    return bloques


@st.dialog("Sesión", width="large")
def dialogo_sesion(s: dict | None = None):
    nueva = s is None
    s = s or {}
    c1, c2, c3 = st.columns([2.2, 1, 1])
    nombre = c1.text_input("Nombre", s.get("nombre") or "")
    tipos = list(TIPOS)
    tipo = c2.selectbox("Tipo", tipos, index=tipos.index(s["tipo"]) if s.get("tipo") in tipos else 0,
                        format_func=TIPOS.get)
    estado = c3.selectbox("Estado", ["completed", "planned"], index=1 if s.get("estado") == "planned" else 0,
                          format_func={"completed": "Realizado", "planned": "Planificado"}.get)
    c1, c2, c3 = st.columns(3)
    fecha = c1.date_input("Fecha", date.fromisoformat(s["fecha"]) if s.get("fecha") else hoy(), format="DD/MM/YYYY")
    minutos = c2.number_input("Duración (min)", 0.0, 400.0, value=s.get("duracion_min"))
    rpe = c3.number_input("Esfuerzo percibido (0–10)", 0, 10, value=s.get("rpe"))
    notas = st.text_area("Notas", s.get("notas") or "")
    st.markdown("**Bloques y ejercicios** · una fila por ejercicio; filas seguidas con el mismo nombre de bloque forman el "
                "bloque. Reps: una cifra por ronda, separadas por comas.")
    tabla = st.data_editor(_a_tabla(s.get("bloques")), num_rows="dynamic", hide_index=True, width="stretch",
                           key=f"bloques_{s.get('id', 'nueva')}",
                           column_config={"rondas": st.column_config.NumberColumn(min_value=1, max_value=100, step=1)})
    b1, b2 = st.columns(2)
    if b1.button("Guardar sesión", type="primary", use_container_width=True):
        if not nombre.strip():
            st.error("Pon un nombre a la sesión.")
            return
        if estado == "completed" and fecha > hoy():
            st.error("Una sesión realizada no puede estar en el futuro: márcala como planificada.")
            return
        datos_s = {"nombre": nombre.strip(), "tipo": tipo, "estado": estado, "fecha": fecha.isoformat(),
                   "duracion_min": minutos, "rpe": rpe, "notas": notas.strip(), "bloques": _a_bloques(tabla, s.get("bloques"))}
        if nueva:
            nuevo = {"id": uuid.uuid4().hex[:10], **datos_s, "origen": "web"}
            ok = guardar(lambda x: x["sesiones"].append(nuevo), f"Sesión {nombre.strip()}")
        else:
            ok = editar_registro("sesiones", s["id"], datos_s, f"Sesión editada: {nombre.strip()}")
        if ok:
            st.rerun()
    if not nueva and b2.checkbox("Quiero borrarla") and b2.button("Borrar sesión", use_container_width=True):
        if borrar_registros("sesiones", [s["id"]], f"Sesión borrada: {s.get('nombre')}"):
            st.rerun()
