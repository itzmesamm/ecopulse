from unittest.mock import MagicMock, patch

from backend.alerts.notifier import check_and_create_alerts, send_alert_notifications
from backend.db import models


def test_repeated_policy_alert_is_deduplicated(db_session):
    org = models.Organization(name="Alert test")
    db_session.add(org)
    db_session.flush()
    db_session.add(models.Recommendation(
        org_id=org.id,
        title="pending approval",
        summary="needs approval",
        action="review",
        environment="production",
        status="pending_approval",
    ))
    db_session.commit()

    first = check_and_create_alerts(db=db_session, org_id=org.id)
    second = check_and_create_alerts(db=db_session, org_id=org.id)

    assert len(first) == 1
    assert second == []
    assert db_session.query(models.Alert).filter_by(org_id=org.id).count() == 1


def test_email_alert_uses_configured_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_USERNAME", "sender")
    monkeypatch.setenv("SMTP_PASSWORD", "test-only")
    monkeypatch.setenv("SMTP_FROM", "alerts@example.test")
    monkeypatch.setenv("ALERT_EMAIL_TO", "ops@example.test")

    with patch("backend.alerts.notifier.smtplib.SMTP_SSL") as smtp:
        smtp.return_value.__enter__.return_value = MagicMock()
        results = send_alert_notifications(message="budget threshold reached", severity="critical")

    assert results == {"email": True}
    smtp.assert_called_once()