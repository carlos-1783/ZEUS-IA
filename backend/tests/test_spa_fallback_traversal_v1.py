"""
Regresion H-10: el fallback SPA (``serve_frontend`` en backend/app/main.py) hacia
``os.path.join(spa_root, full_path)`` sin comprobar que la ruta resultante quedara dentro de
``spa_root``. Un ``full_path`` que empezaba por ``/`` (p.ej. ``//etc/passwd``, que FastAPI
decodifica igual con ``..%2f`` o ``%2e%2e``) o por una letra de unidad de Windows
(``C:/Windows/win.ini``) hacia que ``os.path.join``/``Path.__truediv__`` DESCARTARAN
``spa_root`` y devolvieran esa ruta absoluta tal cual: lectura arbitraria de ficheros del
servidor, reproducida en vivo contra produccion (``requirements.txt``, codigo fuente propio).

Estos tests reproducen exactamente esos exploits contra el fallback real (sin mocks del
enrutador) y exigen 404/200-SPA, nunca el contenido del fichero fuera de ``spa_root``. Tambien
confirman que un fichero legitimo del SPA sigue sirviendose igual que antes del fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module

SECRET_OUTSIDE_SPA = b"CONTENIDO-SECRETO-FUERA-DE-SPA-ROOT"


@pytest.fixture()
def client():
    # Sin context manager: no se ejecuta el lifespan (igual que el resto de la suite).
    c = TestClient(app, raise_server_exceptions=False)
    try:
        yield c
    finally:
        pass


@pytest.fixture()
def spa_tree(tmp_path, monkeypatch):
    """Arbol minimo: spa_root con un index.html y un asset legitimo, y un secreto FUERA de él."""
    root = tmp_path / "spa_root"
    root.mkdir(parents=True)
    # Deliberadamente FUERA de /assets: ese prefijo ya tiene su propio app.mount() fijado en el
    # import de main.py (con el spa_root real, no el de este test), así que no sirve como control.
    (root / "favicon.svg").write_bytes(b"<svg>spa real</svg>")
    (root / "index.html").write_bytes(b"<html>SPA-INDEX</html>")

    # Hermano de spa_root, al mismo nivel que requirements.txt/.env estarian en produccion.
    outside = tmp_path / "requirements.txt"
    outside.write_bytes(SECRET_OUTSIDE_SPA)

    # private_files tambien hermano de spa_root (configuracion real por defecto).
    private = tmp_path / "private_files"
    (private / "fiscal" / "1" / "invoices").mkdir(parents=True)
    (private / "fiscal" / "1" / "invoices" / "secreta.pdf").write_bytes(b"%PDF-1.4 privado")

    monkeypatch.setattr(main_module, "spa_root", str(root))
    return {"root": root, "outside": outside, "private": private, "tmp": tmp_path}


# --------------------------------------------------------------------------- traversal clasico


@pytest.mark.parametrize(
    "path",
    [
        "/../requirements.txt",
        "/..%2frequirements.txt",
        "/%2e%2e/requirements.txt",
        "/..%5crequirements.txt",
        # Nota: deliberadamente sin prefijo /assets/ — ese prefijo tiene su propio
        # app.mount(StaticFiles) fijado en el import de main.py (ver test de /assets más abajo),
        # así que una ruta bajo /assets/.. ejercitaría la protección de Starlette, no la nuestra.
        "/sub/../../requirements.txt",
        "/sub/..%2f..%2frequirements.txt",
    ],
)
def test_traversal_fuera_de_spa_root_no_filtra_contenido(client, spa_tree, path):
    r = client.get(path, headers={"Accept": "text/html"})
    assert SECRET_OUTSIDE_SPA not in r.content, path
    # Debe caer al index del SPA (200) o a 404/503; nunca servir el fichero ajeno.
    assert r.status_code != 200 or b"SPA-INDEX" in r.content, (path, r.status_code, r.content[:80])


# --------------------------------------------------------------------------- ruta absoluta / unidad


@pytest.mark.parametrize(
    "path",
    [
        "//etc/passwd",
        "///etc/passwd",
        "//Windows/win.ini",
    ],
)
def test_ruta_absoluta_doble_barra_no_descarta_spa_root(client, spa_tree, path):
    r = client.get(path, headers={"Accept": "text/html"})
    assert r.status_code != 200 or b"SPA-INDEX" in r.content, (path, r.status_code)
    assert SECRET_OUTSIDE_SPA not in r.content


def test_ruta_con_letra_de_unidad_windows_no_escapa(client, spa_tree):
    # Starlette no deja pasar ":" tal cual en el path sin codificar salvo escapado; probamos
    # ambas formas para cubrir el caso que explotó el revisor (C:/Windows/win.ini).
    for raw in ("/C:/Windows/win.ini", "/C%3A/Windows/win.ini"):
        r = client.get(raw, headers={"Accept": "text/html"})
        assert r.status_code != 200 or b"SPA-INDEX" in r.content, (raw, r.status_code)
        assert SECRET_OUTSIDE_SPA not in r.content


# --------------------------------------------------------------------------- private_files


def test_private_files_no_se_sirve_via_fallback_spa(client, spa_tree):
    for path in (
        "/private_files/fiscal/1/invoices/secreta.pdf",
        "/../private_files/fiscal/1/invoices/secreta.pdf",
        "/..%2fprivate_files%2ffiscal%2f1%2finvoices%2fsecreta.pdf",
    ):
        r = client.get(path, headers={"Accept": "text/html"})
        assert b"%PDF-1.4 privado" not in r.content, path
        assert r.status_code != 200 or b"SPA-INDEX" in r.content, (path, r.status_code)


# --------------------------------------------------------------------------- control positivo


def test_fichero_legitimo_del_spa_sigue_sirviendose(client, spa_tree):
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert r.content == b"<svg>spa real</svg>"


def test_index_sigue_sirviendose_para_ruta_de_la_spa(client, spa_tree):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"SPA-INDEX" in r.content


# --------------------------------------------------------------------------- unidad: _safe_spa_path


def test_safe_spa_path_rechaza_absolutas_y_unidad(spa_tree):
    from app.main import _safe_spa_path

    assert main_module._safe_spa_path("/etc/passwd") is None
    assert main_module._safe_spa_path("//etc/passwd") is None
    assert main_module._safe_spa_path("C:/Windows/win.ini") is None
    assert main_module._safe_spa_path("C:\\Windows\\win.ini") is None
    assert main_module._safe_spa_path("../../requirements.txt") is None
    assert main_module._safe_spa_path("assets/../../requirements.txt") is None
    assert main_module._safe_spa_path("") is None

    ok = main_module._safe_spa_path("favicon.svg")
    assert ok is not None
    assert ok == (Path(spa_tree["root"]) / "favicon.svg").resolve()
