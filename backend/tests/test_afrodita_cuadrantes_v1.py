"""AFRODITA · cuadrantes con los empleados REALES de la empresa de la sesión (chat, ZEUS/JARVIS y ejecutor).

Antes, «hazme los cuadrantes con los empleados reales» llegaba al modelo, que contestaba «no tengo acceso»
e inventaba un horario genérico. Ahora es una lectura real (`get_staff_schedule`): empleados activos de
`company_employees` de la empresa de la sesión y sus horarios de `employee_schedules`.
- Turnos decididos -> cuadrante semanal por empleado (o el día pedido: quién trabaja / quién libra).
- Solo el horario BASE que pone el sistema al dar de alta (L-V 09:00-17:00 «completo») -> se dice que no es
  un turno decidido y se piden los reales.
- Código de empleado repetido en otra empresa del mismo titular (`U{id}-OWNER`) -> horario no atribuible:
  se dice y se pide el dato (employee_schedules no tiene company_id; sin migración).
- Sin horarios o sin empleados -> se pide el dato concreto. Nunca nombres ni horas inventados.
- Órdenes de crear/cambiar/borrar/enviar horarios -> respuesta fija y honesta (no hay acción de chat que los
  guarde), sin modelo.
Otra empresa del mismo usuario y otro tenant no aparecen. Login real (token Bearer); el LLM (run_chat,
openai) no puede llamarse: el test falla si se llama.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import (
    DEFAULT_SCHEDULE_DAYS,
    DEFAULT_SCHEDULE_END,
    DEFAULT_SCHEDULE_SHIFT,
    DEFAULT_SCHEDULE_START,
    EmployeeSchedule,
)
from services.afrodita_workspace_service_v1 import company_staff_schedule
from services.intent_parser import parse_intent
from services.jarvis_schedule_write_block import MSG_SCHEDULE_WRITE, schedule_write_block
from services.local_day_v1 import today_local
from services.onboarding_engine import _create_owner_employee_and_default_schedules
from services.zeus_agent_executor_v1 import execute_agent_action

from test_jarvis_acciones_ops_v1 import _env, _user, approvals, client, db  # noqa: F401

P = "/api/v1"
FRASES = [
    "hazme los cuadrantes con los empleados reales",
    "hazme el cuadrante de la semana",
    "cuadrante de turnos",
    "¿quién trabaja esta semana?",
    "horarios de los empleados",
]
# Frases que antes daban unknown (iban al LLM) -> (día esperado, semana esperada)
FRASES_NUEVAS = {
    "¿quién libra el lunes?": ("lunes", None),
    "pásame los turnos": (None, None),
    "¿me haces el cuadrante?": (None, None),
    "quién trabaja hoy": ("today", None),
    "quién trabaja el sábado": ("sabado", None),
    "turnos de la semana": (None, None),
    "enséñame los turnos de esta semana": (None, None),
    "horario del personal": (None, None),
    "qué turnos hay esta semana": (None, None),
    "haz el cuadrante de turnos de la semana que viene": (None, "next"),
    "cuadrante de la semana que viene": (None, "next"),
    "turnos del equipo": (None, None),
    "horario del equipo": (None, None),
}
ORDENES = [
    "borra el cuadrante", "borra el cuadrante de la semana", "crea un cuadrante nuevo para Ana", "crea un cuadrante",
    "cambia el horario de Ana", "pon a Carlos de tarde", "pon a Carlos de tarde en el cuadrante",
    "añade a Ismael al cuadrante", "modifica los turnos de los empleados", "elimina los horarios de los empleados",
    "asigna turnos a los empleados", "cambia el cuadrante de turnos", "envía el cuadrante a los empleados",
    "hazme el cuadrante de la semana y mándaselo a Ana", "quiero que cambies el turno de Ana",
    # producir un reparto NUEVO (criterio: generar/organizar/planificar/distribuir/repartir/rehacer = orden)
    "genera un cuadrante nuevo", "genera el cuadrante", "generar el cuadrante de la semana",
    "organiza los turnos del equipo", "reparte los turnos de la plantilla", "planifica el cuadrante de la semana",
    "distribuye los turnos entre los camareros", "rehaz el cuadrante", "hazme un cuadrante nuevo",
    "haz otro cuadrante",
    # «turnos» en plural suelto o con complemento de tiempo/plantilla es la plantilla (mismo criterio que la
    # lectura); con otro sustantivo («de caja», «de reservas»…) o en singular, no (ver NO_PLANTILLA)
    "reparte los turnos", "cambia los turnos de esta semana", "cambia los turnos de los camareros",
    "mueve los turnos del lunes",
]
PLANTILLA = ["Ana", "Carlos", "Carmelo", "Ismael"]
# Horarios/turnos que NO son de la plantilla: en HEAD daban unknown y deben seguir sin bloquearse.
NO_PLANTILLA = [
    "envía el horario de verano a los clientes", "cambia el turno de caja",
    "crea un recordatorio para el turno de mañana", "mete el pedido en el turno de tarde", "manda el turno al grupo",
    # «turnos» + de/del/para + OTRO sustantivo: no es la plantilla, ni para leer ni para bloquear
    "cambia los turnos de caja", "crea los turnos de reservas", "envía los turnos de reparto al proveedor",
    "mueve los turnos de entrega al martes", "asigna los turnos de las mesas", "programa los turnos de publicación",
    "cancela los turnos de la web", "envía los turnos de recogida a los clientes", "cambia los turnos de la campaña",
    "crea turnos de reserva para el sábado", "pásame los turnos de reparto",
]
# Intención que daba HEAD (antes de la lectura del cuadrante) para frases con «turnos» que no son la plantilla:
# deben seguir igual.
COMO_EN_HEAD = {**{m: "unknown" for m in NO_PLANTILLA}, "turnos de caja de hoy": "tpv_sales_today"}
BASE = f"lunes a viernes {DEFAULT_SCHEDULE_START}-{DEFAULT_SCHEDULE_END}"


@pytest.fixture(autouse=True)
def sin_llm(monkeypatch, _env):  # noqa: F811 — depende de _env para sobrescribir su stub de run_chat
    """Cualquier llamada al modelo (runtime de agentes u OpenAI directo) hace fallar el test."""
    import agents.base_agent as base_agent
    import services.openai_service as openai_service
    import services.unified_agent_runtime as rt

    calls = []

    def _boom(name):
        def _f(*a, **k):
            calls.append(name)
            raise AssertionError(f"se ha llamado al LLM ({name})")
        return _f

    monkeypatch.setattr(rt, "run_chat", _boom("run_chat"))
    monkeypatch.setattr(openai_service, "chat_completion", _boom("openai_service.chat_completion"))
    monkeypatch.setattr(openai_service, "get_openai_client", _boom("openai_service.get_openai_client"))
    monkeypatch.setattr(base_agent, "chat_completion", _boom("base_agent.chat_completion"))
    yield calls
    assert calls == [], calls


# ----------------------------------------------------------------------------- datos sembrados
def _emp(db, company, name, role=None, code=None):
    e = CompanyEmployee(company_id=company.id, full_name=name, role_title=role,
                        employee_code=code or f"EMP-{uuid.uuid4().hex[:10]}", is_active=True, source="test")
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _sched(db, emp, owner, days, start, end, shift=None):
    code = emp if isinstance(emp, str) else emp.employee_code
    for d in days:
        db.add(EmployeeSchedule(employee_id=code, user_id=owner.id, day_of_week=d,
                                start_time=start, end_time=end, shift_type=shift, is_active=True))
    db.commit()


def _base(db, emp, owner):
    """El horario base, igual que lo crea el alta (mismas constantes)."""
    _sched(db, emp, owner, DEFAULT_SCHEDULE_DAYS, DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END, DEFAULT_SCHEDULE_SHIFT)


def _segunda_empresa(db, u):
    b = Company(company_name=f"B {uuid.uuid4().hex[:6]}", slug=f"b-{uuid.uuid4().hex[:8]}",
                company_type="bar_restaurant")
    db.add(b)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=b.id, role="owner"))  # vinculo posterior: A sigue siendo la sesión
    db.commit()
    db.refresh(b)
    return b


def _empresa_a(db, *, con_horarios):
    """U (empresa de la sesión A: Ana, Carlos, Carmelo, Ismael) + 2ª empresa B de U (Beatriz, con horario)
    + otro tenant T (empresa C: Tomás, con horario; y un horario de T con el MISMO código que Carmelo)."""
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    t, c = _user(db)
    ana, carlos = _emp(db, a, "Ana", "Camarera"), _emp(db, a, "Carlos")
    carmelo, ismael = _emp(db, a, "Carmelo"), _emp(db, a, "Ismael")
    beatriz, tomas = _emp(db, b, "Beatriz"), _emp(db, c, "Tomás")
    _sched(db, beatriz, u, range(7), "08:00", "15:00")
    _sched(db, tomas, t, range(5), "10:00", "18:00")
    # mismo employee_id que Carmelo pero guardado por el otro tenant: no es un horario de A
    _sched(db, carmelo, t, [0], "06:00", "07:00")
    if con_horarios:
        _sched(db, ana, u, range(5), "09:00", "17:00", "mañana")
        _sched(db, carlos, u, (5, 6), "12:00", "20:00", "tarde")
    return u, a, b, t, c


def _login(client, user):
    r = client.post(f"{P}/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _afrodita(client, headers, msg):
    r = client.post(f"{P}/chat/afrodita/chat", headers=headers,
                    json={"message": msg, "thread_id": f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _jarvis(client, headers, msg):
    r = client.post(f"{P}/jarvis/message", headers=headers,
                    json={"message": msg, "thread_id": f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _ajenos_fuera(msg):
    for otro in ("Beatriz", "Tomás", "08:00", "10:00", "06:00"):
        assert otro not in msg, (otro, msg)
    assert "no tengo acceso" not in msg.lower()


# ----------------------------------------------------------------------------- intencion (reglas)
@pytest.mark.parametrize("msg", FRASES + [
    "cuadrante semanal", "muéstrame el cuadrante", "¿quiénes trabajan esta semana?",
    "turnos de los empleados", "dime los horarios de la plantilla", "prepárame el cuadrante de turnos",
    # puestos: misma lista que el criterio de «turnos» y el bloqueo (STAFF_ROLE_WORDS)
    "turnos de los camareros", "pásame los turnos de los camareros", "turnos de los camareros de esta semana",
    "turnos de los cocineros de esta semana", "horarios de los camareros",
])
def test_frases_naturales_se_entienden(msg):
    t = parse_intent(msg)
    assert t.intent == "get_staff_schedule" and not t.needs_clarification and t.confidence >= 0.7, (msg, t.intent)


@pytest.mark.parametrize("msg,esperado", list(FRASES_NUEVAS.items()))
def test_frases_nuevas_se_entienden_con_su_dia_y_semana(msg, esperado):
    t = parse_intent(msg)
    assert t.intent == "get_staff_schedule" and not t.needs_clarification, (msg, t.intent)
    assert (t.metadata.get("day"), t.metadata.get("week")) == esperado, (msg, t.metadata)


@pytest.mark.parametrize("msg,intent", [
    ("quién trabaja ahora", "get_attendance_status"),
    ("¿quiénes están trabajando ahora?", "get_attendance_status"),
    ("estado de mi turno", "shift_status"),
    ("¿tengo turno activo?", "shift_status"),
])
def test_lo_que_no_es_el_cuadrante_sigue_en_su_sitio(msg, intent):
    assert parse_intent(msg).intent == intent, msg


def test_mi_turno_no_es_el_cuadrante():
    # «mi turno» (el propio) nunca es el cuadrante de la empresa
    for msg in ("mi turno", "¿cuál es mi turno?", "mi turno de hoy"):
        assert parse_intent(msg).intent != "get_staff_schedule", msg


@pytest.mark.parametrize("msg", ORDENES)
def test_una_orden_nunca_es_esta_lectura_y_se_bloquea(msg):
    assert parse_intent(msg).intent != "get_staff_schedule", msg
    assert schedule_write_block(msg, PLANTILLA) is not None, msg


@pytest.mark.parametrize("msg", NO_PLANTILLA + ["haz uno nuevo", "pon a Pepe de tarde"])
def test_sin_contexto_de_plantilla_no_se_bloquea(msg):
    # «Pepe» no es empleado de la empresa: con la plantilla a mano no basta un nombre propio cualquiera
    assert schedule_write_block(msg, PLANTILLA) is None, msg
    assert parse_intent(msg).intent == "unknown", msg  # como en HEAD


@pytest.mark.parametrize("msg,intent", list(COMO_EN_HEAD.items()))
def test_turnos_que_no_son_la_plantilla_quedan_como_en_head(msg, intent):
    assert parse_intent(msg).intent == intent, msg
    assert schedule_write_block(msg, PLANTILLA) is None, msg


def test_nombre_de_empleado_real_da_el_contexto():
    assert schedule_write_block("cambia el horario de Ana", PLANTILLA) is not None
    assert schedule_write_block("cambia el horario de Ana", ["Beatriz"]) is None  # Ana no es de esta empresa
    assert schedule_write_block("pon a Ana de mañana") is not None  # sin plantilla: nombre propio + turno


@pytest.mark.parametrize("msg", ["hazme el cuadrante", "móntame el cuadrante", "hazme el cuadrante de la semana",
                                 "prepárame el cuadrante de turnos", "pásame los turnos",
                                 "mándame los turnos", "envíame el cuadrante"])
def test_hazme_el_cuadrante_es_lectura_no_bloqueo(msg):
    assert schedule_write_block(msg, PLANTILLA) is None, msg
    assert parse_intent(msg).intent == "get_staff_schedule", msg


@pytest.mark.parametrize("msg", FRASES + list(FRASES_NUEVAS) + [
    "mándame el cuadrante", "cambia el horario de apertura", "cancela la reserva del turno de cena",
    "crea una campaña para el horario de tarde", "cuadra la caja del turno de tarde",
    "crea una ruta de Madrid a Valencia", "registra una entrada de 5 unidades de Harina", "estado de mi turno",
])
def test_consultas_y_otros_horarios_no_se_bloquean(msg):
    assert schedule_write_block(msg, PLANTILLA) is None, msg


def test_negacion_no_ejecuta():
    t = parse_intent("no me hagas el cuadrante")
    assert t.intent != "get_staff_schedule" or t.needs_clarification


# ----------------------------------------------------------------------------- lectura (servicio)
def test_cuadrante_real_solo_de_la_empresa_de_la_sesion(db):
    u, a, b, t, c = _empresa_a(db, con_horarios=True)
    data = company_staff_schedule(db, a.id, today_local())
    assert data["employees_total"] == 4 and data["employees_with_schedule"] == 2
    assert [r["name"] for r in data["roster"]] == ["Ana", "Carlos"]
    ana = data["roster"][0]
    assert ana["shift_week"] == "lunes a viernes 09:00-17:00 (mañana)" and ana["hours_week"] == 40
    assert data["roster"][1]["shift_week"] == "sábado y domingo 12:00-20:00 (tarde)"
    assert data["without_schedule"] == ["Carmelo", "Ismael"]  # el horario de T con el código de Carmelo no cuenta
    assert data["missing"] == "schedules" and data["shifts_count"] == 7


def test_sin_horarios_y_sin_empleados(db):
    u, a, *_ = _empresa_a(db, con_horarios=False)
    data = company_staff_schedule(db, a.id, today_local())
    assert data["employees_total"] == 4 and data["roster"] == [] and data["missing"] == "schedules"
    _, vacia = _user(db)
    data = company_staff_schedule(db, vacia.id, today_local())
    assert data["employees_total"] == 0 and data["missing"] == "employees"


def test_codigo_del_titular_en_dos_empresas_no_cruza_horarios(db, client):
    """El alta pone U{id}-OWNER al titular en TODAS sus empresas y employee_schedules no tiene company_id:
    el horario guardado en B no puede salir en el cuadrante de A."""
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    ra = _create_owner_employee_and_default_schedules(db, a, u)
    rb = _create_owner_employee_and_default_schedules(db, b, u)
    db.commit()
    code = f"U{u.id}-OWNER"
    assert ra["employee_code"] == rb["employee_code"] == code
    _sched(db, code, u, [5], "07:00", "15:00", "mañana")  # turno del sábado guardado pensando en B
    ana = _emp(db, a, "Ana", "Camarera")
    _sched(db, ana, u, (1, 2, 3), "16:00", "23:00", "tarde")
    owner_name = db.query(CompanyEmployee).filter(CompanyEmployee.company_id == a.id,
                                                  CompanyEmployee.employee_code == code).one().full_name
    data = company_staff_schedule(db, a.id, today_local())
    assert [r["name"] for r in data["roster"]] == ["Ana"]
    assert data["ambiguous_schedule"] == [owner_name] and data["default_schedule_only"] == []
    out = _afrodita(client, _login(client, u), "cuadrante de turnos")
    m = out["message"]
    assert "07:00" not in m and BASE not in m, m
    assert (f"{owner_name}: tiene horarios guardados en varias de tus empresas y no puedo saber cuál es de "
            "esta; dime su turno aquí.") in m, m
    assert "Ana (Camarera): martes a jueves 16:00-23:00 (tarde)" in m, m


def test_titular_de_una_sola_empresa_horario_base_y_puesto_en_espanol(db, client):
    u, a = _user(db)
    _create_owner_employee_and_default_schedules(db, a, u)
    db.commit()
    data = company_staff_schedule(db, a.id, today_local())
    assert data["ambiguous_schedule"] == [] and len(data["default_schedule_only"]) == 1
    # con un turno propio (no base), el puesto «owner» sale como «titular»
    _sched(db, f"U{u.id}-OWNER", u, [5], "10:00", "14:00")
    data = company_staff_schedule(db, a.id, today_local())
    assert data["roster"][0]["role_title"] == "titular", data["roster"]
    out = _afrodita(client, _login(client, u), "cuadrante de turnos")
    assert "(titular)" in out["message"] and "owner" not in out["message"], out["message"]


# ----------------------------------------------------------------------------- horario base del sistema
def test_todos_con_solo_el_horario_base(db, client):
    u, a = _user(db)
    for n in ("Ana", "Carlos"):
        _base(db, _emp(db, a, n), u)
    data = company_staff_schedule(db, a.id, today_local())
    assert data["roster"] == [] and data["default_schedule_only"] == ["Ana", "Carlos"]
    out = _afrodita(client, _login(client, u), "hazme el cuadrante de la semana")
    m = out["message"]
    assert m.startswith(f"Tengo a Ana y Carlos en tu empresa, pero solo tienen el horario base que pone el "
                        f"sistema al darlos de alta ({BASE}), no turnos decididos"), m
    assert "Dime el horario de apertura y los turnos" in m


def test_mezcla_de_horario_base_y_turnos_decididos(db, client):
    u, a = _user(db)
    ana, carlos = _emp(db, a, "Ana", "Camarera"), _emp(db, a, "Carlos")
    _sched(db, ana, u, range(5), "08:00", "16:00", "mañana")
    _base(db, carlos, u)
    out = _afrodita(client, _login(client, u), "cuadrante de turnos")
    m = out["message"]
    assert m.startswith("Cuadrante semanal con los horarios guardados (2 empleados, 1 con turno decidido): "
                        "Ana (Camarera): lunes a viernes 08:00-16:00 (mañana)."), m
    assert (f"Carlos: solo tiene el horario base que pone el sistema al darlo de alta ({BASE}); si no es su "
            "horario real, dime sus turnos.") in m, m


def test_todos_con_turnos_decididos(db, client):
    u, a = _user(db)
    ana, carlos = _emp(db, a, "Ana"), _emp(db, a, "Carlos")
    _sched(db, ana, u, range(5), "08:00", "16:00", "mañana")
    _sched(db, carlos, u, range(5), "16:00", "23:00", "tarde")
    out = _afrodita(client, _login(client, u), "turnos del equipo")
    m = out["message"]
    assert m == ("Cuadrante semanal con los horarios guardados (2 empleados, 2 con turno decidido): "
                 "Ana: lunes a viernes 08:00-16:00 (mañana). Carlos: lunes a viernes 16:00-23:00 (tarde). "
                 "Sin nadie asignado: sábado y domingo."), m
    assert "horario base" not in m


# ----------------------------------------------------------------------------- chat con login real
def test_chat_sin_horarios_pide_el_dato_con_los_nombres_reales(db, client):
    u, *_ = _empresa_a(db, con_horarios=False)
    h = _login(client, u)
    esperado = ("Tengo a Ana, Carlos, Carmelo e Ismael en tu empresa, pero ninguno tiene horario guardado, "
                "así que no te monto el cuadrante inventándomelo.")
    for msg in FRASES + list(FRASES_NUEVAS):
        out = _afrodita(client, h, msg)
        assert out["success"] and out.get("executed_action"), (msg, out)
        assert out["message"].startswith(esperado), (msg, out["message"])
        assert "Dime el horario de apertura y los turnos" in out["message"]
        _ajenos_fuera(out["message"])
    out = _jarvis(client, h, FRASES[0])  # vía ZEUS/JARVIS: misma lectura
    assert out["message"].startswith(esperado), out
    _ajenos_fuera(out["message"])
    assert not approvals(db, u)


def test_chat_con_horarios_muestra_el_cuadrante_real(db, client):
    u, *_ = _empresa_a(db, con_horarios=True)
    h = _login(client, u)
    semanales = FRASES + [f for f, (d, _w) in FRASES_NUEVAS.items() if d is None]
    for msg in semanales:
        out = _afrodita(client, h, msg)
        m = out["message"]
        assert out["success"] and out.get("executed_action"), (msg, out)
        cab = "de la semana que viene" if FRASES_NUEVAS.get(msg, (None, None))[1] == "next" else "semanal"
        assert m.startswith(f"Cuadrante {cab} con los horarios guardados (4 empleados, 2 con turno decidido):"), m
        assert "Ana (Camarera): lunes a viernes 09:00-17:00 (mañana)" in m
        assert "Carlos: sábado y domingo 12:00-20:00 (tarde)" in m
        assert "Sin horario: Carmelo e Ismael" in m
        _ajenos_fuera(m)
    out = _jarvis(client, h, "¿quién trabaja esta semana?")
    assert "Ana (Camarera): lunes a viernes 09:00-17:00 (mañana)" in out["message"]
    _ajenos_fuera(out["message"])
    assert not approvals(db, u)


def test_chat_dia_concreto_quien_trabaja_y_quien_libra(db, client):
    u, *_ = _empresa_a(db, con_horarios=True)
    h = _login(client, u)
    hoy = today_local().weekday()

    def cuando(dow, nombre):  # si el día pedido es hoy, la respuesta lo dice
        return f"hoy ({nombre})" if hoy == dow else f"el {nombre}"

    m = _afrodita(client, h, "¿quién libra el lunes?")["message"]
    assert m.startswith(f"Según los turnos guardados, {cuando(0, 'lunes')} trabaja: Ana 09:00-17:00 (mañana). "
                        "Libra: Carlos."), m
    assert "Sin horario: Carmelo e Ismael" in m
    m = _afrodita(client, h, "quién trabaja el sábado")["message"]
    assert m.startswith(f"Según los turnos guardados, {cuando(5, 'sábado')} trabaja: Carlos 12:00-20:00 (tarde). "
                        "Libra: Ana."), m
    _ajenos_fuera(m)
    m = _jarvis(client, h, "quién trabaja hoy")["message"]
    assert m.startswith("Según los turnos guardados, hoy ("), m
    quien, libra = ("Ana 09:00-17:00 (mañana)", "Carlos") if hoy < 5 else ("Carlos 12:00-20:00 (tarde)", "Ana")
    assert f"trabaja: {quien}. Libra: {libra}." in m, m


def test_chat_sin_empleados_lo_dice(db, client):
    u, _ = _user(db)
    out = _afrodita(client, _login(client, u), "hazme los cuadrantes con los empleados reales")
    assert out["message"].startswith("No hay empleados dados de alta en tu empresa"), out
    assert "Control horario" in out["message"] and "no tengo acceso" not in out["message"].lower()


def test_ordenes_de_escritura_respuesta_fija_sin_llm_y_sin_tocar_nada(db, client):
    u, a, *_ = _empresa_a(db, con_horarios=True)
    h = _login(client, u)
    antes = db.query(EmployeeSchedule).count()
    for msg in ORDENES:
        for out in (_afrodita(client, h, msg), _jarvis(client, h, msg)):
            assert out["success"] is False and out["status"] == "not_available", (msg, out)
            assert out["message"] == MSG_SCHEDULE_WRITE, (msg, out["message"])
            low = out["message"].lower()
            assert "hecho" not in low and "he cambiado" not in low and "he borrado" not in low
            assert not out.get("executed_action")
    db.expire_all()
    assert db.query(EmployeeSchedule).count() == antes
    assert not approvals(db, u)


def test_ejecutor_y_sin_credenciales(db, client):
    u, a, *_ = _empresa_a(db, con_horarios=True)
    r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_staff_schedule", payload={}))
    assert r["success"] and r["executed"] and r["company_id"] == a.id
    assert [x["name"] for x in r["data"]["roster"]] == ["Ana", "Carlos"]
    r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_staff_schedule",
                                         payload={"day": "festivo"}))
    assert not r.get("executed") and r.get("status") == "invalid_payload", r
    # pedida como si fuera de otro agente: rechazada
    r = asyncio.run(execute_agent_action(db, user=u, agent="RAFAEL", action="get_staff_schedule", payload={}))
    assert not r.get("executed")
    r = client.post(f"{P}/chat/afrodita/chat", json={"message": FRASES[0], "thread_id": "t-x"})
    assert r.status_code in (401, 403), r.text


# ----------------------------------------------------------------------------- revisión 2
def test_bloqueo_con_la_plantilla_real_de_la_bd(db):
    """En el chat la plantilla sale de la BD (empresa de la sesión): un empleado de otra empresa no cuenta."""
    from services.afrodita_workspace_service_v1 import active_employee_names_for_session

    u, a, b, t, c = _empresa_a(db, con_horarios=False)
    names = lambda: active_employee_names_for_session(db, u)  # noqa: E731
    assert sorted(names()) == ["Ana", "Carlos", "Carmelo", "Ismael"]
    assert schedule_write_block("cambia el horario de Ana", names) is not None
    assert schedule_write_block("cambia el horario de Beatriz", names) is None  # Beatriz es de la empresa B
    for msg in NO_PLANTILLA:
        assert schedule_write_block(msg, names) is None, msg


def test_concordancia_con_un_solo_empleado(db, client):
    u, a = _user(db)
    ana = _emp(db, a, "Ana")
    h = _login(client, u)
    m = _afrodita(client, h, "cuadrante de turnos")["message"]
    assert m.startswith("Tengo a Ana en tu empresa, pero no tiene horario guardado, así que no te monto"), m
    _base(db, ana, u)
    m = _afrodita(client, h, "cuadrante de turnos")["message"]
    assert m.startswith(f"Tengo a Ana en tu empresa, pero solo tiene el horario base que pone el sistema al darlo "
                        f"de alta ({BASE}), no un turno decidido, así que no te monto el cuadrante con eso."), m
    u2, a2 = _user(db)
    _sched(db, _emp(db, a2, "Ana"), u2, [0], "10:00", "18:00", "mañana")
    _emp(db, a2, "Carlos")
    hoy = today_local().weekday()
    cuando = "hoy (lunes)" if hoy == 0 else "el lunes"
    m = _afrodita(client, _login(client, u2), "¿quién trabaja el lunes?")["message"]
    assert m.startswith(f"Según los turnos guardados, {cuando} trabaja: Ana 10:00-18:00 (mañana)."), m
    assert "trabajan" not in m


def test_codigo_dado_de_baja_en_otra_empresa_con_horarios_es_ambiguo(db):
    """El mismo código, de BAJA en la otra empresa del titular, cuenta como ambiguo si allí hay horarios
    guardados con ese código (pueden ser de cuando trabajaba allí)."""
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    code = f"EMP-{uuid.uuid4().hex[:8]}"
    eva = _emp(db, a, "Eva", code=code)
    old = _emp(db, b, "Eva", code=code)
    old.is_active = False
    db.commit()
    _sched(db, eva, u, range(5), "07:00", "15:00", "mañana")  # guardado por U, que también es de B
    data = company_staff_schedule(db, a.id, today_local())
    assert data["ambiguous_schedule"] == ["Eva"] and data["roster"] == [], data
    # control: el mismo caso, pero el horario lo guardó un usuario que solo es de A -> no es ambiguo
    v, a2 = _user(db)
    w = _user(db, company=a2)[0]  # w solo pertenece a A2
    b2 = _segunda_empresa(db, v)
    code2 = f"EMP-{uuid.uuid4().hex[:8]}"
    luz = _emp(db, a2, "Luz", code=code2)
    old2 = _emp(db, b2, "Luz", code=code2)
    old2.is_active = False
    db.commit()
    _sched(db, luz, w, range(5), "07:00", "15:00", "mañana")
    data = company_staff_schedule(db, a2.id, today_local())
    assert data["ambiguous_schedule"] == [] and [r["name"] for r in data["roster"]] == ["Luz"], data


# ----------------------------------------------------------------------------- consulta por EMPLEADO
from services.intent_parser import staff_member_task  # noqa: E402

FRASES_EMPLEADO = ["turnos de Ana", "turnos de Ana de esta semana", "turnos de Ana López", "horario de Ana",
                   "¿qué turno tiene Ana?", "¿cuándo trabaja Ana?"]
# Lo que daba HEAD para frases de horario que no son de un empleado: no cambia.
HEAD_NO_EMPLEADO = {"horario de apertura": "unknown", "¿cuándo abre el restaurante?": "unknown"}


@pytest.mark.parametrize("msg", FRASES_EMPLEADO)
def test_consulta_de_un_empleado_se_entiende_con_la_plantilla(msg):
    t = staff_member_task(msg, ["Ana López", "Carlos"])
    assert t is not None and t.intent == "get_staff_schedule", msg
    assert t.metadata["employee"] in ("ana", "ana lopez"), t.metadata


@pytest.mark.parametrize("msg", FRASES_EMPLEADO + ["horario de Pepe"])
def test_nombre_fuera_de_la_plantilla_no_se_toca(msg):
    # «Ana» no está en la plantilla (es un cliente, un proveedor u otra empresa): la frase no se toca
    assert staff_member_task(msg, ["Carlos", "Ismael"]) is None, msg


@pytest.mark.parametrize("msg,intent", list(HEAD_NO_EMPLEADO.items()))
def test_horarios_que_no_son_de_un_empleado_quedan_como_en_head(msg, intent):
    assert staff_member_task(msg, ["Ana López", "Carlos"]) is None
    assert parse_intent(msg).intent == intent


@pytest.mark.parametrize("msg", ["cambia el horario de Ana", "no me digas el horario de Ana",
                                 "horario de Ana y bórralo", "envía el horario de Ana a Carlos"])
def test_ordenes_y_negaciones_no_son_consulta_de_empleado(msg):
    assert staff_member_task(msg, ["Ana López", "Carlos"]) is None, msg


def _empresa_empleados(db):
    """A (sesión): Ana López (turnos propios), Carlos (sin horario), Ismael (solo horario base).
    B (2ª empresa del mismo usuario): Beatriz con horario. Otro tenant: Tomás con horario."""
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    t, c = _user(db)
    ana = _emp(db, a, "Ana López", "Camarera")
    _emp(db, a, "Carlos")
    ismael = _emp(db, a, "Ismael")
    _sched(db, ana, u, range(5), "09:00", "17:00", "mañana")
    _base(db, ismael, u)
    _sched(db, _emp(db, b, "Beatriz"), u, range(7), "08:00", "15:00")
    _sched(db, _emp(db, c, "Tomás"), t, range(5), "10:00", "18:00")
    return u, a, b, t, c


ANA = "Turnos guardados de Ana López (Camarera): lunes a viernes 09:00-17:00 (mañana)."


def test_chat_consulta_por_empleado_con_login_real(db, client):
    u, *_ = _empresa_empleados(db)
    h = _login(client, u)
    for msg in FRASES_EMPLEADO:
        for out in (_afrodita(client, h, msg), _jarvis(client, h, msg)):
            assert out["success"] and out.get("executed_action"), (msg, out)
            assert out["message"] == ANA, (msg, out["message"])  # solo Ana: ni Carlos, ni Ismael, ni otras empresas
    m = _afrodita(client, h, "horario de Carlos")["message"]
    assert m == ("Carlos: no tiene horario guardado; dime su turno (qué días y de qué hora a qué hora). "
                 "Para que quede guardado, añádelo en Control horario."), m
    m = _jarvis(client, h, "¿cuándo trabaja Ismael?")["message"]
    assert m == (f"Ismael: solo tiene el horario base que pone el sistema en el alta ({BASE}); si no es su "
                 "horario real, dime su turno."), m
    hoy = today_local().weekday()
    cuando = "hoy (lunes)" if hoy == 0 else "el lunes"
    m = _afrodita(client, h, "¿cuándo trabaja Ana el lunes?")["message"]
    assert m == f"Según los turnos guardados, Ana López (Camarera) {cuando} trabaja 09:00-17:00 (mañana).", m
    assert not approvals(db, u)


def test_empleado_de_otra_empresa_u_otro_tenant_no_se_resuelve(db):
    from services.afrodita_workspace_service_v1 import active_employee_names_for_session

    u, a, *_ = _empresa_empleados(db)
    names = active_employee_names_for_session(db, u)
    for msg in ("turnos de Beatriz", "¿cuándo trabaja Tomás?", "horario de Beatriz"):
        assert staff_member_task(msg, names) is None, msg  # no se toca: sigue su camino como en HEAD
    # aunque alguien lo pida directamente al ejecutor, el nombre se resuelve en la empresa de la sesión
    for nombre in ("Beatriz", "Tomás"):
        r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_staff_schedule",
                                             payload={"employee": nombre}))
        assert r["executed"] and r["data"]["employees_total"] == 0, r
        assert r["message"] == f"No encuentro a «{nombre}» entre los empleados activos de tu empresa.", r
        assert "08:00" not in str(r) and "10:00" not in str(r)
    r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_staff_schedule",
                                         payload={"employee": 7}))
    assert not r.get("executed") and r.get("status") == "invalid_payload", r


def test_dos_empleados_con_el_mismo_nombre_se_dan_los_dos(db, client):
    u, a = _user(db)
    a1, a2 = _emp(db, a, "Ana López"), _emp(db, a, "Ana Ruiz")
    _sched(db, a1, u, range(5), "09:00", "17:00", "mañana")
    m = _afrodita(client, _login(client, u), "¿cuándo trabaja Ana?")["message"]
    assert m == ("Hay 2 empleados con ese nombre en tu empresa. Turnos guardados de Ana López: lunes a viernes "
                 "09:00-17:00 (mañana). Ana Ruiz: no tiene horario guardado; dime su turno (qué días y de qué hora "
                 "a qué hora). Para que quede guardado, añádelo en Control horario."), m
