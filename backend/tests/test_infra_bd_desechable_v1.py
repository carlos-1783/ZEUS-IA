"""JX2: la suite usa una BD SQLite desechable y nunca zeus.db ni una BD real."""
import tempfile
from pathlib import Path

from sqlalchemy import inspect, text

import infra_bd_desechable as infra
from app.core.config import settings
from app.db.base import SessionLocal, engine

BACKEND = Path(__file__).resolve().parent.parent


def test_engine_y_settings_usan_bd_temporal():
    ruta = infra.ruta_sqlite_de_url(settings.DATABASE_URL)
    assert ruta is not None and ruta.name != "zeus.db"
    assert ruta != (BACKEND / "zeus.db").resolve()
    assert Path(tempfile.gettempdir()).resolve() in ruta.parents
    assert Path(engine.url.database).resolve() == ruta
    with SessionLocal() as s:
        fichero = s.execute(text("PRAGMA database_list")).fetchall()[0][2]
    assert Path(fichero).resolve() == ruta
    assert infra.validar_url_temporal(settings.DATABASE_URL) is None


def test_app_usa_la_misma_bd_temporal():
    import app.main  # noqa: F401
    from app.db import base

    assert base.engine is engine
    assert Path(base.engine.url.database).resolve() != (BACKEND / "zeus.db").resolve()


def test_esquema_completo_en_bd_temporal():
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    for t in ("users", "companies", "user_companies", "agent_activities", "zeus_pending_approvals"):
        assert t in tablas, "falta la tabla %s en la BD temporal" % t
    cols = {c["name"] for c in insp.get_columns("agent_activities")}
    assert "company_id" in cols
    # alembic_version no aplica: la app en desarrollo usa create_all + ensure_schema_patches.


def test_validacion_rechaza_urls_no_temporales(tmp_path):
    raiz = tmp_path
    ok = "sqlite:///" + (raiz / "x" / "t.db").as_posix()
    assert infra.validar_url_temporal(ok, raiz) is None
    assert "zeus.db" in infra.validar_url_temporal("sqlite:///" + (raiz / "zeus.db").as_posix(), raiz)
    assert infra.validar_url_temporal("sqlite:///" + (BACKEND / "zeus.db").as_posix(), raiz)
    assert infra.validar_url_temporal("sqlite:///./zeus.db", raiz)
    assert infra.validar_url_temporal("sqlite:///" + (BACKEND / "otra.db").as_posix(), raiz)
    assert infra.validar_url_temporal("postgresql://u:p@host/db", raiz)
    assert infra.validar_url_temporal("sqlite:///:memory:", raiz)
    assert infra.validar_url_temporal("", raiz)


def test_url_del_entorno_no_se_toca_y_se_crea_dir_unico(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    d, url = infra.preparar_url_de_tests()
    assert d is None and url.startswith("postgresql")
    assert infra.validar_url_temporal(url)
    monkeypatch.delenv("DATABASE_URL")
    d, url = infra.preparar_url_de_tests()  # fija os.environ; monkeypatch lo restaura al salir
    try:
        monkeypatch.setenv("DATABASE_URL", settings.DATABASE_URL)
        assert d is not None and d.name.startswith(infra.PREFIJO_DIR)
        assert infra.validar_url_temporal(url) is None
    finally:
        infra.borrar_directorio(d)
    assert not d.exists()


def test_borrar_directorio_no_borra_lo_ajeno(tmp_path):
    ajeno = tmp_path / "importante"
    ajeno.mkdir()
    assert infra.borrar_directorio(ajeno) is True
    assert ajeno.exists()
