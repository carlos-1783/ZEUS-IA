"""Tests for zeus_automation_audit_v1."""

from unittest.mock import MagicMock, patch

from services.zeus_automation_audit_v1 import get_automation_audit, record_automation_audit


def test_record_automation_audit_adds_row():
    db = MagicMock()
    with patch("services.zeus_automation_audit_v1.ZeusAutomationLog") as mock_cls:
        inst = MagicMock()
        inst.id = "log-uuid-1"
        mock_cls.return_value = inst
        log_id = record_automation_audit(
            db,
            automation_name="contract_rrhh_pipeline",
            agent="AFRODITA",
            trigger_type="event_bus",
            status="success",
            input_data={"employee_id": 1},
            output_data={"handlers": ["pipeline"]},
            user_id=1,
        )
    db.add.assert_called_once()
    db.flush.assert_called_once()
    assert log_id == "log-uuid-1"


def test_get_automation_audit_structure():
    db = MagicMock()
    user = MagicMock()
    user.is_superuser = True

    mock_log = MagicMock()
    mock_log.id = "abc"
    mock_log.automation_name = "payment_risk"
    mock_log.agent = "THALOS"
    mock_log.trigger_type = "event_bus"
    mock_log.status = "success"
    mock_log.input_data = {}
    mock_log.output_data = {}
    mock_log.executed_at = None

    with patch.object(db, "query") as mock_query:
        chain = mock_query.return_value
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.group_by.return_value = chain
        chain.all.side_effect = [[mock_log], []]
        out = get_automation_audit(db, user)

    assert out["read_only"] is True
    assert out["success"] is True
    assert len(out["logs"]) == 1
    assert out["logs"][0]["automation_name"] == "payment_risk"
