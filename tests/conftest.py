# tests/conftest.py
"""
Configuración base para todas las pruebas de SafyraShield
Incluye fixtures compartidos y configuración de pytest
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

# Configurar variables de entorno ANTES de importar la app
os.environ["VERCEL"] = "0"  # Simular ambiente local
os.environ["FIREBASE_DATABASE_URL"] = "https://safyrashield-default-rtdb.firebaseio.com"
os.environ["FIREBASE_CREDENTIALS_PATH"] = "Safyra_Shield_Firebase.json"

from app.main import app
from app.routers.auth_api import create_access_token


@pytest.fixture(scope="session")
def test_client():
    """Cliente de prueba para FastAPI"""
    return TestClient(app)


@pytest.fixture(scope="function")
def token_valido():
    """Token JWT válido para pruebas"""
    return create_access_token(data={"sub": "admin"})


@pytest.fixture(scope="function")
def headers_autenticados(token_valido):
    """Headers con autenticación válida"""
    return {"Authorization": f"Bearer {token_valido}"}


@pytest.fixture(scope="function")
def mock_firebase_data():
    """Datos simulados de Firebase para pruebas"""
    return {
        "LAB-PC-01": {
            "irms": 2.5,
            "potencia": 550.0,
            "timestamp": "2025-01-15T10:30:00"
        },
        "LAB-PC-02": {
            "irms": 0.5,
            "potencia": 110.0,
            "timestamp": "2025-01-15T10:30:00"
        },
        "LAB-PC-03": {
            "irms": 12.5,  # Sobrecarga
            "potencia": 2750.0,
            "timestamp": "2025-01-15T10:30:00"
        }
    }


@pytest.fixture(scope="function")
def mock_firebase_vacio():
    """Firebase sin datos"""
    return {}


@pytest.fixture(scope="function")
def mock_history_data():
    """Datos históricos simulados"""
    return {
        "2025-01-15T10:00:00": {
            "irms": 2.3,
            "potencia": 506.0,
            "estado": "Normal"
        },
        "2025-01-15T10:05:00": {
            "irms": 11.2,
            "potencia": 2464.0,
            "estado": "Sobrecarga"
        },
        "2025-01-15T10:10:00": {
            "irms": 3.1,
            "potencia": 682.0,
            "estado": "Normal"
        }
    }


@pytest.fixture(scope="function")
def mock_thresholds():
    """Umbrales configurados"""
    return {
        "LAB-PC-01": {"corriente": 11.0, "potencia": 2420.0},
        "LAB-PC-02": {"corriente": 11.0, "potencia": 2420.0},
        "LAB-PC-03": {"corriente": 11.0, "potencia": 2420.0}
    }


@pytest.fixture(autouse=True)
def reset_firebase_mock():
    """Resetea los mocks de Firebase antes de cada prueba"""
    with patch('app.db.firebase.db') as mock_db:
        yield mock_db


# Configuración de pytest
def pytest_configure(config):
    """Configuración adicional de pytest"""
    config.addinivalue_line(
        "markers", "integracion: marca pruebas de integración"
    )
    config.addinivalue_line(
        "markers", "unitaria: marca pruebas unitarias"
    )
    config.addinivalue_line(
        "markers", "autenticacion: pruebas de autenticación"
    )


# Hook para reportes personalizados
def pytest_runtest_makereport(item, call):
    """Genera reportes personalizados"""
    if call.when == "call":
        print(f"\n✅ Prueba completada: {item.name}")