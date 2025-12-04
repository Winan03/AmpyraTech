# tests/test_datos_actuales.py
"""
Pruebas para el endpoint de datos actuales
Endpoint: GET /api/data/current
"""

import pytest
from unittest.mock import patch


@pytest.mark.unitaria
class TestDatosActualesExitoso:
    """Escenarios exitosos de obtención de datos"""
    
    @patch('app.routers.data_api.get_current_data')
    def test_obtener_datos_sensores_activos(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Sistema con sensores activos
        Dado: Tres sensores con datos válidos
        Cuando: Se consulta /api/data/current
        Entonces: Se retornan datos de todos los sensores
        """
        mock_get.return_value = {
            "sensors": [
                {
                    "id": "LAB-PC-01",
                    "irms": 2.5,
                    "potencia": 550.0,
                    "is_overload": False,
                    "timestamp": "2025-01-15T10:30:00",
                    "device": {
                        "type": "Laptop",
                        "icon": "💻",
                        "description": "Laptop en uso",
                        "color": "#f39c12"
                    },
                    "threshold": {"corriente": 11.0, "potencia": 2420.0}
                }
            ],
            "connected": True,
            "message": "Sistema activo",
            "timestamp": "2025-01-15T10:30:00",
            "total_consumption": 550.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert len(data["sensors"]) == 1
        assert data["sensors"][0]["id"] == "LAB-PC-01"
        assert data["total_consumption"] == 550.0
    
    @patch('app.routers.data_api.get_current_data')
    def test_sistema_sin_dispositivos_conectados(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Sistema activo pero sin dispositivos
        Dado: Sensores sin carga conectada (irms = 0)
        Cuando: Se consulta datos actuales
        Entonces: Se retorna connected=False con valores en 0
        """
        mock_get.return_value = {
            "sensors": [
                {
                    "id": "LAB-PC-01",
                    "irms": 0.0,
                    "potencia": 0.0,
                    "is_overload": False,
                    "timestamp": "",
                    "device": {
                        "type": "Sin carga",
                        "icon": "🔌",
                        "description": "No hay dispositivos conectados",
                        "color": "#95a5a6"
                    },
                    "threshold": {"corriente": 11.0, "potencia": 2420.0}
                }
            ],
            "connected": False,
            "message": "Sin dispositivos conectados",
            "timestamp": "2025-01-15T10:30:00",
            "total_consumption": 0.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["total_consumption"] == 0.0


@pytest.mark.unitaria
class TestDeteccionDispositivos:
    """Pruebas de detección de tipos de dispositivos"""
    
    @patch('app.routers.data_api.get_current_data')
    def test_deteccion_cargador_celular(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Cargador de celular conectado (0.1A - 1.5A)
        Dado: Corriente medida de 0.8A
        Cuando: Sistema detecta dispositivo
        Entonces: Identifica como "Cargador de celular"
        """
        mock_get.return_value = {
            "sensors": [{
                "id": "LAB-PC-01",
                "irms": 0.8,
                "potencia": 176.0,
                "is_overload": False,
                "device": {
                    "type": "Cargador de celular",
                    "icon": "📱",
                    "description": "Smartphone o tablet en carga",
                    "color": "#27ae60"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }],
            "connected": True,
            "total_consumption": 176.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        data = response.json()
        
        assert data["sensors"][0]["device"]["type"] == "Cargador de celular"
        assert data["sensors"][0]["device"]["icon"] == "📱"
    
    @patch('app.routers.data_api.get_current_data')
    def test_deteccion_laptop(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Laptop conectada (1.5A - 4.0A)
        Dado: Corriente de 2.5A
        Cuando: Sistema clasifica dispositivo
        Entonces: Identifica como "Laptop"
        """
        mock_get.return_value = {
            "sensors": [{
                "id": "LAB-PC-02",
                "irms": 2.5,
                "potencia": 550.0,
                "is_overload": False,
                "device": {
                    "type": "Laptop",
                    "icon": "💻",
                    "description": "Laptop en uso o carga",
                    "color": "#f39c12"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }],
            "connected": True,
            "total_consumption": 550.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        data = response.json()
        
        assert data["sensors"][0]["device"]["type"] == "Laptop"
    
    @patch('app.routers.data_api.get_current_data')
    def test_deteccion_pc_escritorio(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: PC de escritorio (4.0A - 8.0A)
        Dado: Corriente de 5.5A
        Cuando: Sistema analiza consumo
        Entonces: Clasifica como "PC de escritorio"
        """
        mock_get.return_value = {
            "sensors": [{
                "id": "LAB-PC-03",
                "irms": 5.5,
                "potencia": 1210.0,
                "is_overload": False,
                "device": {
                    "type": "PC de escritorio",
                    "icon": "🖥️",
                    "description": "Computadora de escritorio (CPU + Monitor)",
                    "color": "#e67e22"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }],
            "connected": True,
            "total_consumption": 1210.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        data = response.json()
        
        assert data["sensors"][0]["device"]["type"] == "PC de escritorio"


@pytest.mark.unitaria
class TestDeteccionSobrecargas:
    """Pruebas de detección de sobrecargas"""
    
    @patch('app.routers.data_api.get_current_data')
    def test_sobrecarga_normal(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Sobrecarga por exceso de umbral
        Dado: Corriente de 12A con umbral de 11A
        Cuando: Sistema detecta sobrecarga
        Entonces: Marca is_overload=True y tipo "SOBRECARGA"
        """
        mock_get.return_value = {
            "sensors": [{
                "id": "LAB-PC-01",
                "irms": 12.0,
                "potencia": 2640.0,
                "is_overload": True,
                "device": {
                    "type": "SOBRECARGA",
                    "icon": "⚠️",
                    "description": "Consumo (12.00A) supera el umbral (11.0A)",
                    "color": "#e74c3c"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }],
            "connected": True,
            "total_consumption": 2640.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        data = response.json()
        
        assert data["sensors"][0]["is_overload"] is True
        assert data["sensors"][0]["device"]["type"] == "SOBRECARGA"
        assert "⚠️" in data["sensors"][0]["device"]["icon"]
    
    @patch('app.routers.data_api.get_current_data')
    def test_pico_extremo_cortocircuito(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Pico extremo (posible cortocircuito)
        Dado: Corriente >= 15A
        Cuando: Sistema detecta pico crítico
        Entonces: Clasifica como "¡PICO EXTREMO!"
        """
        mock_get.return_value = {
            "sensors": [{
                "id": "LAB-PC-02",
                "irms": 16.5,
                "potencia": 3630.0,
                "is_overload": True,
                "device": {
                    "type": "¡PICO EXTREMO!",
                    "icon": "💥",
                    "description": "Cortocircuito o falla grave detectada (16.50A)",
                    "color": "#ff0000"
                },
                "threshold": {"corriente": 11.0, "potencia": 2420.0}
            }],
            "connected": True,
            "total_consumption": 3630.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        data = response.json()
        
        assert data["sensors"][0]["device"]["type"] == "¡PICO EXTREMO!"
        assert data["sensors"][0]["device"]["icon"] == "💥"


@pytest.mark.unitaria
class TestErroresConexion:
    """Pruebas de manejo de errores"""
    
    @patch('app.routers.data_api.get_current_data')
    def test_error_conexion_firebase(self, mock_get, test_client, headers_autenticados):
        """
        Escenario: Error de conexión a Firebase
        Dado: Firebase no responde
        Cuando: Se intenta obtener datos
        Entonces: Sistema maneja el error gracefully
        """
        # En lugar de lanzar excepción, retornar datos de error
        mock_get.return_value = {
            "sensors": [],
            "connected": False,
            "message": "Error de conexión",
            "timestamp": "",
            "total_consumption": 0.0
        }
        
        response = test_client.get("/api/data/current", headers=headers_autenticados)
        
        # El endpoint debe retornar datos vacíos en caso de error
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert len(data["sensors"]) == 0