# JX2: BD desechable. Debe ejecutarse ANTES de importar nada de `app` (config/db leen DATABASE_URL al importar).
import atexit

import pytest

import infra_bd_desechable as _infra_bd

_BD_TMP_DIR, _BD_TMP_URL = _infra_bd.preparar_url_de_tests()
_motivo = _infra_bd.validar_url_temporal(_BD_TMP_URL)
if _motivo:
    _infra_bd.borrar_directorio(_BD_TMP_DIR)
    pytest.exit(
        "JX2: los tests no pueden usar esta BD (" + _motivo + "). Quita DATABASE_URL o apuntala a un "
        "sqlite dentro del directorio temporal. Sesion abortada para proteger zeus.db/produccion.",
        returncode=2,
    )
atexit.register(_infra_bd.borrar_directorio, _BD_TMP_DIR)

from app.core.config import settings  # noqa: E402
import app.db.base as _app_db_base  # noqa: E402

# Segunda salvaguarda, sobre lo que de verdad usa la app (settings y engine).
for _u in (settings.DATABASE_URL, _app_db_base.engine.url.render_as_string(hide_password=False)):
    _motivo = _infra_bd.validar_url_temporal(_u)
    if _motivo:
        _infra_bd.borrar_directorio(_BD_TMP_DIR)
        pytest.exit("JX2: la app apunta a una BD no temporal (" + _motivo + "). Sesion abortada.", returncode=2)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402  (importa routers y, con ellos, los modelos)

# create_tables() solo importa una lista fija de modelos; en una BD vacia create_all falla si falta
# alguno referenciado por FK (p.ej. company_employees). En la app real main ya los ha importado todos
# antes del lifespan; aqui lo garantizamos importando todo `app.models.*`.
import importlib  # noqa: E402
import pkgutil  # noqa: E402
import app.models as _app_models  # noqa: E402

for _m in pkgutil.iter_modules(_app_models.__path__):
    importlib.import_module("app.models." + _m.name)

# Mismo esquema que la app al arrancar: create_all de todos los modelos + parches idempotentes.
_app_db_base.create_tables()


def pytest_unconfigure(config):
    """Cierra conexiones y borra la BD desechable (nunca hace fallar la suite)."""
    try:
        _app_db_base.engine.dispose()
    except Exception:
        pass
    _infra_bd.borrar_directorio(_BD_TMP_DIR)

@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="module")
def test_user():
    return {
        "email": "marketingdigital per,seo@gmail.com",
        "password": "Carnay19!"
    }

@pytest.fixture(scope="module")
def test_token(test_client, test_user):
    response = test_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def authorized_client(test_client, test_token):
    test_client.headers.update({"Authorization": f"Bearer {test_token}"})
    return test_client


class _FakeSendGridResponse:
    status_code = 202
    headers = {"X-Message-Id": "test-message-id"}


class _FakeSendGridClient:
    """Sustituye SOLO al cliente externo de SendGrid: no abre red."""

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)
        return _FakeSendGridResponse()


class _FakeTwilioMessage:
    sid = "SMtest000000000000000000000000000"
    status = "queued"


class _FakeTwilioMessages:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _FakeTwilioMessage()


class _FakeTwilioClient:
    def __init__(self):
        self.messages = _FakeTwilioMessages()


@pytest.fixture(scope="module", autouse=True)
def no_external_messaging():
    """Autouse en toda la suite: ningun test debe alcanzar SendGrid/Twilio reales. Aisla de SendGrid/Twilio reales (DNS y envios con credenciales del entorno).

    Solo reemplaza `client` en los singletons email_service / whatsapp_service; el resto de
    la logica (flags, registro de actividad, resultado) sigue ejecutandose igual."""
    from services.email_service import email_service
    from services.whatsapp_service import whatsapp_service

    old_email, old_wa = email_service.client, whatsapp_service.client
    email_service.client = _FakeSendGridClient()
    whatsapp_service.client = _FakeTwilioClient()
    try:
        yield
    finally:
        email_service.client, whatsapp_service.client = old_email, old_wa


@pytest.fixture(autouse=True)
def no_real_classifier_model(monkeypatch):
    """J8b: ningun test alcanza el modelo real del clasificador de JARVIS (aunque otro test deje una
    OPENAI_API_KEY en settings). Sin modelo rige el criterio estricto J8. Los tests del clasificador
    inyectan su propio cliente simulado con monkeypatch (se aplica despues de este fixture)."""
    import services.jarvis_model_comprehension as mc

    monkeypatch.setattr(mc, "get_client", lambda: None)


# ---------------------------------------------------------------------------
# JX: aislamiento de efectos de los tests sobre el entorno compartido
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _backup_dir_temporal(tmp_path_factory):
    """Las copias de THALOS (handle_thalos_backup / thalos_backup_service) leen AGENT_BACKUP_DIR en
    tiempo de llamada. Durante la suite apuntan a un directorio temporal unico que se borra al final,
    de modo que `storage/backups` real no acumula copias de zeus.db."""
    import os
    import shutil

    tmp = tmp_path_factory.mktemp("agent_backups")
    previo = os.environ.get("AGENT_BACKUP_DIR")
    os.environ["AGENT_BACKUP_DIR"] = str(tmp)
    try:
        yield tmp
    finally:
        if previo is None:
            os.environ.pop("AGENT_BACKUP_DIR", None)
        else:
            os.environ["AGENT_BACKUP_DIR"] = previo
        shutil.rmtree(tmp, ignore_errors=True)


_ACTIVIDADES_CREADAS_EN_TEST: list = []
_ESTADOS_EJECUTABLES = ("pending", "in_progress")


def _registrar_actividad_creada(mapper, connection, target):
    _ACTIVIDADES_CREADAS_EN_TEST.append(target.id)


@pytest.fixture(scope="session", autouse=True)
def _rastrear_actividades_de_test():
    """Registra los ids de AgentActivity insertadas por los tests (solo mientras corre la suite)."""
    from sqlalchemy import event
    from app.models.agent_activity import AgentActivity

    event.listen(AgentActivity, "after_insert", _registrar_actividad_creada)
    try:
        yield
    finally:
        event.remove(AgentActivity, "after_insert", _registrar_actividad_creada)


@pytest.fixture(autouse=True)
def _neutralizar_actividades_ejecutables():
    """Al terminar cada test, las actividades que creo y siguen pending/in_progress pasan a
    'test_finalizado', para que un proceso externo que comparta zeus.db (p.ej. un uvicorn local con
    AgentAutomationExecutor) no ejecute nada creado por los tests. No altera lo que el test comprueba
    (el teardown corre despues del test y de sus fixtures de sesion de BD)."""
    _ACTIVIDADES_CREADAS_EN_TEST.clear()
    yield
    ids = list(_ACTIVIDADES_CREADAS_EN_TEST)
    _ACTIVIDADES_CREADAS_EN_TEST.clear()
    if not ids:
        return
    from app.db.base import SessionLocal
    from app.models.agent_activity import AgentActivity

    session = SessionLocal()
    try:
        session.query(AgentActivity).filter(
            AgentActivity.id.in_(ids), AgentActivity.status.in_(_ESTADOS_EJECUTABLES)
        ).update({AgentActivity.status: "test_finalizado"}, synchronize_session=False)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
