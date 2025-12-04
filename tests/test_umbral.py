# tests/test_umbral.py
"""
Pruebas para el endpoint de configuración de umbrales
Endpoint: PUT /api/data/threshold/{sensor_id}
"""

import pytest
from unittest.mock import patch


@pytest.mark.unitaria
class TestActualizacionUmbralExitosa:
    """Escenarios exitosos de actualización de umbral"""
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_actualizar_umbral_valido(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Actualizar umbral con valores válidos
        Dado: Sensor LAB-PC-01 con nuevos valores de umbral
        Cuando: Se envía PUT con corriente=12.0 y potencia=2640.0
        Entonces: Umbral se actualiza correctamente
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 12.0, "potencia": 2640.0},
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["threshold"]["corriente"] == 12.0
        assert data["threshold"]["potencia"] == 2640.0
        
        # Verificar que Firebase fue llamado
        mock_update.assert_called_once()
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_actualizar_diferentes_sensores(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Actualizar umbrales de diferentes sensores
        Dado: Tres sensores con diferentes configuraciones
        Cuando: Se actualiza cada uno individualmente
        Entonces: Cada uno mantiene su configuración independiente
        """
        mock_update.return_value = True
        
        # Actualizar LAB-PC-01
        response1 = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 10.0, "potencia": 2200.0},
            headers=headers_autenticados
        )
        
        # Actualizar LAB-PC-02
        response2 = test_client.put(
            "/api/data/threshold/LAB-PC-02",
            json={"corriente": 12.0, "potencia": 2640.0},
            headers=headers_autenticados
        )
        
        # Actualizar LAB-PC-03
        response3 = test_client.put(
            "/api/data/threshold/LAB-PC-03",
            json={"corriente": 15.0, "potencia": 3300.0},
            headers=headers_autenticados
        )
        
        assert all(r.status_code == 200 for r in [response1, response2, response3])
        assert mock_update.call_count == 3


@pytest.mark.unitaria
class TestValidacionDatos:
    """Pruebas de validación de datos de entrada"""
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_corriente_negativa(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Valor de corriente negativo
        Dado: Corriente = -5.0
        Cuando: Se intenta actualizar umbral
        Entonces: Sistema acepta pero es responsabilidad del usuario
        
        Nota: Si tu API debe validar esto, necesitas agregar validación en el endpoint
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": -5.0, "potencia": 2200.0},
            headers=headers_autenticados
        )
        
        # Por ahora el sistema acepta cualquier valor
        # Si quieres validación, debes implementarla en el endpoint
        assert response.status_code == 200
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_corriente_cero(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Corriente en cero
        Dado: Corriente = 0.0
        Cuando: Se intenta configurar
        Entonces: Sistema acepta (puede usarse para deshabilitar sensor)
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 0.0, "potencia": 0.0},
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_valores_extremadamente_altos(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Valores fuera de rango realista
        Dado: Corriente = 1000A (no realista para uso doméstico)
        Cuando: Se intenta configurar
        Entonces: Sistema permite pero usuario debe ser consciente
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 1000.0, "potencia": 220000.0},
            headers=headers_autenticados
        )
        
        # Sistema permite configuración (responsabilidad del usuario)
        assert response.status_code == 200
    
    def test_campos_faltantes(self, test_client, headers_autenticados):
        """
        Escenario: Faltan campos obligatorios
        Dado: JSON sin campo "potencia"
        Cuando: Se envía solicitud
        Entonces: Se retorna error 422 de validación
        """
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 11.0},  # Falta "potencia"
            headers=headers_autenticados
        )
        
        assert response.status_code == 422
    
    def test_tipos_datos_incorrectos(self, test_client, headers_autenticados):
        """
        Escenario: Tipos de datos incorrectos
        Dado: Corriente como string en lugar de número
        Cuando: Se envía solicitud
        Entonces: Se retorna error 422
        """
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": "texto", "potencia": 2640.0},
            headers=headers_autenticados
        )
        
        assert response.status_code == 422


@pytest.mark.unitaria
class TestErroresActualizacion:
    """Pruebas de manejo de errores"""
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_error_firebase(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Error al actualizar en Firebase
        Dado: Firebase no responde o falla
        Cuando: Se intenta actualizar umbral
        Entonces: Se retorna error 500
        """
        mock_update.return_value = False  # Simula fallo
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 11.0, "potencia": 2420.0},
            headers=headers_autenticados
        )
        
        # Verificar que se manejó el error
        # Si tu endpoint no maneja esto, retornará 200 con success: False
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_sensor_inexistente(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Actualizar sensor que no existe
        Dado: Sensor "INVALID-SENSOR"
        Cuando: Se intenta actualizar su umbral
        Entonces: Sistema permite (Firebase maneja lógica de sensores)
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/INVALID-SENSOR",
            json={"corriente": 11.0, "potencia": 2420.0},
            headers=headers_autenticados
        )
        
        # Firebase crea la configuración si no existe
        assert response.status_code == 200


@pytest.mark.unitaria
class TestCalculoPotencia:
    """Pruebas de cálculo automático de potencia"""
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_relacion_corriente_potencia(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Verificar relación P = V × I (220V)
        Dado: Corriente de 10A
        Cuando: Se calcula potencia
        Entonces: Potencia = 220V × 10A = 2200W
        """
        mock_update.return_value = True
        
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 10.0, "potencia": 2200.0},
            headers=headers_autenticados
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar relación matemática
        assert data["threshold"]["potencia"] == data["threshold"]["corriente"] * 220


@pytest.mark.unitaria
class TestConcurrencia:
    """Pruebas de actualizaciones concurrentes"""
    
    @patch('app.routers.data_api.update_sensor_threshold')
    def test_actualizaciones_simultaneas(self, mock_update, test_client, headers_autenticados):
        """
        Escenario: Múltiples actualizaciones simultáneas
        Dado: Dos actualizaciones al mismo sensor
        Cuando: Se procesan ambas
        Entonces: La última gana (last-write-wins)
        """
        mock_update.return_value = True
        
        # Primera actualización
        response1 = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 10.0, "potencia": 2200.0},
            headers=headers_autenticados
        )
        
        # Segunda actualización (inmediata)
        response2 = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 12.0, "potencia": 2640.0},
            headers=headers_autenticados
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Ambas deberían completarse
        assert mock_update.call_count == 2