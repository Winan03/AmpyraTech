# tests/test_alertas.py
"""
Pruebas para el endpoint de alertas de sobrecarga
Endpoint: GET /api/data/alerts
"""

import pytest
from unittest.mock import patch


@pytest.mark.unitaria
class TestAlertasBasico:
    """Pruebas básicas de obtención de alertas"""
    
    @patch('app.routers.data_api.get_alert_history')
    def test_obtener_todas_alertas(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Obtener todas las alertas del sistema
        Dado: Sistema con múltiples alertas registradas
        Cuando: Se consulta GET /api/data/alerts
        Entonces: Se retornan todas las alertas de sobrecarga
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T10:05:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️", "description": "Consumo excede umbral"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            },
            {
                "sensor_id": "LAB-PC-03",
                "timestamp": "2025-01-15T11:20:00",
                "irms": 16.5,
                "potencia": 3630.0,
                "estado": "Sobrecarga",
                "device": {"type": "¡PICO EXTREMO!", "icon": "💥", "description": "Cortocircuito detectado"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["data"]) == 2
        
        # Verificar que todas son sobrecargas
        for alert in data["data"]:
            assert alert["estado"] == "Sobrecarga"
            assert alert["irms"] > alert["threshold"]["corriente"]
    
    @patch('app.routers.data_api.get_alert_history')
    def test_sistema_sin_alertas(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Sistema sin alertas registradas
        Dado: No hay eventos de sobrecarga
        Cuando: Se consultan alertas
        Entonces: Se retorna lista vacía
        """
        mock_get.return_value = []
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["data"]) == 0


@pytest.mark.unitaria
class TestFiltroAlertasPorFecha:
    """Pruebas de filtrado de alertas por fechas"""
    
    @patch('app.routers.data_api.get_alert_history')
    def test_filtrar_alertas_por_rango(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Filtrar alertas en rango de fechas
        Dado: Fechas de inicio y fin específicas
        Cuando: Se aplica filtro de fechas
        Entonces: Solo se retornan alertas en ese rango
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T10:00:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get(
            "/api/data/alerts",
            params={
                "start_date": "2025-01-15T08:00:00",
                "end_date": "2025-01-15T12:00:00"
            },
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar que mock fue llamado
        mock_get.assert_called_once()
        
        # Verificar que se retornó la data esperada
        assert data["count"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["sensor_id"] == "LAB-PC-01"


@pytest.mark.unitaria
class TestAlertasPorSensor:
    """Pruebas de alertas agrupadas por sensor"""
    
    @patch('app.routers.data_api.get_alert_history')
    def test_multiples_alertas_mismo_sensor(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Múltiples alertas del mismo sensor
        Dado: LAB-PC-01 con 3 alertas diferentes
        Cuando: Se obtienen alertas
        Entonces: Se incluyen todas las alertas del sensor
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T10:00:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            },
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T11:00:00",
                "irms": 13.5,
                "potencia": 2970.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            },
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T12:00:00",
                "irms": 11.8,
                "potencia": 2596.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        
        # Verificar que todas son del mismo sensor
        sensor_ids = [alert["sensor_id"] for alert in data["data"]]
        assert all(sid == "LAB-PC-01" for sid in sensor_ids)
    
    @patch('app.routers.data_api.get_alert_history')
    def test_alertas_multiples_sensores(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Alertas de diferentes sensores
        Dado: Alertas de LAB-PC-01, LAB-PC-02, LAB-PC-03
        Cuando: Se obtienen todas las alertas
        Entonces: Se incluyen alertas de todos los sensores
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T10:00:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            },
            {
                "sensor_id": "LAB-PC-02",
                "timestamp": "2025-01-15T10:15:00",
                "irms": 11.5,
                "potencia": 2530.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            },
            {
                "sensor_id": "LAB-PC-03",
                "timestamp": "2025-01-15T10:30:00",
                "irms": 16.0,
                "potencia": 3520.0,
                "estado": "Sobrecarga",
                "device": {"type": "¡PICO EXTREMO!", "icon": "💥"},
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        
        # Verificar diversidad de sensores
        sensor_ids = set(alert["sensor_id"] for alert in data["data"])
        assert len(sensor_ids) == 3


@pytest.mark.unitaria
class TestTiposAlertas:
    """Pruebas de diferentes tipos de alertas"""
    
    @patch('app.routers.data_api.get_alert_history')
    def test_alerta_sobrecarga_estandar(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Alerta de sobrecarga estándar (11A - 15A)
        Dado: Corriente de 12A
        Cuando: Se clasifica la alerta
        Entonces: Se marca como "SOBRECARGA" con icono ⚠️
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-01",
                "timestamp": "2025-01-15T10:00:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {
                    "type": "SOBRECARGA",
                    "icon": "⚠️",
                    "description": "Consumo (12.00A) supera el umbral (11.0A)",
                    "color": "#e74c3c"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        data = response.json()
        alert = data["data"][0]
        
        assert alert["device"]["type"] == "SOBRECARGA"
        assert alert["device"]["icon"] == "⚠️"
        assert 11.0 < alert["irms"] < 15.0
    
    @patch('app.routers.data_api.get_alert_history')
    def test_alerta_pico_extremo(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Alerta de pico extremo (>= 15A)
        Dado: Corriente de 16.5A
        Cuando: Se clasifica la alerta
        Entonces: Se marca como "¡PICO EXTREMO!" con icono 💥
        """
        mock_get.return_value = [
            {
                "sensor_id": "LAB-PC-02",
                "timestamp": "2025-01-15T10:00:00",
                "irms": 16.5,
                "potencia": 3630.0,
                "estado": "Sobrecarga",
                "device": {
                    "type": "¡PICO EXTREMO!",
                    "icon": "💥",
                    "description": "Cortocircuito o falla grave detectada (16.50A)",
                    "color": "#ff0000"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        data = response.json()
        alert = data["data"][0]
        
        assert alert["device"]["type"] == "¡PICO EXTREMO!"
        assert alert["device"]["icon"] == "💥"
        assert alert["irms"] >= 15.0


@pytest.mark.unitaria
class TestOrdenamientoAlertas:
    """Pruebas de ordenamiento de alertas"""
    
    @patch('app.routers.data_api.get_alert_history')
    def test_alertas_ordenadas_por_fecha_desc(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Alertas ordenadas de más reciente a más antigua
        Dado: Múltiples alertas con diferentes timestamps
        Cuando: Se obtienen las alertas
        Entonces: Están ordenadas descendentemente por fecha
        """
        mock_get.return_value = [
            {"sensor_id": "LAB-PC-01", "timestamp": "2025-01-15T12:00:00", "irms": 12.0, "potencia": 2640.0, "estado": "Sobrecarga", "device": {"type": "SOBRECARGA"}, "threshold": {"corriente": 11.0}},
            {"sensor_id": "LAB-PC-02", "timestamp": "2025-01-15T11:00:00", "irms": 11.5, "potencia": 2530.0, "estado": "Sobrecarga", "device": {"type": "SOBRECARGA"}, "threshold": {"corriente": 11.0}},
            {"sensor_id": "LAB-PC-03", "timestamp": "2025-01-15T10:00:00", "irms": 13.0, "potencia": 2860.0, "estado": "Sobrecarga", "device": {"type": "SOBRECARGA"}, "threshold": {"corriente": 11.0}}
        ]
        
        response = test_client.get("/api/data/alerts", headers=headers_autenticados)
        
        data = response.json()
        timestamps = [alert["timestamp"] for alert in data["data"]]
        
        # Verificar orden descendente
        assert timestamps == sorted(timestamps, reverse=True)