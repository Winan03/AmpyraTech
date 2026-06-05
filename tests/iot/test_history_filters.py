from unittest.mock import Mock, patch

import pytest

from app.db import firebase as firebase_db


def _firebase_history_ref(records: dict) -> Mock:
    ref = Mock()
    ref.order_by_key.return_value = ref
    ref.limit_to_last.return_value = ref
    ref.get.return_value = records
    return ref


@pytest.mark.unitaria
class TestFirebaseHistoryFilters:
    def test_alerta_utc_se_filtra_con_fecha_local_lima(self, reset_firebase_mock):
        records = {
            "-alerta-utc": {
                "timestamp_utc": "2026-06-05T04:23:23Z",
                "irms": 16.737,
                "potencia": 3684.0,
                "estado": "Sobrecarga",
            }
        }

        def reference(path: str) -> Mock:
            if path == "/history/C-01":
                return _firebase_history_ref(records)
            return _firebase_history_ref({})

        reset_firebase_mock.reference.side_effect = reference

        with patch.object(firebase_db, "SENSOR_IDS", ["C-01", "C-02"]), patch(
            "app.db.firebase.get_sensor_threshold",
            return_value={"corriente": 11.0, "potencia": 2420.0},
        ):
            alerts = firebase_db.get_alert_history(
                "2026-06-04T23%3A00%3A00",
                "2026-06-04T23%3A33%3A00",
            )

        assert len(alerts) == 1
        assert alerts[0]["sensor_id"] == "C-01"
        assert alerts[0]["timestamp_utc"] == "2026-06-05T04:23:23Z"

    def test_historial_ejecutivo_omite_registros_normales(self, reset_firebase_mock):
        records = {
            "-normal": {
                "timestamp": "2026-06-04T23:30:00-05:00",
                "irms": 0.135,
                "potencia": 29.7,
                "estado": "Normal",
            },
            "-fuera-horario": {
                "timestamp": "2026-06-04T23:20:00-05:00",
                "irms": 0.204,
                "potencia": 44.8,
                "estado": "Fuera de horario",
                "is_out_of_schedule": True,
            },
            "-sobrecarga": {
                "timestamp": "2026-06-04T23:25:00-05:00",
                "irms": 16.7,
                "potencia": 3674.0,
                "estado": "Sobrecarga",
                "is_overload": True,
            },
        }
        reset_firebase_mock.reference.return_value = _firebase_history_ref(records)

        with patch(
            "app.db.firebase.get_sensor_threshold",
            return_value={"corriente": 11.0, "potencia": 2420.0},
        ):
            history = firebase_db.get_history_data("C-01", reportable_only=True)

        assert [record["estado"] for record in history] == ["Sobrecarga", "Fuera de horario"]
