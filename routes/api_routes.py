from flask import Blueprint, request, jsonify, session
from models.models import Monitor, Check, SSLInfo, Alert
from services.checker import check_website, check_ssl, run_all_checks

api = Blueprint("api", __name__, url_prefix="/api")

def get_user_id():
    return session.get('user', {}).get('id')


# ── Stats ──────────────────────────────────────────────────────────────────────
@api.route("/stats")
def stats():
    try:
        user_id = get_user_id()
        monitors = Monitor.get_all(user_id)
        total = len(monitors)
        up = sum(1 for m in monitors if m.get("last_status") == "UP")
        down = total - up

        global_metrics = Check.get_global_metrics(user_id)
        ssl_data = SSLInfo.get_all(user_id)
        expiring_soon = sum(1 for s in ssl_data if (s.get("days_remaining") or 999) <= 15)

        return jsonify({
            "total_monitors": total,
            "monitors_up": up,
            "monitors_down": down,
            "uptime_pct": global_metrics.get("uptime_pct") or 0,
            "avg_response_time": global_metrics.get("avg_rt") or 0,
            "ssl_expiring_soon": expiring_soon,
            "active_alerts": len(Alert.get_recent(limit=10, user_id=user_id)),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Websites / Monitors ────────────────────────────────────────────────────────
@api.route("/websites", methods=["GET"])
def list_websites():
    try:
        monitors = Monitor.get_all(get_user_id())
        for m in monitors:
            m["uptime_24h"] = Check.get_uptime_percent(m["id"])
            m["avg_rt_24h"] = Check.get_avg_response(m["id"])
        return jsonify(monitors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/websites", methods=["POST"])
def add_website():
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip()
    threshold = int(data.get("threshold") or 3000)
    alert_email = (data.get("alert_email") or "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        monitor_id = Monitor.create(get_user_id(), url, name or url, threshold, alert_email or None)
        monitor = Monitor.get_by_id(monitor_id, get_user_id())
        # Run initial check immediately
        result = check_website(monitor)
        check_ssl(monitor)
        return jsonify({"id": monitor_id, "check": result}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@api.route("/websites/<int:monitor_id>", methods=["DELETE"])
def delete_website(monitor_id):
    try:
        if not Monitor.get_by_id(monitor_id, get_user_id()):
            return jsonify({"error": "Monitor not found or unauthorized"}), 404
        Monitor.delete(monitor_id, get_user_id())
        return jsonify({"deleted": monitor_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/websites/<int:monitor_id>/check", methods=["POST"])
def force_check(monitor_id):
    try:
        monitor = Monitor.get_by_id(monitor_id, get_user_id())
        if not monitor:
            return jsonify({"error": "Monitor not found"}), 404
        result = check_website(monitor)
        ssl_result = check_ssl(monitor)
        return jsonify({"check": result, "ssl": ssl_result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Metrics / Timeseries ───────────────────────────────────────────────────────
@api.route("/metrics")
def metrics():
    try:
        monitor_id = request.args.get("monitor_id", type=int)
        hours = request.args.get("hours", default=24, type=int)
        user_id = get_user_id()

        if monitor_id:
            if not Monitor.get_by_id(monitor_id, user_id):
                return jsonify({"error": "Unauthorized"}), 404
            series = Check.get_timeseries(monitor_id, hours=hours)
        else:
            series = Check.get_global_timeseries(hours=hours, user_id=user_id)

        return jsonify({"series": series, "monitor_id": monitor_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/history/<int:monitor_id>")
def history(monitor_id):
    try:
        if not Monitor.get_by_id(monitor_id, get_user_id()):
            return jsonify({"error": "Unauthorized"}), 404
        limit = request.args.get("limit", default=50, type=int)
        data = Check.get_history(monitor_id, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SSL ────────────────────────────────────────────────────────────────────────
@api.route("/ssl")
def ssl_status():
    try:
        data = SSLInfo.get_all(get_user_id())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Alerts ─────────────────────────────────────────────────────────────────────
@api.route("/alerts")
def list_alerts():
    try:
        limit = request.args.get("limit", default=50, type=int)
        data = Alert.get_recent(limit=limit, user_id=get_user_id())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Manual full-run trigger ────────────────────────────────────────────────────
@api.route("/run-checks", methods=["POST"])
def trigger_checks():
    try:
        monitors = Monitor.get_all(get_user_id())
        results = []
        for monitor in monitors:
            result = check_website(monitor)
            results.append(result)
            check_ssl(monitor)
        return jsonify({"checked": len(results), "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
