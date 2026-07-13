import json
import os
import atexit
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Mapping

import requests

DEFAULT_ALERT_TIMEOUT_SECONDS = 60.0
_NOTIFICATION_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="safyra-alert")
atexit.register(_NOTIFICATION_EXECUTOR.shutdown, wait=False, cancel_futures=True)


def _notifications_enabled() -> bool:
    return os.getenv("ALERT_NOTIFICATION_ENABLED", "false").lower() in {"1", "true", "yes"}


def _request_timeout_seconds() -> float:
    raw_value = os.getenv("N8N_ALERT_TIMEOUT_SECONDS", str(int(DEFAULT_ALERT_TIMEOUT_SECONDS)))
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return DEFAULT_ALERT_TIMEOUT_SECONDS


def _post_alert_notification(payload: Mapping[str, Any]) -> dict[str, Any]:
    webhook_url = os.getenv("N8N_ALERT_WEBHOOK_URL", "").strip()
    webhook_token = os.getenv("N8N_ALERT_WEBHOOK_TOKEN", "").strip()

    print(f"[WEBHOOK] Intentando enviar alerta a: {webhook_url}")

    if not _notifications_enabled() or not webhook_url:
        print("[WEBHOOK] Envío cancelado: Notificaciones deshabilitadas o URL vacía.")
        return {"sent": False, "reason": "notifications_disabled"}

    headers = {
        "Content-Type": "application/json",
        "X-Safyra-Token": webhook_token,
    }

    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=_request_timeout_seconds(),
        )
        print(f"[WEBHOOK] Respuesta de n8n: Status={response.status_code}, Ok={response.ok}")
        if not response.ok:
            print(f"[WEBHOOK] Detalle de error: {response.text[:200]}")
        return {
            "sent": response.ok,
            "status_code": response.status_code,
            "response": response.text[:500],
            "reason": "" if response.ok else response.reason,
        }
    except requests.RequestException as exc:
        print(f"[WEBHOOK] EXCEPCIÓN al enviar POST: {str(exc)}")
        return {"sent": False, "reason": str(exc)}



def send_alert_notification(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _post_alert_notification(payload)


def queue_alert_notification(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not _notifications_enabled() or not os.getenv("N8N_ALERT_WEBHOOK_URL", "").strip():
        return {"queued": False, "reason": "notifications_disabled"}

    future: Future[dict[str, Any]] = _NOTIFICATION_EXECUTOR.submit(_post_alert_notification, dict(payload))
    return {"queued": True, "done": future.done()}


def _build_and_send_alert(payload_factory: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
    payload = payload_factory()
    return _post_alert_notification(payload)


def queue_alert_notification_factory(payload_factory: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
    if not _notifications_enabled() or not os.getenv("N8N_ALERT_WEBHOOK_URL", "").strip():
        return {"queued": False, "reason": "notifications_disabled"}

    future: Future[dict[str, Any]] = _NOTIFICATION_EXECUTOR.submit(_build_and_send_alert, payload_factory)
    return {"queued": True, "done": future.done()}
