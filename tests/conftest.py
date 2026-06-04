# tests/conftest.py
"""
ConfiguraciÃ³n base para todas las pruebas de SafyraShield
Incluye fixtures compartidos y configuraciÃ³n de pytest
"""

import pytest
import os
import secrets
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime
from passlib.context import CryptContext

# Configurar variables de entorno ANTES de importar la app
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or secrets.token_urlsafe(24)
TEST_AUDITOR_PASSWORD = secrets.token_urlsafe(24)
TEST_CONGELADO_PASSWORD = secrets.token_urlsafe(24)

os.environ["VERCEL"] = "0"  # Simular ambiente local
os.environ["SKIP_FIREBASE_INIT"] = "1"
os.environ["AUTH_PROVIDER"] = "local"
os.environ["ALLOW_LEGACY_PASSWORD_LOGIN"] = "true"
os.environ["FIREBASE_DATABASE_URL"] = "https://example.test/firebase"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_FULL_NAME"] = "Admin Test"
os.environ["ADMIN_ROLE"] = "admin"
os.environ["ADMIN_STATUS"] = "activo"
os.environ["ADMIN_FIREBASE_UID"] = ""
os.environ["ADMIN_PASSWORD_HASH"] = CryptContext(schemes=["bcrypt"], deprecated="auto").hash(
    TEST_ADMIN_PASSWORD
)
os.environ["TEST_ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD
os.environ["TERMS_VERSION"] = "2026-test"
os.environ["TERMS_REQUIRED_ROLES"] = "admin,auditor"
os.environ["SAFYRA_IOT_TOKEN"] = "test-iot-token"

from app.main import app
from app.routers.auth_api import create_access_token, fake_users_db, fake_consent_db, pwd_context, TERMS_VERSION

fake_users_db.update({
    "auditor": {
        "username": "auditor",
        "full_name": "Direccion",
        "email": "auditor@example.test",
        "role": "auditor",
        "status": "activo",
        "disabled": False,
        "hashed_password": pwd_context.hash(TEST_AUDITOR_PASSWORD),
    },
    "congelado": {
        "username": "congelado",
        "full_name": "Usuario Congelado",
        "email": "congelado@example.test",
        "role": "auditor",
        "status": "congelado",
        "disabled": False,
        "hashed_password": pwd_context.hash(TEST_CONGELADO_PASSWORD),
    },
})

for username, user_record in fake_users_db.items():
    if user_record.get("status") == "activo":
        fake_consent_db[username] = [{
            "username": username,
            "uid": user_record.get("uid", ""),
            "role": user_record["role"],
            "terms_version": TERMS_VERSION,
            "accepted_at": datetime.utcnow().isoformat(),
            "event_type": "terms_acceptance",
        }]


@pytest.fixture(scope="session")
def test_client():
    """Cliente de prueba para FastAPI"""
    return TestClient(app)


@pytest.fixture(scope="function")
def token_valido():
    """Token JWT vÃ¡lido para pruebas"""
    return create_access_token(data={"sub": "admin", "role": "admin"})


@pytest.fixture(scope="function")
def headers_autenticados(token_valido):
    """Headers con autenticaciÃ³n vÃ¡lida"""
    return {"Authorization": f"Bearer {token_valido}"}



@pytest.fixture(scope="function")
def headers_auditor():
    """Headers con autenticaciÃ³n de usuario auditor"""
    token = create_access_token(data={"sub": "auditor", "role": "auditor"})
    return {"Authorization": f"Bearer {token}"}



@pytest.fixture(scope="function")
def headers_congelado():
    """Headers de usuario no activo"""
    token = create_access_token(data={"sub": "congelado", "role": "auditor"})
    return {"Authorization": f"Bearer {token}"}


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
    """Datos histÃ³ricos simulados"""
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


# ConfiguraciÃ³n de pytest
def pytest_configure(config):
    """ConfiguraciÃ³n adicional de pytest"""
    config.addinivalue_line(
        "markers", "integracion: marca pruebas de integraciÃ³n"
    )
    config.addinivalue_line(
        "markers", "unitaria: marca pruebas unitarias"
    )
    config.addinivalue_line(
        "markers", "autenticacion: pruebas de autenticaciÃ³n"
    )


# Hook para reportes personalizados
def pytest_runtest_makereport(item, call):
    """Genera reportes personalizados"""
    if call.when == "call":
        print(f"\nOK Prueba completada: {item.name}")
