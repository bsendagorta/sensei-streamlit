"""Descarga diaria de Garmin sin abrir la app (para GitHub Actions en tu repo PRIVADO de datos).

Variables de entorno: GITHUB_DATOS_TOKEN, GITHUB_DATOS_REPO (p. ej. bsendagorta/sensei-datos),
GARMIN_API_KEY (clave API personal de Garmin Connect), DIAS (por defecto 3).
Solo lee de Garmin. Añade a datos.json sin tocar tus registros.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sensei import garmin as gm  # noqa: E402
from sensei import garmin_personal as gp  # noqa: E402
from sensei.almacen import AlmacenGitHub  # noqa: E402


def main():
    al = AlmacenGitHub(os.environ["GITHUB_DATOS_TOKEN"], os.environ["GITHUB_DATOS_REPO"],
                       os.environ.get("GITHUB_DATOS_RUTA", "datos.json"))
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    dias = int(os.environ.get("DIAS", "3"))
    clave = os.environ.get("GARMIN_API_KEY")
    if clave:
        cli = gp.ClientePersonal(clave)
        diarios, acts = gp.descargar_rango(cli, ahora.date() - timedelta(days=dias - 1), ahora.date())
        al.modificar(lambda d: gm.fusionar(d, diarios, acts, ahora.isoformat(timespec="seconds")),
                     "Garmin: descarga automática")
        print(f"OK (API personal): {len(diarios)} días, {len(acts)} actividades.")
        return
    token = al.leer_archivo(gm.RUTA_TOKEN) or os.environ.get("GARMIN_TOKEN")
    if not token:
        sys.exit("Falta GARMIN_API_KEY.")
    api = gm.conectar(token)
    diarios, acts = gm.descargar(api, dias, ahora.date())
    al.modificar(lambda d: gm.fusionar(d, diarios, acts, ahora.isoformat(timespec="seconds")),
                 "Garmin: descarga automática")
    nuevo = gm.token_actual(api)
    if nuevo and nuevo != token:
        al.escribir_archivo(gm.RUTA_TOKEN, nuevo, "Garmin: token renovado")
    print(f"OK: {len(diarios)} días, {len(acts)} actividades.")


if __name__ == "__main__":
    main()
