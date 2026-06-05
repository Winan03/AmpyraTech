# app/routers/data_api.py
from fastapi import APIRouter, HTTPException, Response, Depends, Header, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from app.db.firebase import (
    get_current_data, 
    get_history_data, 
    check_connection,
    update_sensor_threshold,
    export_history_csv,
    export_history_excel,
    get_alert_history,
    LAB_ROOM_ID,
    LAB_ROOM_NAME,
    get_alert_email_contacts,
    list_room_schedules,
    record_iot_reading,
    save_room_schedule,
    update_room_schedule,
)
from app.routers.auth_api import require_roles
from app.routers.auth_api import UserInDB
from app.models.data import ThresholdUpdate
from app.services.notifications import queue_alert_notification_factory, send_alert_notification
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any
import html
import io
import os
import re
import secrets
import uuid

ADMIN_ROLE = "admin"
AUDITOR_ROLE = "auditor"

CURRENT_DATA_ROLES = (ADMIN_ROLE, AUDITOR_ROLE)
ALERT_ROLES = (ADMIN_ROLE, AUDITOR_ROLE)
REPORT_ROLES = (ADMIN_ROLE, AUDITOR_ROLE)
ADMIN_ROLES = (ADMIN_ROLE,)
SCHEDULE_READ_ROLES = (ADMIN_ROLE, AUDITOR_ROLE)
SCHEDULE_WRITE_ROLES = (AUDITOR_ROLE,)
WEEK_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
SCHEDULE_KINDS = {"class", "no_class"}
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
VISIBLE_LABEL_PATTERN = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{3,80}$")
SCHOOL_START_TIME = "08:00"
SCHOOL_END_TIME = "14:30"
IOT_SENSOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,50}$")
_alert_notification_cache: dict[str, float] = {}

router = APIRouter(
    prefix="/data", 
    tags=["data"],
)


class SchedulePayload(BaseModel):
    room_id: str = Field(default=LAB_ROOM_ID, min_length=3, max_length=50)
    kind: str = Field(default="class", min_length=5, max_length=8)
    day_of_week: str = Field(..., min_length=6, max_length=9)
    start_time: str = Field(..., min_length=5, max_length=5)
    end_time: str = Field(..., min_length=5, max_length=5)
    label: str = Field(default="Clase de computación", min_length=3, max_length=80)
    valid_from: str | None = Field(default=None, max_length=10)
    valid_to: str | None = Field(default=None, max_length=10)
    status: str = Field(default="activo", min_length=6, max_length=8)
    source_schedule_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=240)


class SchedulePatch(BaseModel):
    kind: str | None = Field(default=None, min_length=5, max_length=8)
    day_of_week: str | None = Field(default=None, min_length=6, max_length=9)
    start_time: str | None = Field(default=None, min_length=5, max_length=5)
    end_time: str | None = Field(default=None, min_length=5, max_length=5)
    label: str | None = Field(default=None, min_length=3, max_length=80)
    valid_from: str | None = Field(default=None, max_length=10)
    valid_to: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, min_length=6, max_length=8)
    source_schedule_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=240)


class TestAlertPayload(BaseModel):
    room_id: str = Field(default=LAB_ROOM_ID)
    room_name: str = Field(default=LAB_ROOM_NAME)
    event_type: str = Field(default="test_alert")
    message: str = Field(default="Prueba de integracion SafyraShield")


class IotReadingPayload(BaseModel):
    sensor_id: str = Field(..., min_length=3, max_length=50)
    irms: float = Field(..., ge=0, le=100)
    potencia: float | None = Field(default=None, ge=0, le=50000)
    voltage: float = Field(default=220.0, gt=0, le=260)
    circuito: str | None = Field(default=None, max_length=50)


def _validate_time(value: str, field_name: str) -> str:
    if not TIME_PATTERN.fullmatch(value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} debe usar formato HH:MM")
    return value


def _time_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _normalize_label(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_valid_visible_label(value: str) -> bool:
    cleaned_value = _normalize_label(value)
    if len(cleaned_value) < 3 or len(cleaned_value) > 80:
        return False
    return all(character.isalpha() or character.isspace() for character in cleaned_value)


def _validate_schedule_values(values: dict[str, object], *, existing_schedule: dict[str, object] | None = None) -> dict[str, object]:
    if "kind" in values and values["kind"] is not None:
        schedule_kind = str(values["kind"]).strip().lower()
        if schedule_kind not in SCHEDULE_KINDS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tipo de bloque invalido")
        values["kind"] = schedule_kind

    if "day_of_week" in values and values["day_of_week"] is not None:
        day = str(values["day_of_week"]).strip().lower()
        if day not in WEEK_DAYS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dia de semana invalido")
        values["day_of_week"] = day

    for field_name in ("start_time", "end_time"):
        if field_name in values and values[field_name] is not None:
            values[field_name] = _validate_time(str(values[field_name]), field_name)

    if values.get("start_time") and values.get("end_time"):
        start_minutes = _time_to_minutes(str(values["start_time"]))
        end_minutes = _time_to_minutes(str(values["end_time"]))
        school_start_minutes = _time_to_minutes(SCHOOL_START_TIME)
        school_end_minutes = _time_to_minutes(SCHOOL_END_TIME)
        if start_minutes >= end_minutes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La hora inicial debe ser menor que la hora final")
        if start_minutes < school_start_minutes or end_minutes > school_end_minutes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"El horario debe ubicarse entre {SCHOOL_START_TIME} y {SCHOOL_END_TIME}")

    if "label" in values and values["label"] is not None:
        label = _normalize_label(values["label"])
        if not _is_valid_visible_label(label):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El nombre visible debe contener solo letras y espacios")
        values["label"] = label

    for field_name in ("valid_from", "valid_to"):
        if field_name in values and values[field_name] is not None:
            try:
                datetime.strptime(str(values[field_name]), "%Y-%m-%d")
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} debe usar formato YYYY-MM-DD") from exc

    if values.get("valid_from") and values.get("valid_to") and str(values["valid_from"]) > str(values["valid_to"]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha inicial debe ser menor o igual que la fecha final")

    if values.get("kind") == "no_class":
        values["start_time"] = SCHOOL_START_TIME
        values["end_time"] = SCHOOL_END_TIME
        if values.get("valid_from") != values.get("valid_to"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un dia sin clase debe usar la misma fecha en inicio y fin")

    if values.get("valid_from"):
        today_text = date.today().isoformat()
        existing_valid_from = str(existing_schedule.get("valid_from") or "") if existing_schedule else ""
        if not existing_schedule or str(values["valid_from"]) != existing_valid_from:
            if str(values["valid_from"]) < today_text:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vigencia no puede iniciar en una fecha pasada")

    if values.get("valid_to"):
        today_text = date.today().isoformat()
        existing_valid_to = str(existing_schedule.get("valid_to") or "") if existing_schedule else ""
        if not existing_schedule or str(values["valid_to"]) != existing_valid_to:
            if str(values["valid_to"]) < today_text:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La vigencia no puede cerrar en una fecha pasada")

    if "status" in values and values["status"] is not None:
        schedule_status = str(values["status"]).strip().lower()
        if schedule_status not in {"activo", "inactivo"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Estado de horario invalido")
        values["status"] = schedule_status

    if values.get("kind") == "no_class" and (not values.get("valid_from") or not values.get("valid_to")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un dia sin clase requiere vigencia desde y hasta")

    if "source_schedule_id" in values and values["source_schedule_id"] is not None:
        values["source_schedule_id"] = str(values["source_schedule_id"]).strip() or None

    if "notes" in values and values["notes"] is not None:
        values["notes"] = _normalize_label(values["notes"])

    return values


def _model_to_dict(model: BaseModel) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def _schedule_fingerprint(schedule: dict[str, object]) -> tuple[str, ...]:
    return (
        str(schedule.get("room_id") or LAB_ROOM_ID).strip().lower(),
        str(schedule.get("kind") or "class").strip().lower(),
        str(schedule.get("day_of_week") or "").strip().lower(),
        str(schedule.get("start_time") or "").strip(),
        str(schedule.get("end_time") or "").strip(),
        str(schedule.get("valid_from") or "").strip(),
        str(schedule.get("valid_to") or "").strip(),
        str(schedule.get("source_schedule_id") or "").strip(),
    )


def _find_schedule_duplicate(room_id: str, candidate: dict[str, object], *, exclude_id: str | None = None) -> dict[str, object] | None:
    existing_schedules = list_room_schedules(room_id)
    candidate_fingerprint = _schedule_fingerprint(candidate)
    for schedule in existing_schedules:
        if exclude_id and str(schedule.get("id") or "") == exclude_id:
            continue
        if _schedule_fingerprint(schedule) == candidate_fingerprint:
            return schedule
    return None


def _notification_cooldown_seconds() -> float:
    raw_value = os.getenv("ALERT_NOTIFICATION_COOLDOWN_SECONDS", "300")
    try:
        return float(raw_value)
    except ValueError:
        return 300.0


def _require_iot_token(x_safyra_iot_token: str | None = Header(default=None, alias="X-Safyra-Iot-Token")) -> None:
    expected_token = os.getenv("SAFYRA_IOT_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Token IoT no configurado")
    if not x_safyra_iot_token or not secrets.compare_digest(x_safyra_iot_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token IoT invalido")


def _schedule_status_code(schedule: object) -> str:
    if not isinstance(schedule, Mapping):
        return "no_especificado"
    if schedule.get("is_scheduled_now"):
        return "clase_activa"
    if schedule.get("blocked_by_no_class"):
        return "dia_sin_clase"
    if schedule.get("label") == "Fuera de horario":
        return "fuera_de_horario"
    return "sin_horario_activo"


def _alert_copy(event_type: str) -> dict[str, str]:
    if event_type == "overload":
        return {
            "severity": "critical",
            "message": "Sobrecarga detectada en un ramal del laboratorio.",
            "reason": "La corriente medida supero el umbral permitido.",
            "recommended_action": "Revisar los equipos conectados al ramal indicado y reducir la carga electrica.",
        }
    if event_type == "out_of_schedule_consumption":
        return {
            "severity": "warning",
            "message": "Consumo detectado fuera del horario autorizado.",
            "reason": "El laboratorio registra corriente cuando no existe una clase activa.",
            "recommended_action": "Apagar o desconectar los equipos del ramal indicado, o registrar la clase si el uso estaba autorizado.",
        }
    return {
        "severity": "info",
        "message": "Evento electrico detectado.",
        "reason": "Evento generado por SafyraShield.",
        "recommended_action": "Revisar el laboratorio.",
    }


def _alert_type_label(event_type: str) -> str:
    if event_type == "overload":
        return "Sobrecarga electrica"
    if event_type == "out_of_schedule_consumption":
        return "Consumo fuera de horario"
    return "Alerta electrica"


def _severity_label(severity: str) -> str:
    labels = {
        "critical": "Critica",
        "warning": "Advertencia",
        "info": "Informativa",
    }
    return labels.get(severity, "Informativa")


def _schedule_status_label(schedule_status: str) -> str:
    labels = {
        "clase_activa": "Clase activa",
        "dia_sin_clase": "Dia sin clase",
        "fuera_de_horario": "Fuera de horario",
        "sin_horario_activo": "Sin horario activo",
        "prueba_manual": "Prueba manual",
        "no_especificado": "No especificado",
    }
    return labels.get(schedule_status, "No especificado")


def _valid_iso_timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) < 16:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _safe_timestamp(value: object, fallback: datetime) -> str:
    if _valid_iso_timestamp(value):
        return str(value)
    return fallback.isoformat()


def _display_timestamp(value: str) -> str:
    if not _valid_iso_timestamp(value):
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _format_measure(value: object, decimals: int = 2) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def _html_row(label: str, value: object) -> str:
    return f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value))}</p>"


def _notification_reference(payload: Mapping[str, Any]) -> tuple[str, str]:
    alert_type = str(payload.get("alert_type") or "")
    threshold = payload.get("threshold") if isinstance(payload.get("threshold"), Mapping) else {}
    threshold_current = _format_measure(threshold.get("corriente") if isinstance(threshold, Mapping) else None)
    threshold_power = _format_measure(threshold.get("potencia") if isinstance(threshold, Mapping) else None, 0)
    schedule_min_current = _format_measure(payload.get("schedule_min_current_a"), 3)
    if alert_type == "out_of_schedule_consumption":
        return "Referencia de agenda", f"Consumo relevante >= {schedule_min_current} A fuera de horario"
    return "Umbral", f"{threshold_current} A / {threshold_power} W"


def _recipient_display_name(recipient: Mapping[str, Any] | None) -> str:
    if not isinstance(recipient, Mapping):
        return "usuario autorizado"
    for field_name in ("name", "full_name", "username", "email"):
        value = str(recipient.get(field_name) or "").strip()
        if value:
            return value.split("@", 1)[0] if field_name == "email" else value
    return "usuario autorizado"


def _notification_subject(payload: Mapping[str, Any]) -> str:
    severity_label = str(payload.get("severity_label") or "Informativa").upper()
    alert_label = str(payload.get("alert_type_label") or "Alerta electrica")
    room_name = str(payload.get("room_name") or LAB_ROOM_NAME)
    room_id = str(payload.get("room_id") or LAB_ROOM_ID)
    return f"[SafyraShield] {severity_label}: {alert_label} - {room_name} ({room_id})"


def _build_notification_content(
    payload: Mapping[str, Any],
    recipient: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    alert_type = str(payload.get("alert_type") or "")
    alert_label = str(payload.get("alert_type_label") or "Alerta electrica")
    severity = str(payload.get("severity") or "info")
    severity_label = str(payload.get("severity_label") or "Informativa")
    room_name = str(payload.get("room_name") or LAB_ROOM_NAME)
    room_id = str(payload.get("room_id") or LAB_ROOM_ID)
    circuito = str(payload.get("circuito") or room_id)
    schedule_label = str(payload.get("schedule_status_label") or "No especificado")
    detected_at_display = str(payload.get("detected_at_display") or payload.get("detected_at") or "")
    irms = _format_measure(payload.get("irms"))
    potencia = _format_measure(payload.get("potencia"), 0)
    threshold = payload.get("threshold") if isinstance(payload.get("threshold"), Mapping) else {}
    device = payload.get("device") if isinstance(payload.get("device"), Mapping) else {}
    device_type = str(payload.get("device_type") or device.get("type") or "No clasificado")
    device_description = str(payload.get("device_description") or device.get("description") or "Sin detalle del estado electrico.")
    threshold_current = _format_measure(threshold.get("corriente") if isinstance(threshold, Mapping) else None)
    threshold_power = _format_measure(threshold.get("potencia") if isinstance(threshold, Mapping) else None, 0)
    reference_label, reference_value = _notification_reference(payload)
    recipient_name = _recipient_display_name(recipient)
    intro = (
        "ha detectado una anomalia electrica que requiere su intervencion inmediata."
        if severity == "critical"
        else "ha detectado una anomalia electrica que requiere verificacion operativa."
    )
    summary_title = "Resumen de la emergencia" if severity == "critical" else "Resumen de la alerta"
    action_title = "Accion inmediata requerida" if severity == "critical" else "Accion operativa requerida"
    current_detail = (
        f"{irms} A (umbral: {threshold_current} A)"
        if alert_type == "overload"
        else f"{irms} A ({reference_value})"
    )
    power_detail = (
        f"{potencia} W (limite seguro: {threshold_power} W)"
        if alert_type == "overload"
        else f"{potencia} W"
    )

    subject = _notification_subject(payload)
    html_content = (
        "<div style='font-family:Arial,sans-serif;color:#0f172a;line-height:1.5;max-width:720px'>"
        "<h2 style='margin:0 0 12px;color:#0f172a'>SafyraShield IoT</h2>"
        f"<p>Estimado(a) <strong>{html.escape(recipient_name)}</strong>,</p>"
        f"<p>El sistema SafyraShield {html.escape(intro)}</p>"
        "<div style='border:1px solid #cbd5e1;border-radius:8px;padding:14px;margin:16px 0'>"
        f"<h3 style='margin:0 0 10px;color:#0f172a'>{html.escape(summary_title)}</h3>"
        + _html_row("Incidente", f"{alert_label} (Nivel {severity_label})")
        + _html_row("Ubicacion", f"{room_name} ({room_id})")
        + _html_row("Ramal monitoreado", circuito)
        + _html_row("Estado detectado", device_type)
        + _html_row("Estado de agenda", schedule_label)
        + "</div>"
        "<div style='background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:14px;margin:16px 0'>"
        f"<h3 style='margin:0 0 10px;color:#9a3412'>{html.escape(action_title)}</h3>"
        f"<p style='margin:0'>{html.escape(str(payload.get('recommended_action') or 'Revisar el laboratorio.'))}</p>"
        + "</div>"
        "<div style='border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:16px 0'>"
        "<h3 style='margin:0 0 10px;color:#0f172a'>Reporte tecnico de telemetria</h3>"
        + _html_row("Corriente medida", current_detail)
        + _html_row("Potencia estimada", power_detail)
        + _html_row(reference_label, reference_value)
        + _html_row("Detalle del estado", device_description)
        + _html_row("Motivo", payload.get("reason") or "Evento generado por SafyraShield")
        + _html_row("Fecha y hora", detected_at_display)
        + _html_row("ID de auditoria", payload.get("alert_id") or "-")
        + "</div>"
        "<hr style='border:none;border-top:1px solid #cbd5e1;margin:18px 0'>"
        "<small>Mensaje automatico. Usted recibe esta alerta operativa porque su cuenta se encuentra activa "
        "y ha aceptado los Terminos y Condiciones vigentes del sistema SafyraShield. No responder.</small>"
        "</div>"
    )
    whatsapp_text = (
        f"SafyraShield - {severity_label.upper()}\n"
        f"Incidente: {alert_label}\n"
        f"Lugar: {room_name} ({room_id})\n"
        f"Ramal: {circuito}\n"
        f"Estado: {device_type}\n"
        f"Accion: {payload.get('recommended_action') or 'Revisar el laboratorio.'}\n"
        f"Lectura: {irms} A / {potencia} W\n"
        f"{reference_label}: {reference_value}\n"
        f"Agenda: {schedule_label}\n"
        f"Hora: {detected_at_display}\n"
        f"ID: {payload.get('alert_id') or '-'}"
    )
    return {
        "email_subject": subject,
        "email_html": html_content,
        "whatsapp_text": whatsapp_text,
    }


def _build_email_notifications(
    payload: Mapping[str, Any],
    recipients: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    for recipient in recipients:
        email = str(recipient.get("email") or "").strip()
        if not email or "@" not in email:
            continue
        content = _build_notification_content(payload, recipient)
        notifications.append(
            {
                "to": {
                    "email": email,
                    "name": _recipient_display_name(recipient),
                },
                "subject": content["email_subject"],
                "htmlContent": content["email_html"],
            }
        )
    return notifications


def _build_alert_notification_payload(
    sensor: Mapping[str, Any],
    event_type: str,
    detected_at: datetime | None = None,
) -> dict[str, Any]:
    now = detected_at or datetime.now(timezone.utc)
    copy = _alert_copy(event_type)
    room_id = str(sensor.get("id") or LAB_ROOM_ID)
    threshold = sensor.get("threshold") if isinstance(sensor.get("threshold"), Mapping) else {}
    schedule = sensor.get("schedule") if isinstance(sensor.get("schedule"), Mapping) else {}
    device = sensor.get("device") if isinstance(sensor.get("device"), Mapping) else {}
    detected_at_value = _safe_timestamp(sensor.get("timestamp"), now)
    schedule_status = _schedule_status_code(schedule)

    email_contacts = get_alert_email_contacts()
    payload: dict[str, Any] = {
        "source": "SafyraShield",
        "alert_id": f"{room_id}-{event_type}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "alert_type": event_type,
        "alert_type_label": _alert_type_label(event_type),
        "event_type": event_type,
        "severity": copy["severity"],
        "severity_label": _severity_label(copy["severity"]),
        "room_id": room_id,
        "room_name": sensor.get("room_name") or LAB_ROOM_NAME,
        "circuito": sensor.get("circuito") or room_id,
        "message": copy["message"],
        "reason": copy["reason"],
        "recommended_action": copy["recommended_action"],
        "irms": sensor.get("irms"),
        "potencia": sensor.get("potencia"),
        "threshold": dict(threshold),
        "device": dict(device),
        "device_type": device.get("type"),
        "device_description": device.get("description"),
        "schedule_min_current_a": schedule.get("min_current_a"),
        "schedule_status": schedule_status,
        "schedule_status_label": _schedule_status_label(schedule_status),
        "detected_at": detected_at_value,
        "detected_at_display": _display_timestamp(detected_at_value),
        "detected_at_utc": sensor.get("timestamp_utc") or now.isoformat(),
        "created_at": now.isoformat(),
        "email_recipients": [contact["email"] for contact in email_contacts],
    }
    payload["notification"] = _build_notification_content(payload)
    payload["email_notifications"] = _build_email_notifications(payload, email_contacts)
    return payload


def _event_type_for_sensor(sensor: Mapping[str, Any]) -> str:
    if sensor.get("is_overload"):
        return "overload"
    if sensor.get("is_out_of_schedule"):
        return "out_of_schedule_consumption"
    return ""


def _queue_sensor_alert(sensor: Mapping[str, Any]) -> dict[str, Any]:
    event_type = _event_type_for_sensor(sensor)
    if not event_type:
        return {"queued": False, "reason": "no_alert"}

    current_timestamp = datetime.now(timezone.utc).timestamp()
    cooldown = _notification_cooldown_seconds()
    cache_key = f"{sensor.get('id')}:{event_type}"
    last_sent = _alert_notification_cache.get(cache_key, 0)
    if current_timestamp - last_sent < cooldown:
        return {"queued": False, "reason": "cooldown"}

    sensor_snapshot = dict(sensor)
    queue_result = queue_alert_notification_factory(
        lambda: _build_alert_notification_payload(sensor_snapshot, event_type)
    )
    if queue_result.get("queued"):
        _alert_notification_cache[cache_key] = current_timestamp
    return {**queue_result, "event_type": event_type}


@router.post("/iot/readings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(_require_iot_token)])
async def ingest_iot_reading(reading: IotReadingPayload):
    sensor_id = reading.sensor_id.strip()
    if not IOT_SENSOR_ID_PATTERN.fullmatch(sensor_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sensor_id invalido")

    try:
        sensor = await run_in_threadpool(
            record_iot_reading,
            sensor_id=sensor_id,
            irms=reading.irms,
            potencia=reading.potencia,
            voltage=reading.voltage,
            circuito=reading.circuito,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al registrar lectura IoT: {exc}") from exc

    notification = _queue_sensor_alert(sensor)
    return {
        "success": True,
        "sensor": sensor,
        "notification": {
            "queued": bool(notification.get("queued")),
            "reason": notification.get("reason", ""),
        },
    }

@router.get("/current", dependencies=[Depends(require_roles(*CURRENT_DATA_ROLES))])
async def read_current_data():
    """
    Endpoint para obtener datos actuales con detección de dispositivos
    (Protegido por autenticación)
    """
    result = await run_in_threadpool(get_current_data)
    return result

@router.get("/history/{sensor_id}", dependencies=[Depends(require_roles(*REPORT_ROLES))])
async def read_history_data(
    sensor_id: str,
    limit: int = 20,
    start_date: str = None, # (HU-010)
    end_date: str = None   # (HU-010)
):
    """
    Endpoint para obtener el historial con filtros de fecha (HU-010)
    (Protegido por autenticación)
    """
    history = await run_in_threadpool(get_history_data, sensor_id, limit, start_date, end_date)
    return {
        "sensor_id": sensor_id,
        "data": history,
        "count": len(history)
    }

# ======================================================================
# ¡NUEVO ENDPOINT DE ALERTAS!
# ======================================================================
@router.get("/alerts", dependencies=[Depends(require_roles(*ALERT_ROLES))])
async def read_alert_history(
    start_date: str = None,
    end_date: str = None
):
    """
    Endpoint para obtener SÓLO el historial de alertas (sobrecargas)
    (Protegido por autenticación)
    """
    alerts = await run_in_threadpool(get_alert_history, start_date, end_date)
    return {
        "data": alerts,
        "count": len(alerts)
    }
# ======================================================================

@router.get("/connection", dependencies=[Depends(require_roles(*CURRENT_DATA_ROLES))])
async def check_connection_status():
    """
    Endpoint para verificar el estado de la conexión
    (Protegido por autenticación)
    """
    is_connected = check_connection()
    return {
        "connected": is_connected,
        "message": "Sistema operativo" if is_connected else "Sistema desconectado"
    }


@router.get("/schedule", dependencies=[Depends(require_roles(*SCHEDULE_READ_ROLES))])
async def read_room_schedule(room_id: str | None = None):
    schedules = list_room_schedules(room_id)
    return {
        "room_id": room_id or "all",
        "data": schedules,
        "count": len(schedules),
    }


@router.post("/schedule", status_code=status.HTTP_201_CREATED)
async def create_room_schedule(
    schedule_data: SchedulePayload,
    current_user: UserInDB = Depends(require_roles(*SCHEDULE_WRITE_ROLES)),
):
    payload = _validate_schedule_values(_model_to_dict(schedule_data))
    duplicate = _find_schedule_duplicate(str(payload["room_id"]), payload)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un bloque con el mismo horario y vigencia")

    schedule_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    record = {
        **payload,
        "id": schedule_id,
        "created_at": now,
        "created_by": current_user.username,
        "updated_at": now,
        "updated_by": current_user.username,
    }
    saved_record = save_room_schedule(str(payload["room_id"]), schedule_id, record)
    return {"success": True, "schedule": saved_record}


@router.patch("/schedule/{room_id}/{schedule_id}")
async def patch_room_schedule(
    room_id: str,
    schedule_id: str,
    schedule_data: SchedulePatch,
    current_user: UserInDB = Depends(require_roles(*SCHEDULE_WRITE_ROLES)),
):
    payload = _model_to_dict(schedule_data)
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No hay cambios para aplicar")

    current_schedules = list_room_schedules(room_id)
    current_record = next((item for item in current_schedules if str(item.get("id") or "") == schedule_id), None)
    if not isinstance(current_record, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado")

    merged_record = {**current_record, **payload}
    validated_record = _validate_schedule_values(merged_record, existing_schedule=current_record)
    duplicate = _find_schedule_duplicate(room_id, validated_record, exclude_id=schedule_id)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un bloque con el mismo horario y vigencia")

    payload = _validate_schedule_values(payload, existing_schedule=current_record)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user.username
    try:
        updated_record = update_room_schedule(room_id, schedule_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado") from exc
    return {"success": True, "schedule": updated_record}


@router.post("/integrations/n8n/test-alert", dependencies=[Depends(require_roles(*ADMIN_ROLES))])
async def send_n8n_test_alert(alert_data: TestAlertPayload):
    now = datetime.now(timezone.utc)
    email_contacts = get_alert_email_contacts()
    payload = {
        "source": "SafyraShield",
        "alert_id": f"{alert_data.room_id}-{alert_data.event_type}-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "alert_type": alert_data.event_type,
        "alert_type_label": _alert_type_label(alert_data.event_type),
        "event_type": alert_data.event_type,
        "severity": "info",
        "severity_label": _severity_label("info"),
        "room_id": alert_data.room_id,
        "room_name": alert_data.room_name,
        "message": alert_data.message,
        "reason": "Prueba manual de integracion.",
        "recommended_action": "Validar recepcion de correo y WhatsApp.",
        "threshold": {},
        "schedule_status": "prueba_manual",
        "schedule_status_label": _schedule_status_label("prueba_manual"),
        "detected_at": now.isoformat(),
        "detected_at_display": _display_timestamp(now.isoformat()),
        "created_at": now.isoformat(),
        "email_recipients": [contact["email"] for contact in email_contacts],
    }
    payload["notification"] = _build_notification_content(payload)
    payload["email_notifications"] = _build_email_notifications(payload, email_contacts)
    result = send_alert_notification(payload)
    return {"success": bool(result.get("sent")), "notification": result, "payload": payload}

@router.put("/threshold/{sensor_id}", dependencies=[Depends(require_roles(*ADMIN_ROLES))])
async def update_threshold(sensor_id: str, threshold: ThresholdUpdate):
    """
    Actualizar umbral de un sensor específico (HU-005)
    (Protegido por autenticación)
    """
    success = update_sensor_threshold(
        sensor_id, 
        threshold.corriente, 
        threshold.potencia
    )
    
    if success:
        return {
            "success": True,
            "message": f"Umbral actualizado para {sensor_id}",
            "threshold": {
                "corriente": threshold.corriente,
                "potencia": threshold.potencia
            }
        }
    else:
        raise HTTPException(status_code=500, detail="Error al actualizar umbral")

# ======================================================================
# ENDPOINTS DE EXPORTACIÓN (CSV y NUEVO EXCEL)
# ======================================================================

@router.get("/export/csv", dependencies=[Depends(require_roles(*REPORT_ROLES))])
async def export_csv(
    sensor_id: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Exportar datos históricos en formato CSV (HU-011)
    (Protegido por autenticación)
    """
    csv_content = await run_in_threadpool(export_history_csv, sensor_id, start_date, end_date)
    
    if not csv_content:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")
    
    filename = f"safyrashield_export_{sensor_id or 'all'}.csv"
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/export/excel", dependencies=[Depends(require_roles(*REPORT_ROLES))])
async def export_excel(
    sensor_id: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    NUEVO: Exportar datos históricos en formato Excel con estilos (HU-011)
    (Protegido por autenticación)
    """
    excel_content_bytes = await run_in_threadpool(export_history_excel, sensor_id, start_date, end_date)
    
    if not excel_content_bytes:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")
    
    filename = f"safyrashield_export_{sensor_id or 'all'}.xlsx"
    
    return Response(
        content=excel_content_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/statistics", dependencies=[Depends(require_roles(*CURRENT_DATA_ROLES))])
async def get_statistics():
    """
    Obtener estadísticas generales del sistema
    (Protegido por autenticación)
    """
    current_data = get_current_data()
    
    # ... (lógica de estadísticas existente) ...
    active_sensors = sum(1 for s in current_data["sensors"] if s["irms"] > 0)
    overload_count = sum(1 for s in current_data["sensors"] if s["is_overload"])
    
    device_types = {}
    for sensor in current_data["sensors"]:
        device_type = sensor["device"]["type"]
        device_types[device_type] = device_types.get(device_type, 0) + 1
    
    return {
        "total_sensors": len(current_data["sensors"]),
        "active_sensors": active_sensors,
        "overload_count": overload_count,
        "total_consumption": current_data["total_consumption"],
        "device_distribution": device_types,
        "timestamp": current_data["timestamp"]
    }
