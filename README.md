# Sensei · Streamlit

App web (también desde el móvil) para preparar las pruebas físicas de bombero de AENA —dominadas,
press de banca, 60 m, 1500 m, trepa de cuerda y flexibilidad— **rindiendo más sin lesionarte**, con tus
datos reales de Garmin.

- **Hoy**: semáforo verde / ámbar / rojo con reglas fijas y explicadas (pulso en reposo, VFC, sueño,
  sensación, molestias, carga agudo:crónico y disposición de Garmin) y la mejor hora para entrenar fuera.
- **Aprende de ti**: se reentrena con cada dato nuevo y te dice qué influye en cómo te sientes, cuántos días
  tardas en recuperarte de una sesión dura, si tu eficiencia de carrera mejora de verdad y cuáles son tus
  puntos débiles en el baremo.
- **Registrar**: check-in diario (20 s), sesiones con esfuerzo percibido, controles y mediciones.
- **Pruebas y previsión**, **Carga y recuperación**, **Nutrición**, **Historial** y **Ajustes** (baremo,
  umbrales, fecha del examen, lugar).

Principio: **un control real vale más que una extrapolación.** La previsión solo usa tus marcas, y una
mejora solo se da por demostrada cuando el intervalo de confianza del 95 % excluye el cero.

## Dónde están tus datos

| Qué | Dónde | ¿Público? |
|---|---|---|
| Código de la app | este repositorio | Sí |
| Tus registros y lo que baja de Garmin | `datos.json` en tu repo **privado** `sensei-datos` | No |
| Token de Garmin renovado | `privado/garmin_token.json` en `sensei-datos` | No |
| Contraseñas y tokens | Secretos de Streamlit Cloud | No |

Cada cambio que haces en la app es un commit en `sensei-datos`: el historial completo queda en git.

## APIs que usa

| API | Para qué | Clave |
|---|---|---|
| Garmin Connect (librería [`garminconnect`](https://github.com/cyberjunky/python-garminconnect), no oficial) | Recuperación diaria y actividades. **Solo lectura** | Tu token |
| [Open-Meteo](https://open-meteo.com) | Sensación térmica, lluvia, viento y calidad del aire por horas; búsqueda de municipios | No |
| [Open Food Facts](https://world.openfoodfacts.org) | Proteína y kcal de alimentos por nombre o código de barras | No |
| GitHub | Guardar tus datos en el repo privado | Token de grano fino |

## Puesta en marcha (una vez)

1. **Token de GitHub** — github.com → Settings → Developer settings → *Fine-grained tokens* → Generate:
   *Only select repositories* → `sensei-datos`; *Repository permissions* → **Contents: Read and write**.
2. **Token de Garmin** — en la Terminal de tu Mac:
   ```bash
   git clone https://github.com/bsendagorta/sensei-streamlit.git && cd sensei-streamlit
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python herramientas/exportar_token_garmin.py
   ```
   Escribes correo, contraseña y 2FA **en la Terminal**; la contraseña no se guarda. El token queda en el
   portapapeles.
3. **Desplegar** — [share.streamlit.io](https://share.streamlit.io) → *Create app* → repo
   `bsendagorta/sensei-streamlit`, rama `main`, archivo `streamlit_app.py` → *Advanced settings* → *Secrets*:
   pega el contenido de [`.streamlit/secrets.toml.ejemplo`](.streamlit/secrets.toml.ejemplo) con tus valores.
4. Abre la URL en el móvil y **Añadir a pantalla de inicio**.
5. En **Aprende de ti** pulsa *Traer 45 días más antiguos de Garmin* unas cuantas veces para darle historia.

### Descarga automática cada mañana (opcional)
Para que Garmin se descargue aunque no abras la app, copia
[`herramientas/plantilla-repo-datos/.github/workflows/garmin.yml`](herramientas/plantilla-repo-datos/.github/workflows/garmin.yml)
al repo privado `sensei-datos` y añade allí dos secretos de Actions: `DATOS_TOKEN` (el token de GitHub) y
`GARMIN_TOKEN` (el de Garmin).

## Si algo falla
- **«No se pudo entrar en Garmin»**: repite el paso 2 y sustituye `[garmin] token` en los secretos.
  Garmin a veces bloquea servidores en la nube; mientras tanto, registra a mano: el semáforo funciona igual.
- **«GitHub rechaza el token»**: el token caducó o no tiene *Contents: Read and write* en `sensei-datos`.

## Desarrollo
```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q          # lógica (reglas, previsión, aprendizaje, almacén)
.venv/bin/python tests/app_smoke.py    # abre cada página con datos locales
.venv/bin/streamlit run streamlit_app.py   # sin secretos: modo local en datos_local/
```
Toda la lógica está en `sensei/` sin dependencias de Streamlit; las páginas están en `paginas/`.
Faltantes = `None`, nunca `0`. Lo de Garmin se *añade* y nunca sustituye tus registros.
