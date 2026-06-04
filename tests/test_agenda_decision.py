from datetime import datetime
from unittest.mock import patch

import pytest

from app.db.firebase import get_schedule_status, is_room_in_allowed_schedule


@pytest.mark.unitaria
class TestDecisionAgenda:
    @patch("app.db.firebase.list_room_schedules")
    def test_clase_regular_autoriza_consumo(self, mock_list):
        mock_list.return_value = [
            {
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "valid_from": "2026-03-01",
                "valid_to": "2026-12-20",
                "status": "activo",
            }
        ]

        result = is_room_in_allowed_schedule("LAB-PC-01", datetime(2026, 6, 8, 9, 0))

        assert result is True

    @patch("app.db.firebase.list_room_schedules")
    def test_dia_sin_clase_anula_horario_regular(self, mock_list):
        mock_list.return_value = [
            {
                "kind": "class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "10:00",
                "valid_from": "2026-03-01",
                "valid_to": "2026-12-20",
                "status": "activo",
            },
            {
                "kind": "no_class",
                "day_of_week": "monday",
                "start_time": "08:00",
                "end_time": "14:30",
                "valid_from": "2026-06-08",
                "valid_to": "2026-06-08",
                "status": "activo",
            },
        ]

        result = get_schedule_status("LAB-PC-01", 0.2, datetime(2026, 6, 8, 9, 0))

        assert result["is_scheduled_now"] is False
        assert result["blocked_by_no_class"] is True
        assert result["is_out_of_schedule"] is True

    @patch("app.db.firebase.list_room_schedules", return_value=[])
    def test_consumo_residual_fuera_de_horario_no_alerta(self, _mock_list):
        result = get_schedule_status("LAB-PC-01", 0.135, datetime(2026, 6, 8, 9, 0))

        assert result["is_out_of_schedule"] is False

    @patch("app.db.firebase.list_room_schedules", return_value=[])
    def test_una_pc_encendida_fuera_de_horario_alerta(self, _mock_list):
        result = get_schedule_status("LAB-PC-01", 0.175, datetime(2026, 6, 8, 9, 0))

        assert result["is_out_of_schedule"] is True
