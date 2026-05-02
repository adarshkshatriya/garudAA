import time
import ssl
import socket
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse

from models.models import Monitor, Check, SSLInfo, Alert
from services.alert_service import maybe_send_alert


TIMEOUT = 10
REQUEST_HEADERS = {
    "User-Agent": "SynthMon/1.0 (Synthetic Monitoring)"
}


def check_website(monitor: dict) -> dict:
    url = monitor["url"]
    monitor_id = monitor["id"]
    threshold = monitor.get("threshold") or 3000

    result = {
        "monitor_id": monitor_id,
        "url": url,
        "status": "DOWN",
        "response_time": None,
        "status_code": None,
        "error_msg": None,
    }

    try:
        start = time.monotonic()
        resp = requests.get(
            url,
            timeout=TIMEOUT,
            headers=REQUEST_HEADERS,
            allow_redirects=True,
            verify=True,
        )
        elapsed = round((time.monotonic() - start) * 1000, 1)

        result["response_time"] = elapsed
        result["status_code"] = resp.status_code
        result["status"] = "UP" if resp.status_code < 500 else "DOWN"

        if elapsed > threshold:
            result["slow"] = True

    except requests.exceptions.SSLError as e:
        result["error_msg"] = f"SSL Error: {str(e)[:120]}"
    except requests.exceptions.ConnectionError as e:
        result["error_msg"] = f"Connection Error: {str(e)[:120]}"
    except requests.exceptions.Timeout:
        result["error_msg"] = "Timeout"
    except Exception as e:
        result["error_msg"] = str(e)[:120]

    Check.insert(
        monitor_id=monitor_id,
        status=result["status"],
        response_time=result.get("response_time"),
        status_code=result.get("status_code"),
        error_msg=result.get("error_msg"),
    )

    maybe_send_alert(monitor, result)
    return result


def check_ssl(monitor: dict) -> dict:
    url = monitor["url"]
    monitor_id = monitor["id"]
    parsed = urlparse(url)
    hostname = parsed.hostname

    ssl_result = {
        "monitor_id": monitor_id,
        "hostname": hostname,
        "expiry_date": None,
        "days_remaining": None,
        "issuer": None,
        "error": None,
    }

    if not hostname or parsed.scheme != "https":
        ssl_result["error"] = "Not HTTPS"
        return ssl_result

    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection((hostname, 443), timeout=10),
            server_hostname=hostname,
        ) as ssock:
            cert = ssock.getpeercert()

        expiry_str = cert.get("notAfter", "")
        expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_remaining = (expiry_dt - datetime.now(timezone.utc)).days

        issuer_dict = dict(x[0] for x in cert.get("issuer", []))
        issuer = issuer_dict.get("organizationName", "Unknown")

        ssl_result.update({
            "expiry_date": expiry_dt.strftime("%Y-%m-%d"),
            "days_remaining": days_remaining,
            "issuer": issuer,
        })

        SSLInfo.upsert(monitor_id, ssl_result["expiry_date"], days_remaining, issuer)

        if days_remaining <= 7:
            maybe_send_alert(monitor, {"type": "ssl_critical", "days": days_remaining})
        elif days_remaining <= 15:
            maybe_send_alert(monitor, {"type": "ssl_warning", "days": days_remaining})

    except Exception as e:
        ssl_result["error"] = str(e)[:120]

    return ssl_result


def run_all_checks():
    monitors = Monitor.get_all()
    results = []
    for monitor in monitors:
        result = check_website(monitor)
        results.append(result)
        # SSL check every ~10th run or on first check
        check_ssl(monitor)
    return results
