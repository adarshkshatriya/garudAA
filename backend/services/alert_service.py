import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from models.models import Alert

COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", 30))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")


def _is_on_cooldown(monitor_id: int, alert_type: str) -> bool:
    last = Alert.get_last_alert_time(monitor_id, alert_type)
    if not last:
        return False
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        diff = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        return diff < COOLDOWN_MINUTES
    except Exception:
        return False


def _send_email(to: str, subject: str, html_body: str):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[ALERT] Email skipped (no SMTP config): {subject}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to], msg.as_string())
        print(f"[ALERT] Email sent to {to}: {subject}")
        return True
    except Exception as e:
        print(f"[ALERT] Email failed: {e}")
        return False


def maybe_send_alert(monitor: dict, result: dict):
    monitor_id = monitor["id"]
    monitor_name = monitor.get("name") or monitor["url"]
    to_email = monitor.get("alert_email") or os.environ.get("DEFAULT_ALERT_EMAIL", "")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    alert_type = result.get("type")

    # Website down
    if result.get("status") == "DOWN" and not alert_type:
        if _is_on_cooldown(monitor_id, "DOWN"):
            return
        message = f"{monitor_name} is DOWN. Error: {result.get('error_msg', 'Unknown')}"
        Alert.insert(monitor_id, "DOWN", message)
        if to_email:
            subject = f"🔴 ALERT: {monitor_name} is DOWN"
            html = _down_email_html(monitor_name, monitor["url"], result, now)
            _send_email(to_email, subject, html)

    # Slow response
    elif result.get("slow") and result.get("status") == "UP":
        if _is_on_cooldown(monitor_id, "SLOW"):
            return
        threshold = monitor.get("threshold", 3000)
        message = f"{monitor_name} is slow: {result.get('response_time')}ms (threshold: {threshold}ms)"
        Alert.insert(monitor_id, "SLOW", message)
        if to_email:
            subject = f"🟡 ALERT: {monitor_name} slow response"
            html = _slow_email_html(monitor_name, monitor["url"], result, threshold, now)
            _send_email(to_email, subject, html)

    # SSL Critical
    elif alert_type == "ssl_critical":
        if _is_on_cooldown(monitor_id, "SSL_CRITICAL"):
            return
        days = result.get("days", "?")
        message = f"SSL certificate for {monitor_name} expires in {days} days!"
        Alert.insert(monitor_id, "SSL_CRITICAL", message)
        if to_email:
            subject = f"🔴 SSL EXPIRING: {monitor_name} ({days} days)"
            html = _ssl_email_html(monitor_name, monitor["url"], days, "critical", now)
            _send_email(to_email, subject, html)

    # SSL Warning
    elif alert_type == "ssl_warning":
        if _is_on_cooldown(monitor_id, "SSL_WARNING"):
            return
        days = result.get("days", "?")
        message = f"SSL certificate for {monitor_name} expires in {days} days."
        Alert.insert(monitor_id, "SSL_WARNING", message)
        if to_email:
            subject = f"🟡 SSL WARNING: {monitor_name} ({days} days)"
            html = _ssl_email_html(monitor_name, monitor["url"], days, "warning", now)
            _send_email(to_email, subject, html)


def _down_email_html(name, url, result, now):
    return f"""
<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:32px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:12px;padding:32px;border:1px solid #334155">
  <h2 style="color:#f87171;margin:0 0 16px">🔴 Monitor Alert: Site Down</h2>
  <p><strong>Monitor:</strong> {name}</p>
  <p><strong>URL:</strong> <a href="{url}" style="color:#60a5fa">{url}</a></p>
  <p><strong>Status:</strong> <span style="color:#f87171">DOWN</span></p>
  <p><strong>Error:</strong> {result.get("error_msg") or "Unknown"}</p>
  <p><strong>Time:</strong> {now}</p>
  <hr style="border-color:#334155;margin:24px 0">
  <p style="color:#64748b;font-size:12px">SynthMon Synthetic Monitoring Platform</p>
</div></body></html>"""


def _slow_email_html(name, url, result, threshold, now):
    return f"""
<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:32px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:12px;padding:32px;border:1px solid #334155">
  <h2 style="color:#fbbf24;margin:0 0 16px">🟡 Monitor Alert: Slow Response</h2>
  <p><strong>Monitor:</strong> {name}</p>
  <p><strong>URL:</strong> <a href="{url}" style="color:#60a5fa">{url}</a></p>
  <p><strong>Response Time:</strong> {result.get("response_time")}ms</p>
  <p><strong>Threshold:</strong> {threshold}ms</p>
  <p><strong>Time:</strong> {now}</p>
  <hr style="border-color:#334155;margin:24px 0">
  <p style="color:#64748b;font-size:12px">SynthMon Synthetic Monitoring Platform</p>
</div></body></html>"""


def _ssl_email_html(name, url, days, severity, now):
    color = "#f87171" if severity == "critical" else "#fbbf24"
    return f"""
<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:32px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:12px;padding:32px;border:1px solid #334155">
  <h2 style="color:{color};margin:0 0 16px">🔐 SSL Certificate Expiring</h2>
  <p><strong>Monitor:</strong> {name}</p>
  <p><strong>URL:</strong> <a href="{url}" style="color:#60a5fa">{url}</a></p>
  <p><strong>Days Remaining:</strong> <span style="color:{color}">{days} days</span></p>
  <p><strong>Time:</strong> {now}</p>
  <hr style="border-color:#334155;margin:24px 0">
  <p style="color:#64748b;font-size:12px">SynthMon Synthetic Monitoring Platform</p>
</div></body></html>"""
