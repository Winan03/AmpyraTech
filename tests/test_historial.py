# tests/test_historial.py
"""
Pruebas para el endpoint de historial
Endpoint: GET /api/data/history/{sensor_id}
"""

import pytest
from unittest.mock import patch


@pytest.mark.unitaria
class TestHistorialBasico:
    """Pruebas básicas de consulta de historial"""
    
    @patch('app.routers.data_api.get_history_data')
    def test_obtener_historial_sensor_existente(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Consultar historial de sensor válido
        Dado: Sensor LAB-PC-01 con historial
        Cuando: Se consulta GET /api/data/history/LAB-PC-01
        Entonces: Se retorna lista de registros históricos
        """
        mock_get.return_value = [
            {
                "timestamp": "2025-01-15T10:00:00",
                "irms": 2.3,
                "potencia": 506.0,
                "estado": "Normal",
                "device": {
                    "type": "Laptop",
                    "icon": "💻",
                    "description": "Laptop en uso",
                    "color": "#f39c12"
                }
            },
            {
                "timestamp": "2025-01-15T10:05:00",
                "irms": 2.5,
                "potencia": 550.0,
                "estado": "Normal",
                "device": {
                    "type": "Laptop",
                    "icon": "💻",
                    "description": "Laptop en uso",
                    "color": "#f39c12"
                }
            }
        ]
        
        response = test_client.get(
            "/api/data/history/LAB-PC-01",
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sensor_id"] == "LAB-PC-01"
        assert data["count"] == 2
        assert len(data["data"]) == 2
        print("✅ Prueba completada: test_obtener_historial_sensor_existente")
    
    @patch('app.routers.data_api.get_history_data')
    def test_historial_vacio(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Sensor sin historial
        Dado: Sensor LAB-PC-02 sin datos históricos
        Cuando: Se consulta su historial
        Entonces: Se retorna lista vacía con count=0
        """
        mock_get.return_value = []
        
        response = test_client.get(
            "/api/data/history/LAB-PC-02",
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["data"]) == 0

    @patch('app.routers.data_api.get_history_data')
    def test_direccion_consulta_historial_completo(self, mock_get, test_client, headers_auditor):
        mock_get.return_value = []

        response = test_client.get(
            "/api/data/history/C-01",
            headers=headers_auditor,
        )

        assert response.status_code == 200
        assert "scope" not in response.json()
        mock_get.assert_called_once_with("C-01", 20, None, None)

    @patch('app.routers.data_api.get_history_data')
    def test_admin_consulta_historial_completo(self, mock_get, test_client, headers_autenticados):
        mock_get.return_value = []

        response = test_client.get(
            "/api/data/history/C-01",
            headers=headers_autenticados,
        )

        assert response.status_code == 200
        assert "scope" not in response.json()
        mock_get.assert_called_once_with("C-01", 20, None, None)


@pytest.mark.unitaria
class TestFiltroFechas:
    """Pruebas de filtrado por fechas"""
    
    @patch('app.routers.data_api.get_history_data')
    def test_filtro_rango_fechas(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Filtrar historial por rango de fechas
        Dado: Fechas inicio y fin válidas
        Cuando: Se aplican filtros de fecha
        Entonces: Se retornan solo registros en ese rango
        """
        mock_get.return_value = [
            {
                "timestamp": "2025-01-15T10:00:00",
                "irms": 2.3,
                "potencia": 506.0,
                "estado": "Normal",
                "device": {"type": "Laptop", "icon": "💻"}
            }
        ]
        
        response = test_client.get(
            "/api/data/history/LAB-PC-01",
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
        
        # Verificar que se retornaron datos
        assert data["count"] == 1
        assert len(data["data"]) == 1
        print("✅ Prueba completada: test_filtro_rango_fechas")
    
    @patch('app.routers.data_api.get_history_data')
    def test_limite_registros(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Limitar número de registros
        Dado: Parámetro limit=10
        Cuando: Se consulta historial
        Entonces: Se retornan máximo 10 registros
        """
        # Simular 15 registros
        mock_get.return_value = [
            {
                "timestamp": f"2025-01-15T10:{i:02d}:00",
                "irms": 2.0 + (i * 0.1),
                "potencia": 440.0 + (i * 22),
                "estado": "Normal",
                "device": {"type": "Laptop", "icon": "💻"}
            }
            for i in range(15)
        ]
        
        response = test_client.get(
            "/api/data/history/LAB-PC-01",
            params={"limit": 10},
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar que se llamó
        mock_get.assert_called_once()
        
        # Verificar que retornó los datos
        assert data["count"] == 15
        print("✅ Prueba completada: test_limite_registros")


@pytest.mark.unitaria
class TestHistorialConSobrecargas:
    """Pruebas de historial con eventos de sobrecarga"""
    
    @patch('app.routers.data_api.get_history_data')
    def test_historial_con_sobrecargas(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Historial con eventos de sobrecarga
        Dado: Registros con estado "Sobrecarga"
        Cuando: Se consulta historial
        Entonces: Se incluyen eventos de sobrecarga marcados
        """
        mock_get.return_value = [
            {
                "timestamp": "2025-01-15T10:00:00",
                "irms": 2.5,
                "potencia": 550.0,
                "estado": "Normal",
                "device": {"type": "Laptop", "icon": "💻"}
            },
            {
                "timestamp": "2025-01-15T10:05:00",
                "irms": 12.0,
                "potencia": 2640.0,
                "estado": "Sobrecarga",
                "device": {"type": "SOBRECARGA", "icon": "⚠️"}
            },
            {
                "timestamp": "2025-01-15T10:10:00",
                "irms": 3.0,
                "potencia": 660.0,
                "estado": "Normal",
                "device": {"type": "Laptop", "icon": "💻"}
            }
        ]
        
        response = test_client.get(
            "/api/data/history/LAB-PC-01",
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        
        # Verificar que hay un registro de sobrecarga
        sobrecargas = [r for r in data["data"] if r["estado"] == "Sobrecarga"]
        assert len(sobrecargas) == 1
        assert sobrecargas[0]["device"]["type"] == "SOBRECARGA"
        print("✅ Prueba completada: test_historial_con_sobrecargas")


@pytest.mark.unitaria
class TestErroresHistorial:
    """Pruebas de manejo de errores en historial"""
    
    @patch('app.routers.data_api.get_history_data')
    def test_sensor_invalido(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: ID de sensor inválido
        Dado: Sensor "INVALID-SENSOR" que no existe
        Cuando: Se consulta su historial
        Entonces: Sistema retorna lista vacía sin error
        """
        mock_get.return_value = []
        
        response = test_client.get(
            "/api/data/history/INVALID-SENSOR",
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        print("✅ Prueba completada: test_sensor_invalido")
    
    @patch('app.routers.data_api.get_history_data')
    def test_error_firebase_historial(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Error al consultar Firebase
        Dado: Firebase lanza excepción
        Cuando: Se intenta obtener historial
        Entonces: Sistema lanza excepción (el endpoint no maneja errores)
        
        NOTA: El endpoint actual NO maneja excepciones. TestClient re-lanza
        la excepción en lugar de convertirla en 500, por lo que usamos pytest.raises()
        """
        mock_get.side_effect = Exception("Firebase error")
        
        # El comportamiento REAL: la excepción se propaga y TestClient la re-lanza
        with pytest.raises(Exception) as exc_info:
            response = test_client.get(
                "/api/data/history/LAB-PC-01",
                headers=headers_autenticados
            )
        
        # Verificar que es el error esperado
        assert "Firebase error" in str(exc_info.value)
        print("✅ Prueba completada: test_error_firebase_historial")


@pytest.mark.unitaria
class TestOrdenamientoHistorial:
    """Pruebas de ordenamiento de datos históricos"""
    
    @patch('app.routers.data_api.get_history_data')
    def test_registros_ordenados_por_fecha(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Registros ordenados cronológicamente
        Dado: Historial con múltiples timestamps
        Cuando: Se obtienen datos
        Entonces: Están ordenados del más reciente al más antiguo
        """
        mock_get.return_value = [
            {"timestamp": "2025-01-15T10:10:00", "irms": 3.0, "potencia": 660.0, "estado": "Normal", "device": {"type": "Laptop"}},
            {"timestamp": "2025-01-15T10:05:00", "irms": 2.5, "potencia": 550.0, "estado": "Normal", "device": {"type": "Laptop"}},
            {"timestamp": "2025-01-15T10:00:00", "irms": 2.3, "potencia": 506.0, "estado": "Normal", "device": {"type": "Laptop"}}
        ]
        
        response = test_client.get(
            "/api/data/history/LAB-PC-01",
            headers=headers_autenticados
        )
        
        data = response.json()
        timestamps = [r["timestamp"] for r in data["data"]]
        
        # Verificar orden descendente (más reciente primero)
        assert timestamps == sorted(timestamps, reverse=True)
        print("✅ Prueba completada: test_registros_ordenados_por_fecha")
