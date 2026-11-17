"""Evaluación dinámica del día y recomendación del entrenamiento óptimo para mañana.

Se recalcula con cada dato nuevo (descarga de Garmin, comida, check-in, control). Usa:
- el modelo personal de «Sensei te conoce» (cómo te afecta cada tipo de sesión a la mañana siguiente),
- tus controles y el baremo (qué pruebas dan más puntos si mejoran),
- tu recuperación aprendida (días que tardas en volver a tu normalidad tras sesiones duras),
- tus molestias, la fase de preparación y lo que tengas planificado.
Las prescripciones son plantillas de entrenamiento estándar ajustadas con tus marcas; no sustituyen a tu entrenador.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

from .baremo import calificar
from .carga import acwr, carga_diaria_garmin
from .conocerte import TIPOS, carga_tipica, categoria, fila_hoy, predecir
from .modelo import PRUEBAS
from .prevision import prevision

PIERNAS = ("Rodilla", "Tobillo", "Gemelo", "Isquio", "Cuádriceps", "Cadera", "Lumbar")
TREN_SUPERIOR = ("Hombro", "Codo", "Muñeca", "Cuello")


def _d(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _pct(valor, lista):
    if not lista:
        return None
    return round(100 * sum(1 for v in lista if v < valor) / len(lista))


# ------------------------------------------------------------------ hoy

def carga_auto_dia(d: dict, fecha: str) -> str:
    """Carga del día para nutrición, deducida de Garmin si no la has elegido tú."""
    acts = [a for a in d.get("garmin_actividades", []) if a["fecha"] == fecha]
    minutos = sum(a.get("duracion_min") or 0 for a in acts)
    resistencia = sum(a.get("duracion_min") or 0 for a in acts if categoria(a) in ("carrera", "series", "otro"))
    if resistencia >= 75:
        return "endurance"
    if minutos >= 35:
        return "moderate"
    return "light"


def evaluar_hoy(d: dict, hoy: date, modelos: dict, peso: float, nutricion: dict) -> dict:
    f = hoy.isoformat()
    acts = [a for a in d.get("garmin_actividades", []) if a["fecha"] == f]
    hist = {}
    for a in d.get("garmin_actividades", []):
        if a.get("carga") and a["fecha"] < f:
            hist.setdefault(categoria(a), []).append(a["carga"])
    sesiones = []
    for a in acts:
        cat = categoria(a)
        p = _pct(a["carga"], hist.get(cat, [])) if a.get("carga") else None
        if p is None:
            juicio = "sin carga de Garmin"
        elif p >= 80:
            juicio = f"más dura que el {p} % de tus sesiones de {TIPOS[cat].lower()}"
        elif p <= 20:
            juicio = f"más suave que el {100 - p} % de tus sesiones de {TIPOS[cat].lower()}"
        else:
            juicio = f"carga normal para ti ({p}.º percentil)"
        sesiones.append({"nombre": a.get("nombre") or TIPOS[cat], "tipo": TIPOS[cat], "min": a.get("duracion_min"),
                         "carga": a.get("carga"), "fc": a.get("fc_media"), "juicio": juicio, "percentil": p})

    carga = carga_diaria_garmin(d.get("garmin_actividades", []))
    r = acwr(carga, hoy)
    # Mañana según lo que de verdad has hecho hoy
    fila = fila_hoy(d, hoy)
    manana = {}
    if fila:
        for obj, m in modelos.items():
            if m.get("ok") and m.get("util"):
                p = predecir(m, fila)
                if p is not None and fila.get(f"base_{obj}") is not None:
                    manana[obj] = {"dif": p, "abs": fila[f"base_{obj}"] + p}

    # Nutrición del día con la carga real
    t = nutricion["totales"]
    carga_dia = nutricion["carga"]
    hc_ref = {"light": (3, 5), "moderate": (5, 7), "endurance": (6, 10)}[carga_dia]
    prot_min, hc_min = 1.4 * peso, hc_ref[0] * peso
    g = next((x for x in d.get("garmin_diario", []) if x["fecha"] == f), {})
    consejos = []
    if not t["n"]:
        estado_n = "Sin comidas registradas"
    else:
        falta_p = prot_min - (t["prot"] or 0)
        falta_h = hc_min - (t["hc"] or 0)
        if falta_p > 10:
            consejos.append(f"Te faltan unos {falta_p:.0f} g de proteína: p. ej. {max(100, round(falta_p / 0.25 / 10) * 10)} g "
                            "de pollo, pavo o pescado, o yogur griego + 2 huevos.")
        if falta_h > 30:
            consejos.append(f"Te faltan unos {falta_h:.0f} g de hidratos para la carga de hoy: p. ej. "
                            f"{max(50, round(falta_h / 0.75 / 10) * 10)} g (en crudo) de arroz o pasta, o pan y fruta.")
        if not consejos:
            consejos.append("Proteína e hidratos cubiertos para la carga de hoy.")
        estado_n = "Cubierto" if len(consejos) == 1 and "cubiertos" in consejos[0] else "Revisar aporte"
        if g.get("kcal_total") and t["kcal"]:
            consejos.append(f"Gasto de Garmin {'hasta ahora ' if g.get('partial', True) else ''}{g['kcal_total']:.0f} kcal "
                            f"frente a {t['kcal']:.0f} kcal registradas.")
    return {"sesiones": sesiones, "acwr": r, "manana": manana, "nutricion": {"estado": estado_n, "consejos": consejos,
            "carga": carga_dia, "prot_min": prot_min, "hc_min": hc_min}}


# ------------------------------------------------------------------ mañana

CANDIDATAS = {
    "series_1500": {"nombre": "Series para el 1500", "tipo": "series", "pruebas": ["1500m"], "dura": True},
    "velocidad": {"nombre": "Velocidad y salidas (60 m)", "tipo": "series", "pruebas": ["60m"], "dura": True},
    "fuerza": {"nombre": "Fuerza específica: dominadas, banca y cuerda", "tipo": "fuerza",
               "pruebas": ["dominadas", "banca", "cuerda"], "dura": True},
    "carrera_suave": {"nombre": "Rodaje aeróbico suave", "tipo": "carrera", "pruebas": ["1500m"], "dura": False},
    "movilidad": {"nombre": "Movilidad y flexibilidad", "tipo": "otro", "pruebas": ["flexibilidad"], "dura": False},
    "descanso": {"nombre": "Descanso activo", "tipo": None, "pruebas": [], "dura": False},
}


def _notas(d, ajustes):
    out = {}
    for p in PRUEBAS:
        prev = prevision(p, d.get("controles", []))
        g = calificar(p, prev["rango"], ajustes) if prev["central"] is not None else None
        out[p] = g["etiqueta"] if g and g["tipo"] == "nota" else (3.0 if g else None)
    return out


def _prescripcion(clave, d, ajustes, minutos, reducida):
    ctrl = {c["prueba"]: c for c in sorted(d.get("controles", []), key=lambda c: c["fecha"])}
    if clave == "series_1500":
        t = ctrl.get("1500m", {}).get("resultado")
        r400 = f"{int(t / 1500 * 400 // 60)}:{round(t / 1500 * 400 % 60):02d}" if t else None
        n = 4 if reducida else 6
        ritmo = f"a tu ritmo de 1500 ({r400}/400 m, sale de tu control de {int(t // 60)}:{round(t % 60):02d})" if t \
            else "a ritmo de 1500 (esfuerzo 8/10)"
        return [f"Calentamiento: 15 min suave + 4 progresivos de 80 m", f"{n} × 400 m {ritmo}, 1:30–2:00 de trote entre series",
                "Enfriamiento: 10 min suave + 5 min de movilidad de cadera"]
    if clave == "velocidad":
        return ["Calentamiento: 15 min suave + técnica (skipping, talones, multisaltos suaves)",
                f"{4 if reducida else 6} × 30 m lanzados al 90–95 %, recuperación completa (3 min)",
                f"{2 if reducida else 4} × 60 m desde posición de salida, recuperación 4 min · cronometra a mano, el GPS no sirve",
                "Si notas que el tiempo empeora más de 0,2 s, para: la calidad manda"]
    if clave == "fuerza":
        dom = ctrl.get("dominadas", {}).get("resultado")
        ban = ctrl.get("banca", {}).get("resultado")
        s = 3 if reducida else 5
        return [f"Dominadas: {s} × {max(3, round((dom or 10) * 0.5))} repeticiones (50 % de tu control"
                f"{' de ' + str(int(dom)) if dom else ''}), 2 min de pausa, sin fallo",
                f"Banca 40 kg: {s - 1} × 20 s a ritmo de prueba (objetivo {round((ban or 30) * 2 / 3)} reps), 2:30 de pausa",
                "Cuerda: 3 subidas técnicas con pinza de pies, bajando controlado",
                "Core: 3 × 30 s de plancha lateral por lado"]
    if clave == "carrera_suave":
        return [f"{minutos} min de carrera continua en zona 2: puedes hablar en frases completas",
                "Al final, 4 rectas de 80 m relajadas (no sprint)", "10 min de movilidad"]
    if clave == "movilidad":
        return ["25–30 min: isquiotibiales, cadera y zona lumbar, 3 × 30 s por posición",
                "3 intentos suaves del gesto de flexibilidad del examen, sin rebotes", "10–15 min de paseo o bici muy suave"]
    return ["Paseo de 30–40 min o bici muy suave", "10 min de movilidad", "Prioriza dormir más de 7,5 h"]


def recomendar_manana(d: dict, hoy: date, modelos: dict, ajustes: dict, recuperacion: dict | None = None,
                      examen: date | None = None) -> dict:
    manana = hoy + timedelta(days=1)
    razones = []
    # 1. Cómo llegarás mañana (modelo personal con lo que has hecho hoy)
    fila = fila_hoy(d, hoy)
    prev = {}
    if fila:
        for obj in ("disposicion", "vfc", "fc_reposo", "body_battery_despertar"):
            m = modelos.get(obj, {})
            if m.get("ok") and m.get("util"):
                p = predecir(m, fila)
                if p is not None:
                    prev[obj] = p
    nivel = 0
    if "disposicion" in prev and fila.get("base_disposicion") is not None:
        disp = fila["base_disposicion"] + prev["disposicion"]
        nivel = 2 if disp < 40 else 1 if disp < 60 else 0
        razones.append(f"Disposición prevista para mañana: {disp:.0f}/100.")
    elif "vfc" in prev:
        nivel = 1 if prev["vfc"] < -8 or prev.get("fc_reposo", 0) > 4 else 0
        razones.append(f"VFC prevista para mañana: {prev['vfc']:+.0f} ms respecto a tu media.")

    # 2. Molestias recientes
    ch = sorted(d.get("checkins", []), key=lambda c: c["fecha"])[-2:]
    zonas = {m["zona"] for c in ch if (hoy - _d(c["fecha"])).days <= 2 for m in c.get("molestias", [])
             if (m.get("intensidad") or 0) >= 3}
    piernas = any(any(p in z for p in PIERNAS) for z in zonas)
    superior = any(any(p in z for p in TREN_SUPERIOR) for z in zonas)
    if zonas:
        razones.append(f"Molestias recientes: {', '.join(sorted(zonas))}.")

    # 3. Recuperación aprendida y última sesión dura de cada tipo
    dias_rec = (recuperacion or {}).get("dias_hasta_normal") or 2
    cargas = [a["carga"] for a in d.get("garmin_actividades", []) if a.get("carga")]
    umbral = statistics.quantiles(cargas, n=5)[-1] if len(cargas) >= 10 else 80
    ultima = {}
    for a in d.get("garmin_actividades", []):
        cat = categoria(a)
        if cat == "series" or (a.get("carga") or 0) >= umbral:
            ultima[cat] = max(ultima.get(cat, date.min), _d(a["fecha"]))
    ultima_dura = max(ultima.values(), default=None)
    dias_desde_dura = (manana - ultima_dura).days if ultima_dura else 99

    # 4. Prioridades por puntos y frecuencia reciente
    notas = _notas(d, ajustes)
    hace14 = [a for a in d.get("garmin_actividades", []) if 0 <= (hoy - _d(a["fecha"])).days <= 13]
    frec = {c: sum(1 for a in hace14 if categoria(a) == c) for c in TIPOS}
    dias_examen = (examen - manana).days if examen else 99
    tipica = carga_tipica(d)
    plan = [s for s in d.get("sesiones", []) if s.get("estado") == "planned" and s["fecha"] == manana.isoformat()]

    puntuaciones = []
    for clave, c in CANDIDATAS.items():
        motivo, score = [], 0.0
        notas_c = [notas.get(p) for p in c["pruebas"]]
        if c["pruebas"]:
            hueco = [10 - (n if n is not None else 4) for n in notas_c]  # sin marca = gran incógnita
            score += max(hueco) * 1.2
            peor = min(c["pruebas"], key=lambda p: notas.get(p) if notas.get(p) is not None else -1)
            motivo.append(f"{PRUEBAS[peor]['nombre']} " + (f"está en {notas[peor]:.1f}/10".replace(".", ",")
                                                            if notas.get(peor) is not None else "aún no tiene marca"))
        if c["tipo"] in ("series", "carrera") and frec["carrera"] + frec["series"] < 4:
            score += 2
            motivo.append(f"solo {frec['carrera'] + frec['series']} carreras en 14 días")
        if c["tipo"] == "fuerza" and frec["fuerza"] < 3:
            score += 1.5
            motivo.append(f"solo {frec['fuerza']} sesiones de fuerza en 14 días")
        # efecto aprendido sobre la disposición del día siguiente
        m = modelos.get("disposicion", {})
        if m.get("ok") and c["tipo"]:
            ef = next((e["efecto"] for e in m["efectos"] if e["variable"] == f"carga_{c['tipo']}"), 0)
            score += ef / 15  # coste: lo que te baja la disposición del día siguiente
        if c["dura"]:
            if nivel == 2:
                score -= 100
                motivo.append("tu recuperación prevista no lo permite")
            elif nivel == 1:
                score -= 6
            if dias_desde_dura < dias_rec:
                score -= 5
                motivo.append(f"hace {dias_desde_dura} día(s) de tu última sesión dura y tú recuperas en {dias_rec}")
            if dias_examen <= 2:
                score -= 100
        if clave == "descanso":
            score = 1 + (8 if nivel == 2 else 3 if nivel == 1 else 0) + (6 if dias_examen <= 1 else 0)
        if clave == "movilidad":
            score += 1.5 if nivel >= 1 else 0
        if piernas and c["tipo"] in ("series", "carrera"):
            score -= 100
            motivo.append("molestia en piernas")
        if superior and c["tipo"] == "fuerza":
            score -= 100
            motivo.append("molestia en tren superior")
        puntuaciones.append((score, clave, motivo))
    puntuaciones.sort(reverse=True)
    mejor = puntuaciones[0][1]
    reducida = nivel == 1 or 3 <= dias_examen <= 10
    cand = CANDIDATAS[mejor]
    minutos = {"carrera_suave": 40, "movilidad": 30, "descanso": 30}.get(mejor, 55)
    rec = {"clave": mejor, "nombre": cand["nombre"] + (" (versión reducida)" if reducida and cand["dura"] else ""),
           "minutos": minutos, "pasos": _prescripcion(mejor, d, ajustes, minutos, reducida),
           "motivos": puntuaciones[0][2], "nivel_previsto": nivel}
    if plan:
        rec["plan"] = plan[0].get("nombre")
        if nivel == 2:
            rec["plan_veredicto"] = "Cámbialo por descanso activo: tu recuperación prevista es baja."
        elif nivel == 1:
            rec["plan_veredicto"] = "Hazlo en versión reducida (−30–40 % de volumen, sin ir al fallo)."
        else:
            rec["plan_veredicto"] = "Adelante con lo planificado: llegarás bien."
    if dias_examen <= 10:
        razones.append(f"Faltan {dias_examen} días para el examen: puesta a punto, menos volumen y la misma intensidad.")
    alternativas = [{"nombre": CANDIDATAS[k]["nombre"], "motivo": "; ".join(mo) or "—", "apta": s > -50}
                    for s, k, mo in puntuaciones[1:4]]
    return {"fecha": manana, "recomendacion": rec, "alternativas": alternativas, "razones": razones,
            "tasa": tipica}
