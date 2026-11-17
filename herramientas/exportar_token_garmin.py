"""Genera el token de Garmin para la app (ejecútalo TÚ en la Terminal de tu Mac, una vez).

    cd sensei-streamlit
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python herramientas/exportar_token_garmin.py

Te pide correo, contraseña y el código 2FA en la Terminal. La contraseña no se guarda en ningún
sitio: solo sale un token (texto JSON) que se copia al portapapeles para que lo pegues en los
secretos de Streamlit Cloud como `[garmin] token`. Trátalo como una contraseña: no lo pegues en
el repositorio ni lo compartas.
"""
import getpass
import subprocess
import sys

from garminconnect import Garmin


def main():
    correo = input("Correo de Garmin Connect: ").strip()
    clave = getpass.getpass("Contraseña (no se muestra): ")
    api = Garmin(correo, clave, prompt_mfa=lambda: input("Código 2FA: ").strip())
    api.login()
    token = api.client.dumps()
    try:
        subprocess.run(["pbcopy"], input=token.encode(), check=True)
        print("\n✅ Token copiado al portapapeles. Pégalo en Streamlit Cloud → Settings → Secrets así:\n")
        print("[garmin]\ntoken = '''<pega aquí>'''\n")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\nCopia este token (todo, entre las comillas triples) en los secretos:\n")
        print(f"[garmin]\ntoken = '''{token}'''\n")
    print("Nombre de la cuenta:", api.get_full_name())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
