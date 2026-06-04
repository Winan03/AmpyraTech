from datetime import date, timedelta
from unittest.mock import patch

import pytest


@pytest.mark.unitaria
class TestAgendaDireccion:
    @patch("app.routers.data_api.list_room_schedules")
    def test_admin_puede_leer_horarios(self, mock_list, test_client, headers_autenticados):
        mock_list.return_value = [
            {
                "id": "horario-test",
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase programada",
                "status": "activo",
            }
        ]

        response = test_client.get("/api/data/schedule?room_id=LAB-PC-01", headers=headers_autenticados)

        assert response.status_code == 200
        assert response.json()["count"] == 1

    @patch("app.routers.data_api.save_room_schedule")
    def test_direccion_puede_crear_horario(self, mock_save, test_client, headers_auditor):
        mock_save.return_value = {
            "id": "horario-test",
            "room_id": "LAB-PC-01",
            "kind": "class",
            "day_of_week": "monday",
            "start_time": "08:00",
            "end_time": "10:00",
            "label": "Clase programada",
            "status": "activo",
        }

        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase programada",
                "status": "activo",
            },
        )

        assert response.status_code == 201
        assert response.json()["success"] is True
        mock_save.assert_called_once()

    @patch("app.routers.data_api.list_room_schedules", return_value=[])
    def test_direccion_rechaza_nombre_visible_con_numeros(self, _mock_list, test_client, headers_auditor):
        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase 101",
                "status": "activo",
            },
        )

        assert response.status_code == 422
        assert "letras y espacios" in response.json()["detail"]

    @patch("app.routers.data_api.list_room_schedules", return_value=[])
    def test_direccion_rechaza_horario_fuera_del_rango_escolar(self, _mock_list, test_client, headers_auditor):
        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "07:00",
                "end_time": "10:00",
                "label": "Clase de computacion",
                "status": "activo",
            },
        )

        assert response.status_code == 422
        assert "08:00" in response.json()["detail"]

    @patch("app.routers.data_api.list_room_schedules", return_value=[])
    def test_direccion_rechaza_vigencia_pasada(self, _mock_list, test_client, headers_auditor):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase de computacion",
                "valid_from": yesterday,
                "valid_to": yesterday,
                "status": "activo",
            },
        )

        assert response.status_code == 422
        assert "fecha pasada" in response.json()["detail"]

    @patch("app.routers.data_api.save_room_schedule")
    def test_direccion_puede_crear_dia_sin_clase(self, mock_save, test_client, headers_auditor):
        mock_save.return_value = {
            "id": "feriado-test",
            "room_id": "LAB-PC-01",
            "kind": "no_class",
            "day_of_week": "monday",
            "start_time": "08:00",
            "end_time": "14:30",
            "label": "Dia sin clase",
            "valid_from": "2026-06-08",
            "valid_to": "2026-06-08",
            "status": "activo",
        }

        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "no_class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "14:30",
                "label": "Dia sin clase",
                "valid_from": "2026-06-08",
                "valid_to": "2026-06-08",
                "status": "activo",
            },
        )

        assert response.status_code == 201
        assert response.json()["success"] is True
        mock_save.assert_called_once()

    @patch("app.routers.data_api.save_room_schedule")
    @patch("app.routers.data_api.list_room_schedules")
    def test_direccion_rechaza_bloque_duplicado(self, mock_list, mock_save, test_client, headers_auditor):
        mock_list.return_value = [
            {
                "id": "base-1",
                "room_id": "LAB-PC-01",
                "kind": "no_class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "14:30",
                "label": "Dia sin clase",
                "valid_from": "2026-06-08",
                "valid_to": "2026-06-08",
                "status": "activo",
                "source_schedule_id": "base-1",
            }
        ]

        response = test_client.post(
            "/api/data/schedule",
            headers=headers_auditor,
            json={
                "room_id": "LAB-PC-01",
                "kind": "no_class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "14:30",
                "label": "Dia sin clase",
                "valid_from": "2026-06-08",
                "valid_to": "2026-06-08",
                "status": "activo",
                "source_schedule_id": "base-1",
            },
        )

        assert response.status_code == 409
        mock_save.assert_not_called()

    def test_admin_no_puede_crear_horario(self, test_client, headers_autenticados):
        response = test_client.post(
            "/api/data/schedule",
            headers=headers_autenticados,
            json={
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase programada",
                "status": "activo",
            },
        )

        assert response.status_code == 403

    @patch("app.routers.data_api.update_room_schedule")
    @patch("app.routers.data_api.list_room_schedules")
    def test_direccion_puede_editar_horario(self, mock_list, mock_update, test_client, headers_auditor):
        mock_list.return_value = [
            {
                "id": "horario-test",
                "room_id": "LAB-PC-01",
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "label": "Clase programada",
                "status": "activo",
            }
        ]
        mock_update.return_value = {
            "id": "horario-test",
            "room_id": "LAB-PC-01",
            "kind": "class",
            "day_of_week": "monday",
            "start_time": "10:00",
            "end_time": "12:00",
            "label": "Clase de computacion",
            "status": "activo",
        }

        response = test_client.patch(
            "/api/data/schedule/LAB-PC-01/horario-test",
            headers=headers_auditor,
            json={
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "10:00",
                "end_time": "12:00",
                "label": "Clase de computacion",
                "status": "activo",
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_update.assert_called_once()

    def test_admin_no_puede_editar_horario(self, test_client, headers_autenticados):
        response = test_client.patch(
            "/api/data/schedule/LAB-PC-01/horario-test",
            headers=headers_autenticados,
            json={
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "10:00",
                "end_time": "12:00",
                "label": "Clase de computacion",
                "status": "activo",
            },
        )

        assert response.status_code == 403

    def test_direccion_no_puede_actualizar_umbral(self, test_client, headers_auditor):
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            headers=headers_auditor,
            json={"corriente": 11.0, "potencia": 2420.0},
        )

        assert response.status_code == 403

    def test_direccion_no_puede_listar_usuarios(self, test_client, headers_auditor):
        response = test_client.get("/admin/users", headers=headers_auditor)

        assert response.status_code == 403
