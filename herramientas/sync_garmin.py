"""Descarga diaria de Garmin sin abrir la app (para GitHub Actions en tu repo PRIVADO de datos).

Variables de entorno: GITHUB_DATOS_TOKEN, GITHUB_DATOS_REPO (p. ej. bsendagorta/sensei-datos),
GARMIN_TOKEN (opcional si ya hay privado/garmin_token.json en el repo), DIAS (por defecto 3).
Solo lee de Garmin. Añade a datos.json sin tocar tus registros.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sensei import garmin as gm  # noqa: E402
from sensei.almacen import AlmacenGitHub  # noqa: E402


def main():
    al = AlmacenGitHub(os.environ["GITHUB_DATOS_TOKEN"], os.environ["GITHUB_DATOS_REPO"],
                       os.environ.get("GITHUB_DATOS_RUTA", "datos.json"))
    token = al.leer_archivo(gm.RUTA_TOKEN) or os.environ.get("GARMIN_TOKEN")
    if not token:
        sys.exit("Falta el token de Garmin.")
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    api = gm.conectar(token)
    diarios, acts = gm.descargar(api, int(os.environ.get("DIAS", "3")), ahora.date())
    al.modificar(lambda d: gm.fusionar(d, diarios, acts, ahora.isoformat(timespec="seconds")),
                 "Garmin: descarga automática")
    nuevo = gm.token_actual(api)
    if nuevo and nuevo != token:
        al.escribir_archivo(gm.RUTA_TOKEN, nuevo, "Garmin: token renovado")
    print(f"OK: {len(diarios)} días, {len(acts)} actividades.")


if __name__ == "__main__":
    main()
