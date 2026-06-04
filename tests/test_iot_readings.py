from unittest.mock import Mock, patch

import pytest

from app.db import firebase as firebase_db
from app.routers import data_api


@pytest.mark.unitaria
class TestBranchClassification:
    def test_clasifica_consumo_residual_de_ramal(self):
        result = firebase_db.detect_device_type(0.135, 11.0)

        assert result["type"] == "Consumo residual"

    def test_clasifica_una_pc_encendida(self):
        result = firebase_db.detect_device_type(0.175, 11.0)

        assert result["type"] == "1 PC encendida"

    def test_clasifica_dos_pc_encendidas(self):
        result = firebase_db.detect_device_type(0.255, 11.0)

        assert result["type"] == "2 PCs encendidas"

    def test_clasifica_una_pc_con_programas(self):
        result = firebase_db.detect_device_type(0.215, 11.0)

        assert result["type"] == "1 PC con programas"

    def test_clasifica_ramal_en_uso_alto(self):
        result = firebase_db.detect_device_type(0.45, 11.0)

        assert result["type"] == "Ramal en uso alto"

    def test_ramales_monitoreados_por_defecto(self):
        assert "C-01" in firebase_db.SENSOR_IDS
        assert "C-10" in firebase_db.SENSOR_IDS


@pytest.mark.unitaria
class TestIotReadings:
    def setup_method(self) -> None:
        data_api._alert_notification_cache.clear()

    def test_rechaza_token_iot_invalido(self, test_client):
        response = test_client.post(
            "/api/data/iot/readings",
            headers={"X-Safyra-Iot-Token": "token-incorrecto"},
            json={"sensor_id": "LAB-PC-01", "irms": 1.0, "potencia": 220.0},
        )

        assert response.status_code == 401

    @patch("app.routers.data_api.get_alert_email_contacts")
    @patch("app.routers.data_api.queue_alert_notification_factory")
    @patch("app.routers.data_api.record_iot_reading")
    def test_registra_lectura_y_encola_alerta_sobrecarga(
        self,
        mock_record,
        mock_queue,
        mock_contacts,
        test_client,
    ):
        mock_contacts.return_value = [
            {
                "email": "admin@example.test",
                "name": "Admin Safyra",
                "username": "admin",
                "role": "admin",
            },
            {
                "email": "direccion@example.test",
                "name": "Cynthia Araujo",
                "username": "Direccion",
                "role": "auditor",
            },
        ]
        captured_payload = {}

        def queue_factory(payload_factory):
            captured_payload.update(payload_factory())
            return {"queued": True}

        mock_queue.side_effect = queue_factory
        mock_record.return_value = {
            "id": "LAB-PC-01",
            "room_name": "Laboratorio de Computo",
            "circuito": "LAB-PC-01",
            "irms": 13.4,
            "potencia": 2948.0,
            "is_overload": True,
            "is_out_of_schedule": False,
            "timestamp": "2026-06-03T06:15:30-05:00",
            "timestamp_utc": "2026-06-03T11:15:30Z",
            "estado": "Sobrecarga",
            "threshold": {"corriente": 11.0, "potencia": 2420.0},
            "schedule": {"is_scheduled_now": True, "blocked_by_no_class": False, "label": "En horario"},
        }

        response = test_client.post(
            "/api/data/iot/readings",
            headers={"X-Safyra-Iot-Token": "test-iot-token"},
            json={"sensor_id": "LAB-PC-01", "irms": 13.4, "potencia": 2948.0},
        )

        assert response.status_code == 201
        assert response.json()["sensor"]["estado"] == "Sobrecarga"
        assert response.json()["notification"]["queued"] is True
        mock_record.assert_called_once()
        mock_queue.assert_called_once()

        payload = captured_payload
        assert payload["alert_type"] == "overload"
        assert payload["email_recipients"] == ["admin@example.test", "direccion@example.test"]
        assert len(payload["email_notifications"]) == 2
        assert payload["email_notifications"][1]["to"] == {
            "email": "direccion@example.test",
            "name": "Cynthia Araujo",
        }
        assert "Estimado(a) <strong>Cynthia Araujo</strong>" in payload["email_notifications"][1]["htmlContent"]
        assert "Terminos y Condiciones vigentes" in payload["email_notifications"][1]["htmlContent"]
        assert payload["detected_at_display"] == "2026-06-03 06:15:30"
        assert payload["notification"]["email_subject"].startswith("[SafyraShield] CRITICA")
        assert "Sobrecarga electrica" in payload["notification"]["whatsapp_text"]

    @patch("app.routers.data_api.queue_alert_notification_factory")
    @patch("app.routers.data_api.record_iot_reading")
    def test_registra_lectura_normal_sin_notificacion(self, mock_record, mock_queue, test_client):
        mock_record.return_value = {
            "id": "LAB-PC-01",
            "room_name": "Laboratorio de Computo",
            "circuito": "LAB-PC-01",
            "irms": 0.0,
            "potencia": 0.0,
            "is_overload": False,
            "is_out_of_schedule": False,
            "timestamp": "2026-06-03T06:15:30-05:00",
            "timestamp_utc": "2026-06-03T11:15:30Z",
            "estado": "Normal",
            "threshold": {"corriente": 11.0, "potencia": 2420.0},
            "schedule": {"is_scheduled_now": False, "blocked_by_no_class": False, "label": "Sin horario activo"},
        }

        response = test_client.post(
            "/api/data/iot/readings",
            headers={"X-Safyra-Iot-Token": "test-iot-token"},
            json={"sensor_id": "LAB-PC-01", "irms": 0.0, "potencia": 0.0},
        )

        assert response.status_code == 201
        assert response.json()["notification"]["reason"] == "no_alert"
        mock_queue.assert_not_called()

    @patch("app.db.firebase.get_schedule_status")
    @patch("app.db.firebase.get_sensor_threshold")
    def test_registro_iot_evalua_agenda_del_salon(
        self,
        mock_threshold,
        mock_schedule_status,
    ):
        mock_threshold.return_value = {"corriente": 11.0, "potencia": 2420.0}
        mock_schedule_status.return_value = {
            "is_scheduled_now": True,
            "is_out_of_schedule": False,
            "blocked_by_no_class": False,
            "label": "En horario",
        }

        sensor = firebase_db.record_iot_reading("C-01", 0.175, potencia=38.5)

        assert sensor["id"] == "C-01"
        assert sensor["schedule_room_id"] == firebase_db.LAB_ROOM_ID
        assert mock_schedule_status.call_args.args[0] == firebase_db.LAB_ROOM_ID

    @patch("app.db.firebase.get_schedule_status")
    @patch("app.db.firebase.get_sensor_threshold")
    def test_dashboard_actual_evalua_agenda_del_salon(
        self,
        mock_threshold,
        mock_schedule_status,
        reset_firebase_mock,
    ):
        mock_threshold.return_value = {"corriente": 11.0, "potencia": 2420.0}
        mock_schedule_status.return_value = {
            "is_scheduled_now": False,
            "is_out_of_schedule": True,
            "blocked_by_no_class": False,
            "label": "Fuera de horario",
        }
        ref = Mock()
        ref.get.return_value = {
            "C-01": {
                "circuito": "C-01 (PC 01-02) - Prototipo fisico",
                "irms": 0.175,
                "potencia": 38.5,
                "timestamp": "2026-06-03T09:00:00-05:00",
            }
        }
        reset_firebase_mock.reference.return_value = ref

        data = firebase_db.get_current_data()

        assert data["sensors"][0]["id"] == "C-01"
        assert data["sensors"][0]["schedule_room_id"] == firebase_db.LAB_ROOM_ID
        assert {call.args[0] for call in mock_schedule_status.call_args_list} == {firebase_db.LAB_ROOM_ID}


@pytest.mark.unitaria
class TestAlertRecipients:
    def test_destinatarios_salen_de_usuarios_activos_con_tyc(self, reset_firebase_mock):
        users = {
            "admin": {
                "email": "admin@example.test",
                "full_name": "Admin Safyra",
                "role": "admin",
                "status": "activo",
                "disabled": False,
                "uid": "uid-admin",
            },
            "Direccion": {
                "email": "direccion@example.test",
                "full_name": "Cynthia Araujo",
                "role": "auditor",
                "status": "activo",
                "disabled": False,
                "uid": "uid-direccion",
            },
            "congelado": {
                "email": "congelado@example.test",
                "role": "auditor",
                "status": "congelado",
                "disabled": False,
                "uid": "uid-congelado",
            },
        }
        consents = {
            "/app_consents/admin": {
                "consent-1": {
                    "event_type": "terms_acceptance",
                    "terms_version": firebase_db.TERMS_VERSION,
                    "role": "admin",
                    "uid": "uid-admin",
                }
            },
            "/app_consents/Direccion": {
                "consent-2": {
                    "event_type": "terms_acceptance",
                    "terms_version": firebase_db.TERMS_VERSION,
                    "role": "auditor",
                    "uid": "uid-direccion",
                }
            },
        }

        def reference(path: str):
            ref = Mock()
            ref.get.return_value = users if path == "/app_users" else consents.get(path, {})
            return ref

        reset_firebase_mock.reference.side_effect = reference

        recipients = firebase_db.get_alert_email_recipients()
        contacts = firebase_db.get_alert_email_contacts()

        assert recipients == ["admin@example.test", "direccion@example.test"]
        assert contacts == [
            {
                "email": "admin@example.test",
                "name": "Admin Safyra",
                "username": "admin",
                "role": "admin",
            },
            {
                "email": "direccion@example.test",
                "name": "Cynthia Araujo",
                "username": "Direccion",
                "role": "auditor",
            },
        ]


@pytest.mark.unitaria
class TestNotificationContent:
    def test_correo_fuera_de_horario_usa_referencia_de_agenda(self):
        payload = {
            "alert_type": "out_of_schedule_consumption",
            "alert_type_label": "Consumo fuera de horario",
            "severity_label": "Advertencia",
            "room_id": "C-01",
            "room_name": "Laboratorio de Computo",
            "circuito": "C-01 (PC 01-02) - Prototipo fisico",
            "message": "Consumo detectado fuera del horario autorizado.",
            "reason": "El laboratorio registra corriente cuando no existe una clase activa.",
            "recommended_action": "Apagar los equipos.",
            "irms": 0.175,
            "potencia": 38.5,
            "device": {
                "type": "1 PC encendida",
                "description": "Consumo compatible con 1 PC encendida en el ramal (0.175A)",
            },
            "threshold": {"corriente": 15.0, "potencia": 3300.0},
            "schedule_min_current_a": 0.16,
            "schedule_status_label": "Fuera de horario",
            "detected_at_display": "2026-06-03 21:09:03",
            "alert_id": "test-alert",
        }

        content = data_api._build_notification_content(
            payload,
            {
                "email": "direccion@example.test",
                "name": "Cynthia Araujo",
                "username": "Direccion",
                "role": "auditor",
            },
        )

        assert "Estimado(a) <strong>Cynthia Araujo</strong>" in content["email_html"]
        assert "C-01 (PC 01-02) - Prototipo fisico" in content["email_html"]
        assert "1 PC encendida" in content["email_html"]
        assert "Ramal: C-01 (PC 01-02) - Prototipo fisico" in content["whatsapp_text"]
        assert "Referencia de agenda" in content["email_html"]
        assert "Consumo relevante &gt;= 0.160 A fuera de horario" in content["email_html"]
        assert "Umbral: 15.00 A / 3300 W" not in content["whatsapp_text"]
