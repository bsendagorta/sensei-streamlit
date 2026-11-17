"""Dónde viven tus datos.

- Modo GitHub (el normal): un archivo JSON en un repositorio PRIVADO tuyo, leído y escrito con
  la API de GitHub. El código de la app es público; tus datos no.
- Modo local (para probar en el ordenador): `datos_local/datos.json`, ignorado por git.

Cada escritura relee la última versión, aplica tu cambio y guarda con un commit. Si alguien
escribió a la vez (otra pestaña, el Mac), se reintenta sobre la versión nueva: no se pisa nada.
"""
from __future__ import annotations

import base64
import copy
import json
import time
from pathlib import Path
from typing import Callable

import requests

SCHEMA = "sensei-streamlit-v1"


def datos_vacios() -> dict:
    return {"schema": SCHEMA, "ajustes": {}, "checkins": [], "sesiones": [], "controles": [],
            "comidas": [], "dias_nutricion_completos": [], "dias_nutricion": {}, "citas": [], "aprendizaje_historial": [], "borrados_sensei": [], "garmin_diario": [],
            "garmin_actividades": [], "garmin_ultima_sync": None}


def normalizar(d: dict) -> dict:
    base = datos_vacios()
    if d.get("schema") not in (None, SCHEMA):
        raise ValueError(f"Formato de datos desconocido: {d.get('schema')}")
    for k, v in base.items():
        d.setdefault(k, copy.deepcopy(v))
    return d


class ErrorAlmacen(RuntimeError):
    pass


class AlmacenLocal:
    descripcion = "local (solo este ordenador)"

    def __init__(self, ruta: str = "datos_local/datos.json"):
        self.ruta = Path(ruta)

    def leer_archivo(self, ruta_rel: str):
        p = self.ruta.parent / ruta_rel
        return p.read_text(encoding="utf-8") if p.exists() else None

    def escribir_archivo(self, ruta_rel: str, texto: str, mensaje: str):
        p = self.ruta.parent / ruta_rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")

    def cargar(self) -> dict:
        if not self.ruta.exists():
            return datos_vacios()
        return normalizar(json.loads(self.ruta.read_text(encoding="utf-8")))

    def modificar(self, cambio: Callable[[dict], None], mensaje: str) -> dict:
        d = self.cargar()
        cambio(d)
        normalizar(d)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.ruta)
        return d


class AlmacenGitHub:
    def __init__(self, token: str, repo: str, ruta: str = "datos.json", rama: str = "main"):
        self.repo, self.ruta, self.rama = repo, ruta, rama
        self.descripcion = f"repositorio privado {repo}"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28"})

    def _url(self, ruta):
        return f"https://api.github.com/repos/{self.repo}/contents/{ruta}"

    def _get(self, ruta):
        r = self.s.get(self._url(ruta), params={"ref": self.rama}, timeout=20)
        if r.status_code == 404:
            return None, None
        if r.status_code in (401, 403):
            raise ErrorAlmacen("GitHub rechaza el token: revisa que tenga permiso de lectura y escritura "
                               f"de contenidos en {self.repo} y que no haya caducado.")
        r.raise_for_status()
        j = r.json()
        if j.get("encoding") == "none" or not j.get("content"):  # > 1 MB: la API de contenidos no lo incluye
            b = self.s.get(f"https://api.github.com/repos/{self.repo}/git/blobs/{j['sha']}", timeout=60)
            b.raise_for_status()
            return base64.b64decode(b.json()["content"]).decode("utf-8"), j["sha"]
        return base64.b64decode(j["content"]).decode("utf-8"), j["sha"]

    def _put(self, ruta, texto, sha, mensaje):
        body = {"message": mensaje, "branch": self.rama,
                "content": base64.b64encode(texto.encode("utf-8")).decode()}
        if sha:
            body["sha"] = sha
        r = self.s.put(self._url(ruta), json=body, timeout=90)
        if r.status_code in (409, 422) and "sha" in r.text:
            return False
        if r.status_code in (401, 403, 404):
            raise ErrorAlmacen(f"No puedo escribir en {self.repo} (HTTP {r.status_code}). Revisa el token.")
        r.raise_for_status()
        return True

    def leer_archivo(self, ruta_rel: str):
        return self._get(ruta_rel)[0]

    def escribir_archivo(self, ruta_rel: str, texto: str, mensaje: str):
        for _ in range(3):
            _, sha = self._get(ruta_rel)
            if self._put(ruta_rel, texto, sha, mensaje):
                return
            time.sleep(1)
        raise ErrorAlmacen("No se pudo guardar tras 3 intentos (conflicto).")

    def cargar(self) -> dict:
        texto, _ = self._get(self.ruta)
        return datos_vacios() if texto is None else normalizar(json.loads(texto))

    def modificar(self, cambio: Callable[[dict], None], mensaje: str) -> dict:
        for _ in range(4):
            texto, sha = self._get(self.ruta)
            d = datos_vacios() if texto is None else normalizar(json.loads(texto))
            cambio(d)
            normalizar(d)
            if self._put(self.ruta, json.dumps(d, ensure_ascii=False, separators=(",", ":")), sha, mensaje):
                return d
            time.sleep(1)
        raise ErrorAlmacen("Otro dispositivo estaba guardando a la vez y no se pudo guardar. Vuelve a intentarlo.")
