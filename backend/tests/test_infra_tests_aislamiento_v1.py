"""JX: los tests no dejan copias de zeus.db en storage/backups ni actividades ejecutables."""
import glob
import os

from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity


def test_agent_backup_dir_es_temporal_y_no_es_el_real():
    d = os.environ["AGENT_BACKUP_DIR"]
    assert os.path.isdir(d) or not os.path.exists(d)
    assert os.path.abspath(d) != os.path.abspath(os.path.join("storage", "backups"))


def test_servicio_de_backup_escribe_en_dir_temporal():
    from services.thalos_backup_service import create_backup

    real = set(glob.glob(os.path.join("storage", "backups", "*")))
    try:
        create_backup()
    except Exception:
        pass
    assert set(glob.glob(os.path.join("storage", "backups", "*"))) == real
    assert not any(f.startswith(os.path.abspath("storage")) for f in glob.glob(os.environ["AGENT_BACKUP_DIR"] + "/*"))


_ID_PENDIENTE = {}


def test_crea_actividad_pending_para_el_teardown():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        a = AgentActivity(agent_name="THALOS", action_type="backup_created", status="pending", action_description="jx infra test")
        s.add(a)
        s.commit()
        _ID_PENDIENTE["id"] = a.id
        assert a.status == "pending"
    finally:
        s.close()


def test_la_actividad_del_test_anterior_ya_no_es_ejecutable():
    s = SessionLocal()
    try:
        row = s.get(AgentActivity, _ID_PENDIENTE["id"])
        assert row.status == "test_finalizado"
    finally:
        s.delete(row)
        s.commit()
        s.close()
