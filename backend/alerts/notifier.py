from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.db import models
from backend.forecasting.forecaster import forecast_costs_safe


def _try_send_webhook(*, url: str | None, payload: dict[str, Any]) -> bool:
    if not url:
        return False


def _try_send_email(*, message: str, severity: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or username
    recipient = os.getenv("ALERT_EMAIL_TO")
    if not all((host, username, password, sender, recipient)):
        return False

    email = EmailMessage()
    email["Subject"] = f"[EcoPulse][{severity.upper()}] Alert"
    email["From"] = sender
    email["To"] = recipient
    email.set_content(message)
    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=10) as server:
            server.login(username, password)
            server.send_message(email)
        return True
    except Exception:
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            _ = resp.read()
        return True
    except Exception:
        return False


def send_alert_notifications(*, message: str, severity: str, channel: Optional[str] = None) -> dict[str, bool]:
    """
    Best-effort delivery. If webhook env vars are missing, this is a no-op.
    """
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    teams_url = os.getenv("TEAMS_WEBHOOK_URL")

    # Simple payloads: keep generic for both Slack/Teams incoming webhooks.
    payload = {"text": f"[EcoPulse][{severity.upper()}] {message}"}

    delivered = {}
    if slack_url:
        delivered["slack"] = _try_send_webhook(url=slack_url, payload=payload)
    if teams_url:
        delivered["teams"] = _try_send_webhook(url=teams_url, payload=payload)
    if os.getenv("ALERT_EMAIL_TO"):
        delivered["email"] = _try_send_email(message=message, severity=severity)
    return delivered


def create_alert_row(
    *,
    db: Session,
    org_id: str,
    alert_type: str,
    message: str,
    severity: str,
    channel: Optional[str] = "internal",
) -> models.Alert:
    row = models.Alert(
        org_id=org_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        channel=channel,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _create_alert_once(
    *,
    db: Session,
    org_id: str,
    alert_type: str,
    message: str,
    severity: str,
) -> tuple[models.Alert | None, dict[str, bool]]:
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    existing = db.query(models.Alert).filter(
        models.Alert.org_id == org_id,
        models.Alert.alert_type == alert_type,
        models.Alert.message == message,
        models.Alert.sent_at >= cutoff,
    ).first()
    if existing:
        return None, {}
    row = create_alert_row(
        db=db,
        org_id=org_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        channel="internal",
    )
    return row, send_alert_notifications(message=message, severity=severity, channel="internal")


def check_and_create_alerts(
    *,
    db: Session,
    org_id: str,
    budget_limit_usd: float = 5000.0,
    anomaly_threshold: float = 0.8,
    forecast_days: int = 30,
) -> list[dict[str, Any]]:
    """
    Minimal alert checks aligned with the roadmap:
      - anomaly alerts
      - budget alerts (forecast vs budget_limit_usd)
      - policy violations (recommendations waiting for production approval)
    """
    created: list[dict[str, Any]] = []

    # 1) Anomaly alerts
    top_anomaly = (
        db.query(models.AnomalyFinding)
        .filter(models.AnomalyFinding.org_id == org_id)
        .order_by(models.AnomalyFinding.severity_score.desc())
        .first()
    )
    if top_anomaly and float(top_anomaly.severity_score or 0.0) >= anomaly_threshold:
        msg = (
            f"High anomaly score ({top_anomaly.anomaly_score:.3f}) on {top_anomaly.resource_id} "
            f"(severity={top_anomaly.severity_score:.3f})."
        )
        row, deliveries = _create_alert_once(
            db=db,
            org_id=org_id,
            alert_type="anomaly",
            message=msg,
            severity="critical" if float(top_anomaly.severity_score) >= 0.95 else "warning",
        )
        if row:
            created.append({"id": row.id, "type": row.alert_type, "severity": row.severity, "message": row.message, "deliveries": deliveries})

    # 2) Budget alerts (forecasted spend vs limit)
    result, error = forecast_costs_safe(
        db=db,
        org_id=org_id,
        forecast_days=forecast_days,
    )
    if result and not error:
        total_forecast_cost = sum(float(f.forecasted_cost_usd or 0.0) for f in result.forecasts)
        if total_forecast_cost >= float(budget_limit_usd):
            msg = f"Forecasted cost ${total_forecast_cost:.2f} exceeds budget limit ${budget_limit_usd:.2f}."
            row, deliveries = _create_alert_once(
                db=db,
                org_id=org_id,
                alert_type="budget",
                message=msg,
                severity="critical",
            )
            if row:
                created.append({"id": row.id, "type": row.alert_type, "severity": row.severity, "message": row.message, "deliveries": deliveries})

    # 3) Policy violations (production pending approval)
    pending_approval_count = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.org_id == org_id, models.Recommendation.status == "pending_approval")
        .count()
    )
    if pending_approval_count > 0:
        msg = f"{pending_approval_count} recommendations require production approval (pending_approval)."
        row, deliveries = _create_alert_once(
            db=db,
            org_id=org_id,
            alert_type="policy_violation",
            message=msg,
            severity="warning",
        )
        if row:
            created.append({"id": row.id, "type": row.alert_type, "severity": row.severity, "message": row.message, "deliveries": deliveries})

    return created

